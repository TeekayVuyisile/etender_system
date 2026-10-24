# Tender Insight Hub

[![CI](https://github.com/TeekayVuyisile/etender_system/actions/workflows/ci.yml/badge.svg)](https://github.com/TeekayVuyisile/etender_system/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_19-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white)

A multi-tenant SaaS platform that helps South African SMEs **find public tenders that fit their
business, understand the bid documents in minutes and decide where they can win**. It's built on
live data from the National Treasury [OCDS eTenders API](https://ocds-api.etenders.gov.za/).

![Tender Insight Hub landing page](docs/screenshots/landing.jpg)

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/search.jpg" alt="Full-text tender search with filters"><br><sub><b>Search</b>: full-text search across open tenders, with province, buyer and deadline filters</sub></td>
    <td width="50%"><img src="docs/screenshots/workspace.jpg" alt="Team workspace ranked by match score"><br><sub><b>Workspace</b>: the team's saved tenders, ranked by readiness score</sub></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/summary.jpg" alt="AI summary of a tender's documents"><br><sub><b>AI summary</b>: scope, dates, CIDB, B-BBEE and evaluation criteria pulled from the bid documents</sub></td>
    <td><img src="docs/screenshots/readiness.jpg" alt="Rule-based readiness check"><br><sub><b>Match This Tender</b>: a transparent, rule-based score against the company profile</sub></td>
  </tr>
</table>

## Features

- **Tender discovery.** Tenders are synced from the OCDS API every few hours and enriched with
  province, category, briefing and contact details from the eTenders portal. Search them with
  PostgreSQL full-text search and filters.
- **AI document summaries.** The app downloads the bid documents (PDF, DOCX, ZIP), picks the
  passages that matter and has an LLM turn them into a plain-language summary with structured
  requirements.
- **Readiness scoring.** "Match This Tender" checks CIDB grading, provinces, B-BBEE, experience,
  certifications, scope and briefings against the company profile. You get a score out of 100,
  a checklist and a recommendation.
- **Team workspace.** Save tenders, move them through a bid pipeline (Pending → Submitted), and
  keep a status history, notes and assigned tasks.
- **Notifications.** In-app alerts for assignments, status changes and finished summaries, plus
  reminders before closing dates and compulsory briefings.
- **SaaS plans.** Free, Basic and Pro, with seat, search and feature limits enforced on the server.
  CSV and PDF reports are available on Pro.
- **Public REST API.** API keys, OpenAPI docs and rate limiting, serving enriched tenders, spend
  analytics, document summaries and readiness checks to third-party systems.
- **One-click demo.** Each visitor gets a private, pre-filled demo workspace that cleans itself
  up after 24 hours.

## Try it

```bash
git clone https://github.com/TeekayVuyisile/etender_system.git
cd etender_system
docker compose up --build
```

Open **http://localhost:8080**. See [Quick start with Docker](#quick-start-with-docker) for the
optional settings (AI summaries need a free Groq API key).

## Architecture

```mermaid
flowchart TB
    subgraph clients ["Clients"]
        direction LR
        browser(["Browser"])
        apps(["Third-party apps<br/>X-API-Key"])
    end

    subgraph compose ["Docker Compose"]
        direction LR
        web["web<br/>nginx + React build"]
        api["api<br/>FastAPI"]
        worker["worker<br/>sync, reminders,<br/>summary jobs"]
        migrate["migrate<br/>Alembic, runs once"]
        pg[("PostgreSQL<br/>teams, tenders,<br/>workspace, plans")]
        mongo[("MongoDB<br/>AI summaries, scores,<br/>notifications, logs")]
        redis[("Redis<br/>cache, rate limits,<br/>job queue")]
    end

    subgraph external ["External services"]
        direction LR
        groq["Groq LLM"]
        etenders["eTenders OCDS API<br/>+ portal"]
    end

    browser --> web
    apps --> web
    web -- "/api, /docs" --> api
    api --> pg
    api --> mongo
    api --> redis
    migrate --> pg
    worker --> pg
    worker --> mongo
    worker --> redis
    worker -. "every 6 h" .-> etenders
    api -. "summaries" .-> groq
    worker -. "summaries" .-> groq
```

**Design decisions**

- **Two databases, each for what it's good at.** Relational data with constraints (teams,
  tenders, workspace, plans) lives in PostgreSQL. Variable-shaped AI output, match results,
  notifications and logs live in MongoDB.
- **Rule-based scoring instead of AI scoring.** The LLM only extracts requirements. The score is
  calculated by code, so it's repeatable, explainable line by line and free to recalculate.
- **Fitting a large document into a small token budget.** Tender packs run to 50–150 pages, while
  the free LLM tier allows about 8k tokens a minute. A keyword-scored excerpt selector sends only
  the passages that matter.
- **AI jobs that survive restarts and share one rate limit.** Summary jobs go on a Redis
  Stream that the worker and API processes read as a consumer group, so a job interrupted by
  a crash is picked up again. Every process reserves Groq tokens from a budget shared in Redis,
  so together they stay under the free tier's per-minute limit instead of hitting 429 errors.
- **A separate worker with a database lock.** Scheduled syncs and reminders run outside the API.
  A PostgreSQL lock guarantees only one sync runs at a time, even with several processes.
- **Redis as a cache that can be lost.** Tender data only changes when the sync runs, so searches
  are served from Redis and invalidated by a version bump after each sync. Rate limits live in
  Redis too, so they hold across API processes. If Redis goes down, the app carries on reading
  from PostgreSQL.
- **Multi-tenancy by team.** Every query is scoped to the user's team, and plan limits are
  enforced by server-side dependencies, not just hidden in the UI.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic |
| Data | PostgreSQL (Neon in development), MongoDB (Atlas in development), Redis (cache and rate limits) |
| AI | Groq (`openai/gpt-oss-120b`), PyMuPDF and python-docx for text extraction |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Router |
| Auth | JWT (PyJWT), Argon2 password hashing, hashed API keys |
| Infrastructure | Docker Compose, nginx, GitHub Actions (CI with a SQLite/PostgreSQL test matrix and image builds) |
| Quality | pytest (225 tests), Ruff, oxlint, TypeScript strict mode, branch protection with required checks |

## How it works

### Tender data

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

### AI pipeline

Tender summaries are generated on request (`POST /api/tenders/{id}/summary`) as a background job;
the frontend polls `GET /api/tenders/{id}/summary` until it's ready. The job is queued in Redis
(see [Background jobs and the Groq budget](#background-jobs-and-the-groq-budget)).

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
and say so. LLM calls wait for the shared token budget and are retried on rate limits.

### Readiness scoring

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

### SaaS plans

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

### Public API

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

### Caching and rate limits (Redis)

Tender data changes only when the sync runs, every 6 hours, but each search costs three
PostgreSQL queries (province counts, total and the page). Searches, tender details, the buyer
list, sync status and the public API's buyer analytics are therefore cached in Redis
(read-through, with TTLs of 1 minute to 1 hour). Responses carry an `X-Cache: HIT` or `MISS`
header.

- **Invalidation by version, not by deleting keys.** Cached tender keys include a version
  number (`tih:search:v42:<hash of the filters>`). After a sync, or when an AI summary fills in
  a missing tender value, the version is incremented. New requests build new keys, and the old
  entries are never read again and expire on their own.
- **Plan limits still apply.** A cached search counts towards the Free plan's weekly limit just
  like an uncached one; the cache only saves the database work.
- **Shared rate limits.** The public API's 60 requests per minute and the demo's 10 per hour
  are counted in a Redis sorted set by a Lua script. The script runs atomically, so two API
  processes can't both let a request through at the limit, and it uses Redis's clock so servers
  can't disagree about time.
- **Failing open.** Redis is optional (`REDIS_URL`). If it's unreachable, lookups count as
  misses, rate limits fall back to per-process counting, and Redis is skipped for 30 seconds so
  requests don't each wait for a timeout. `/api/health` reports the cache as `connected`,
  `unavailable` or `disabled`.
- **One database.** Every key starts with `tih:`, so the app fits in a single Redis database
  (such as the Redis Cloud free plan) alongside other apps.

Measured from South Africa against Neon (Frankfurt) and the Redis Cloud free plan, median of
5 requests through the API:

| Request | Without cache (miss) | Cache hit |
|---|---|---|
| Search, no filters | 1,042 ms | 433 ms |
| Search, keyword | 1,248 ms | 423 ms |
| Search, keyword + province | 1,249 ms | 424 ms |
| Tender detail | 1,397 ms | 427 ms |
| Buyer list | 665 ms | 457 ms |

About 360 ms of every request is the signed-in user lookup in PostgreSQL, which isn't cached.
A cache hit spends only around 70 ms in Redis itself (two round trips).

### Background jobs and the Groq budget

A summary takes up to a minute, so it runs outside the request. FastAPI's `BackgroundTasks`
would lose the job if the process restarted mid-way, so jobs go on a **Redis Stream**
(`tih:queue:summaries`) instead:

- The API adds the job (`XADD`) and returns `202` straight away.
- The worker and every API process read the stream as one **consumer group**, so each job goes
  to exactly one of them, whichever is free.
- A job is acknowledged (`XACK`) only once it has finished. If its process dies first, the job
  stays pending, and another consumer claims it (`XAUTOCLAIM`) after 10 minutes idle. A job
  delivered 3 times without finishing is marked as failed, so it can't loop forever.

Groq's free tier allows about 8,000 tokens a minute **per API key**, however many processes
use it. Before each call, a process reserves its estimated tokens (prompt plus requested
output, which Groq counts up front) in a sliding one-minute window in Redis, using a Lua
script. If the budget is used up, it waits for the oldest call to leave the window rather than
sending a request that would be rejected.

In a test with the real services, two summaries were queued while no consumer was running and
the API was restarted. Both were picked up from the queue: the first finished in 7 seconds, and
the second waited 55 seconds for the token budget and then finished, with no 429 errors from Groq.

Redis is configured to evict only keys that have a TTL (`volatile-lru`, as on Redis Cloud), so
under memory pressure it drops old cache entries but never the queue. Without Redis, summaries
run in the API process with `BackgroundTasks` and LLM calls are made one at a time per process.

### Notifications

In-app notifications appear under the bell in the header: task assignments, status changes,
new notes, finished AI summaries, and reminders when a saved tender closes within 3 days or a
compulsory briefing is within 2 days. Reminders come from an hourly job (alongside the tender
sync) and carry dedupe keys, so each one is sent once.

They're stored in MongoDB (`notifications`) and delivered through a `Notifier` with pluggable
channels. Only the in-app channel exists today; an email channel can be added without
changing the code that raises notifications.

### Demo mode

With `DEMO_MODE_ENABLED=true`, the login page offers **Try the demo**: one click creates a
private demo team (*Thabo's Civil Works*, Pro plan, three members) whose workspace is built
from real open tenders that suit its profile, with AI summaries, match scores, status history,
notes, tasks and notifications. Each visitor gets their own team, so nobody sees anyone else's
changes. Demo teams are deleted after `DEMO_TTL_HOURS` (default 24) by an hourly job, which
also keeps a few demo-ready AI summaries in stock (`python -m app.cli prepare-demo` does the
same on demand). Demo creation is rate-limited to 10 per hour per visitor.

## Quick start with Docker

Runs the whole stack (React app, API, background worker, PostgreSQL, MongoDB and Redis) with one
command. Only [Docker](https://www.docker.com/products/docker-desktop/) is required.

```bash
cp .env.example .env     # optional: add a GROQ_API_KEY for AI summaries, set JWT_SECRET_KEY
docker compose up --build
```

Open **http://localhost:8080**. On first start the worker imports the last `SYNC_DAYS` (default 7)
of tenders, which takes a few minutes; it then syncs every 6 hours.

| Service    | What it does                                                       |
| ---------- | ------------------------------------------------------------------ |
| `web`      | nginx: serves the built React app and proxies `/api` and `/docs`   |
| `api`      | FastAPI backend                                                    |
| `worker`   | Scheduled tender sync, deadline reminders, demo upkeep and AI summary jobs |
| `migrate`  | Applies Alembic migrations, then exits; `api` and `worker` wait for it |
| `postgres` | PostgreSQL 18                                                      |
| `mongo`    | MongoDB 8                                                          |
| `redis`    | Redis 8: cache, rate limits and the AI summary queue               |

Only port 8080 is published; the databases are reachable only inside the Compose network and
keep their data in named volumes.

```bash
docker compose logs -f worker                                   # watch the tender sync
docker compose exec api python -m app.cli sync-tenders --days 30  # import more history
docker compose down        # stop (data is kept)
docker compose down -v     # stop and delete the database volumes
docker system df           # see how much disk Docker uses; `docker system prune` frees it
```

## Deployment

Production runs on free tiers, defined as code in [`render.yaml`](render.yaml) (a Render
Blueprint):

| Part | Where | Notes |
|---|---|---|
| Frontend | Render static site | Served from a CDN; rewrite rules forward `/api/*` to the API, so the browser sees one site |
| API | Render web service (Docker, Frankfurt) | Runs Alembic migrations on start, then FastAPI; also works through the summary queue |
| PostgreSQL | Neon (Frankfurt) | |
| Redis | Redis Cloud free plan (Frankfurt) | Cache, rate limits, job queue and Groq token budget |
| MongoDB | MongoDB Atlas free cluster | |
| Scheduled jobs | GitHub Actions ([`scheduled-jobs.yml`](.github/workflows/scheduled-jobs.yml)) | Tender sync every 6 hours, reminders and demo upkeep hourly |

- **Same city.** The API, Neon and Redis all run in Frankfurt, a few milliseconds apart.
  Every request makes several database and cache calls, so the API sits next to its data
  rather than next to its users.
- **Continuous deployment.** Render deploys each push to `main` once the CI checks have passed,
  and only switches traffic to a new version after its health check (`/api/health`) responds.
- **Sleeping on the free plan.** The API sleeps after 15 minutes idle and takes up to a minute
  to wake. The static frontend never sleeps, and shows a "waking up the server" notice while
  the first request waits. Scheduled work runs from GitHub Actions rather than inside the API,
  because a sleeping service can't run a scheduler.

## Getting started (local development)

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

Tests use in-memory SQLite by default. To run them against PostgreSQL (as CI does), point
`TEST_DATABASE_URL` at an **empty, dedicated** database whose name contains `test`; the suite
deletes all data in it and refuses any other database:

```bash
TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/tih_test pytest
```

CI runs the backend tests on both SQLite and a PostgreSQL service container, and on PostgreSQL
also applies every migration to an empty database and checks the models match (`alembic check`).
It also validates `docker-compose.yml` and builds both Docker images.

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/routes/     HTTP endpoints (auth, tenders, workspace, team, public API...)
│   │   ├── core/           settings, security, plan definitions, reference data
│   │   ├── models/         SQLAlchemy models (PostgreSQL)
│   │   ├── schemas/        Pydantic request and response models
│   │   ├── services/       business logic: sync, AI pipeline, scoring, notifications, demo
│   │   └── cli.py          sync, scheduler and demo commands
│   ├── alembic/            database migrations
│   ├── tests/              pytest suite
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/          one component per route
│   │   ├── landing/        landing page sections
│   │   └── tenders/, workspace/, readiness/, summaries/, ...   features grouped by domain
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
└── .github/workflows/ci.yml
```

## What I learned

I built this project on my own to go from basic Python to shipping a full-stack product. These
are the things that stuck with me most:

- **Real-world data is messy.** The OCDS API returns HTTP 500 for a handful of records, reports
  a budget of 0 for almost every tender, and labels South African local times as UTC. A lot of
  the sync code exists to cope with that gracefully: narrowing failing pages down to single
  records, enriching from a second source, and not trusting what the data claims to be.
- **Working within LLM limits.** I had to fit 100-page documents into a free-tier token budget.
  That meant selecting excerpts rather than sending everything, asking for structured JSON,
  validating it with Pydantic, and keeping decisions like scoring out of the model.
- **Frontend from scratch.** React, TypeScript and Tailwind, with server state in TanStack Query,
  protected routes and plan-aware UI.
- **CI/CD.** GitHub Actions with a test matrix (SQLite and a real PostgreSQL service container),
  migration drift checks, image builds, and branch protection with required status checks. I also
  learned that renaming a CI job silently breaks the required checks until the ruleset is
  updated.
- **Docker.** Layer caching, multi-stage builds, non-root containers, health checks, startup
  ordering with `depends_on`, why `localhost` inside a container isn't your machine, and why
  proxied apps need to trust `X-Forwarded-For` for per-IP rate limits.
- **Testing catches what you don't expect.** One test passed in CI but failed locally, because
  the suite was reading my local `.env`. Pinning configuration in tests fixed it.
- **A professional Git workflow.** Feature branches, Conventional Commits and pull requests
  for every change, merged only when CI passed.

I used Claude Code as an AI pair programmer throughout. I owned the Git and GitHub side (every
branch, commit, PR and merge) and worked through the CI and Docker configuration line by line
until I understood it.

## License

[MIT](LICENSE)
