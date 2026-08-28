"""Ingest repository: the only file I/O in the ingest module."""

from __future__ import annotations

from pathlib import Path

from seamly.modules.ingest.service import REQUIRED_FILES


def read_source_texts(fixture_dir: Path) -> dict[str, str]:
    missing = [n for n in REQUIRED_FILES if not (fixture_dir / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing source files under {fixture_dir}: {missing}. Check SEAMLY_FIXTURE_DIR."
        )
    return {name: (fixture_dir / name).read_text() for name in REQUIRED_FILES}
