"""Pure verifier tests: the boundary that keeps the LLM honest."""

from __future__ import annotations

from seamly.modules.analyst.contract import CitedException
from seamly.modules.analyst.service import (
    SYSTEM_PROMPT,
    build_user_prompt,
    extract_citations,
    verify_answer,
)


def _item(eid: int, amount_minor: int, rule: str = "R01") -> CitedException:
    return CitedException(
        id=eid,
        rule_id=rule,
        customer_name="Acme Industrial Supplies Ltd",
        amount_minor=amount_minor,
        currency="GBP",
        status="open",
        owner=None,
        formula=f"{amount_minor} pence of leakage",
        record_refs="O-1|D-1",
    )


def test_citations_extracted_in_order():
    assert extract_citations("see [E3] then [E1] then [E3]") == [3, 1, 3]


def test_answer_with_valid_citations_and_figures_passes():
    context = [_item(1, 412_500), _item(2, 51_000)]
    answer = "Two leaks: [E1] at £4,125.00 and [E2] at GBP 510.00. Total £4,635.00."
    verified = verify_answer(answer, context)
    assert not verified.is_err
    assert verified.value == [1, 2]


def test_answer_without_citations_fails():
    verified = verify_answer("There are two leaks totalling £4,635.00.", [_item(1, 412_500)])
    assert verified.is_err
    assert verified.error_or_raise().code == "analyst.no_citations"


def test_answer_citing_unknown_exception_fails():
    verified = verify_answer("See [E99] at £1.00.", [_item(1, 100)])
    assert verified.is_err
    assert verified.error_or_raise().code == "analyst.unknown_citation"


def test_answer_with_hallucinated_figure_fails():
    context = [_item(1, 412_500)]
    verified = verify_answer("[E1] shows £9,999.99 at risk.", context)
    assert verified.is_err
    assert verified.error_or_raise().code == "analyst.ungrounded_figure"


def test_sum_of_cited_figures_is_allowed():
    context = [_item(1, 412_500), _item(2, 51_000)]
    verified = verify_answer("[E1] and [E2] total £4,635.00.", context)
    assert not verified.is_err


def test_unformatted_pound_figures_are_ignored():
    """Numbers without a pound sign are prose; only £ figures are checked."""

    context = [_item(1, 412_500)]
    verified = verify_answer("[E1] is the biggest of the 7 exceptions we found.", context)
    assert not verified.is_err


def test_prompt_carries_citation_instructions_and_data():
    context = [_item(1, 412_500)]
    prompt = build_user_prompt("why is revenue down?", context)
    assert "[E1]" in prompt
    assert "4,125.00" in prompt
    assert "Cite them as [E<id>]" in prompt
    assert "Answer only from the exception data" in SYSTEM_PROMPT
