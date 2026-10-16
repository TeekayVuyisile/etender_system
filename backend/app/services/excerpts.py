"""Pick the most informative parts of long tender documents to fit the LLM's token budget.

Tender packs are often 50-150 pages, mostly standard forms and legal boilerplate, while the
free Groq tier allows roughly 8,000 tokens per minute. So instead of sending everything we
keep the opening pages (title, closing date, briefing details) plus the passages that score
highest for the information a summary needs: scope, eligibility, CIDB, B-BBEE, evaluation...
"""

import re
from dataclasses import dataclass

from app.services.documents import ExtractedDocument

CHUNK_CHARS = 700
OPENING_CHARS = 4_000
DEFAULT_BUDGET_CHARS = 20_000

_KEYWORDS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(pattern, re.IGNORECASE), weight)
    for pattern, weight in [
        (r"scope of (work|services|the project)|terms of reference|specification", 4),
        (r"\bcidb\b|grading|\b\d{1,2}\s?(ce|gb|eb|ep|me)\b", 4),
        (r"b-?bbee|\bbee\b|level \d contributor", 3),
        (r"eligib|mandatory|minimum requirement|pre-?qualif|disqualif", 4),
        (r"functionality|evaluation criteria|80/20|90/10|preference points", 3),
        (r"closing date|closing time|compulsory|briefing|site (visit|meeting)", 3),
        (r"contract (period|duration)|duration of|period of \w+ \(?\d", 3),
        (r"\bexperience\b|years of|track record|reference letters", 2),
        (r"\bcsd\b|tax compliance|psira|nhbrc|iso \d{4}|accreditation|registered with", 2),
        (r"deliverables|objective|purpose of|background", 2),
        (r"\bestimated (value|budget|cost)\b|\bbudget\b|\bR\s?\d[\d ,.]*(million|m)?\b", 2),
        (r"\bmust\b|\bshall\b|\brequired\b", 1),
    ]
]
# Standard bidding forms and blank fields add little to a summary.
_BOILERPLATE = re.compile(
    r"\b(sbd|mbd) ?\d|declaration of interest|bidder'?s disclosure|signature of bidder"
    r"|commissioner of oaths|witness(es)?:",
    re.IGNORECASE,
)


@dataclass
class Excerpt:
    text: str
    total_chars: int
    chars_used: int

    @property
    def truncated(self) -> bool:
        return self.chars_used < self.total_chars


def _clean(text: str) -> str:
    text = re.sub(r"[_.]{4,}", " ", text)  # form fill-in lines
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def _chunks(text: str) -> list[str]:
    """Split text into ~CHUNK_CHARS pieces on line boundaries."""
    chunks, current = [], ""
    for line in text.splitlines():
        if len(current) + len(line) > CHUNK_CHARS and current:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


def score_chunk(chunk: str) -> float:
    score = sum(weight * min(len(p.findall(chunk)), 3) for p, weight in _KEYWORDS)
    if _BOILERPLATE.search(chunk):
        score -= 6
    return score


def build_excerpt(
    documents: list[ExtractedDocument], budget: int = DEFAULT_BUDGET_CHARS
) -> Excerpt:
    texts = [(doc.title, _clean("\n".join(doc.pages))) for doc in documents]
    total = sum(len(text) for _, text in texts)
    if total <= budget:
        joined = "\n\n".join(f"=== {title} ===\n{text}" for title, text in texts if text)
        return Excerpt(text=joined, total_chars=total, chars_used=total)

    # Candidates: (doc index, chunk index, text, score). Opening chunks of each document get
    # a large bonus so cover-page details are always included.
    candidates = []
    for doc_index, (_, text) in enumerate(texts):
        position = 0
        for chunk_index, chunk in enumerate(_chunks(text)):
            bonus = 100 if position < OPENING_CHARS / max(len(texts), 1) else 0
            candidates.append((doc_index, chunk_index, chunk, score_chunk(chunk) + bonus))
            position += len(chunk)

    selected, used = [], 0
    for candidate in sorted(candidates, key=lambda c: c[3], reverse=True):
        if candidate[3] <= 0 or used + len(candidate[2]) > budget:
            continue
        selected.append(candidate)
        used += len(candidate[2])

    # Put the selected chunks back into document order, marking gaps.
    parts, last = [], None
    for doc_index, chunk_index, chunk, _ in sorted(selected):
        if last is None or last[0] != doc_index:
            parts.append(f"\n=== {texts[doc_index][0]} ===\n")
        elif chunk_index != last[1] + 1:
            parts.append("[...]\n")
        parts.append(chunk)
        last = (doc_index, chunk_index)
    return Excerpt(text="".join(parts).strip(), total_chars=total, chars_used=used)
