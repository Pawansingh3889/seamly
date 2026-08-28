"""Ingest repository: the only file I/O in the ingest module."""

from __future__ import annotations

from pathlib import Path

from seamly.modules.ingest.service import OPTIONAL_FILES, REQUIRED_FILES


def read_source_texts(fixture_dir: Path) -> dict[str, str]:
    missing = [n for n in REQUIRED_FILES if not (fixture_dir / n).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing source files under {fixture_dir}: {missing}. Check SEAMLY_FIXTURE_DIR."
        )
    texts = {name: (fixture_dir / name).read_text() for name in REQUIRED_FILES}
    for name in OPTIONAL_FILES:
        path = fixture_dir / name
        if path.exists():
            texts[name] = path.read_text()
    return texts
