"""Ingest module: load a validated source bundle into the canonical ledger."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result
from seamly.config import get_settings
from seamly.modules.ingest import repository as ingest_repo
from seamly.modules.ingest import service as ingest_service
from seamly.modules.ledger import repository as ledger_repository
from seamly.modules.ledger.models import (
    Contract,
    Customer,
    Delivery,
    Invoice,
    Order,
    ServiceEvent,
)

PERMISSIONS: dict[str, set[str]] = {
    "ingest.load": {"ops", "analyst", "cfo", "admin"},
}


def _as_date(raw: str, context: str) -> date:
    parsed = ingest_service.parse_date(raw, context)
    if parsed.is_err:
        raise ValueError(parsed.error_or_raise().message)
    return parsed.value_or_raise()


async def handle_load(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    fixture_dir = Path(payload.get("fixture_dir") or get_settings().fixture_dir)
    try:
        texts = ingest_repo.read_source_texts(fixture_dir)
    except FileNotFoundError as exc:
        return Result.err("ingest.missing_file", str(exc))
    parsed = ingest_service.parse_bundle(texts)
    if parsed.is_err:
        err = parsed.error_or_raise()
        return Result.err(err.code, err.message)
    bundle = parsed.value_or_raise()

    customers: dict[str, Customer] = {}
    for crow in bundle.customers:
        customer = await ledger_repository.upsert_customer(
            session,
            code=crow.customer_id,
            name=crow.name,
            normalised=ingest_service.normalise_name(crow.name),
        )
        customers[ingest_service.normalise_name(crow.name)] = customer

    def customer_for(raw_name: str) -> int:
        resolved = customers.get(ingest_service.normalise_name(raw_name))
        if resolved is None:
            raise ValueError(
                f"Unknown customer name {raw_name!r}: it does not match any customers.csv row "
                "after normalisation. Fix the source or add the customer there."
            )
        return resolved.id

    for ctrow in bundle.contracts:
        await ledger_repository.upsert_contract(
            session,
            code=ctrow.contract_id,
            customer_code=ctrow.customer_id,
            invoice_window_days=ctrow.invoice_window_days,
            duplicate_window_days=ctrow.duplicate_window_days,
            late_delivery_penalty_minor=ctrow.late_delivery_penalty_minor,
        )
    for prow in bundle.price_book:
        await ledger_repository.upsert_price_book_entry(
            session,
            contract_code=prow.contract_id,
            sku=prow.sku,
            kind=prow.kind,
            unit_price_minor=prow.unit_price_minor,
        )

    orders: dict[str, Order] = {}
    for orow in bundle.orders:
        orders[orow.order_id] = Order(
            code=orow.order_id,
            order_ref=orow.order_ref,
            customer_id=customer_for(orow.customer),
            promised_date=_as_date(orow.promised_date, f"order {orow.order_id}"),
        )
    order_specs: dict[str, list[tuple[str, int, int]]] = {}
    for oline in bundle.order_lines:
        if oline.order_id not in orders:
            return Result.err(
                "ingest.orphan_line",
                f"order_lines row references unknown order {oline.order_id!r}.",
            )
        order_specs.setdefault(oline.order_id, []).append(
            (oline.sku, oline.quantity, oline.unit_price_minor)
        )
    await ledger_repository.replace_orders(
        session, [(orders[oid], order_specs[oid]) for oid in orders if oid in order_specs]
    )

    deliveries: dict[str, Delivery] = {}
    for drow in bundle.deliveries:
        deliveries[drow.delivery_id] = Delivery(
            code=drow.delivery_id,
            carrier_reference=drow.carrier_reference,
            order_ref=drow.order_ref,
            customer_id=customer_for(drow.customer),
            delivery_date=_as_date(drow.delivery_date, f"delivery {drow.delivery_id}"),
        )
    delivery_specs: dict[str, list[tuple[str, int]]] = {}
    for dline in bundle.delivery_lines:
        if dline.delivery_id not in deliveries:
            return Result.err(
                "ingest.orphan_line",
                f"delivery_lines row references unknown delivery {dline.delivery_id!r}.",
            )
        delivery_specs.setdefault(dline.delivery_id, []).append((dline.sku, dline.quantity))
    await ledger_repository.replace_deliveries(
        session,
        [(deliveries[did], delivery_specs[did]) for did in deliveries if did in delivery_specs],
    )

    invoices: dict[str, Invoice] = {}
    for irow in bundle.invoices:
        invoices[irow.invoice_id] = Invoice(
            code=irow.invoice_id,
            external_ref=irow.external_ref,
            order_ref=irow.order_ref,
            customer_id=customer_for(irow.customer),
            contract_id=await _contract_id(session, irow.contract_id),
            invoice_date=_as_date(irow.invoice_date, f"invoice {irow.invoice_id}"),
        )
    invoice_specs: dict[str, list[tuple[str, int, int]]] = {}
    for iline in bundle.invoice_lines:
        if iline.invoice_id not in invoices:
            return Result.err(
                "ingest.orphan_line",
                f"invoice_lines row references unknown invoice {iline.invoice_id!r}.",
            )
        invoice_specs.setdefault(iline.invoice_id, []).append(
            (iline.sku, iline.quantity, iline.unit_price_minor)
        )
    await ledger_repository.replace_invoices(
        session, [(invoices[iid], invoice_specs[iid]) for iid in invoices if iid in invoice_specs]
    )

    events: list[ServiceEvent] = []
    for srow in bundle.service_events:
        events.append(
            ServiceEvent(
                code=srow.event_id,
                customer_id=customer_for(srow.customer),
                service_code=srow.code,
                units=srow.units,
                event_date=_as_date(srow.event_date, f"service event {srow.event_id}"),
            )
        )
    await ledger_repository.replace_service_events(session, events)

    return Result.ok({"run_id": ingest_service.new_run_id()})


async def _contract_id(session: AsyncSession, code: str) -> int:
    found = await session.scalar(select(Contract).where(Contract.code == code))
    if found is None:
        raise ValueError(f"invoice references unknown contract {code!r}.")
    return found.id
