.PHONY: help setup db-up db-down migrate serve demo demo-reset test lint fmt typecheck guards eval gate gate-proof clean

PY := uv run

help:
	@echo "make setup      Install dependencies"
	@echo "make db-up      Start Postgres (podman-compose)"
	@echo "make db-down    Stop Postgres"
	@echo "make migrate    Apply alembic migrations"
	@echo "make serve      Run the dev server on :8010"
	@echo "make demo       db + migrations + auto-seeded server (demo mode)"
	@echo "make demo-reset Wipe and reseed the demo data"
	@echo "make test       Run the test suite"
	@echo "make lint       ruff check + format check"
	@echo "make fmt        ruff format + fix"
	@echo "make typecheck  mypy strict"
	@echo "make guards     structural guards (size, doc freshness)"
	@echo "make eval        analyst eval set (verifier + prompt regression)"
	@echo "make gate        everything CI runs"
	@echo "make gate-proof prove each guard rejects a planted violation"

setup:
	uv sync

db-up:
	podman-compose up -d
	@until podman exec seamly-db pg_isready -U seamly -q; do sleep 0.5; done
	@echo "postgres ready on :5433"

db-down:
	podman-compose down

migrate:
	$(PY) alembic upgrade head

serve:
	$(PY) uvicorn seamly.app:create_app --factory --reload --port 8010

demo: db-up migrate
	@echo "Demo boots seeded: log in as cfo@kestrel.example / demo-secret"
	$(MAKE) serve

demo-reset: db-up
	$(PY) python scripts/seed_demo.py

test:
	$(PY) pytest

lint:
	$(PY) ruff check src tests scripts
	$(PY) ruff format --check src tests scripts

fmt:
	$(PY) ruff format src tests scripts
	$(PY) ruff check --fix src tests scripts

typecheck:
	$(PY) mypy

guards:
	$(PY) python scripts/check_module_size.py
	$(PY) python scripts/check_doc_freshness.py

eval:
	$(PY) python scripts/eval_analyst.py

gate: lint typecheck test guards eval
	@echo ""
	@echo "All gates passed."

gate-proof:
	$(PY) pytest tests/test_gates.py -v

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
