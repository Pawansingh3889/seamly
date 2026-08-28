"""Audit repository. Intentionally insert and read only."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.audit.models import AuditLog


async def append(session: AsyncSession, actor: str, event: str, detail: str) -> None:
    session.add(AuditLog(actor=actor, event=event, detail=detail))


async def recent(session: AsyncSession, limit: int = 50) -> list[AuditLog]:
    rows = await session.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
    return list(rows.scalars())
