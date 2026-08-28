"""Food vertical rule pack. Pure functions, additive to the general R01-R07.

Operationalised definitions (docs/domain/food/vertical.md):

- F01 rejected_batch_billed: a quality hold that was never released, where
  stock from that batch moved out (shipped) on or after the hold date.
  Price: shipped units x contracted unit price.
- F02 yield_shortfall_unbilled: a batch whose yield fell short of plan,
  where invoiced units of that sku for that customer (from the batch's
  production date onward) exceed what was actually produced. Priced as an
  exposure: the excess units x contracted unit price.
- F03 shelf_life_writeoff: stock written off. Price: written-off units x
  contracted unit price. Open-demand checking is a refinement, not a gate.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from seamly.modules.reconcile.contract import Finding, PriceRow

RULE_REJECTED_BATCH_BILLED = "F01"
RULE_YIELD_SHORTFALL_UNBILLED = "F02"
RULE_SHELF_LIFE_WRITEOFF = "F03"


def rejected_batch_billed(
    holds: list[dict[str, Any]],
    movements: list[dict[str, Any]],
    prices: dict[tuple[str, str], PriceRow],
    customer_contract: dict[int, str],
) -> list[Finding]:
    findings: list[Finding] = []
    batches_on_hold = {h["batch_code"]: h for h in holds if not h["released"]}
    for movement in movements:
        batch_code = movement["batch_code"]
        hold = batches_on_hold.get(batch_code)
        if hold is None or movement["direction"] != "out":
            continue
        if movement["movement_date"] < hold["hold_date"]:
            continue
        customer_id = movement["customer_id"]
        contract = customer_contract.get(customer_id, "")
        if (contract, movement["sku"]) not in prices:
            continue
        findings.append(
            Finding(
                rule_id=RULE_REJECTED_BATCH_BILLED,
                customer_id=customer_id,
                contract_code=contract,
                refs=[
                    hold["code"],
                    batch_code,
                    movement["code"],
                    movement["movement_date"].isoformat(),
                ],
                sku=movement["sku"],
                quantity=movement["quantity"],
            )
        )
    return findings


def yield_shortfall_unbilled(
    batches: list[dict[str, Any]],
    invoice_lines: list[Any],
    prices: dict[tuple[str, str], PriceRow],
    customer_contract: dict[int, str],
) -> list[Finding]:
    findings: list[Finding] = []
    invoiced: dict[tuple[int, str], int] = defaultdict(int)
    for line in invoice_lines:
        invoiced[(line.customer_id, line.sku)] += line.quantity
    for batch in batches:
        if batch["actual_units"] >= batch["planned_units"]:
            continue
        contract = customer_contract.get(batch["customer_id"], "")
        if (contract, batch["sku"]) not in prices:
            continue
        produced = batch["actual_units"]
        billed = invoiced.get((batch["customer_id"], batch["sku"]), 0)
        if billed <= produced:
            continue
        findings.append(
            Finding(
                rule_id=RULE_YIELD_SHORTFALL_UNBILLED,
                customer_id=batch["customer_id"],
                contract_code=contract,
                refs=[
                    batch["code"],
                    batch["production_date"].isoformat(),
                    f"produced {produced}",
                    f"invoiced {billed}",
                ],
                sku=batch["sku"],
                quantity=billed - produced,
            )
        )
    return findings


def shelf_life_writeoff(
    movements: list[dict[str, Any]],
    prices: dict[tuple[str, str], PriceRow],
    customer_contract: dict[int, str],
) -> list[Finding]:
    findings: list[Finding] = []
    for movement in movements:
        if movement["direction"] != "writeoff":
            continue
        contract = customer_contract.get(movement["customer_id"], "")
        if (contract, movement["sku"]) not in prices:
            continue
        findings.append(
            Finding(
                rule_id=RULE_SHELF_LIFE_WRITEOFF,
                customer_id=movement["customer_id"],
                contract_code=contract,
                refs=[
                    movement["batch_code"],
                    movement["code"],
                    movement["movement_date"].isoformat(),
                ],
                sku=movement["sku"],
                quantity=movement["quantity"],
            )
        )
    return findings
