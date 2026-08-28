"""Vercel serverless entry: exposes the Seamly ASGI app.

The repo is a src-layout package, so the source tree is added to sys.path
here; on Vercel the whole project is bundled into the function and the
function directory is api/, which sits one level below the repo root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from seamly.app import create_app

app = create_app()
