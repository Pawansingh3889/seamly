"""End-to-end smoke test: real app, real HTTP, SQLite on disk.

Exercises login, the ingest-to-reconcile pipeline, the summary, the
exception loop and the analyst boundary, exactly as a user would.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'smoke.db'}"
    monkeypatch.setenv("SEAMLY_DATABASE_URL", db_url)
    monkeypatch.setenv("SEAMLY_SESSION_SECRET", "test-secret")
    # The journey drives ingest and reconcile itself; auto-seed would skip them.
    monkeypatch.setenv("SEAMLY_AUTO_SEED", "0")
    from seamly.app import create_app
    from seamly.common.db import Base, make_engine
    from seamly.config import get_settings

    get_settings.cache_clear()

    async def create_tables() -> None:
        engine = make_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_tables())
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_auto_seed_populates_a_fresh_boot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """With auto-seed on (the default), a fresh boot lands on a populated board."""

    monkeypatch.setenv("SEAMLY_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'auto.db'}")
    monkeypatch.setenv("SEAMLY_SESSION_SECRET", "test-secret")
    from seamly.app import create_app
    from seamly.common.db import Base, make_engine
    from seamly.config import get_settings

    get_settings.cache_clear()

    async def create_tables() -> None:
        engine = make_engine(f"sqlite+aiosqlite:///{tmp_path / 'auto.db'}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_tables())
    with TestClient(create_app()) as fresh:
        summary = fresh.get("/api/v1/summary").json()
        assert summary["total_at_risk_minor"] == 1_511_000
        assert summary["open_exceptions"] == 7
    get_settings.cache_clear()


def _post(client: TestClient, path: str, payload: dict | None = None) -> dict:
    response = client.post(path, json={"payload": payload or {}})
    assert response.status_code == 200, response.text
    return response.json()


def test_full_journey(client: TestClient):
    health = client.get("/api/v1/health").json()
    assert health["role"] == "anonymous"

    _post(
        client,
        "/api/v1/login",
        {"email": "cfo@kestrel.example", "password": "demo-secret"},
    )
    assert client.get("/api/v1/health").json()["role"] == "cfo"

    # Anonymous cannot run the pipeline; the CFO can.
    fresh_client = TestClient(client.app)
    forbidden = fresh_client.post("/api/v1/ingest/run", json={"payload": {}})
    assert forbidden.status_code == 400
    assert forbidden.json()["detail"]["code"] == "engine.forbidden"

    ingest = _post(client, "/api/v1/ingest/run")
    assert ingest["ok"]

    reconcile = _post(client, "/api/v1/reconcile/run")
    assert reconcile["new_exceptions"] == 7

    summary = client.get("/api/v1/summary").json()
    assert summary["total_at_risk_minor"] == 1_511_000
    assert summary["open_exceptions"] == 7

    exceptions = client.get("/api/v1/exceptions").json()
    assert len(exceptions) == 7
    top = exceptions[0]
    assert top["amount_minor"] == 487_500  # the R05 duplicate, GBP 4,875.00
    assert "GBP" in top["formula"]

    detail = client.get(f"/exceptions/{top['id']}")
    assert detail.status_code == 200

    assigned = _post(client, f"/api/v1/exceptions/{top['id']}/assign", {"owner": "R. Poon"})
    assert assigned["owner"] == "R. Poon"

    resolved = _post(
        client,
        f"/api/v1/exceptions/{top['id']}/resolve",
        {"amount_minor": 487_500, "evidence": "credit note CN-101"},
    )
    assert resolved["recovered_minor"] == 487_500

    summary = client.get("/api/v1/summary").json()
    assert summary["total_recovered_minor"] == 487_500
    assert summary["total_at_risk_minor"] == 1_511_000 - 487_500

    analyst = client.post(
        "/api/v1/analyst/ask", json={"payload": {"question": "why is revenue down?"}}
    )
    assert analyst.status_code == 400
    assert analyst.json()["detail"]["code"] == "analyst.not_configured"

    by_customer = client.get("/api/v1/summary/by-customer").json()
    amounts = {row["customer_name"]: row["amount_minor"] for row in by_customer}
    assert amounts["Calder Engineering Ltd"] == 682_500 - 487_500  # duplicate resolved above

    digest = client.get("/api/v1/digest").json()
    assert digest["ok"]
    assert digest["recovered_this_week_minor"] == 487_500
    headings = [section["heading"] for section in digest["sections"]]
    assert "Recommended actions" in headings

    customer_page = client.get("/customers/3")
    assert customer_page.status_code == 200
    digest_page = client.get("/digest")
    assert digest_page.status_code == 200

    board = client.get("/")
    assert board.status_code == 200
    assert "15,110.00" not in board.text  # the top one is resolved; verify the page renders
    assert "10,235.00" in board.text  # 1,023,500 pence remaining
