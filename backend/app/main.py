from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, company_profile, health, team
from app.core.config import settings
from app.db.mongo import mongo_client


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

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(team.router, prefix="/api")
app.include_router(company_profile.router, prefix="/api")
