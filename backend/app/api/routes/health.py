from fastapi import APIRouter

from app.core.config import settings
from app.services.cache import get_cache

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    """Confirms the API is running, and tells the frontend which optional features are on.

    `cache` is "connected", "unavailable" (the app still works, just without caching) or
    "disabled" (no REDIS_URL)."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode_enabled,
        "cache": get_cache().status(),
    }
