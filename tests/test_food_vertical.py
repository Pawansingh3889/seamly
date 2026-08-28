"""Golden test: the food vertical pack adds F01-F03 on top of the general set."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.exception import repository as exception_repo
from seamly.modules.ingest import handle_load
from seamly.modules.reconcile import handle_run

REPO_ROOT = Path(__file__).resolve().parent.parent
FOOD_FIXTURES = REPO_ROOT / "data" / "fixtures" / "food"

FD220 = 26_500

# rule_id -> expected amount in pence
EXPECTED: dict[str, int] = {
    # general pack, unchanged by the food additions
    "R01": 10 * 41_250,
    "R02": 200 * 975,
    "R03": 4 * 41_250,
    "R04": 60 * (29_500 - 26_500),
    "R05": 500 * 975,
    "R06": 6 * 8_500,
    "R07": 20_000,
    # food pack
    "F01": 182 * FD220,  # B-2201 shipped 182 units after hold H-3301 (never released)
    "F02": (285 - 182) * FD220,  # 285 invoiced vs 182 produced
    "F03": 18 * FD220,  # M-4402 writeoff
}


async def test_food_pack_runs_the_vertical_rules(session: AsyncSession):
    load = await handle_load(session, {"fixture_dir": str(FOOD_FIXTURES)})
    assert not load.is_err, load.error_or_raise().message
    run = await handle_run(session, {})
    assert not run.is_err, run.error_or_raise().message

    rows = await exception_repo.all_exceptions(session)
    by_rule: dict[str, int] = {}
    for row in rows:
        by_rule.setdefault(row.rule_id, 0)
        by_rule[row.rule_id] += row.amount_minor
    assert by_rule == EXPECTED
    assert len(rows) == 10
    total = sum(EXPECTED.values())
    assert total == 9_540_500
    assert await exception_repo.total_at_risk(session) == total


async def test_food_pack_does_not_break_the_general_pack(session: AsyncSession):
    """Generic fixtures (no batch tables) produce exactly the 7 general leaks."""

    generic = REPO_ROOT / "data" / "fixtures" / "generic"
    load = await handle_load(session, {"fixture_dir": str(generic)})
    assert not load.is_err
    run = await handle_run(session, {})
    assert not run.is_err
    rows = await exception_repo.all_exceptions(session)
    assert {r.rule_id for r in rows} <= {"R01", "R02", "R03", "R04", "R05", "R06", "R07"}
    assert len(rows) == 7


async def test_food_additions_do_not_trip_general_rules(session: AsyncSession):
    """O-1006/D-5006/I-7007 (BF-4444) is clean on the general rules: the only
    exceptions touching that order ref come from the F-pack."""

    load = await handle_load(session, {"fixture_dir": str(FOOD_FIXTURES)})
    assert not load.is_err
    run = await handle_run(session, {})
    assert not run.is_err
    rows = await exception_repo.all_exceptions(session)
    for row in rows:
        if row.rule_id.startswith("R"):
            assert "BF-4444" not in row.record_refs, f"clean order flagged: {row.formula}"


async def test_food_reruns_are_idempotent(session: AsyncSession):
    await handle_load(session, {"fixture_dir": str(FOOD_FIXTURES)})
    first = await handle_run(session, {})
    assert first.value["new_exceptions"] == 10
    second = await handle_run(session, {})
    assert second.value["new_exceptions"] == 0
