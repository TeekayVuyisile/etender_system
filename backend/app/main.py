import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api.routes import (
    auth,
    company_profile,
    health,
    notifications,
    public,
    team,
    tenders,
    workspace,
)
from app.core.config import settings
from app.db.mongo import mongo_client
from app.db.session import SessionLocal
from app.services import sync_job
from app.services.sync_job import SyncScheduler, reminder_job

logger = logging.getLogger(__name__)

# Uvicorn only configures its own loggers; without this the app's INFO messages (e.g. the
# tender sync scheduler) would be dropped.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.sync_schedule_enabled:
        sync_job.scheduler = SyncScheduler(SessionLocal)
        sync_job.scheduler.start()
        sync_job.reminders = reminder_job(SessionLocal)
        sync_job.reminders.start()
    yield
    for job in (sync_job.scheduler, sync_job.reminders):
        if job:
            job.stop()
    mongo_client.close()


API_DESCRIPTION = """
Helps South African SMEs discover, understand and assess public tenders from the
[OCDS eTenders API](https://ocds-api.etenders.gov.za/swagger).

## Public API

Four endpoints are designed for third-party systems and civic-tech apps (see **public API**):
enriched tender releases, spend by buyer, document summaries and readiness checks.

**Authentication.** A team owner creates an API key on the *API access* page. Send it in the
`X-API-Key` header. (A Bearer token from `/api/auth/login` also works, which is handy for
trying the endpoints here: use **Authorize**.)

**Limits.** 60 requests per minute per key. The key's team plan applies: AI summaries and
readiness checks need the Basic plan or above, and on the Free plan each distinct search
counts towards 3 searches a week. Blocked requests return `403` with
`{"code": "upgrade_required", "required_plan": ...}`.
"""

OPENAPI_TAGS = [
    {"name": "public API", "description": "Endpoints for third-party integrations."},
    {"name": "auth", "description": "Register a team and log in."},
    {"name": "team", "description": "Members, plans and API keys."},
    {"name": "company profile", "description": "The company details used for matching."},
    {"name": "tenders", "description": "Search, AI summaries and readiness checks."},
    {"name": "workspace", "description": "Saved tenders, statuses, notes, tasks and exports."},
    {"name": "notifications", "description": "In-app notifications for the signed-in user."},
    {"name": "health", "description": "Service status."},
]

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

# CORS: browsers block requests from one origin (the React app on :5173) to another
# (this API on :8000) unless the API explicitly allows it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PyMongoError)
def mongo_unavailable(request: Request, error: PyMongoError) -> JSONResponse:
    """MongoDB holds AI summaries, match results and logs. If it's unreachable, say so clearly
    instead of failing with a generic 500 error."""
    logger.warning("MongoDB error on %s %s: %s", request.method, request.url.path, error)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The document database is temporarily unavailable. Please try again shortly"
        },
    )


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(team.router, prefix="/api")
app.include_router(company_profile.router, prefix="/api")
app.include_router(tenders.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
