"""Engine behaviour: routing, permission, audit, crash isolation."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly import engine as engine_module
from seamly.common.types import Result
from seamly.modules.audit.models import AuditLog


async def test_unknown_event_returns_actionable_error(session: AsyncSession):
    engine = engine_module.new_engine(actor="t", role="admin")
    result = await engine.dispatch(session, "nothing.here", {})
    assert result.is_err
    assert result.error.code == "engine.unknown_event"
    assert "nothing.here" in result.error.message


async def test_forbidden_role_is_rejected(session: AsyncSession):
    engine = engine_module.new_engine(actor="t", role="ops")

    async def admin_only(s: AsyncSession, p: dict[str, Any]) -> Result:
        return Result.ok()

    engine.register("thing.do", admin_only, {"admin"})
    result = await engine.dispatch(session, "thing.do", {})
    assert result.is_err
    assert result.error.code == "engine.forbidden"
    assert "ops" in result.error.message


async def test_crashing_handler_is_isolated(session: AsyncSession):
    engine = engine_module.new_engine(actor="t", role="admin")

    async def explodes(s: AsyncSession, p: dict[str, Any]) -> Result:
        raise RuntimeError("boom")

    async def healthy(s: AsyncSession, p: dict[str, Any]) -> Result:
        return Result.ok({"fine": True})

    engine.register("thing.explode", explodes, {"admin"})
    engine.register("thing.healthy", healthy, {"admin"})

    crash = await engine.dispatch(session, "thing.explode", {})
    assert crash.is_err
    assert crash.error.code == "engine.handler_crash"
    assert "boom" in crash.error.message

    fine = await engine.dispatch(session, "thing.healthy", {})
    assert not fine.is_err


async def test_success_appends_audit_row(session: AsyncSession):
    engine = engine_module.new_engine(actor="tester@example", role="admin")

    async def ok(s: AsyncSession, p: dict[str, Any]) -> Result:
        return Result.ok()

    engine.register("thing.ok", ok, {"admin"})
    result = await engine.dispatch(session, "thing.ok", {})
    assert not result.is_err
    rows = (await session.execute(select(AuditLog))).scalars().all()
    assert any(r.event == "thing.ok" and r.actor == "tester@example" for r in rows)
