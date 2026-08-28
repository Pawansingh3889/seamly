"""Analyst service: prompt construction and the deterministic verifier.

The boundary that makes this safe for a CFO product: the LLM narrates, the
engine computes. Every answer must cite exception ids as [E12] and may only
quote pound figures that the cited exceptions actually carry. The verifier
is plain regex and arithmetic, so an unverified answer never reaches a user.
"""

from __future__ import annotations

import re

from seamly.common.types import Result
from seamly.modules.analyst.contract import CitedException

CITATION_PATTERN = re.compile(r"\[E(\d+)\]")
MONEY_PATTERN = re.compile(r"(?:£|GBP\s?)([\d,]+(?:\.\d{1,2})?)")

SYSTEM_PROMPT = """You are the Seamly analyst. You answer management questions
about revenue leakage exceptions. Rules you must never break:
1. Answer only from the exception data provided in the user message.
2. Cite every exception you mention as [E<id>], for example [E12].
3. Quote pound figures only as they appear in the data, formatted like
   GBP 1,234.56 or £1,234.56. Never compute new figures except simple sums
   of the cited exceptions' amounts.
4. If the data does not answer the question, say so plainly.
5. Be brief: findings, amounts, owners, next actions.
"""


def _gbp(amount_minor: int) -> float:
    return amount_minor / 100


def extract_citations(text: str) -> list[int]:
    return [int(m) for m in CITATION_PATTERN.findall(text)]


def verify_answer(text: str, context: list[CitedException]) -> Result[list[int]]:
    """Check citations resolve and every quoted pound figure is grounded."""

    by_id = {item.id: item for item in context}
    cited = extract_citations(text)
    if not cited:
        return Result.err(
            "analyst.no_citations",
            "The answer cites no exceptions. It cannot be verified, so it is not shown.",
        )
    unknown = [cid for cid in cited if cid not in by_id]
    if unknown:
        return Result.err(
            "analyst.unknown_citation",
            f"The answer cites exceptions that were not in the retrieved data: {unknown}.",
        )

    cited_items = [by_id[cid] for cid in dict.fromkeys(cited)]
    allowed = {_gbp(item.amount_minor) for item in cited_items}
    allowed.add(sum(_gbp(item.amount_minor) for item in cited_items))
    allowed.add(sum(_gbp(item.amount_minor) for item in context))

    for raw in MONEY_PATTERN.findall(text):
        quoted = float(raw.replace(",", ""))
        if not any(abs(quoted - candidate) < 0.01 for candidate in allowed):
            return Result.err(
                "analyst.ungrounded_figure",
                f"The answer quotes GBP {quoted:,.2f}, which does not match any cited "
                "exception or their sum. It cannot be verified, so it is not shown.",
            )
    return Result.ok(list(dict.fromkeys(cited)))


def build_user_prompt(question: str, context: list[CitedException]) -> str:
    lines = [f"Question: {question}", "", "Exception data:"]
    for item in context:
        owner = item.owner or "unassigned"
        lines.append(
            f"[E{item.id}] rule {item.rule_id}, customer {item.customer_name}, "
            f"{_gbp(item.amount_minor):,.2f} {item.currency}, status {item.status}, "
            f"owner {owner}. Arithmetic: {item.formula}. Records: {item.record_refs}."
        )
    lines.append("")
    lines.append("Answer the question using only the exceptions above. Cite them as [E<id>].")
    return "\n".join(lines)
