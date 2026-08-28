"""Analyst handler: retrieval, narration gate, and the not-configured path."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from seamly.modules import analyst
from seamly.modules.analyst import repository as analyst_repo


@pytest.fixture
def llm_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEAMLY_LLM_BASE_URL", "http://localhost:9/v1")
    monkeypatch.setenv("SEAMLY_LLM_API_KEY", "test-key")
    monkeypatch.setenv("SEAMLY_LLM_MODEL", "test-model")
    from seamly.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_ask_without_config_fails_actionably(loaded_session: AsyncSession):
    result = await analyst.handle_ask(loaded_session, {"question": "why is revenue down?"})
    assert result.is_err
    err = result.error_or_raise()
    assert err.code == "analyst.not_configured"
    assert "SEAMLY_LLM_BASE_URL" in err.message


async def test_ask_without_a_question_fails(loaded_session: AsyncSession):
    result = await analyst.handle_ask(loaded_session, {"question": "  "})
    assert result.is_err
    assert result.error_or_raise().code == "analyst.question_required"


async def test_ask_returns_a_verified_answer(
    loaded_session: AsyncSession, llm_configured, monkeypatch: pytest.MonkeyPatch
):
    rows = await analyst_repo.load_context(loaded_session, "why is revenue down?")
    top = rows[0]

    async def fake_llm(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
        assert "Question: why is revenue down?" in user
        assert "Answer only from the exception data" in system
        return (
            f"The biggest open leak is [E{top.id}] on {top.customer_name} at "
            f"GBP {top.amount_minor / 100:,.2f}. Investigate the records listed."
        )

    monkeypatch.setattr(analyst_repo, "call_llm", fake_llm)
    result = await analyst.handle_ask(loaded_session, {"question": "why is revenue down?"})
    assert not result.is_err
    data = result.value
    assert top.id in data["citations"]
    assert f"[E{top.id}]" in data["answer"]


async def test_ask_discards_an_unverified_answer(
    loaded_session: AsyncSession, llm_configured, monkeypatch: pytest.MonkeyPatch
):
    async def hallucinating_llm(
        base_url: str, api_key: str, model: str, system: str, user: str
    ) -> str:
        return "Revenue is down because [E1] lost GBP 999,999.99."

    monkeypatch.setattr(analyst_repo, "call_llm", hallucinating_llm)
    result = await analyst.handle_ask(loaded_session, {"question": "why is revenue down?"})
    assert result.is_err
    assert result.error_or_raise().code == "analyst.unverified"
    assert result.value is None


async def test_ask_discards_an_uncited_answer(
    loaded_session: AsyncSession, llm_configured, monkeypatch: pytest.MonkeyPatch
):
    async def uncited_llm(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
        return "Everything looks fine, nothing to worry about."

    monkeypatch.setattr(analyst_repo, "call_llm", uncited_llm)
    result = await analyst.handle_ask(loaded_session, {"question": "why is revenue down?"})
    assert result.is_err
    assert result.error_or_raise().code == "analyst.unverified"


async def test_llm_transport_errors_are_contained(
    loaded_session: AsyncSession, llm_configured, monkeypatch: pytest.MonkeyPatch
):
    import httpx

    async def failing_llm(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(analyst_repo, "call_llm", failing_llm)
    result = await analyst.handle_ask(loaded_session, {"question": "why is revenue down?"})
    assert result.is_err
    assert result.error_or_raise().code == "analyst.llm_error"


async def test_retrieval_matches_keywords_and_falls_back_to_top(loaded_session: AsyncSession):
    late = await analyst_repo.load_context(loaded_session, "late delivery credits")
    assert any(item.rule_id == "R07" for item in late)

    everything = await analyst_repo.load_context(loaded_session, "gibberish xylophone")
    assert len(everything) == 7
    assert everything[0].amount_minor >= everything[-1].amount_minor
