"""Readiness scoring: compare a tender's requirements with a company profile.

Deliberately rule-based rather than AI-based, so every point of the score can be traced to a
checklist line, the same inputs always give the same result, and checks cost no API tokens.
The AI's job (Milestone 6) is turning documents into structured requirements; this module
only compares structured data.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.company_profile import ReadinessProfile
from app.schemas.readiness import ChecklistItem, Competition, ReadinessResult, Verdict
from app.schemas.summary import TenderRequirements
from app.services.tender_sync import SAST

NATIONAL = "National"

# Certifications are written many ways ("SARS Tax Clearance", "Tax compliance pin"...).
# Each group lists patterns that identify the same registration.
CERTIFICATION_GROUPS: dict[str, list[str]] = {
    "CSD registration": [r"\bcsd\b", r"central supplier"],
    "Tax compliance": [r"\btax\b", r"\bsars\b", r"\btcs\b"],
    "PSIRA registration": [r"psira"],
    "COIDA letter of good standing": [r"coida", r"compensation fund", r"good standing"],
    "NHBRC registration": [r"nhbrc"],
    "SANAS accreditation": [r"sanas"],
    "ISO 9001": [r"iso\s?9001"],
    "ISO 14001": [r"iso\s?14001"],
    "ISO 45001": [r"iso\s?45001", r"ohsas\s?18001", r"iso\s?18001"],
    "UIF registration": [r"\buif\b"],
    "ECSA registration": [r"\becsa\b"],
}
# Things every registered company has; not worth flagging.
_ASSUMED = re.compile(r"company registration|cipc|\bcipro\b|vat registration", re.IGNORECASE)

_STOPWORDS = {
    "and",
    "for",
    "the",
    "of",
    "to",
    "in",
    "on",
    "with",
    "services",
    "service",
    "supply",
    "provision",
    "delivery",
    "appointment",
    "provider",
    "management",
    "general",
    "other",
}


@dataclass
class TenderFacts:
    """What the scorer needs to know about a tender."""

    requirements: TenderRequirements
    title: str
    province: str | None = None
    category: str | None = None
    procurement_method: str | None = None
    closing_at: datetime | None = None
    briefing_compulsory: bool = False
    briefing_at: datetime | None = None
    scope: list[str] = field(default_factory=list)


def _check(key: str, label: str, status: str, detail: str, weight: int) -> ChecklistItem:
    fraction = {"met": 1.0, "partial": 0.5, "unknown": 0.5, "not_met": 0.0}[status]
    return ChecklistItem(
        key=key, label=label, status=status, detail=detail, weight=weight, points=weight * fraction
    )


def _certification_group(name: str) -> str | None:
    for group, patterns in CERTIFICATION_GROUPS.items():
        if any(re.search(p, name, re.IGNORECASE) for p in patterns):
            return group
    return None


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z]{3,}", text.lower())
    # Crude stemming: "construction"/"constructing" -> "constr", so related words match.
    return {w[:6] for w in words if w not in _STOPWORDS}


# --- Individual checks ----------------------------------------------------------


def check_cidb(req: TenderRequirements, profile: ReadinessProfile) -> ChecklistItem | None:
    if not req.cidb:
        return None
    held = {g.class_code: g.grade for g in profile.cidb_gradings}
    required = ", ".join(f"{r.min_grade}{r.class_code}" for r in req.cidb)
    missing = [r for r in req.cidb if held.get(r.class_code, 0) < r.min_grade]
    if not missing:
        return _check("cidb", f"Has required CIDB grading ({required})", "met", "Yes", 25)
    yours = ", ".join(f"{g}{c}" for c, g in held.items()) or "none"
    return _check(
        "cidb",
        f"Has required CIDB grading ({required})",
        "not_met",
        f"No: you have {yours}",
        25,
    )


def check_province(facts: TenderFacts, profile: ReadinessProfile) -> ChecklistItem | None:
    required = facts.requirements.provinces or (
        [facts.province] if facts.province and facts.province != NATIONAL else []
    )
    if not required:
        return None
    covered = [p for p in required if p in profile.provinces]
    label = f"Operates in {', '.join(required)}"
    if len(covered) == len(required):
        return _check("province", label, "met", "Yes", 20)
    if covered:
        missing = ", ".join(p for p in required if p not in covered)
        return _check("province", label, "partial", f"Partly: not in {missing}", 20)
    return _check("province", label, "not_met", "No: outside your coverage", 20)


def check_bbbee(req: TenderRequirements, profile: ReadinessProfile) -> ChecklistItem:
    level = profile.bbbee_level
    yours = f"Level {level}" if level else "not rated"
    if req.bbbee_min_level:
        label = f"Meets minimum B-BBEE level (Level {req.bbbee_min_level})"
        if level and level <= req.bbbee_min_level:  # Level 1 is the best
            return _check("bbbee", label, "met", f"Yes: {yours}", 15)
        return _check("bbbee", label, "not_met", f"No: you are {yours}", 15)

    # Not mandatory, but B-BBEE status still earns preference points.
    label = "B-BBEE status earns preference points"
    if level and level <= 2:
        return _check("bbbee", label, "met", f"Yes: {yours}", 5)
    if level and level <= 4:
        return _check("bbbee", label, "partial", f"Some: {yours}", 5)
    return _check("bbbee", label, "not_met", f"Few or none: {yours}", 5)


def check_experience(req: TenderRequirements, profile: ReadinessProfile) -> ChecklistItem | None:
    if not req.min_years_experience:
        return None
    label = f"Has {req.min_years_experience}+ years of experience"
    years = profile.years_of_experience
    if years >= req.min_years_experience:
        return _check("experience", label, "met", f"Yes: {years} years", 15)
    return _check("experience", label, "not_met", f"No: {years} years", 15)


def check_certifications(
    req: TenderRequirements, profile: ReadinessProfile
) -> ChecklistItem | None:
    required = [c for c in req.certifications if not _ASSUMED.search(c)]
    if not required:
        return None
    held_groups = {_certification_group(c) for c in profile.certifications} - {None}
    held_text = " ".join(profile.certifications).lower()

    have, missing, unconfirmed = [], [], []
    for cert in required:
        group = _certification_group(cert)
        if group and group in held_groups:
            have.append(cert)
        elif not group and cert.lower() in held_text:
            have.append(cert)
        elif group:
            missing.append(cert)
        else:
            unconfirmed.append(cert)  # not something we can recognise in a profile

    label = "Holds required certifications"
    parts = []
    if missing:
        parts.append(f"missing {', '.join(missing)}")
    if unconfirmed:
        parts.append(f"confirm you have {', '.join(unconfirmed)}")
    if not missing and not unconfirmed:
        return _check("certifications", label, "met", f"Yes: {', '.join(have)}", 15)
    if missing and not have and not unconfirmed:
        return _check("certifications", label, "not_met", "No: " + "; ".join(parts), 15)
    status = "partial" if missing else "unknown"
    detail = "; ".join(parts)
    return _check("certifications", label, status, detail[0].upper() + detail[1:], 15)


def check_services(facts: TenderFacts, profile: ReadinessProfile) -> ChecklistItem:
    # Portal categories are broad ("Cleaning and Security Services"), so services are matched
    # against the tender's own title and scope; the category only counts for the sector.
    tender_words = _keywords(" ".join([facts.title, *facts.scope]))
    matching = [s for s in profile.services if _keywords(s) & tender_words]
    label = "Your services match the tender's scope"
    if matching:
        return _check("services", label, "met", f"Yes: {', '.join(matching[:3])}", 10)
    sector_words = tender_words | _keywords(facts.category or "")
    if _keywords(profile.industry_sector) & sector_words:
        return _check("services", label, "partial", f"Same sector ({profile.industry_sector})", 10)
    return _check("services", label, "not_met", "No obvious overlap with your services", 10)


def as_utc(value: datetime) -> datetime:
    """Treat timezone-less datetimes (e.g. from SQLite) as UTC so they can be compared."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def check_briefing(facts: TenderFacts, now: datetime) -> ChecklistItem | None:
    from_documents = facts.requirements.compulsory_briefing
    compulsory = facts.briefing_compulsory or from_documents
    if not compulsory or facts.briefing_at is None:
        return None
    label = "Compulsory briefing session not missed"
    when = f"{as_utc(facts.briefing_at).astimezone(SAST):%d %b %Y %H:%M}"
    if facts.briefing_compulsory and from_documents is False:
        # The portal and the documents disagree (often an addendum changed it): don't block,
        # but make sure the bidder checks.
        return _check(
            "briefing",
            label,
            "unknown",
            f"The portal lists a compulsory briefing on {when}, but the documents describe it "
            "as optional. Confirm with the buyer",
            10,
        )
    if as_utc(facts.briefing_at) < now:
        return _check("briefing", label, "not_met", f"It was on {when}", 10)
    return _check("briefing", label, "met", f"Attend on {when}", 10)


