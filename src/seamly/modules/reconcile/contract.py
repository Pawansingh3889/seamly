"""Typed rows the reconciliation rules operate on, and the findings they emit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class PriceRow:
    contract_code: str
    sku: str
    kind: str
    unit_price_minor: int


@dataclass
class ContractRow:
    code: str
    customer_id: int
    duplicate_window_days: int
    late_delivery_penalty_minor: int


@dataclass
class DeliveryLineRow:
    order_ref: str
    customer_id: int
    sku: str
    quantity: int
    delivery_date: date


@dataclass
class InvoiceLineRow:
    invoice_code: str
    external_ref: str
    order_ref: str
    customer_id: int
    contract_code: str
    sku: str
    quantity: int
    unit_price_minor: int
    invoice_date: date


@dataclass
class ServiceEventRow:
    code: str
    customer_id: int
    service_code: str
    units: int
    event_date: date


@dataclass
class OrderPromiseRow:
    order_ref: str
    customer_id: int
    promised_date: date


@dataclass
class Finding:
    """A structural disagreement between systems, not yet priced."""

    rule_id: str
    customer_id: int
    contract_code: str
    refs: list[str] = field(default_factory=list)
    sku: str = ""
    quantity: int = 0
    unit_price_minor: int = 0
    invoiced_price_minor: int = 0
