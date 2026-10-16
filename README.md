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

Tenders are imported from the [OCDS eTenders API](https://ocds-api.etenders.gov.za/swagger) by
`python -m app.cli sync-tenders`, which upserts releases into PostgreSQL and records each run in
MongoDB. Some notes on the source data:

- **Province, category, briefing sessions and contact details** aren't part of the OCDS releases.
  They are added from the eTenders portal listing (matched on tender ID). If that enrichment fails,
  the province is estimated from place names in the tender text.
- **Budgets**: the API reports a value of 0 for virtually all tenders, so the budget filter only
  matches tenders whose value is known.
- **Times** are South African local time, even though the API labels them as UTC.
- A small number of records cause the OCDS API to return HTTP 500; the sync narrows failing pages
  down and skips only those records.

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
