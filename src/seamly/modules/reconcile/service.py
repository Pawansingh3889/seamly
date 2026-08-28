"""Reconciliation rules, pure functions over typed rows. No I/O.

Rule precedence: duplicates (R05) are detected first; the later invoice of a
duplicate pair is excluded from R01-R04 matching so one leak is not reported
twice. See docs/domain/general/order-to-cash.md.
"""

from __future__ import annotations

from collections import defaultdict

from seamly.modules.reconcile.contract import (
    ContractRow,
    DeliveryLineRow,
    Finding,
    InvoiceLineRow,
    OrderPromiseRow,
    PriceRow,
    ServiceEventRow,
)

RULE_DELIVERED_NOT_INVOICED = "R01"
RULE_INVOICED_NOT_DELIVERED = "R02"
RULE_QUANTITY_MISMATCH = "R03"
RULE_RATE_MISMATCH = "R04"
RULE_DUPLICATE_INVOICE = "R05"
RULE_SERVICE_NOT_INVOICED = "R06"
RULE_LATE_DELIVERY_CREDIT = "R07"

GroupKey = tuple[int, str, str]


def _key(customer_id: int, order_ref: str, sku: str) -> GroupKey:
    return (customer_id, order_ref, sku)


def _delivered_totals(delivery_lines: list[DeliveryLineRow]) -> dict[GroupKey, int]:
    totals: dict[GroupKey, int] = defaultdict(int)
    for dline in delivery_lines:
        totals[_key(dline.customer_id, dline.order_ref, dline.sku)] += dline.quantity
    return totals


def _invoiced_totals(
    invoice_lines: list[InvoiceLineRow], excluded_invoices: set[str]
) -> dict[GroupKey, int]:
    totals: dict[GroupKey, int] = defaultdict(int)
    for iline in invoice_lines:
        if iline.invoice_code not in excluded_invoices:
            totals[_key(iline.customer_id, iline.order_ref, iline.sku)] += iline.quantity
    return totals


def detect_duplicates(
    invoice_lines: list[InvoiceLineRow], contracts: dict[int, ContractRow]
) -> set[str]:
    """Return invoice codes that duplicate an earlier invoice."""

    flagged: set[str] = set()
    by_ref: dict[tuple[int, str], list[InvoiceLineRow]] = defaultdict(list)
    for iline in invoice_lines:
        by_ref[(iline.customer_id, iline.external_ref)].append(iline)
    for lines in by_ref.values():
        if len(lines) < 2:
            continue
        by_invoice: dict[str, list[InvoiceLineRow]] = defaultdict(list)
        for iline in lines:
            by_invoice[iline.invoice_code].append(iline)
        codes = sorted(by_invoice)
        window_days = contracts.get(lines[0].customer_id)
        limit = window_days.duplicate_window_days if window_days else 14
        for later_index, later_code in enumerate(codes[1:], start=1):
            later_date = by_invoice[later_code][0].invoice_date
            for earlier_code in codes[:later_index]:
                earlier_date = by_invoice[earlier_code][0].invoice_date
                if abs((later_date - earlier_date).days) > limit:
                    continue
                earlier_sigs = {
                    (ln.sku, ln.quantity, ln.unit_price_minor) for ln in by_invoice[earlier_code]
                }
                later_sigs = {
                    (ln.sku, ln.quantity, ln.unit_price_minor) for ln in by_invoice[later_code]
                }
                if earlier_sigs & later_sigs:
                    flagged.add(later_code)
                    break
    return flagged


