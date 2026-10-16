"""A simple cross-process lock stored in PostgreSQL.

Each acquire/release is a single atomic statement, so it works through connection poolers
(such as Neon's) where session-level advisory locks don't.
"""

import os
import socket
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import JobLock


def lock_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def acquire(db: Session, name: str, ttl: timedelta, owner: str | None = None) -> bool:
    """Take the lock if it's free or expired. Returns False if someone else holds it."""
    owner = owner or lock_owner()
    now = datetime.now(UTC)
    taken = db.execute(
        update(JobLock)
        .where(JobLock.name == name, or_(JobLock.locked_until < now, JobLock.owner == owner))
        .values(owner=owner, locked_until=now + ttl)
    ).rowcount
    if taken:
        db.commit()
        return True
    # No row was updated: either the lock doesn't exist yet, or it's held by someone else.
    db.rollback()
    if db.get(JobLock, name) is not None:
        return False
    db.add(JobLock(name=name, owner=owner, locked_until=now + ttl))
    try:
        db.commit()
    except IntegrityError:  # another process created it at the same moment
        db.rollback()
        return False
    return True


def release(db: Session, name: str, owner: str | None = None) -> None:
    db.execute(
        update(JobLock)
        .where(JobLock.name == name, JobLock.owner == (owner or lock_owner()))
        # Clearly in the past, so the next acquire succeeds even if clocks differ slightly
        # between processes (or timestamps are stored with limited precision).
        .values(locked_until=datetime.now(UTC) - timedelta(minutes=1))
    )
    db.commit()
