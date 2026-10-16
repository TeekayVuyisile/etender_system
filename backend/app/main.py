import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from app.api.routes import auth, company_profile, health, team, tenders, workspace
from app.core.config import settings
from app.db.mongo import mongo_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    mongo_client.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Helps South African SMEs discover, understand and assess public tenders.",
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
