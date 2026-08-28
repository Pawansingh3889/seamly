"""Structural guard: living docs must carry a recent Last updated date.

Docs with stale dates drift from the code they describe; the guard makes
staleness loud rather than polite.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

GUARDED_DOCS = ("ARCHITECTURE.md", "ROADMAP.md", "PROBLEM.md")
HEADER_DATE = re.compile(r"Last updated:\*{0,2}\s*(\d{1,2} \w+ \d{4})")
MAX_AGE_DAYS = 30


def parse_header_date(text: str) -> date | None:
    match = HEADER_DATE.search(text)
    if match is None:
        return None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            from datetime import datetime

            return datetime.strptime(match.group(1), fmt).date()
        except ValueError:
            continue
    return None


def check_docs(
    root: Path, today: date | None = None, max_age_days: int = MAX_AGE_DAYS
) -> list[str]:
    today = today or date.today()
    cutoff = today - timedelta(days=max_age_days)
    violations: list[str] = []
    for name in GUARDED_DOCS:
        path = root / name
        if not path.exists():
            violations.append(f"{name}: missing, but the guard requires it")
            continue
        parsed = parse_header_date(path.read_text())
        if parsed is None:
            violations.append(f"{name}: no 'Last updated: DD Month YYYY' header line")
        elif parsed < cutoff:
            violations.append(
                f"{name}: dated {parsed.isoformat()}, older than {max_age_days} days; update it or justify keeping it"
            )
    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    violations = check_docs(root)
    for violation in violations:
        print(f"DOC FRESHNESS FAIL: {violation}")
    if not violations:
        print("doc freshness ok: all guarded docs carry a recent date")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
