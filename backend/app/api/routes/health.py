from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    """Confirms the API is running, and tells the frontend which optional features are on."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "demo_mode": settings.demo_mode_enabled,
    }
