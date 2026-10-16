from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Neon suspends idle databases after 5 minutes, closing their connections. Recycling
# pooled connections after 4 minutes avoids reusing a dead one, without the extra
# round trip per request that pool_pre_ping would add.
engine = create_engine(settings.database_url, pool_recycle=240)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
