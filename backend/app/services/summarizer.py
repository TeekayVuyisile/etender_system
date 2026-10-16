"""AI summary pipeline: download documents -> extract text -> select excerpts -> Groq -> store.

Runs as a background job so the API can respond immediately; the frontend polls for the result.
"""

import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models import Tender
from app.schemas.summary import TenderSummaryContent
from app.services.documents import (
    DocumentError,
    ExtractedDocument,
    download,
    extract,
    guess_format,
)
from app.services.excerpts import build_excerpt
from app.services.llm import LLMClient, LLMError
from app.services.summary_store import SummaryStore

logger = logging.getLogger(__name__)

MAX_DOCUMENTS = 3

SYSTEM_PROMPT = """\
You help small and medium South African businesses understand public tenders.
You are given a tender's official details and excerpts from its documents (excerpts may skip
parts, marked "[...]"). Write for a busy business owner: plain language, no legal jargon.
Only use information in the input. If something isn't stated, use null or an empty list;
never guess or invent requirements.

Respond with a JSON object with exactly these keys:
- "summary": string, 100-150 words: what is being bought, by whom, where, the deadline and
  the most important eligibility conditions.
- "objective": string, one sentence on the purpose of the tender.
- "scope": list of up to 6 short strings describing the work or goods required.
- "closing_date": string "YYYY-MM-DD HH:MM" (South African time) or null.
- "eligibility": list of up to 8 short strings: who may bid and mandatory requirements.
- "requirements": object with:
    "cidb": list of {"class_code": one of CE, GB, EB, EP, ME, "min_grade": integer 1-9},
    "bbbee_min_level": integer 1-8 or null (only if a minimum B-BBEE level is mandatory),
    "min_years_experience": integer or null,
    "certifications": list of required registrations/certificates (e.g. "CSD Registration",
      "SARS Tax Compliance Status", "PSIRA Registration", "ISO 9001"),
    "provinces": list of South African provinces where the work is delivered,
    "compulsory_briefing": true, false or null.
- "contract_duration": string or null (e.g. "36 months").
- "evaluation": string or null: how bids are scored (e.g. "80/20 preference points;
  functionality minimum 70%").
- "estimated_value": number in rand or null (only if a budget or value is stated).
- "other_highlights": list of up to 5 other things a bidder must not miss (penalties,
  site visits, sample submissions, local content, unusual conditions).
"""


def tender_details(tender: Tender) -> str:
    lines = [
        f"Tender number: {tender.tender_number}",
        f"Description: {tender.title}",
        f"Buyer: {tender.buyer_name}",
        f"Province: {tender.province or 'not specified'}",
        f"Category: {tender.category or 'not specified'}",
        f"Procurement method: {tender.procurement_method or 'not specified'}",
        f"Closing date: {tender.closing_at:%Y-%m-%d %H:%M}" if tender.closing_at else "",
        f"Delivery location: {tender.delivery_location}" if tender.delivery_location else "",
    ]
    if tender.briefing_session:
        kind = "Compulsory" if tender.briefing_compulsory else "Optional"
        when = f" on {tender.briefing_at:%Y-%m-%d %H:%M}" if tender.briefing_at else ""
        lines.append(f"Briefing session: {kind}{when}. {tender.briefing_venue or ''}")
    if tender.special_conditions:
        lines.append(f"Special conditions: {tender.special_conditions}")
    return "\n".join(line for line in lines if line)


def collect_documents(
    client: httpx.Client, tender: Tender
) -> tuple[list[ExtractedDocument], list[str]]:
    """Download and extract the tender's supported documents. Returns (documents, unreadable)."""
    documents: list[ExtractedDocument] = []
    unreadable: list[str] = []
    candidates = [
        (doc, fmt)
        for doc in tender.documents
        if (fmt := guess_format(doc.get("title", ""), doc.get("format"))) and doc.get("url")
    ][:MAX_DOCUMENTS]

    for doc, file_format in candidates:
        title = doc.get("title") or "Document"
        try:
            extracted = extract(download(client, doc["url"]), title, file_format)
        except DocumentError as error:
            logger.info("Could not use %s for tender %s: %s", title, tender.id, error)
            unreadable.append(title)
            continue
        readable = [d for d in extracted if d.char_count >= 200]
        if not readable:
            unreadable.append(title)  # e.g. scanned PDFs with no text layer
        documents.extend(readable)
    return documents, unreadable


