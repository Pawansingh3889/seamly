"""Analyst module: read-only Q&A over exceptions, citation-verified.

The engine computes, the LLM narrates. See ARCHITECTURE.md section 6 and
the module service: an answer is shown only when every citation resolves
and every pound figure is grounded in the retrieved data.
"""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.common.types import Result
from seamly.config import get_settings
from seamly.modules.analyst import repository as analyst_repo
from seamly.modules.analyst import service as analyst_service

PERMISSIONS: dict[str, set[str]] = {
    "analyst.ask": {"analyst", "cfo", "admin"},
}


async def handle_ask(session: AsyncSession, payload: dict[str, Any]) -> Result[Any]:
    question = str(payload.get("question", "")).strip()
    if not question:
        return Result.err("analyst.question_required", "Ask a question about the exceptions.")

    settings = get_settings()
    if not settings.llm_base_url or not settings.llm_model:
        return Result.err(
            "analyst.not_configured",
            "Set SEAMLY_LLM_BASE_URL, SEAMLY_LLM_API_KEY and SEAMLY_LLM_MODEL to enable "
            "the analyst. The deterministic API already answers totals and rankings.",
        )

    context = await analyst_repo.load_context(session, question)
    if not context:
        return Result.err(
            "analyst.no_relevant_exceptions",
            "There are no open exceptions to answer from. Run the pipeline first.",
        )

    try:
        text = await analyst_repo.call_llm(
            settings.llm_base_url,
            settings.llm_api_key,
            settings.llm_model,
            analyst_service.SYSTEM_PROMPT,
            analyst_service.build_user_prompt(question, context),
        )
    except (httpx.HTTPError, ValueError) as exc:
        return Result.err("analyst.llm_error", f"The LLM call failed: {exc}")

    verified = analyst_service.verify_answer(text, context)
    if verified.is_err:
        err = verified.error_or_raise()
        return Result.err(
            "analyst.unverified",
            f"{err.message} Rephrase the question or check the data; the raw answer "
            "is discarded, never shown.",
        )

    return Result.ok(
        {"answer": text, "citations": verified.value, "context": [c.id for c in context]}
    )
