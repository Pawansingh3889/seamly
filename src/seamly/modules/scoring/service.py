"""Pound-impact scoring: every finding priced from the price book. Pure."""

from __future__ import annotations

from dataclasses import dataclass

from seamly.modules.reconcile.contract import Finding, PriceRow
from seamly.modules.reconcile.service import (
    RULE_DELIVERED_NOT_INVOICED,
    RULE_DUPLICATE_INVOICE,
    RULE_INVOICED_NOT_DELIVERED,
    RULE_LATE_DELIVERY_CREDIT,
    RULE_QUANTITY_MISMATCH,
    RULE_RATE_MISMATCH,
    RULE_SERVICE_NOT_INVOICED,
)

REASONS = {
    RULE_DELIVERED_NOT_INVOICED: "delivered but never invoiced",
    RULE_INVOICED_NOT_DELIVERED: "invoiced with no delivery evidence",
    RULE_QUANTITY_MISMATCH: "billed beyond what was delivered",
    RULE_RATE_MISMATCH: "invoiced at the wrong contracted rate",
    RULE_DUPLICATE_INVOICE: "duplicate invoice",
    RULE_SERVICE_NOT_INVOICED: "service completed but never invoiced",
    RULE_LATE_DELIVERY_CREDIT: "late delivery credit owed to the customer",
}


@dataclass
class PricedException:
    rule_id: str
    customer_id: int
    contract_code: str
    sku: str
    quantity: int
    amount_minor: int
    currency: str
    formula: str
    refs: list[str]


def _gbp(minor: int) -> str:
    return f"GBP {minor / 100:,.2f}"


def price_finding(
    finding: Finding,
    prices: dict[tuple[str, str], PriceRow],
    penalties: dict[str, int],
    customer_contract: dict[int, str],
) -> PricedException | None:
    """Turn a structural finding into a priced exception.

    prices maps (contract code, sku) to the contracted unit price.
    penalties maps contract code to the late-delivery penalty amount.
    customer_contract maps customer id to their contract code, used when a
    rule does not know the contract (delivery- and service-side findings).
    Returns None when a finding cannot be priced from known data; unpriced
    findings are never shown as pounds.
    """

    contract = finding.contract_code or customer_contract.get(finding.customer_id, "")
    reason = REASONS[finding.rule_id]

    if finding.rule_id == RULE_LATE_DELIVERY_CREDIT:
        amount = penalties.get(contract, 0)
        if amount <= 0:
            return None
        return PricedException(
            rule_id=finding.rule_id,
            customer_id=finding.customer_id,
            contract_code=contract,
            sku="",
            quantity=0,
            amount_minor=amount,
            currency="GBP",
            formula=f"late delivery penalty clause ({contract}) = {_gbp(amount)}: {reason}",
            refs=finding.refs,
        )

    price_row = prices.get((contract, finding.sku))
    if price_row is None:
        return None

    if finding.rule_id == RULE_RATE_MISMATCH:
        amount = finding.quantity * (finding.invoiced_price_minor - finding.unit_price_minor)
        formula = (
            f"{finding.quantity} units x ({_gbp(finding.invoiced_price_minor)} invoiced "
            f"vs {_gbp(finding.unit_price_minor)} contracted) = {_gbp(amount)} "
            f"({contract}, {finding.sku}): {reason}"
        )
    else:
        unit = finding.unit_price_minor or price_row.unit_price_minor
        amount = finding.quantity * unit
        formula = (
            f"{finding.quantity} units x {_gbp(unit)} = {_gbp(amount)} "
            f"({contract}, {finding.sku}): {reason}"
        )

    return PricedException(
        rule_id=finding.rule_id,
        customer_id=finding.customer_id,
        contract_code=contract,
        sku=finding.sku,
        quantity=finding.quantity,
        amount_minor=amount,
        currency="GBP",
        formula=formula,
        refs=finding.refs,
    )


def price_findings(
    findings: list[Finding],
    prices: dict[tuple[str, str], PriceRow],
    penalties: dict[str, int],
    customer_contract: dict[int, str],
) -> list[PricedException]:
    priced = []
    for finding in findings:
        result = price_finding(finding, prices, penalties, customer_contract)
        if result is not None:
            priced.append(result)
    return priced