def summarize(tender: Tender, documents: list[ExtractedDocument], llm: LLMClient) -> dict[str, Any]:
    excerpt = build_excerpt(documents)
    if excerpt.text:
        body = f"DOCUMENT EXCERPTS:\n{excerpt.text}"
    else:
        body = (
            "No readable document text was available (documents may be scanned images). "
            "Summarise from the tender details only and leave unknown fields empty."
        )
    response = llm.chat_json(
        SYSTEM_PROMPT, f"TENDER DETAILS:\n{tender_details(tender)}\n\n{body}", max_tokens=1600
    )
    content = TenderSummaryContent.model_validate(response.data)
    if not content.summary:
        raise LLMError("The AI model returned an empty summary")
    return {
        "content": content.model_dump(),
        "source": "documents" if excerpt.text else "details_only",
        "documents": [{"title": d.title, "chars": d.char_count} for d in documents],
        "truncated": excerpt.truncated,
        "model": response.model,
        "total_tokens": response.total_tokens,
    }


def default_http_client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(90.0, connect=15.0), follow_redirects=True)


def run_summary_job(
    tender_id: int,
    *,
    session_factory: Callable[[], Session],
    store: SummaryStore,
    llm: LLMClient,
    http_client_factory: Callable[[], httpx.Client] = default_http_client,
) -> None:
    """Background job: generate and store the summary for one tender."""
    try:
        with session_factory() as db, http_client_factory() as client:
            tender = db.get(Tender, tender_id)
            if tender is None:
                store.save_failed(tender_id, "Tender not found")
                return
            documents, unreadable = collect_documents(client, tender)
            result = summarize(tender, documents, llm)
            result["unreadable_documents"] = unreadable

            # Most tenders don't publish a value; if the documents state one, keep it so the
            # budget filter can use it.
            value = result["content"]["estimated_value"]
            if value and tender.estimated_value is None:
                tender.estimated_value = Decimal(str(round(value, 2)))
                db.commit()
        store.save_ready(tender_id, result)
    except LLMError as error:
        store.save_failed(tender_id, str(error))
    except Exception:
        logger.exception("Summary job failed for tender %s", tender_id)
        store.save_failed(tender_id, "Something went wrong while generating the summary")


# --- Single-document summaries (public API: POST /api/summary/extract) ---------------

TARGET_WORDS = 120

DOCUMENT_PROMPT = """\
You summarise South African tender documents for small businesses in plain language.
Write ONE paragraph of about 120 words (between 105 and 125) covering: what is being
procured and by whom, the scope, the closing date, and who is eligible (key mandatory
requirements such as CIDB grading, B-BBEE, registrations or experience). Only use
information in the document; don't invent details. If the text is not a tender document,
summarise what it is instead.
Respond with a JSON object: {"summary": "<the paragraph>"}
"""


def limit_words(text: str, limit: int = TARGET_WORDS, slack: int = 10) -> str:
    """Keep summaries at about `limit` words, cutting at a sentence end where possible."""
    words = text.split()
    if len(words) <= limit + slack:
        return " ".join(words)
    cut = " ".join(words[:limit])
    sentence_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if sentence_end > len(cut) * 0.6:
        return cut[: sentence_end + 1]
    return cut.rstrip(",;:") + "…"


def summarize_document(documents: list[ExtractedDocument], llm: LLMClient) -> dict[str, Any]:
    excerpt = build_excerpt(documents)
    if not excerpt.text:
        raise DocumentError("No readable text found (the file may be a scanned image)")
    response = llm.chat_json(DOCUMENT_PROMPT, f"DOCUMENT:\n{excerpt.text}", max_tokens=900)
    summary = limit_words(str(response.data.get("summary") or "").strip())
    if not summary:
        raise LLMError("The AI model returned an empty summary")
    return {
        "summary": summary,
        "word_count": len(summary.split()),
        "truncated_input": excerpt.truncated,
        "model": response.model,
    }
