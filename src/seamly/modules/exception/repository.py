"""Exception repository: idempotent upserts and the loop's data access."""

from __future__ import annotations

import hashlib
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.exception.models import (
    STATUS_OPEN,
    ExceptionRecord,
    RecoveryEntry,
)
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


async def all_exceptions(session: AsyncSession, status: str | None = None) -> list[ExceptionRecord]:
    query = select(ExceptionRecord).order_by(ExceptionRecord.amount_minor.desc())
    if status:
        query = query.where(ExceptionRecord.status == status)
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
