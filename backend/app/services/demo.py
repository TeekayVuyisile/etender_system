"""One-click demo workspaces for visitors (e.g. recruiters viewing the portfolio).

Each "Try the demo" creates a private demo team with sample data built from real open
tenders, so visitors never see each other's changes. Demo teams are deleted after
`settings.demo_ttl_hours` by a recurring job.
"""

import logging
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    CompanyProfile,
    Plan,
    Team,
    Tender,
    User,
    UserRole,
    WorkspaceNote,
    WorkspaceStatus,
    WorkspaceStatusChange,
    WorkspaceTask,
    WorkspaceTender,
)
from app.schemas.company_profile import ReadinessProfile
from app.schemas.summary import TenderSummaryContent
from app.services.llm import LLMClient
from app.services.match_store import MatchStore
from app.services.matching import tender_facts
from app.services.notification_events import STATUS_LABELS, short
from app.services.notifications import Notification, NotificationStore
from app.services.readiness import score_readiness
from app.services.summarizer import run_summary_job
from app.services.summary_store import SummaryStore
from app.services.tender_sync import SAST

logger = logging.getLogger(__name__)

TEAM_NAME = "Thabo's Civil Works"
PEOPLE = [  # (full name, role); the first is the owner the visitor logs in as
    ("Thabo Mokoena", UserRole.OWNER),
    ("Lerato Dlamini", UserRole.MEMBER),
    ("Sipho Nkosi", UserRole.MEMBER),
]
PROFILE: dict[str, Any] = {
    "industry_sector": "Construction and Civil Works",
    "services": [
        "Routine road maintenance",
        "Road construction",
        "Paving",
        "Stormwater drainage",
        "Bridge repairs",
    ],
    "cidb_gradings": [{"class_code": "CE", "grade": 7}, {"class_code": "GB", "grade": 5}],
    "bbbee_level": 1,
    "certifications": [
        "CSD Registration",
        "SARS Tax Compliance Status",
        "COIDA Letter of Good Standing",
        "NHBRC Registration",
    ],
    "provinces": ["Gauteng", "Limpopo", "Mpumalanga", "North West"],
    "years_of_experience": 12,
}
KEYWORDS = re.compile(
    r"\b(road|roads|paving|stormwater|bridge|civil|construction|resurfac\w*|pothole\w*|"
    r"reseal\w*|culvert\w*|kerb\w*|asphalt|gravel|sewer\w*|bulk water|pipeline)\b",
    re.IGNORECASE,
)
DEMO_TENDER_COUNT = 6


@dataclass
class DemoStores:
    summaries: SummaryStore
    matches: MatchStore
    notifications: NotificationStore


# --- Choosing tenders -------------------------------------------------------------------


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def relevant_tenders(db: Session, now: datetime, min_days_open: float = 0.5) -> list[Tender]:
    """Open tenders that suit the demo company, most relevant first."""
    candidates = db.scalars(
        select(Tender)
        .where(
            Tender.closing_at > now + timedelta(days=min_days_open),
            Tender.province.in_([*PROFILE["provinces"], "National"]),
        )
        .order_by(Tender.closing_at)
        .limit(600)
    ).all()
    scored = [(len(KEYWORDS.findall(t.search_text or "")), t) for t in candidates]
    return [t for hits, t in sorted(scored, key=lambda pair: -pair[0]) if hits > 0]


def choose_demo_tenders(
    db: Session, summaries: SummaryStore, now: datetime, count: int = DEMO_TENDER_COUNT
) -> list[Tender]:
    """Prefer tenders that already have AI summaries, and include one closing soon so the
    demo shows a deadline reminder."""
    relevant = relevant_tenders(db, now)
    docs = summaries.get_many([t.id for t in relevant])
    summarised = [t for t in relevant if (docs.get(t.id) or {}).get("status") == "ready"]
    others = [t for t in relevant if t not in summarised]
    chosen = (summarised + others)[:count]

    closing_soon = [t for t in relevant if _aware(t.closing_at) <= now + timedelta(days=3)]
    if closing_soon and not any(t in closing_soon for t in chosen) and chosen:
        chosen[-1] = closing_soon[0]
    return chosen


# --- Creating a demo team -------------------------------------------------------------------

