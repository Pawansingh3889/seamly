"""Database plumbing: shared declarative base, engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from seamly.common.types import SeamlyError


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> AsyncEngine:
    if not database_url:
        raise SeamlyError(
            "config.no_database_url",
            "No database configured. Set SEAMLY_DATABASE_URL, for example "
            "postgresql+asyncpg://user:pass@host:5432/db?ssl=require",
        )
    if database_url.startswith("postgresql+asyncpg://") or database_url.startswith(
        "sqlite+aiosqlite://"
    ):
        return create_async_engine(database_url, echo=False)
    raise SeamlyError(
        "config.bad_database_url",
        f"Unsupported database URL scheme: {database_url.split('://', 1)[0]}. "
        "Use postgresql+asyncpg:// or sqlite+aiosqlite://",
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
