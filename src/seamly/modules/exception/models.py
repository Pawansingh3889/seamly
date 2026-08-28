"""Exception store: the system of record for the detect-to-recovery loop."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from seamly.common.db import Base

STATUS_OPEN = "open"
STATUS_ASSIGNED = "assigned"
STATUS_RESOLVED = "resolved"
STATUS_ACCEPTED_RISK = "accepted_risk"


class ExceptionRecord(Base):
    __tablename__ = "exception_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(32), unique=True)
    rule_id: Mapped[str] = mapped_column(String(32), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.id"))
    contract_code: Mapped[str] = mapped_column(String(64), default="")
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="GBP")
    formula: Mapped[str] = mapped_column(Text)
    record_refs: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=STATUS_OPEN, index=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raised_run: Mapped[int] = mapped_column(Integer, default=1)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecoveryEntry(Base):
    __tablename__ = "recovery_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("exception_record.id"))
    amount_minor: Mapped[int] = mapped_column(Integer)
    evidence: Mapped[str] = mapped_column(Text)
    recovered_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
