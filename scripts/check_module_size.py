"""Structural guard: no source file larger than the size cap."""

from __future__ import annotations

import sys
from pathlib import Path

CAP_LINES = 400
SCAN_DIRS = ("src", "tests", "scripts", "alembic")


def check_tree(
    root: Path, cap: int = CAP_LINES, scan_dirs: tuple[str, ...] = SCAN_DIRS
) -> list[str]:
    violations: list[str] = []
    for scan_dir in scan_dirs:
        base = root / scan_dir
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            line_count = len(path.read_text().splitlines())
            if line_count > cap:
                violations.append(f"{path}: {line_count} lines exceeds the {cap}-line cap")
    return violations


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    violations = check_tree(root)
    for violation in violations:
        print(f"SIZE GUARD FAIL: {violation}")
    if not violations:
        print(f"size guard ok: every file within {CAP_LINES} lines")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
