"""Shared fixtures: in-memory SQLite session, registered engine, pipeline."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seamly import engine as engine_module
from seamly.app import register_all
from seamly.common.db import Base, make_engine
from seamly.modules import auth
from seamly.modules.ingest import handle_load
from seamly.modules.reconcile import handle_run

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERIC_FIXTURES = REPO_ROOT / "data" / "fixtures" / "generic"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = make_engine("sqlite+aiosqlite://")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def app_engine() -> engine_module.Engine:
    engine = engine_module.new_engine(actor="test", role="admin")
    register_all(engine)
    return engine


@pytest.fixture
async def loaded_session(session: AsyncSession) -> AsyncSession:
    """A session with the generic fixtures ingested and reconciled."""

    result = await handle_load(session, {"fixture_dir": str(GENERIC_FIXTURES)})
    assert not result.is_err, result.error.message if result.error else "unknown"
    run = await handle_run(session, {})
    assert not run.is_err, run.error.message if run.error else "unknown"
    await session.commit()
    return session


@pytest.fixture
async def logged_in_session(session: AsyncSession) -> AsyncSession:
    await auth.handle_bootstrap_demo_user(session, {})
    await session.commit()
    return session