def delivered_not_invoiced(
    invoice_lines: list[InvoiceLineRow],
    delivery_lines: list[DeliveryLineRow],
    excluded_invoices: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    invoiced = _invoiced_totals(invoice_lines, excluded_invoices)
    delivered_rows: dict[GroupKey, list[DeliveryLineRow]] = defaultdict(list)
    for dline in delivery_lines:
        delivered_rows[_key(dline.customer_id, dline.order_ref, dline.sku)].append(dline)
    for group_key, rows in delivered_rows.items():
        total = sum(row.quantity for row in rows)
        if total > 0 and invoiced.get(group_key, 0) == 0:
            findings.append(
                Finding(
                    rule_id=RULE_DELIVERED_NOT_INVOICED,
                    customer_id=group_key[0],
                    contract_code="",
                    refs=[r.order_ref for r in rows] + [r.delivery_date.isoformat() for r in rows],
                    sku=group_key[2],
                    quantity=total,
                )
            )
    return findings


def invoiced_not_delivered(
    invoice_lines: list[InvoiceLineRow],
    delivery_lines: list[DeliveryLineRow],
    excluded_invoices: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    delivered = _delivered_totals(delivery_lines)
    for iline in invoice_lines:
        if iline.invoice_code in excluded_invoices:
            continue
        if delivered.get(_key(iline.customer_id, iline.order_ref, iline.sku), 0) == 0:
            findings.append(
                Finding(
                    rule_id=RULE_INVOICED_NOT_DELIVERED,
                    customer_id=iline.customer_id,
                    contract_code=iline.contract_code,
                    refs=[iline.invoice_code, iline.order_ref, iline.sku],
                    sku=iline.sku,
                    quantity=iline.quantity,
                    unit_price_minor=iline.unit_price_minor,
                )
            )
    return findings


def quantity_mismatch(
    invoice_lines: list[InvoiceLineRow],
    delivery_lines: list[DeliveryLineRow],
    excluded_invoices: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    delivered = _delivered_totals(delivery_lines)
    invoiced = _invoiced_totals(invoice_lines, excluded_invoices)
    for group_key in sorted(invoiced):
        billed = invoiced[group_key]
        shipped = delivered.get(group_key, 0)
        if 0 < shipped < billed:
            sample = next(
                iline
                for iline in invoice_lines
                if _key(iline.customer_id, iline.order_ref, iline.sku) == group_key
            )
            findings.append(
                Finding(
                    rule_id=RULE_QUANTITY_MISMATCH,
                    customer_id=group_key[0],
                    contract_code=sample.contract_code,
                    refs=[sample.invoice_code, sample.order_ref, sample.sku],
                    sku=sample.sku,
                    quantity=billed - shipped,
                    unit_price_minor=sample.unit_price_minor,
                )
            )
    return findings


def rate_mismatch(
    invoice_lines: list[InvoiceLineRow],
    delivery_lines: list[DeliveryLineRow],
    prices: dict[tuple[str, str], PriceRow],
    excluded_invoices: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    delivered = _delivered_totals(delivery_lines)
    for iline in invoice_lines:
        if iline.invoice_code in excluded_invoices:
            continue
        if delivered.get(_key(iline.customer_id, iline.order_ref, iline.sku), 0) == 0:
            continue
        contracted = prices.get((iline.contract_code, iline.sku))
        if contracted is None:
            continue
        if iline.unit_price_minor != contracted.unit_price_minor:
            findings.append(
                Finding(
                    rule_id=RULE_RATE_MISMATCH,
                    customer_id=iline.customer_id,
                    contract_code=iline.contract_code,
                    refs=[iline.invoice_code, iline.order_ref, iline.sku],
                    sku=iline.sku,
                    quantity=iline.quantity,
                    unit_price_minor=contracted.unit_price_minor,
                    invoiced_price_minor=iline.unit_price_minor,
                )
            )
    return findings


def duplicate_invoices(
    invoice_lines: list[InvoiceLineRow], excluded_invoices: set[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for iline in invoice_lines:
        if iline.invoice_code in excluded_invoices:
            findings.append(
                Finding(
                    rule_id=RULE_DUPLICATE_INVOICE,
                    customer_id=iline.customer_id,
                    contract_code=iline.contract_code,
                    refs=[iline.invoice_code, iline.external_ref, iline.sku],
                    sku=iline.sku,
                    quantity=iline.quantity,
                    unit_price_minor=iline.unit_price_minor,
                )
            )
    return findings


def service_not_invoiced(
    invoice_lines: list[InvoiceLineRow], service_events: list[ServiceEventRow]
) -> list[Finding]:
    findings: list[Finding] = []
    invoiced_units: dict[tuple[int, str], int] = defaultdict(int)
    for iline in invoice_lines:
        invoiced_units[(iline.customer_id, iline.sku)] += iline.quantity
    for event in service_events:
        covered = invoiced_units.get((event.customer_id, event.service_code), 0)
        if event.units > covered:
            findings.append(
                Finding(
                    rule_id=RULE_SERVICE_NOT_INVOICED,
                    customer_id=event.customer_id,
                    contract_code="",
                    refs=[event.code, event.service_code, event.event_date.isoformat()],
                    sku=event.service_code,
                    quantity=event.units - covered,
                )
            )
    return findings


def late_delivery_credit(
    delivery_lines: list[DeliveryLineRow],
    promises: dict[tuple[int, str], OrderPromiseRow],
    contracts: dict[int, ContractRow],
) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    for dline in delivery_lines:
        promise = promises.get((dline.customer_id, dline.order_ref))
        if promise is None or dline.delivery_date <= promise.promised_date:
            continue
        contract = contracts.get(dline.customer_id)
        if contract is None or contract.late_delivery_penalty_minor <= 0:
            continue
        if (dline.customer_id, dline.order_ref) in seen:
            continue
        seen.add((dline.customer_id, dline.order_ref))
        findings.append(
            Finding(
                rule_id=RULE_LATE_DELIVERY_CREDIT,
                customer_id=dline.customer_id,
                contract_code=contract.code,
                refs=[dline.order_ref, dline.delivery_date.isoformat(), "penalty clause"],
            )
        )
    return findings
