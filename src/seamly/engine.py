"""In-process event bus: route, permit, audit, isolate."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result
from seamly.modules.audit import repository as audit_repo

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[Result[Any]]]
logger = logging.getLogger("seamly.engine")


@dataclass
class Registration:
    handler: Handler
    allowed_roles: set[str]


@dataclass
class Engine:
    actor: str = "anonymous"
    role: str = "anonymous"
    registrations: dict[str, Registration] = field(default_factory=dict)

    def register(self, event: str, handler: Handler, allowed_roles: set[str]) -> None:
        if event in self.registrations:
            raise ValueError(f"event already registered: {event}")
        self.registrations[event] = Registration(handler=handler, allowed_roles=allowed_roles)

    async def dispatch(
        self, session: AsyncSession, event: str, payload: dict[str, Any] | None = None
    ) -> Result[Any]:
        payload = payload or {}
        registration = self.registrations.get(event)
        if registration is None:
            return Result.err("engine.unknown_event", f"No handler registered for {event!r}.")
        if self.role not in registration.allowed_roles:
            return Result.err(
                "engine.forbidden",
                f"Role {self.role!r} may not run {event!r}. "
                f"Allowed: {sorted(registration.allowed_roles)}.",
            )
        try:
            result = await registration.handler(session, payload)
        except Exception as exc:
            logger.exception("handler failed for %s", event)
            await session.rollback()
            return Result.err(
                "engine.handler_crash",
                f"{event} failed unexpectedly and was isolated: {exc}",
            )
        if result.is_err:
            await session.rollback()
            return result
        await audit_repo.append(session, actor=self.actor, event=event, detail="")
        await session.commit()
        return result


def new_engine(actor: str, role: str) -> Engine:
    return Engine(actor=actor, role=role)
