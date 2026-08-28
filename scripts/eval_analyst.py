"""Analyst eval set: the gate a prompt or model change must rerun.

Prompts are code; a change to SYSTEM_PROMPT or the verifier reruns this set
(before merge, same as a model upgrade). Cases are pure: canned context and
canned responses, no network, no LLM key. The live LLM path is covered by
tests/test_analyst.py with a stubbed call.

Run: make eval  (also part of make gate)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from seamly.modules.analyst import service as analyst_service
from seamly.modules.analyst.contract import CitedException

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class EvalCase:
    name: str
    question: str
    context: list[CitedException]
    response: str
    should_pass: bool
    expect_code: str | None = None


def _exc(
    eid: int, rule: str, amount_minor: int, customer: str = "Calder Engineering Ltd"
) -> CitedException:
    return CitedException(
        id=eid,
        rule_id=rule,
        customer_name=customer,
        amount_minor=amount_minor,
        currency="GBP",
        status="open",
        owner=None,
        formula=f"{amount_minor} pence priced from the price book",
        record_refs=f"O-{eid}|D-{eid}",
    )


CONTEXT = [
    _exc(1, "R01", 412_500, "Acme Industrial Supplies Ltd"),
    _exc(2, "R05", 487_500),
    _exc(3, "R06", 51_000, "Acme Industrial Supplies Ltd"),
]

CASES: list[EvalCase] = [
    EvalCase(
        name="grounded answer with citations and figures",
        question="where is the money?",
        context=CONTEXT,
        response="The biggest leak is [E2] at £4,875.00, then [E1] at GBP 4,125.00.",
        should_pass=True,
    ),
    EvalCase(
        name="sum of cited figures is allowed",
        question="how much in total?",
        context=CONTEXT,
        response="[E1] and [E2] come to £9,000.00 before the smaller items.",
        should_pass=True,
    ),
    EvalCase(
        name="admits the data does not answer",
        question="why is revenue down?",
        context=CONTEXT,
        response="The data I have shows open exceptions [E1] and [E2]; it does not say why revenue moved.",
        should_pass=True,
    ),
    EvalCase(
        name="unformatted quantities are prose, not figures",
        question="how many exceptions?",
        context=CONTEXT,
        response="There are 3 exceptions above; the largest is [E2].",
        should_pass=True,
    ),
    EvalCase(
        name="no citations",
        question="what should I do?",
        context=CONTEXT,
        response="Assign owners and chase the duplicates.",
        should_pass=False,
        expect_code="analyst.no_citations",
    ),
    EvalCase(
        name="unknown citation",
        question="what about shipping?",
        context=CONTEXT,
        response="[E99] covers the shipping gap at £50.00.",
        should_pass=False,
        expect_code="analyst.unknown_citation",
    ),
    EvalCase(
        name="hallucinated pound-prefixed figure",
        question="how bad is it?",
        context=CONTEXT,
        response="It is bad: [E1] alone has cost £41,250.00 so far.",
        should_pass=False,
        expect_code="analyst.ungrounded_figure",
    ),
    EvalCase(
        name="hallucinated GBP-prefixed figure",
        question="how bad is it?",
        context=CONTEXT,
        response="It is bad: [E1] alone has cost GBP 41,250.00 so far.",
        should_pass=False,
        expect_code="analyst.ungrounded_figure",
    ),
]

REQUIRED_PROMPT_PHRASES = [
    "Answer only from the exception data",
    "Cite every exception you mention as [E<id>]",
    "Never compute new figures except simple sums",
    "If the data does not answer the question, say so plainly",
    "Be brief",
]


def run_eval() -> list[str]:
    failures: list[str] = []

    for phrase in REQUIRED_PROMPT_PHRASES:
        if phrase not in analyst_service.SYSTEM_PROMPT:
            failures.append(f"prompt regression: SYSTEM_PROMPT lost the requirement: {phrase!r}")

    for case in CASES:
        prompt = analyst_service.build_user_prompt(case.question, case.context)
        if f"Question: {case.question}" not in prompt:
            failures.append(f"{case.name}: prompt dropped the question")
        for item in case.context:
            if f"[E{item.id}]" not in prompt:
                failures.append(f"{case.name}: prompt dropped exception E{item.id}")

        verified = analyst_service.verify_answer(case.response, case.context)
        if case.should_pass and verified.is_err:
            err = verified.error_or_raise()
            failures.append(f"{case.name}: should pass but failed with {err.code}: {err.message}")
        if not case.should_pass:
            if not verified.is_err:
                failures.append(f"{case.name}: should fail but passed")
            elif case.expect_code and verified.error_or_raise().code != case.expect_code:
                failures.append(
                    f"{case.name}: expected error {case.expect_code}, "
                    f"got {verified.error_or_raise().code}"
                )

    return failures


def main() -> int:
    failures = run_eval()
    for failure in failures:
        print(f"EVAL FAIL: {failure}")
    if not failures:
        print(f"analyst eval ok: {len(CASES)} cases, {len(REQUIRED_PROMPT_PHRASES)} prompt checks")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