# For each saved tender: (status, saved by, final status set by, note author, note,
# tasks as (title, assignee index, due in days, done)).
SCRIPT: list[tuple[WorkspaceStatus, int, int, int, str, list[tuple[str, int, int, bool]]]] = [
    (
        WorkspaceStatus.PREPARING,
        0,
        1,
        1,
        "Our 7CE grading qualifies. I've started on the pricing schedule; can someone get "
        "updated bitumen rates from the supplier?",
        [
            ("Complete the pricing schedule", 1, 2, False),
            ("Get updated bitumen rates from supplier", 2, 1, False),
            ("Download and print the bid document", 0, -2, True),
        ],
    ),
    (
        WorkspaceStatus.INTERESTED,
        1,
        0,
        0,
        "Good fit for our Limpopo crew. Let's check whether a site visit is required before "
        "we commit.",
        [
            ("Read the full bid document", 0, 3, False),
            ("Confirm CIDB certificate is still valid", 2, 5, True),
        ],
    ),
    (
        WorkspaceStatus.SUBMITTED,
        2,
        1,
        2,
        "Bid submitted at the municipal offices; Lerato has the stamped receipt.",
        [("File the submission receipt", 1, -1, True)],
    ),
    (
        WorkspaceStatus.PENDING,
        0,
        0,
        1,
        "Saved for later: worth a closer look once the AI summary is ready.",
        [],
    ),
    (
        WorkspaceStatus.NOT_ELIGIBLE,
        1,
        2,
        2,
        "Outside our grading for this one; skipping.",
        [],
    ),
    (
        WorkspaceStatus.INTERESTED,
        2,
        2,
        0,
        "Closing soon. If we bid, we need the pricing done this week.",
        [("Decide whether to bid", 0, 1, False)],
    ),
]


def create_demo_team(db: Session, stores: DemoStores, now: datetime | None = None) -> User:
    """Create a demo team with sample data and return its owner (the visitor's account)."""
    now = now or datetime.now(UTC)
    token = secrets.token_hex(6)
    team = Team(name=TEAM_NAME, plan=Plan.PRO, is_demo=True)
    db.add(team)
    db.flush()

    users = []
    for i, (name, role) in enumerate(PEOPLE):
        users.append(
            User(
                # Unique per demo, but still reads like a person's address in the UI.
                email=f"{name.lower().replace(' ', '.')}.{token[:6]}@demo.example.com",
                full_name=name,
                # Demo accounts are only reached through the demo button, never by password.
                hashed_password=hash_password(secrets.token_urlsafe(32)),
                role=role,
                team_id=team.id,
                created_at=now - timedelta(days=30 - i),
            )
        )
    db.add_all(users)
    db.add(
        CompanyProfile(
            team_id=team.id,
            contact_name=PEOPLE[0][0],
            contact_email=f"tenders.{token[:6]}@demo.example.com",
            contact_phone="+27 12 555 0147",
            physical_address="14 Church Street, Pretoria",
            **PROFILE,
        )
    )
    db.flush()

    tenders = choose_demo_tenders(db, stores.summaries, now)
    profile = ReadinessProfile.model_validate(PROFILE)
    summary_docs = stores.summaries.get_many([t.id for t in tenders])
    notifications: list[Notification] = []
    owner = users[0]

    for index, tender in enumerate(tenders):
        status, saver, changer, author, note, tasks = SCRIPT[index % len(SCRIPT)]
        saved_at = now - timedelta(days=6 - index, hours=3)
        changed_at = saved_at + timedelta(hours=20)
        entry = WorkspaceTender(
            team_id=team.id,
            tender_id=tender.id,
            status=status,
            saved_by_id=users[saver].id,
            status_changed_by_id=users[changer if status != WorkspaceStatus.PENDING else saver].id,
            status_changed_at=changed_at if status != WorkspaceStatus.PENDING else saved_at,
            created_at=saved_at,
        )
        db.add(entry)
        db.flush()

        history = [
            WorkspaceStatusChange(
                entry_id=entry.id,
                from_status=None,
                to_status=WorkspaceStatus.PENDING,
                changed_by_id=users[saver].id,
                created_at=saved_at,
            )
        ]
        if status != WorkspaceStatus.PENDING:
            history.append(
                WorkspaceStatusChange(
                    entry_id=entry.id,
                    from_status=WorkspaceStatus.PENDING,
                    to_status=status,
                    changed_by_id=users[changer].id,
                    created_at=changed_at,
                )
            )
        db.add_all(history)
        db.add(
            WorkspaceNote(
                entry_id=entry.id,
                author_id=users[author].id,
                body=note,
                created_at=saved_at + timedelta(hours=2),
                updated_at=saved_at + timedelta(hours=2),
            )
        )
        for title, assignee, due_in, done in tasks:
            db.add(
                WorkspaceTask(
                    entry_id=entry.id,
                    title=title,
                    assignee_id=users[assignee].id,
                    due_date=date.today() + timedelta(days=due_in),
                    is_done=done,
                    completed_at=now - timedelta(hours=5) if done else None,
                    created_by_id=users[author].id,
                    created_at=saved_at + timedelta(hours=1),
                )
            )

        doc = summary_docs.get(tender.id)
        if doc and doc.get("status") == "ready":
            content = TenderSummaryContent.model_validate(doc["content"])
            result = score_readiness(tender_facts(tender, content), profile, now)
            stores.matches.save(
                team.id,
                tender.id,
                {
                    **result.model_dump(),
                    "checked_by": users[changer].full_name,
                    "profile_updated_at": now,
                    "summary_updated_at": doc.get("updated_at"),
                },
            )

        # Notifications waiting for the visitor, only about things teammates did.
        link, title = f"/workspace/{entry.id}", short(tender.title)
        if changer != 0 and status != WorkspaceStatus.PENDING:
            notifications.append(
                Notification(
                    owner.id,
                    team.id,
                    "status_changed",
                    f"{users[changer].full_name} changed a tender to {STATUS_LABELS[status]}",
                    title,
                    link,
                    users[changer].full_name,
                )
            )
        if author != 0:
            notifications.append(
                Notification(
                    owner.id,
                    team.id,
                    "note_added",
                    f"{users[author].full_name} added a note: “{short(note, 70)}”",
                    title,
                    link,
                    users[author].full_name,
                )
            )
        for task_title, assignee, _, done in tasks:
            if assignee == 0 and author != 0 and not done:
                notifications.append(
                    Notification(
                        owner.id,
                        team.id,
                        "task_assigned",
                        f"{users[author].full_name} assigned you a task: {task_title}",
                        title,
                        link,
                        users[author].full_name,
                    )
                )
        closing = _aware(tender.closing_at)
        if closing <= now + timedelta(days=3) and status not in (
            WorkspaceStatus.SUBMITTED,
            WorkspaceStatus.NOT_ELIGIBLE,
        ):
            notifications.append(
                Notification(
                    owner.id,
                    team.id,
                    "deadline_reminder",
                    f"Closes {closing.astimezone(SAST):%a %d %b}",
                    title,
                    link,
                    dedupe_key=f"deadline:{entry.id}:demo",
                )
            )

    db.commit()
    stores.notifications.add(notifications)
    logger.info("Created demo team %s with %d tenders", team.id, len(tenders))
    return owner


