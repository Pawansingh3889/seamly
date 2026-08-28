"""Reconcile repository: reads canonical tables into typed rule-input rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.ledger.models import (
    Batch,
    Contract,
    Delivery,
    DeliveryLine,
    Invoice,
    InvoiceLine,
    Order,
    PriceBookEntry,
    QualityHold,
    ServiceEvent,
    StockMovement,
)
from seamly.modules.reconcile.contract import (
    ContractRow,
    DeliveryLineRow,
    InvoiceLineRow,
    OrderPromiseRow,
    PriceRow,
    ServiceEventRow,
)


async def load_rows(
    session: AsyncSession,
) -> tuple[
    list[InvoiceLineRow],
    list[DeliveryLineRow],
    list[ServiceEventRow],
    dict[tuple[int, str], OrderPromiseRow],
    dict[int, ContractRow],
    dict[tuple[str, str], PriceRow],
    dict[str, int],
    dict[int, str],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    invoice_rows = (
        await session.execute(
            select(InvoiceLine, Invoice, Contract)
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
            .join(Contract, Invoice.contract_id == Contract.id)
        )
    ).all()
    invoice_lines = [
        InvoiceLineRow(
            invoice_code=invoice.code,
            external_ref=invoice.external_ref,
            order_ref=invoice.order_ref,
            customer_id=invoice.customer_id,
            contract_code=contract.code,
            sku=line.sku,
            quantity=line.quantity,
            unit_price_minor=line.unit_price_minor,
            invoice_date=invoice.invoice_date,
        )
        for line, invoice, contract in invoice_rows
    ]

    delivery_rows = (
        await session.execute(
            select(DeliveryLine, Delivery).join(Delivery, DeliveryLine.delivery_id == Delivery.id)
        )
    ).all()
    delivery_lines = [
        DeliveryLineRow(
            order_ref=delivery.order_ref,
            customer_id=delivery.customer_id,
            sku=line.sku,
            quantity=line.quantity,
            delivery_date=delivery.delivery_date,
        )
        for line, delivery in delivery_rows
    ]

    event_rows = (await session.execute(select(ServiceEvent))).scalars()
    service_events = [
        ServiceEventRow(
            code=e.code,
            customer_id=e.customer_id,
            service_code=e.service_code,
            units=e.units,
            event_date=e.event_date,
        )
        for e in event_rows
    ]

    promise_rows = (await session.execute(select(Order))).scalars()
    promises = {
        (o.customer_id, o.order_ref): OrderPromiseRow(
            order_ref=o.order_ref, customer_id=o.customer_id, promised_date=o.promised_date
        )
        for o in promise_rows
    }

    contract_rows = (await session.execute(select(Contract))).scalars()
    contracts: dict[int, ContractRow] = {}
    penalties: dict[str, int] = {}
    customer_contract: dict[int, str] = {}
    for c in contract_rows:
        contracts[c.customer_id] = ContractRow(
            code=c.code,
            customer_id=c.customer_id,
            duplicate_window_days=c.duplicate_window_days,
            late_delivery_penalty_minor=c.late_delivery_penalty_minor,
        )
        penalties[c.code] = c.late_delivery_penalty_minor
        customer_contract[c.customer_id] = c.code

    price_rows = (
        await session.execute(
            select(PriceBookEntry, Contract).join(
                Contract, PriceBookEntry.contract_id == Contract.id
            )
        )
    ).all()
    prices = {
        (contract.code, entry.sku): PriceRow(
            contract_code=contract.code,
            sku=entry.sku,
            kind=entry.kind,
            unit_price_minor=entry.unit_price_minor,
        )
        for entry, contract in price_rows
    }

    batches = (await session.execute(select(Batch))).scalars()
    batch_rows: list[dict[str, Any]] = [
        {
            "code": b.code,
            "customer_id": b.customer_id,
            "sku": b.sku,
            "production_date": b.production_date,
            "planned_units": b.planned_units,
            "actual_units": b.actual_units,
        }
        for b in batches
    ]
    hold_rows = (
        await session.execute(
            select(QualityHold, Batch).join(Batch, QualityHold.batch_id == Batch.id)
        )
    ).all()
    holds: list[dict[str, Any]] = [
        {
            "code": hold.code,
            "batch_code": batch.code,
            "reason": hold.reason,
            "hold_date": hold.hold_date,
            "released": hold.released,
            "customer_id": batch.customer_id,
        }
        for hold, batch in hold_rows
    ]
    movement_rows = (
        await session.execute(
            select(StockMovement, Batch).join(Batch, StockMovement.batch_id == Batch.id)
        )
    ).all()
    movements: list[dict[str, Any]] = [
        {
            "code": movement.code,
            "batch_code": batch.code,
            "sku": movement.sku,
            "quantity": movement.quantity,
            "direction": movement.direction,
            "movement_date": movement.movement_date,
            "customer_id": batch.customer_id,
        }
        for movement, batch in movement_rows
    ]

    return (
        invoice_lines,
        delivery_lines,
        service_events,
        promises,
        contracts,
        prices,
        penalties,
        customer_contract,
        batch_rows,
        holds,
        movements,
    )
