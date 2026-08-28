"""Canonical ledger model. Owns the tables nothing downstream may bypass."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from seamly.common.db import Base


class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    normalised_name: Mapped[str] = mapped_column(String(255), index=True)


class Contract(Base):
    __tablename__ = "contract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    invoice_window_days: Mapped[int] = mapped_column(Integer, default=21)
    duplicate_window_days: Mapped[int] = mapped_column(Integer, default=14)
    late_delivery_penalty_minor: Mapped[int] = mapped_column(Integer, default=0)


class PriceBookEntry(Base):
    __tablename__ = "price_book_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"))
    sku: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16), default="product")
    unit_price_minor: Mapped[int] = mapped_column(Integer)


class Order(Base):
    __tablename__ = "order"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    order_ref: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    promised_date: Mapped[date] = mapped_column(Date)


class OrderLine(Base):
    __tablename__ = "order_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"))
    sku: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)


class Delivery(Base):
    __tablename__ = "delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    carrier_reference: Mapped[str] = mapped_column(String(64))
    order_ref: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    delivery_date: Mapped[date] = mapped_column(Date)


class DeliveryLine(Base):
    __tablename__ = "delivery_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("delivery.id"))
    sku: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)


class Invoice(Base):
    __tablename__ = "invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    external_ref: Mapped[str] = mapped_column(String(64), index=True)
    order_ref: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"))
    invoice_date: Mapped[date] = mapped_column(Date)


class InvoiceLine(Base):
    __tablename__ = "invoice_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoice.id"))
    sku: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)


class ServiceEvent(Base):
    __tablename__ = "service_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    service_code: Mapped[str] = mapped_column(String(64))
    units: Mapped[int] = mapped_column(Integer)
    event_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Batch(Base):
    """Food vertical: a production batch with planned and achieved yield."""

    __tablename__ = "batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    sku: Mapped[str] = mapped_column(String(64))
    production_date: Mapped[date] = mapped_column(Date)
    planned_units: Mapped[int] = mapped_column(Integer)
    actual_units: Mapped[int] = mapped_column(Integer)


class QualityHold(Base):
    """Food vertical: a QC hold against a batch; released=no means blocked."""

    __tablename__ = "quality_hold"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"))
    reason: Mapped[str] = mapped_column(String(255))
    hold_date: Mapped[date] = mapped_column(Date)
    released: Mapped[bool] = mapped_column(Boolean, default=False)


class StockMovement(Base):
    """Food vertical: batch-level stock movement (out, writeoff, return)."""

    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batch.id"))
    sku: Mapped[str] = mapped_column(String(64))
    quantity: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(16))
    movement_date: Mapped[date] = mapped_column(Date)
