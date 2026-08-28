"""Exception module: the detect-to-recovery loop's system of record."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result
from seamly.modules.exception import repository as exception_repo
from seamly.modules.exception.models import (
    STATUS_ACCEPTED_RISK,
    STATUS_ASSIGNED,
    STATUS_RESOLVED,
)

PERMISSIONS: dict[str, set[str]] = {
    "exception.assign": {"ops", "analyst", "cfo", "admin"},
    "exception.resolve": {"ops", "analyst", "cfo", "admin"},
    "exception.accept_risk": {"cfo", "admin"},
}


async def handle_assign(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    record = await exception_repo.get_exception(session, int(payload["exception_id"]))
    if record is None:
        return Result.err(
            "exception.not_found", f"No exception with id {payload.get('exception_id')}."
        )
    owner = str(payload.get("owner", "")).strip()
    if not owner:
        return Result.err("exception.owner_required", "Provide the owner's name to assign.")
    record.owner = owner
    record.status = STATUS_ASSIGNED
    return Result.ok({"id": record.id, "owner": owner})


async def handle_resolve(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    record = await exception_repo.get_exception(session, int(payload["exception_id"]))
    if record is None:
        return Result.err(
            "exception.not_found", f"No exception with id {payload.get('exception_id')}."
        )
    amount = payload.get("amount_minor")
    if amount is None:
        return Result.err(
            "exception.recovery_amount_required",
            "Provide amount_minor: the pounds actually recovered or credited.",
        )
    evidence = str(payload.get("evidence", "")).strip()
    if not evidence:
        return Result.err(
            "exception.evidence_required",
            "Provide evidence: where the recovery is visible (credit note, payment, correction).",
        )
    recovered_on = payload.get("recovered_on")
    day = date.fromisoformat(recovered_on) if recovered_on else date.today()
    await exception_repo.add_recovery(session, record.id, int(amount), evidence, day)
    record.status = STATUS_RESOLVED
    return Result.ok({"id": record.id, "recovered_minor": int(amount)})


async def handle_accept_risk(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    record = await exception_repo.get_exception(session, int(payload["exception_id"]))
    if record is None:
        return Result.err(
            "exception.not_found", f"No exception with id {payload.get('exception_id')}."
        )
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        return Result.err("exception.reason_required", "Accepted risk needs a recorded reason.")
    record.status = STATUS_ACCEPTED_RISK
    record.owner = payload.get("owner", record.owner)
    return Result.ok({"id": record.id, "reason": reason})
