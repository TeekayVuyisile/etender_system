import os

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Simple endpoint to confirm the API is running."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}
