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

## Getting started

_Setup instructions will be added as the project develops._
