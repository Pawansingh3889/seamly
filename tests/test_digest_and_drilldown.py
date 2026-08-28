"""Drill-down and digest: the management view over the exception store."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules import exception as exception_module
from seamly.modules.exception import repository as exception_repo
from seamly.modules.exception.digest import build_digest
from seamly.modules.exception.repository import DigestInputs


async def test_at_risk_by_customer_ranks_and_names(loaded_session: AsyncSession):
    rows = await exception_repo.at_risk_by_customer(loaded_session)
    amounts = {r.customer_name: r.amount_minor for r in rows}
    assert amounts["Calder Engineering Ltd"] == 682_500  # R05 487,500 + R02 195,000
    assert amounts["Acme Industrial Supplies Ltd"] == 412_500 + 165_000 + 51_000
    assert amounts["Brightwater Foods Ltd"] == 180_000 + 20_000
    assert [r.customer_name for r in rows] == [
        "Calder Engineering Ltd",
        "Acme Industrial Supplies Ltd",
        "Brightwater Foods Ltd",
    ]


async def test_customer_filter_scopes_exceptions(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session, customer_id=1)
    assert rows
    assert all(r.customer_id == 1 for r in rows)
    assert any(r.rule_id == "R01" for r in rows)


async def test_owner_filter_finds_assigned_work(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session)
    await exception_module.handle_assign(
        loaded_session, {"exception_id": rows[0].id, "owner": "R. Poon"}
    )
    found = await exception_repo.all_exceptions(loaded_session, owner="R. Poon")
    assert [r.id for r in found] == [rows[0].id]


def _inputs(week_start: date) -> DigestInputs:
    return DigestInputs(
        week_start=week_start,
        open_items=[],
        raised_this_week=[],
        resolved_this_week=[],
        accepted_risk_items=[],
        recovered_this_week_minor=0,
    )


def test_digest_is_quiet_when_nothing_is_open():
    digest = build_digest(_inputs(date(2026, 8, 24)))
    assert digest.at_risk_minor == 0
    assert digest.sections[-1].lines == ["None. The seams are quiet."]


def test_digest_recommends_deterministic_actions_per_rule():
    monday = date(2026, 8, 24)
    session_stub = _inputs(monday)
    session_stub.open_items = _digest_stub_records()
    digest = build_digest(session_stub)
    actions = next(s for s in digest.sections if s.heading == "Recommended actions")
    joined = "\n".join(actions.lines)
    assert "R01: Raise the missing invoice" in joined
    assert "R07: Issue the late-delivery credit" in joined
    assert digest.at_risk_minor == 432_500
    assert digest.open_count == 2


def _digest_stub_records():
    """Minimal stand-ins with only the attributes the digest builder reads."""

    from types import SimpleNamespace

    return [
        SimpleNamespace(
            id=1,
            rule_id="R01",
            amount_minor=412_500,
            status="open",
            owner=None,
            formula="10 units x GBP 412.50",
            created_at=None,
            resolved_at=None,
        ),
        SimpleNamespace(
            id=2,
            rule_id="R07",
            amount_minor=20_000,
            status="assigned",
            owner="R. Poon",
            formula="late delivery penalty clause",
            created_at=None,
            resolved_at=None,
        ),
    ]


async def test_digest_handler_reports_week(loaded_session: AsyncSession):
    result = await exception_module.handle_digest(loaded_session, {})
    assert not result.is_err
    data = result.value
    assert data["at_risk_minor"] == 1_511_000
    assert data["open_count"] == 7
    headings = [s["heading"] for s in data["sections"]]
    assert "Where the money sits (top open exceptions)" in headings
    assert "Recommended actions" in headings


async def test_digest_handler_rejects_a_bad_week_start(loaded_session: AsyncSession):
    result = await exception_module.handle_digest(loaded_session, {"week_start": "not-a-date"})
    assert result.is_err
    assert result.error_or_raise().code == "exception.bad_week_start"


async def test_digest_handler_honours_week_start(loaded_session: AsyncSession):
    future = date.today() + timedelta(days=14)
    result = await exception_module.handle_digest(
        loaded_session, {"week_start": future.isoformat()}
    )
    assert not result.is_err
    data = result.value
    assert data["week_start"] == future.isoformat()
    assert data["open_count"] == 7  # nothing resolved, so everything is still open
