# Tender Insight Hub

A multi-tenant SaaS platform that helps South African SMEs discover, understand and assess public tenders from the [OCDS eTenders API](https://ocds-api.etenders.gov.za/).

> 🚧 Work in progress: a personal portfolio project, built feature by feature.

## Features (planned)

- **Keyword search and filtering** of tenders by province, deadline, buyer and budget
- **Company profiles** (sector, services, CIDB/BBBEE certifications, coverage, experience)
- **AI summaries** of tender documents (PDF/ZIP), highlighting objective, scope, deadline and eligibility
- **Readiness scoring**: a suitability score out of 100, a matched/unmatched checklist and a recommendation
- **Team workspace**: save tenders, track status, leave notes and assign tasks
- **Public REST API** documented with OpenAPI/Swagger
- **SaaS plans** (Free / Basic / Pro) with feature and seat limits

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.12), Pydantic, SQLAlchemy, Alembic |
| Databases | PostgreSQL (structured data), MongoDB (AI results, logs) |
| Frontend | React, TypeScript, Tailwind CSS, Vite |
| AI | Groq LLM API |
| Tooling | GitHub Actions (CI), Docker Compose |

## Project structure

```
backend/    FastAPI application
frontend/   React application
```

## Tender data

Tenders are imported from the [OCDS eTenders API](https://ocds-api.etenders.gov.za/swagger),
upserted into PostgreSQL, and each run is recorded in MongoDB (`tender_sync_runs`).

- **On a schedule:** every `SYNC_INTERVAL_HOURS` (default 6), importing the last `SYNC_DAYS`
  (default 3) and re-enriching all open tenders. Run it as a worker with
  `python -m app.cli scheduler`, or inside the API with `SYNC_SCHEDULE_ENABLED=true`.
- **On demand:** `python -m app.cli sync-tenders --days 30` (e.g. the first import).
- A lock in PostgreSQL (`job_locks`) ensures only one sync runs at a time across processes;
  it expires automatically if a sync crashes. The Tenders page shows when data was last updated
  (`GET /api/tenders/sync-status`).

Some notes on the source data:

- **Province, category, briefing sessions and contact details** aren't part of the OCDS releases.
  They are added from the eTenders portal listing (matched on tender ID). If that enrichment fails,
  the province is estimated from place names in the tender text.
- **Budgets**: the API reports a value of 0 for virtually all tenders, so the budget filter only
  matches tenders whose value is known.
- **Times** are South African local time, even though the API labels them as UTC.
- A small number of records cause the OCDS API to return HTTP 500; the sync narrows failing pages
  down and skips only those records.

## AI pipeline

Tender summaries are generated on request (`POST /api/tenders/{id}/summary`) as a background job;
the frontend polls `GET /api/tenders/{id}/summary` until it's ready.

1. **Download** up to 3 of the tender's documents (PDF, DOCX, or ZIPs containing them), with
   size limits and zip-bomb protection.
2. **Extract text** with PyMuPDF (PDF) and python-docx (DOCX, including tables).
3. **Select excerpts.** Tender packs are often 50–150 pages, mostly standard forms, while the
   free Groq tier allows ~8,000 tokens per minute. The pipeline keeps each document's opening
   pages and the passages that score highest for scope, eligibility, CIDB, B-BBEE, evaluation,
   briefing and duration keywords (boilerplate forms are penalised), within ~20k characters.
4. **Summarise** with Groq (`openai/gpt-oss-120b`, JSON mode, low reasoning effort). The prompt
   asks for a plain-language summary plus structured fields: objective, scope, closing date,
   eligibility, requirements (CIDB class/grade, B-BBEE level, experience, certifications,
   provinces, compulsory briefing), contract duration, evaluation method, estimated value and
   other highlights. The model is told to leave unknown fields empty rather than guess.
5. **Validate** the response with Pydantic (invalid CIDB classes, provinces, numbers are
   dropped) and **store** it in MongoDB (`tender_summaries`). Extracted values also fill in the
   tender's budget when the source data has none.

Scanned documents without a text layer fall back to a summary of the tender's portal details,
and say so. LLM calls are serialised and retried on rate limits.

## Readiness scoring

"Match This Tender" (`POST /api/tenders/{id}/match`) compares the requirements the AI extracted
with the team's company profile. Scoring is **rule-based, not AI-based**, so every point traces
to a checklist line, results are repeatable, and checks cost no API tokens.

| Check | Weight | Applies when |
|---|---|---|
| Required CIDB grading (class and grade) | 25 | The tender requires CIDB |
| Operates in the delivery province(s) | 20 | A province is known |
| Minimum B-BBEE level (or preference points if not mandatory) | 15 (5) | Always |
| Years of experience | 15 | A minimum is stated |
| Required certifications (matched across different wordings) | 15 | Certifications are listed |
| Services match the tender's title and scope | 10 | Always |
| Compulsory briefing not missed | 10 | A compulsory briefing date is known |

The score is the points earned out of the points available for applicable checks. Missing a
required CIDB grading, a mandatory B-BBEE level or a compulsory briefing makes a tender
"Not suitable" regardless of score. Competition is a heuristic based on how restrictive the
requirements are. Results are stored per team in MongoDB (`match_results`), flagged as outdated
when the profile or summary changes, and used to rank the team's workspace.

## SaaS plans

| | Free | Basic | Pro |
|---|---|---|---|
| Team members | 1 | 3 | Unlimited |
| Tender searches | 3 per week | Unlimited | Unlimited |
| AI summaries and readiness checks | – | ✓ | ✓ |
| Workspace report export (CSV, PDF) | – | – | ✓ |

Limits are enforced on the server (`app/core/plans.py` defines them, `app/services/plans.py`
enforces them): feature-gated endpoints use a `require_feature(...)` dependency and blocked
requests return `403` with `{"code": "upgrade_required", "required_plan": ...}`. A "search" is a
distinct combination of keywords and filters per calendar week (Monday, SA time), so paging or
re-sorting doesn't count. Billing is simulated: team owners switch plans on the Plan page.

## Public API

Documented with OpenAPI at `/docs`. Authenticate with an API key (created by a team owner on
the API page) in the `X-API-Key` header; a Bearer token also works. 60 requests per minute per
key, and the key's team plan applies.

| Endpoint | Description |
|---|---|
| `GET /api/enriched-releases` | Filtered tenders with metadata, AI summary and a suitability score calculated live against the team's company profile |
| `GET /api/analytics/spend-by-buyer` | Tenders advertised, open tenders and known values per buyer, with `value_coverage`. Cached in MongoDB for an hour |
| `POST /api/summary/extract` | Upload a PDF or DOCX (max 15 MB) and get a ~120-word summary |
| `POST /api/readiness/check` | `{tender_id, company_profile?}` returns the score, checklist and recommendation; defaults to the team's profile |

```bash
curl -H "X-API-Key: tih_your_key" \
  "http://localhost:8000/api/enriched-releases?q=road+maintenance&province=Limpopo"
curl -H "X-API-Key: tih_your_key" -F "file=@bid-document.pdf" \
  http://localhost:8000/api/summary/extract
```

API keys are stored as SHA-256 hashes and shown once on creation. Because neither eTenders
source publishes award values, spend-by-buyer reports advertised activity and known values
rather than actual spend.

## Getting started

**Prerequisites:** Python 3.12+, Node.js 20+

**Backend** (http://localhost:8000, API docs at `/docs`):

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then set DATABASE_URL, MONGODB_URL, JWT_SECRET_KEY
alembic upgrade head            # create/upgrade database tables
python -m app.cli sync-tenders --days 30   # import tenders from the eTenders APIs
fastapi dev app/main.py
```

**Frontend** (http://localhost:5173), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api/*` requests to the backend.

**Checks:**

```bash
cd backend && pytest && ruff check .      # backend tests + lint
cd frontend && npm run lint && npm run build   # frontend lint + type-check/build
```
