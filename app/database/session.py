"""SQLAlchemy engine and request-scoped sessions.

Imports: app/api/dependencies.py (get_db), app/main.py (get_async_session)
Exports: get_engine(), get_async_engine(), get_db(), get_async_session()
User instruction: complete all phases in plan.md
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

@lru_cache
def get_engine():
    """Create the configured engine on first database use, not at app import."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
    )


@lru_cache
def get_async_engine():
    """Create async engine for health checks and async operations."""
    settings = get_settings()
    async_url = settings.database_url.replace("postgresql+psycopg", "postgresql+asyncpg")
    if "sqlite" in async_url:
        async_url = settings.database_url.replace("sqlite://", "sqlite+aiosqlite://")
    return create_async_engine(
        async_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
    )


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


async def get_async_session() -> Generator[AsyncSession, None, None]:
    """Yield an async session for async operations."""
    async_session = async_sessionmaker(
        bind=get_async_engine(), class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
