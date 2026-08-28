"""Analyst repository: retrieval from the store, and the LLM call.

Both are I/O. The LLM is called through an OpenAI-compatible endpoint and
returns raw text; nothing it says is trusted until service.verify_answer
passes.
"""

from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules.analyst.contract import CitedException
from seamly.modules.exception.models import STATUS_ASSIGNED, STATUS_OPEN, ExceptionRecord
from seamly.modules.ledger.models import Customer

STOPWORDS = {
    "the",
    "and",
    "are",
    "what",
    "which",
    "why",
    "who",
    "how",
    "when",
    "does",
    "did",
    "was",
    "were",
    "our",
    "for",
    "with",
    "from",
    "that",
    "this",
    "have",
    "has",
    "any",
    "all",
    "can",
    "you",
    "tell",
    "about",
    "into",
    "most",
    "biggest",
    "should",
    "first",
    "show",
    "list",
    "give",
}


async def load_context(
    session: AsyncSession, question: str, limit: int = 10
) -> list[CitedException]:
    rows = (
        await session.execute(
            select(ExceptionRecord, Customer.name)
            .join(Customer, ExceptionRecord.customer_id == Customer.id)
            .where(ExceptionRecord.status.in_([STATUS_OPEN, STATUS_ASSIGNED]))
            .order_by(ExceptionRecord.amount_minor.desc())
        )
    ).all()

    candidates = [
        CitedException(
            id=record.id,
            rule_id=record.rule_id,
            customer_name=name,
            amount_minor=record.amount_minor,
            currency=record.currency,
            status=record.status,
            owner=record.owner,
            formula=record.formula,
            record_refs=record.record_refs,
        )
        for record, name in rows
    ]

    tokens = {
        word for word in re_lower_tokens(question) if len(word) >= 3 and word not in STOPWORDS
    }
    if not tokens:
        return candidates[:limit]

    def matches(item: CitedException) -> bool:
        haystack = " ".join(
            [
                item.rule_id,
                item.customer_name,
                item.formula,
                item.record_refs,
                item.status,
            ]
        ).lower()
        return any(token in haystack for token in tokens)

    matched = [item for item in candidates if matches(item)]
    return (matched or candidates)[:limit]


def re_lower_tokens(text: str) -> list[str]:
    return "".join(ch if ch.isalnum() else " " for ch in text.lower()).split()


async def call_llm(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
    response = await httpx.AsyncClient(timeout=60).post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    response.raise_for_status()
    body = response.json()
    try:
        return str(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"LLM response had no message content: {body}") from exc
