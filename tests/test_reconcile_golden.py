"""Golden test: the generic fixtures must produce exactly the planted leaks."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.exception import repository as exception_repo
from seamly.modules.ingest import handle_load
from seamly.modules.reconcile import handle_run
from tests.conftest import GENERIC_FIXTURES

# rule_id -> expected amount in pence, from the planted discrepancies
EXPECTED: dict[str, int] = {
    "R01": 10 * 41_250,  # O-1001 / D-5001: 10 brackets delivered, never invoiced
    "R02": 200 * 975,  # I-7005: billed, no delivery evidence (CE-1191)
    "R03": 4 * 41_250,  # I-7001 billed 100 vs D-5002's 96
    "R04": 60 * (29_500 - 26_500),  # I-7002 at 29500 vs contracted 26500
    "R05": 500 * 975,  # I-7004 duplicates I-7003 (PO-8817)
    "R06": 6 * 8_500,  # S-9001 installation, never invoiced
    "R07": 20_000,  # D-5003 late against BF-4410's promised date
}


async def test_pipeline_yields_exactly_the_planted_exceptions(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session)
    by_rule: dict[str, int] = {}
    for row in rows:
        by_rule.setdefault(row.rule_id, 0)
        by_rule[row.rule_id] += row.amount_minor
    assert by_rule == EXPECTED
    assert len(rows) == len(EXPECTED)
    total = sum(EXPECTED.values())
    assert total == 1_511_000
    assert await exception_repo.total_at_risk(loaded_session) == total


async def test_reruns_are_idempotent(session: AsyncSession):
    load = await handle_load(session, {"fixture_dir": str(GENERIC_FIXTURES)})
    assert not load.is_err
    first = await handle_run(session, {})
    assert not first.is_err
    assert first.value["new_exceptions"] == 7
    second = await handle_run(session, {})
    assert not second.is_err
    assert second.value["new_exceptions"] == 0
    rows = await exception_repo.all_exceptions(session)
    assert len(rows) == 7


async def test_clean_order_never_fires(loaded_session: AsyncSession):
    """O-1005 / D-5005 / I-7006 (BF-4433, 25 units at the contracted rate) is clean."""

    rows = await exception_repo.all_exceptions(loaded_session)
    for row in rows:
        assert "BF-4433" not in row.record_refs, f"clean order flagged: {row.formula}"


async def test_every_pound_shows_its_arithmetic(loaded_session: AsyncSession):
    rows = await exception_repo.all_exceptions(loaded_session)
    for row in rows:
        assert "GBP" in row.formula or row.rule_id == "R07"
        assert row.record_refs, "an exception without record refs cannot be trusted"
