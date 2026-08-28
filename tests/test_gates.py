"""Gate-proof: every guard is proven to reject a planted violation.

A gate that has never been observed to fail is decoration.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_size_guard_rejects_an_oversized_file(tmp_path: Path):
    guard = load_script("check_module_size")
    big = tmp_path / "src" / "big.py"
    big.parent.mkdir(parents=True)
    big.write_text("\n".join(f"x{i} = {i}" for i in range(500)))
    violations = guard.check_tree(tmp_path, cap=400)
    assert any("big.py" in v for v in violations)
    assert guard.check_tree(tmp_path, cap=1000) == []


def test_size_guard_accepts_the_current_repo():
    guard = load_script("check_module_size")
    assert guard.check_tree(REPO_ROOT) == []


def test_doc_freshness_rejects_a_stale_doc(tmp_path: Path):
    guard = load_script("check_doc_freshness")
    today = date(2026, 8, 28)
    for name in guard.GUARDED_DOCS:
        (tmp_path / name).write_text("# Doc\n\n> Last updated: 1 January 2026\n")
    violations = guard.check_docs(tmp_path, today=today)
    assert len(violations) == 3
    for name in guard.GUARDED_DOCS:
        (tmp_path / name).write_text(f"# Doc\n\n> Last updated: {today.strftime('%d %B %Y')}\n")
    assert guard.check_docs(tmp_path, today=today) == []


def test_doc_freshness_rejects_a_missing_header(tmp_path: Path):
    guard = load_script("check_doc_freshness")
    for name in guard.GUARDED_DOCS:
        header = (
            "No header here.\n"
            if name == "PROBLEM.md"
            else f"> Last updated: {date(2026, 8, 28).strftime('%d %B %Y')}\n"
        )
        (tmp_path / name).write_text(f"# Doc\n\n{header}")
    violations = guard.check_docs(tmp_path, today=date(2026, 8, 28))
    assert len(violations) == 1
    assert "no 'Last updated" in violations[0]


def test_doc_freshness_current_repo_is_fresh():
    guard = load_script("check_doc_freshness")
    assert guard.check_docs(REPO_ROOT) == []


@pytest.mark.parametrize("doc", ["ARCHITECTURE.md", "ROADMAP.md", "PROBLEM.md"])
def test_guarded_docs_exist(doc: str):
    assert (REPO_ROOT / doc).exists()
