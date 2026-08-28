"""Exception repository: idempotent upserts and the loop's data access."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.exception.models import (
    STATUS_ACCEPTED_RISK,
    STATUS_ASSIGNED,
    STATUS_OPEN,
    STATUS_RESOLVED,
    ExceptionRecord,
    RecoveryEntry,
)
from seamly.modules.ledger.models import Customer
from seamly.modules.scoring.service import PricedException


def fingerprint(rule_id: str, refs: list[str], quantity: int) -> str:
    material = "|".join([rule_id, *refs, str(quantity)])
    return hashlib.sha1(material.encode()).hexdigest()[:24]


async def upsert_priced(session: AsyncSession, priced: PricedException) -> bool:
    """Insert unless this exact finding already exists. Returns True if new."""

    fp = fingerprint(priced.rule_id, priced.refs, priced.quantity)
    existing = await session.scalar(
        select(ExceptionRecord).where(ExceptionRecord.fingerprint == fp)
    )
    if existing is not None:
        return False
    session.add(
        ExceptionRecord(
            fingerprint=fp,
            rule_id=priced.rule_id,
            customer_id=priced.customer_id,
            contract_code=priced.contract_code,
            amount_minor=priced.amount_minor,
            currency=priced.currency,
            formula=priced.formula,
            record_refs="|".join(priced.refs),
            status=STATUS_OPEN,
        )
    )
    return True


async def all_exceptions(
    session: AsyncSession,
    status: str | None = None,
    customer_id: int | None = None,
    owner: str | None = None,
) -> list[ExceptionRecord]:
    query = select(ExceptionRecord).order_by(ExceptionRecord.amount_minor.desc())
    if status:
        query = query.where(ExceptionRecord.status == status)
    if customer_id is not None:
        query = query.where(ExceptionRecord.customer_id == customer_id)
    if owner:
        query = query.where(ExceptionRecord.owner == owner)
    rows = await session.execute(query)
    return list(rows.scalars())


async def get_exception(session: AsyncSession, exception_id: int) -> ExceptionRecord | None:
    return await session.get(ExceptionRecord, exception_id)


async def total_at_risk(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.coalesce(func.sum(ExceptionRecord.amount_minor), 0)).where(
            ExceptionRecord.status.in_([STATUS_OPEN, "assigned"])
        )
    )
    return int(result.scalar_one())


async def total_recovered(session: AsyncSession) -> int:
    result = await session.execute(select(func.coalesce(func.sum(RecoveryEntry.amount_minor), 0)))
    return int(result.scalar_one())


async def add_recovery(
    session: AsyncSession, exception_id: int, amount_minor: int, evidence: str, recovered_on: date
) -> RecoveryEntry:
    entry = RecoveryEntry(
        exception_id=exception_id,
        amount_minor=amount_minor,
        evidence=evidence,
        recovered_on=recovered_on,
    )
    session.add(entry)
    return entry


async def recoveries_for(session: AsyncSession, exception_id: int) -> list[RecoveryEntry]:
    rows = await session.execute(
        select(RecoveryEntry).where(RecoveryEntry.exception_id == exception_id)
    )
    return list(rows.scalars())


@dataclass
class CustomerAtRisk:
    customer_id: int
    customer_name: str
    amount_minor: int
    exception_count: int


async def at_risk_by_customer(session: AsyncSession) -> list[CustomerAtRisk]:
    rows = await session.execute(
        select(
            Customer.id,
            Customer.name,
            func.coalesce(func.sum(ExceptionRecord.amount_minor), 0),
            func.count(ExceptionRecord.id),
        )
        .join(ExceptionRecord, ExceptionRecord.customer_id == Customer.id)
        .where(ExceptionRecord.status.in_([STATUS_OPEN, STATUS_ASSIGNED]))
        .group_by(Customer.id, Customer.name)
        .order_by(func.sum(ExceptionRecord.amount_minor).desc())
    )
    return [
        CustomerAtRisk(
            customer_id=cid, customer_name=name, amount_minor=amount, exception_count=count
        )
        for cid, name, amount, count in rows
    ]


async def customer_name(session: AsyncSession, customer_id: int) -> str | None:
    found: Customer | None = await session.get(Customer, customer_id)
    return found.name if found else None


@dataclass
class DigestInputs:
    """Everything the weekly digest needs, fetched in one repository pass."""

    week_start: date
    open_items: list[ExceptionRecord]
    raised_this_week: list[ExceptionRecord]
    resolved_this_week: list[ExceptionRecord]
    accepted_risk_items: list[ExceptionRecord]
    recovered_this_week_minor: int


async def load_digest_inputs(session: AsyncSession, week_start: date) -> DigestInputs:
    all_rows = await all_exceptions(session)
    # Compare on the date portion: Postgres returns timezone-aware datetimes
    # and SQLite naive ones, so datetime comparison would break on one of them.
    raised = [r for r in all_rows if r.created_at and r.created_at.date() >= week_start]
    resolved = [
        r
        for r in all_rows
        if r.status == STATUS_RESOLVED and r.resolved_at and r.resolved_at.date() >= week_start
    ]
    accepted = [r for r in all_rows if r.status == STATUS_ACCEPTED_RISK]
    open_items = [r for r in all_rows if r.status in (STATUS_OPEN, STATUS_ASSIGNED)]
    recovered_result = await session.execute(
        select(func.coalesce(func.sum(RecoveryEntry.amount_minor), 0)).where(
            RecoveryEntry.recovered_on >= week_start
        )
    )
    return DigestInputs(
        week_start=week_start,
        open_items=open_items,
        raised_this_week=raised,
        resolved_this_week=resolved,
        accepted_risk_items=accepted,
        recovered_this_week_minor=int(recovered_result.scalar_one()),
    )
