from datetime import datetime

from pydantic import BaseModel


class SyncRunInfo(BaseModel):
    status: str
    trigger: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created: int | None = None
    updated: int | None = None
    enriched: int | None = None
    releases_skipped: int | None = None
    duration_seconds: float | None = None
    error: str | None = None
    portal_error: str | None = None


class SyncStatusResponse(BaseModel):
    last_run: SyncRunInfo | None
    last_success_at: datetime | None
    schedule_enabled: bool
    interval_hours: float
    next_run_at: datetime | None