# --- Upkeep -------------------------------------------------------------------------------


def delete_expired_demos(
    db: Session,
    ttl: timedelta,
    delete_team_documents: Callable[[int], None],
    now: datetime | None = None,
) -> int:
    """Delete demo teams older than `ttl`, including their MongoDB documents."""
    cutoff = (now or datetime.now(UTC)) - ttl
    team_ids = list(
        db.scalars(select(Team.id).where(Team.is_demo.is_(True), Team.created_at < cutoff))
    )
    for team_id in team_ids:
        delete_team_documents(team_id)
        db.execute(delete(Team).where(Team.id == team_id))  # cascades to users, workspace...
    db.commit()
    if team_ids:
        logger.info("Deleted %d expired demo team(s)", len(team_ids))
    return len(team_ids)


def prepare_demo_summaries(
    session_factory: Callable[[], Session],
    summaries: SummaryStore,
    llm: LLMClient,
    target: int = 4,
    now: datetime | None = None,
) -> int:
    """Make sure enough suitable open tenders have AI summaries for new demos.

    Picks tenders that stay open for at least 5 more days and have readable documents, so
    demo workspaces show real AI summaries and scores without calling Groq on each click.
    Returns how many summaries were generated.
    """
    now = now or datetime.now(UTC)
    with session_factory() as db:
        relevant = relevant_tenders(db, now, min_days_open=5)
    docs = summaries.get_many([t.id for t in relevant])
    ready = [t for t in relevant if (docs.get(t.id) or {}).get("status") == "ready"]
    missing = target - len(ready)
    candidates = [
        t
        for t in relevant
        if t not in ready
        and (docs.get(t.id) or {}).get("status") != "failed"
        and any((d.get("format") or "").lower() in ("pdf", "docx") for d in t.documents)
    ]

    generated = 0
    for tender in candidates:
        if generated >= missing:
            break
        if not summaries.try_start(tender.id, user_id=0, team_id=0):
            continue
        run_summary_job(tender.id, session_factory=session_factory, store=summaries, llm=llm)
        if (summaries.get(tender.id) or {}).get("status") == "ready":
            generated += 1
    logger.info("Demo summaries: %d ready, %d generated", len(ready), generated)
    return generated


def delete_team_mongo_documents(team_id: int) -> None:
    from app.db.mongo import get_mongo_db

    db = get_mongo_db()
    for collection in ("notifications", "activity_logs", "match_results"):
        db[collection].delete_many({"team_id": team_id})


def run_demo_upkeep(session_factory: Callable[[], Session]) -> None:
    """Hourly: delete expired demo teams and keep a few demo-ready AI summaries in stock."""
    from app.core.config import settings
    from app.services.llm import LLMError, get_llm_client
    from app.services.summary_store import get_summary_store

    with session_factory() as db:
        delete_expired_demos(
            db, timedelta(hours=settings.demo_ttl_hours), delete_team_mongo_documents
        )
    try:
        llm = get_llm_client()
    except LLMError:
        return  # no Groq key: demos still work, just without fresh summaries
    prepare_demo_summaries(session_factory, get_summary_store(), llm)
