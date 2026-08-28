"""Digest service: builds the weekly management summary. Pure, no I/O.

The digest reads only the exception store: what changed, why it matters in
pounds, and what to do next. Recommended actions are deterministic per rule,
never generated.
"""

from __future__ import annotations

from dataclasses import dataclass

from seamly.modules.exception.models import ExceptionRecord
from seamly.modules.exception.repository import DigestInputs

RULE_ACTIONS: dict[str, str] = {
    "R01": "Raise the missing invoice or confirm non-billable with the account owner.",
    "R02": "Verify delivery evidence or issue a credit note.",
    "R03": "Reconcile the quantity difference, then correct or credit the invoice.",
    "R04": "Rebill at the contracted rate or record why the variance is valid.",
    "R05": "Recover the duplicate payment or cancel the second invoice.",
    "R06": "Raise the service invoice from the recorded service events.",
    "R07": "Issue the late-delivery credit before the customer finds it.",
    "F01": "Quarantine the held batch and confirm the shipment was stopped or recalled.",
    "F02": "Review the yield variance and correct the costing or the invoice.",
    "F03": "Write the stock off against the batch record and check open demand first.",
}


@dataclass
class DigestSection:
    heading: str
    lines: list[str]


@dataclass
class Digest:
    week_start: str
    at_risk_minor: int
    recovered_this_week_minor: int
    open_count: int
    sections: list[DigestSection]


def _gbp(minor: int) -> str:
    return f"GBP {minor / 100:,.2f}"


def _exception_line(record: ExceptionRecord) -> str:
    owner = f", owner {record.owner}" if record.owner else ""
    return f"[E{record.id}] {record.rule_id} {_gbp(record.amount_minor)} ({record.status}{owner}): {record.formula}"


def _action_lines(records: list[ExceptionRecord]) -> list[str]:
    rules_in_play = sorted({r.rule_id for r in records})
    return [
        f"{rule}: {RULE_ACTIONS.get(rule, 'Investigate and assign an owner.')}"
        for rule in rules_in_play
    ]


def build_digest(inputs: DigestInputs) -> Digest:
    at_risk = sum(r.amount_minor for r in inputs.open_items)
    sections: list[DigestSection] = []

    if inputs.raised_this_week:
        sections.append(
            DigestSection(
                heading="New exceptions this week",
                lines=[_exception_line(r) for r in inputs.raised_this_week],
            )
        )

    if inputs.open_items:
        top = inputs.open_items[:5]
        sections.append(
            DigestSection(
                heading="Where the money sits (top open exceptions)",
                lines=[_exception_line(r) for r in top],
            )
        )
        sections.append(
            DigestSection(
                heading="Recommended actions",
                lines=_action_lines(inputs.open_items),
            )
        )
    else:
        sections.append(
            DigestSection(heading="Open exceptions", lines=["None. The seams are quiet."])
        )

    if inputs.resolved_this_week:
        recovered = sum(r.amount_minor for r in inputs.resolved_this_week)
        sections.append(
            DigestSection(
                heading="Resolved this week",
                lines=[
                    f"{len(inputs.resolved_this_week)} exceptions resolved, {_gbp(recovered)} priced"
                ]
                + [_exception_line(r) for r in inputs.resolved_this_week],
            )
        )

    if inputs.accepted_risk_items:
        sections.append(
            DigestSection(
                heading="Accepted risk on the books",
                lines=[_exception_line(r) for r in inputs.accepted_risk_items],
            )
        )

    return Digest(
        week_start=inputs.week_start.isoformat(),
        at_risk_minor=at_risk,
        recovered_this_week_minor=inputs.recovered_this_week_minor,
        open_count=len(inputs.open_items),
        sections=sections,
    )
