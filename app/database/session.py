"""SQLAlchemy engine and request-scoped sessions."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

@lru_cache
def get_engine():
    """Create the configured engine on first database use, not at app import."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_db() -> Generator[Session, None, None]:
    """Yield a session and roll back any uncommitted request work on errors."""
    session = sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False
    )()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
