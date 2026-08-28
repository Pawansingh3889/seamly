"""Reconcile repository: reads canonical tables into typed rule-input rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.ledger.models import (
    Contract,
    Delivery,
    DeliveryLine,
    Invoice,
    InvoiceLine,
    Order,
    PriceBookEntry,
    ServiceEvent,
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

    return (
        invoice_lines,
        delivery_lines,
        service_events,
        promises,
        contracts,
        prices,
        penalties,
        customer_contract,
    )
