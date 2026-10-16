"""Workspace report exports (Pro plan): CSV for spreadsheets, PDF for sharing."""

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from html import escape

import pymupdf

from app.schemas.workspace import WorkspaceEntryRead
from app.services.tender_sync import SAST

STATUS_LABELS = {
    "pending": "Pending",
    "interested": "Interested",
    "preparing": "Preparing bid",
    "submitted": "Submitted",
    "not_eligible": "Not eligible",
}
VERDICT_LABELS = {
    "suitable": "Suitable",
    "possibly_suitable": "Possibly suitable",
    "not_suitable": "Not suitable",
}


@dataclass
class ReportRow:
    entry: WorkspaceEntryRead
    verdict: str | None


def _date(value: datetime | None, with_time: bool = False) -> str:
    if value is None:
        return ""
    return value.astimezone(SAST).strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def build_csv(rows: list[ReportRow]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Tender number",
            "Title",
            "Buyer",
            "Province",
            "Closing date",
            "Status",
            "Status changed by",
            "Match score",
            "Verdict",
            "Open tasks",
            "Notes",
            "Saved by",
            "AI summary",
        ]
    )
    for row in rows:
        e = row.entry
        writer.writerow(
            [
                e.tender.tender_number,
                e.tender.title,
                e.tender.buyer_name,
                e.tender.province or "",
                _date(e.tender.closing_at, with_time=True),
                STATUS_LABELS[e.status],
                e.status_changed_by.full_name if e.status_changed_by else "",
                "" if e.match_score is None else round(e.match_score),
                VERDICT_LABELS.get(row.verdict or "", ""),
                e.open_task_count,
                e.note_count,
                e.saved_by.full_name if e.saved_by else "",
                e.ai_summary or "",
            ]
        )
    # A byte-order mark makes Excel open the file as UTF-8 (names with accents, "–" etc.).
    return ("﻿" + buffer.getvalue()).encode("utf-8")


_CSS = """
* { font-family: sans-serif; }
body { font-size: 9pt; color: #0f172a; }
h1 { font-size: 16pt; margin: 0; }
.muted { color: #64748b; }
.counts { margin: 10px 0 14px 0; }
table { border-collapse: collapse; width: 100%; }
th { background: #ecfdf5; color: #065f46; text-align: left; font-size: 8pt; padding: 4px; }
td { border-bottom: 1px solid #e2e8f0; padding: 4px; vertical-align: top; }
.score { font-weight: bold; }
.summary { color: #475569; font-size: 8pt; }
"""


def build_pdf(team_name: str, rows: list[ReportRow], generated_at: datetime) -> bytes:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.entry.status] = counts.get(row.entry.status, 0) + 1
    counts_text = " · ".join(
        f"{label}: {counts.get(status, 0)}" for status, label in STATUS_LABELS.items()
    )

    body_rows = []
    for row in rows:
        e = row.entry
        score = "–" if e.match_score is None else f"{round(e.match_score)}/100"
        verdict = VERDICT_LABELS.get(row.verdict or "", "")
        summary = f'<div class="summary">{escape(e.ai_summary)}</div>' if e.ai_summary else ""
        body_rows.append(
            "<tr>"
            f'<td><b>{escape(e.tender.title)}</b><br/><span class="muted">'
            f"{escape(e.tender.tender_number)} · {escape(e.tender.buyer_name)}</span>{summary}</td>"
            f"<td>{escape(e.tender.province or '')}</td>"
            f"<td>{_date(e.tender.closing_at)}</td>"
            f"<td>{STATUS_LABELS[e.status]}</td>"
            f'<td class="score">{score}<br/><span class="muted">{verdict}</span></td>'
            f"<td>{e.open_task_count}</td>"
            "</tr>"
        )

    html = f"""
    <h1>{escape(team_name)}: workspace report</h1>
    <p class="muted">Generated {generated_at.astimezone(SAST):%d %B %Y, %H:%M} (SAST) ·
    {len(rows)} tender{"" if len(rows) == 1 else "s"} · Tender Insight Hub</p>
    <p class="counts">{counts_text}</p>
    <table>
      <tr><th>Tender</th><th>Province</th><th>Closes</th><th>Status</th><th>Match</th>
      <th>Open tasks</th></tr>
      {"".join(body_rows) or '<tr><td colspan="6">No saved tenders.</td></tr>'}
    </table>
    """

    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    story = pymupdf.Story(html=html, user_css=_CSS)
    page_rect = pymupdf.paper_rect("a4-l")  # landscape fits the table better
    content_rect = page_rect + (36, 36, -36, -36)
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()
