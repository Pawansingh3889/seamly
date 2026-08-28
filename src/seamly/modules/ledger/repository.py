"""Ledger repository: the only writer of canonical tables."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.ledger.models import (
    Contract,
    Customer,
    Delivery,
    DeliveryLine,
    Invoice,
    InvoiceLine,
    Order,
    OrderLine,
    PriceBookEntry,
    ServiceEvent,
)


async def upsert_customer(session: AsyncSession, code: str, name: str, normalised: str) -> Customer:
    existing = await session.scalar(select(Customer).where(Customer.code == code))
    if existing:
        existing.name = name
        existing.normalised_name = normalised
        return existing
    row = Customer(code=code, name=name, normalised_name=normalised)
    session.add(row)
    return row


async def upsert_contract(
    session: AsyncSession,
    code: str,
    customer_code: str,
    invoice_window_days: int,
    duplicate_window_days: int,
    late_delivery_penalty_minor: int,
) -> Contract:
    customer = await session.scalar(select(Customer).where(Customer.code == customer_code))
    if customer is None:
        raise ValueError(f"unknown customer code {customer_code!r} for contract {code!r}")
    existing = await session.scalar(select(Contract).where(Contract.code == code))
    if existing:
        existing.customer_id = customer.id
        existing.invoice_window_days = invoice_window_days
        existing.duplicate_window_days = duplicate_window_days
        existing.late_delivery_penalty_minor = late_delivery_penalty_minor
        return existing
    row = Contract(
        code=code,
        customer_id=customer.id,
        invoice_window_days=invoice_window_days,
        duplicate_window_days=duplicate_window_days,
        late_delivery_penalty_minor=late_delivery_penalty_minor,
    )
    session.add(row)
    return row


async def upsert_price_book_entry(
    session: AsyncSession, contract_code: str, sku: str, kind: str, unit_price_minor: int
) -> PriceBookEntry:
    contract = await session.scalar(select(Contract).where(Contract.code == contract_code))
    if contract is None:
        raise ValueError(f"unknown contract code {contract_code!r} in price book")
    existing = await session.scalar(
        select(PriceBookEntry).where(
            PriceBookEntry.contract_id == contract.id, PriceBookEntry.sku == sku
        )
    )
    if existing:
        existing.kind = kind
        existing.unit_price_minor = unit_price_minor
        return existing
    row = PriceBookEntry(
        contract_id=contract.id, sku=sku, kind=kind, unit_price_minor=unit_price_minor
    )
    session.add(row)
    return row


async def replace_orders(
    session: AsyncSession, orders: list[tuple[Order, list[tuple[str, int, int]]]]
) -> None:
    """Each entry is (order, [(sku, quantity, unit_price_minor), ...])."""

    for order, specs in orders:
        existing = await session.scalar(select(Order).where(Order.code == order.code))
        if existing:
            await session.delete(existing)
            await session.flush()
        session.add(order)
        await session.flush()
        session.add_all(
            [
                OrderLine(order_id=order.id, sku=sku, quantity=qty, unit_price_minor=price)
                for sku, qty, price in specs
            ]
        )


async def replace_deliveries(
    session: AsyncSession, deliveries: list[tuple[Delivery, list[tuple[str, int]]]]
) -> None:
    """Each entry is (delivery, [(sku, quantity), ...])."""

    for delivery, specs in deliveries:
        existing = await session.scalar(select(Delivery).where(Delivery.code == delivery.code))
        if existing:
            await session.delete(existing)
            await session.flush()
        session.add(delivery)
        await session.flush()
        session.add_all(
            [DeliveryLine(delivery_id=delivery.id, sku=sku, quantity=qty) for sku, qty in specs]
        )


async def replace_invoices(
    session: AsyncSession, invoices: list[tuple[Invoice, list[tuple[str, int, int]]]]
) -> None:
    """Each entry is (invoice, [(sku, quantity, unit_price_minor), ...])."""

    for invoice, specs in invoices:
        existing = await session.scalar(select(Invoice).where(Invoice.code == invoice.code))
        if existing:
            await session.delete(existing)
            await session.flush()
        session.add(invoice)
        await session.flush()
        session.add_all(
            [
                InvoiceLine(invoice_id=invoice.id, sku=sku, quantity=qty, unit_price_minor=price)
                for sku, qty, price in specs
            ]
        )


async def replace_service_events(session: AsyncSession, events: list[ServiceEvent]) -> None:
    for event in events:
        existing = await session.scalar(select(ServiceEvent).where(ServiceEvent.code == event.code))
        if existing:
            await session.delete(existing)
            await session.flush()
        session.add(event)


async def all_customers(session: AsyncSession) -> list[Customer]:
    rows = await session.execute(select(Customer))
    return list(rows.scalars())


async def all_contracts(session: AsyncSession) -> list[Contract]:
    rows = await session.execute(select(Contract))
    return list(rows.scalars())
