"""Reconcile module: runs the rule pack and prices what it finds."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result
from seamly.modules.exception import repository as exception_repo
from seamly.modules.reconcile import repository as reconcile_repo
from seamly.modules.reconcile import service as rules
from seamly.modules.reconcile.contract import Finding
from seamly.modules.scoring import service as scoring

PERMISSIONS: dict[str, set[str]] = {
    "reconcile.run": {"ops", "analyst", "cfo", "admin"},
}


async def handle_run(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    (
        invoice_lines,
        delivery_lines,
        service_events,
        promises,
        contracts,
        prices,
        penalties,
        customer_contract,
    ) = await reconcile_repo.load_rows(session)

    excluded = rules.detect_duplicates(invoice_lines, contracts)

    findings: list[Finding] = []
    findings += rules.delivered_not_invoiced(invoice_lines, delivery_lines, excluded)
    findings += rules.invoiced_not_delivered(invoice_lines, delivery_lines, excluded)
    findings += rules.quantity_mismatch(invoice_lines, delivery_lines, excluded)
    findings += rules.rate_mismatch(invoice_lines, delivery_lines, prices, excluded)
    findings += rules.duplicate_invoices(invoice_lines, excluded)
    findings += rules.service_not_invoiced(invoice_lines, service_events)
    findings += rules.late_delivery_credit(delivery_lines, promises, contracts)

    priced = scoring.price_findings(findings, prices, penalties, customer_contract)

    created = 0
    for exception in priced:
        if await exception_repo.upsert_priced(session, exception):
            created += 1

    return Result.ok(
        {
            "findings": len(findings),
            "priced": len(priced),
            "new_exceptions": created,
        }
    )
