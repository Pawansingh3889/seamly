"""Scoring module: deterministic pounds. The LLM never touches this path."""

from __future__ import annotations

from seamly.modules.scoring import service as service

PERMISSIONS: dict[str, set[str]] = {}
