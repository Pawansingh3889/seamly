"""The loop: assign, resolve with recovery, accept risk, summary totals."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules import exception as exception_module
from seamly.modules.exception import repository as exception_repo


async def test_assign_requires_owner(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session)
    result = await exception_module.handle_assign(
        loaded_session, {"exception_id": rows[0].id, "owner": "  "}
    )
    assert result.is_err
    assert result.error.code == "exception.owner_required"


async def test_assign_then_resolve_records_recovery(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session)
    target = rows[0]
    assigned = await exception_module.handle_assign(
        loaded_session, {"exception_id": target.id, "owner": "R. Poon"}
    )
    assert not assigned.is_err

    missing_amount = await exception_module.handle_resolve(
        loaded_session, {"exception_id": target.id, "evidence": "credit note CN-77"}
    )
    assert missing_amount.is_err
    assert missing_amount.error.code == "exception.recovery_amount_required"

    missing_evidence = await exception_module.handle_resolve(
        loaded_session, {"exception_id": target.id, "amount_minor": 1000, "evidence": ""}
    )
    assert missing_evidence.is_err

    resolved = await exception_module.handle_resolve(
        loaded_session,
        {
            "exception_id": target.id,
            "amount_minor": 41_250,
            "evidence": "credit note CN-77",
            "recovered_on": "2026-08-20",
        },
    )
    assert not resolved.is_err
    entries = await exception_repo.recoveries_for(loaded_session, target.id)
    assert len(entries) == 1
    assert entries[0].amount_minor == 41_250
    assert entries[0].recovered_on == date(2026, 8, 20)
    assert await exception_repo.total_recovered(loaded_session) == 41_250


async def test_accept_risk_requires_a_reason(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session)
    refused = await exception_module.handle_accept_risk(
        loaded_session, {"exception_id": rows[0].id, "reason": ""}
    )
    assert refused.is_err
    accepted = await exception_module.handle_accept_risk(
        loaded_session, {"exception_id": rows[0].id, "reason": "customer goodwill, absorbed"}
    )
    assert not accepted.is_err


async def test_resolved_exceptions_leave_the_at_risk_total(loaded_session: AsyncSession):
    before = await exception_repo.total_at_risk(loaded_session)
    rows = await exception_repo.all_exceptions(loaded_session)
    target = rows[0]
    await exception_module.handle_resolve(
        loaded_session,
        {
            "exception_id": target.id,
            "amount_minor": target.amount_minor,
            "evidence": "paid in full",
        },
    )
    after = await exception_repo.total_at_risk(loaded_session)
    assert after == before - target.amount_minor
