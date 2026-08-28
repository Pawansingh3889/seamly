"""Ingest service: pure parsing, validation and identity resolution."""

from __future__ import annotations

import csv
import re
import uuid
from datetime import date
from io import StringIO

from seamly.common.types import Result
from seamly.modules.ingest.contract import (
    BatchCsv,
    ContractCsv,
    CustomerCsv,
    DeliveryCsv,
    DeliveryLineCsv,
    InvoiceCsv,
    InvoiceLineCsv,
    OrderCsv,
    OrderLineCsv,
    PriceBookCsv,
    QualityHoldCsv,
    ServiceEventCsv,
    SourceBundle,
    StockMovementCsv,
)

LEGAL_SUFFIXES = ("limited", "ltd", "co", "company", "plc", "inc", "llp", "uk")
_PUNCT = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")

REQUIRED_FILES = (
    "customers.csv",
    "contracts.csv",
    "price_book.csv",
    "orders.csv",
    "order_lines.csv",
    "deliveries.csv",
    "delivery_lines.csv",
    "invoices.csv",
    "invoice_lines.csv",
    "service_events.csv",
)

# Vertical packs add these on top of the general set; absence is normal.
OPTIONAL_FILES = ("batches.csv", "quality_holds.csv", "stock_movements.csv")


def normalise_name(raw: str) -> str:
    """Resolve source identity variants: punctuation, spacing, legal suffixes."""

    cleaned = raw.strip().lower().replace("&", " and ")
    cleaned = _SPACES.sub(" ", _PUNCT.sub(" ", cleaned)).strip()
    words = cleaned.split(" ")
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)


def parse_date(raw: str, context: str) -> Result[date]:
    try:
        return Result.ok(date.fromisoformat(raw))
    except ValueError:
        return Result.err("ingest.bad_date", f"{context}: {raw!r} is not an ISO date (YYYY-MM-DD).")


def parse_int(raw: str, context: str) -> Result[int]:
    try:
        value = int(raw)
    except ValueError:
        return Result.err("ingest.bad_int", f"{context}: {raw!r} is not a whole number.")
    if value < 0:
        return Result.err("ingest.negative_int", f"{context}: {raw!r} must not be negative.")
    return Result.ok(value)


def read_csv(name: str, text: str) -> Result[list[dict[str, str]]]:
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return Result.err("ingest.empty_csv", f"{name}: file has no header row.")
    return Result.ok(list(reader))


def validate_bundle(rows: dict[str, list[dict[str, str]]]) -> Result[SourceBundle]:
    for name in REQUIRED_FILES:
        if name not in rows:
            return Result.err("ingest.missing_file", f"Source bundle is missing {name}.")
    for name in OPTIONAL_FILES:
        rows.setdefault(name, [])
    try:
        bundle = SourceBundle(
            customers=[CustomerCsv(**r) for r in rows["customers.csv"]],
            contracts=[
                ContractCsv(
                    contract_id=r["contract_id"],
                    customer_id=r["customer_id"],
                    invoice_window_days=int(r["invoice_window_days"]),
                    duplicate_window_days=int(r["duplicate_window_days"]),
                    late_delivery_penalty_minor=int(r["late_delivery_penalty_minor"]),
                )
                for r in rows["contracts.csv"]
            ],
            price_book=[
                PriceBookCsv(
                    contract_id=r["contract_id"],
                    sku=r["sku"],
                    kind=r["kind"],
                    unit_price_minor=int(r["unit_price_minor"]),
                )
                for r in rows["price_book.csv"]
            ],
            orders=[OrderCsv(**r) for r in rows["orders.csv"]],
            order_lines=[
                OrderLineCsv(
                    order_id=r["order_id"],
                    sku=r["sku"],
                    quantity=int(r["quantity"]),
                    unit_price_minor=int(r["unit_price_minor"]),
                )
                for r in rows["order_lines.csv"]
            ],
            deliveries=[DeliveryCsv(**r) for r in rows["deliveries.csv"]],
            delivery_lines=[
                DeliveryLineCsv(
                    delivery_id=r["delivery_id"], sku=r["sku"], quantity=int(r["quantity"])
                )
                for r in rows["delivery_lines.csv"]
            ],
            invoices=[InvoiceCsv(**r) for r in rows["invoices.csv"]],
            invoice_lines=[
                InvoiceLineCsv(
                    invoice_id=r["invoice_id"],
                    sku=r["sku"],
                    quantity=int(r["quantity"]),
                    unit_price_minor=int(r["unit_price_minor"]),
                )
                for r in rows["invoice_lines.csv"]
            ],
            service_events=[
                ServiceEventCsv(
                    event_id=r["event_id"],
                    customer=r["customer"],
                    code=r["code"],
                    units=int(r["units"]),
                    event_date=r["event_date"],
                )
                for r in rows["service_events.csv"]
            ],
            batches=[
                BatchCsv(
                    batch_id=r["batch_id"],
                    customer=r["customer"],
                    sku=r["sku"],
                    production_date=r["production_date"],
                    planned_units=int(r["planned_units"]),
                    actual_units=int(r["actual_units"]),
                )
                for r in rows.get("batches.csv", [])
            ],
            quality_holds=[
                QualityHoldCsv(
                    hold_id=r["hold_id"],
                    batch_id=r["batch_id"],
                    reason=r["reason"],
                    hold_date=r["hold_date"],
                    released=r["released"],
                )
                for r in rows.get("quality_holds.csv", [])
            ],
            stock_movements=[
                StockMovementCsv(
                    movement_id=r["movement_id"],
                    batch_id=r["batch_id"],
                    sku=r["sku"],
                    quantity=int(r["quantity"]),
                    direction=r["direction"],
                    movement_date=r["movement_date"],
                )
                for r in rows.get("stock_movements.csv", [])
            ],
        )
    except (KeyError, TypeError, ValueError) as exc:
        return Result.err("ingest.malformed_row", f"A source row is missing or malformed: {exc}")
    return Result.ok(bundle)


def parse_bundle(texts: dict[str, str]) -> Result[SourceBundle]:
    rows: dict[str, list[dict[str, str]]] = {}
    for name in REQUIRED_FILES:
        if name not in texts:
            return Result.err("ingest.missing_file", f"Source bundle is missing {name}.")
    for name in (*REQUIRED_FILES, *OPTIONAL_FILES):
        if name not in texts:
            continue
        parsed = read_csv(name, texts[name])
        if parsed.error is not None:
            return Result.err(parsed.error.code, parsed.error.message)
        rows[name] = parsed.value or []
    return validate_bundle(rows)


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]