# --- Overall result -----------------------------------------------------------


def estimate_competition(facts: TenderFacts) -> Competition:
    """Rough guess: strict requirements shrink the pool of eligible bidders."""
    req = facts.requirements
    top_grade = max((r.min_grade for r in req.cidb), default=0)
    common = (None, "CSD registration", "Tax compliance")
    specialist = sum(1 for c in req.certifications if _certification_group(c) not in common)
    if top_grade >= 7 or (req.min_years_experience or 0) >= 10 or specialist >= 2:
        return "low"
    if "quotation" in (facts.procurement_method or "").lower() and top_grade <= 3:
        return "high"
    return "moderate"


def _verdict(score: int, blockers: list[str]) -> Verdict:
    if blockers or score < 50:
        return "not_suitable"
    return "suitable" if score >= 75 else "possibly_suitable"


def _recommendation(verdict: Verdict, competition: Competition, blockers: list[str]) -> str:
    if verdict == "not_suitable":
        if blockers:
            return f"Not suitable: {'; '.join(blockers)}"
        return "Not suitable: you meet too few of the requirements"
    prefix = "Suitable" if verdict == "suitable" else "Possibly suitable: check the gaps first"
    return f"{prefix}. {competition.capitalize()} competition expected"


def score_readiness(
    facts: TenderFacts, profile: ReadinessProfile, now: datetime | None = None
) -> ReadinessResult:
    now = now or datetime.now(UTC)
    req = facts.requirements
    checks = [
        check_cidb(req, profile),
        check_province(facts, profile),
        check_bbbee(req, profile),
        check_experience(req, profile),
        check_certifications(req, profile),
        check_services(facts, profile),
        check_briefing(facts, now),
    ]
    checklist = [c for c in checks if c is not None]
    possible = sum(c.weight for c in checklist)
    score = round(100 * sum(c.points for c in checklist) / possible) if possible else 0

    blockers = []
    for item in checklist:
        if item.status != "not_met":
            continue
        if item.key == "cidb":
            blockers.append("you don't have the required CIDB grading")
        elif item.key == "bbbee" and req.bbbee_min_level:
            blockers.append("your B-BBEE level is below the minimum")
        elif item.key == "briefing":
            blockers.append("the compulsory briefing has already taken place")

    competition = estimate_competition(facts)
    verdict = _verdict(score, blockers)
    return ReadinessResult(
        score=score,
        verdict=verdict,
        competition=competition,
        recommendation=_recommendation(verdict, competition, blockers),
        checklist=checklist,
        blockers=blockers,
    )
