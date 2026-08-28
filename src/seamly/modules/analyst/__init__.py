"""Analyst module: read-only Q&A over exceptions. Phase 3.

Design boundary (see ARCHITECTURE.md section 6): the engine computes, the
LLM narrates. Every answer must cite exception and record ids and every
number quoted must match the stored figures; a deterministic verifier
rejects anything else. Not implemented yet: asking questions returns a
clear not-ready error rather than an unverified answer.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result

PERMISSIONS: dict[str, set[str]] = {
    "analyst.ask": {"analyst", "cfo", "admin"},
}


async def handle_ask(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    question = str(payload.get("question", "")).strip()
    if not question:
        return Result.err("analyst.question_required", "Ask a question about the exceptions.")
    return Result.err(
        "analyst.not_ready",
        "The citation-verified analyst lands in Phase 3. The CFO board and the "
        "JSON API already answer the deterministic part: totals, rankings and "
        "drill-down.",
    )
