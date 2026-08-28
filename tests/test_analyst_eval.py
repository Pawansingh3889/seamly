"""The eval set runs as part of the suite too, so a red eval blocks CI twice."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_eval_module():
    spec = importlib.util.spec_from_file_location(
        "eval_analyst", REPO_ROOT / "scripts" / "eval_analyst.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_analyst"] = module
    spec.loader.exec_module(module)
    return module


def test_analyst_eval_set_is_green():
    module = _load_eval_module()
    assert module.run_eval() == []


def test_eval_set_covers_both_figure_spellings():
    """The GBP-without-pound-sign escape hatch must stay covered."""

    module = _load_eval_module()
    responses = " ".join(case.response for case in module.CASES)
    assert "£" in responses
    assert "GBP " in responses
