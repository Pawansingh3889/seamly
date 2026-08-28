"""Analyst contracts: retrieved context and the verified answer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CitedException:
    """One exception, as the analyst may present it."""

    id: int
    rule_id: str
    customer_name: str
    amount_minor: int
    currency: str
    status: str
    owner: str | None
    formula: str
    record_refs: str


@dataclass
class AnalystAnswer:
    text: str
    cited_ids: list[int] = field(default_factory=list)
    context_ids: list[int] = field(default_factory=list)
