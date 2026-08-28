"""Ingest contracts: typed rows as they appear in a source CSV."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CustomerCsv:
    customer_id: str
    name: str


@dataclass
class ContractCsv:
    contract_id: str
    customer_id: str
    invoice_window_days: int
    duplicate_window_days: int
    late_delivery_penalty_minor: int


@dataclass
class PriceBookCsv:
    contract_id: str
    sku: str
    kind: str
    unit_price_minor: int


@dataclass
class OrderCsv:
    order_id: str
    order_ref: str
    customer: str
    promised_date: str


@dataclass
class OrderLineCsv:
    order_id: str
    sku: str
    quantity: int
    unit_price_minor: int


@dataclass
class DeliveryCsv:
    delivery_id: str
    carrier_reference: str
    order_ref: str
    customer: str
    delivery_date: str


@dataclass
class DeliveryLineCsv:
    delivery_id: str
    sku: str
    quantity: int


@dataclass
class InvoiceCsv:
    invoice_id: str
    external_ref: str
    order_ref: str
    customer: str
    invoice_date: str
    contract_id: str


@dataclass
class InvoiceLineCsv:
    invoice_id: str
    sku: str
    quantity: int
    unit_price_minor: int


@dataclass
class ServiceEventCsv:
    event_id: str
    customer: str
    code: str
    units: int
    event_date: str


@dataclass
class BatchCsv:
    batch_id: str
    customer: str
    sku: str
    production_date: str
    planned_units: int
    actual_units: int


@dataclass
class QualityHoldCsv:
    hold_id: str
    batch_id: str
    reason: str
    hold_date: str
    released: str


@dataclass
class StockMovementCsv:
    movement_id: str
    batch_id: str
    sku: str
    quantity: int
    direction: str
    movement_date: str


@dataclass
class SourceBundle:
    """Everything one ingest run needs, already validated and name-normalised."""

    customers: list[CustomerCsv]
    contracts: list[ContractCsv]
    price_book: list[PriceBookCsv]
    orders: list[OrderCsv]
    order_lines: list[OrderLineCsv]
    deliveries: list[DeliveryCsv]
    delivery_lines: list[DeliveryLineCsv]
    invoices: list[InvoiceCsv]
    invoice_lines: list[InvoiceLineCsv]
    service_events: list[ServiceEventCsv]
    batches: list[BatchCsv] = field(default_factory=list)
    quality_holds: list[QualityHoldCsv] = field(default_factory=list)
    stock_movements: list[StockMovementCsv] = field(default_factory=list)
