"""MySQL async engine and session management."""

from __future__ import annotations

from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import settings
from core.exceptions import DBConfigError, ServiceError


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""


engine: Optional[AsyncEngine] = None
session_factory: Optional[async_sessionmaker[AsyncSession]] = None


async def connect_to_mysql() -> None:
    """Initialise the global async engine and session factory."""

    global engine, session_factory

    if not settings.MYSQL_ASYNC_URL:
        raise DBConfigError(detail="MYSQL connection string is not configured.")

    try:
        engine = create_async_engine(
            settings.MYSQL_ASYNC_URL,
            pool_pre_ping=True,
            echo=False,
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        # Import models to register metadata before creating tables
        from infrastructure.models import user as user_models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("--- MySQL Connected ---")
    except Exception as exc:  # pragma: no cover - connection errors propagated
        raise ServiceError(
            status_code=500,
            code="MYSQL_CONNECTION_ERROR",
            message="Failed to initialise MySQL engine.",
            detail=str(exc),
        ) from exc


async def close_mysql_connection() -> None:
    """Dispose of the async engine during application shutdown."""

    global engine
    if engine is not None:
        await engine.dispose()
        engine = None
        print("--- MySQL Disconnected ---")


async def get_mysql_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession for dependency injection layers."""

    if session_factory is None:
        raise ServiceError(
            status_code=500,
            code="MYSQL_SESSION_UNINITIALISED",
            message="MySQL session factory has not been initialised.",
        )

    async with session_factory() as session:
        yield session
