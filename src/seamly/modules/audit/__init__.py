"""Audit module: append-only log of every dispatched event."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.audit.models import AuditLog

PERMISSIONS: dict[str, set[str]] = {
    "audit.list": {"admin", "cfo"},
}


async def append(session: AsyncSession, actor: str, event: str, detail: str) -> None:
    """Insert-only by design. No update or delete path exists anywhere."""

    session.add(AuditLog(actor=actor, event=event, detail=detail))
