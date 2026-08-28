# Seamly — Architecture

> **Last updated:** 28 August 2026
> **Update rule:** this file is updated with every structural change
> (mechanised by `scripts/check_doc_freshness.py`).

## 1. Helicopter view

Seamly is a **monolith with enforced seams**. One FastAPI process, one
Postgres, two thin adapters (JSON and HTML) over one set of modules, an
in-process engine wiring them together. The name is the architecture: the
product sits at the seams between a company's existing systems, and the
codebase is built along the same lines, seams that provably hold so the
monolith can split later if it must.

It exists to find the money leaking between finance systems and operations
systems at UK mid-market companies, price every leak in pounds, and drive it
to resolution.

```
                ┌────────────────────────────────────────┐
                │  seamly.app  (composition root)        │
                └────────┬──────────────────┬────────────┘
                ┌────────▼───────┐  ┌───────▼────────┐
                │ seamly.api     │  │ seamly.ui      │  two adapters,
                │ JSON, /api/v1  │  │ Jinja2 + HTMX  │  never importing
                └────────┬───────┘  └───────┬────────┘  each other
                         └────────┬─────────┘
                          ┌───────▼───────┐
                          │    engine     │  route, permit, audit
                          └───────┬───────┘
        ┌──────────┬──────────┬───┴──────┬──────────┬──────────┐
  ┌─────▼────┐ ┌───▼─────┐ ┌──▼──────┐ ┌─▼───────┐ ┌▼────────┐ ┌▼───────┐
  │  ingest  │ │ ledger  │ │reconcile│ │ scoring │ │exception│ │  auth  │
  └──────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └────────┘
        (later phases: analyst, connectors)
                ┌────────────────────────┐
                │  audit  │  common      │
                └────────────────────────┘
```

## 2. The two-adapter rule

Every capability is exposed twice from one service layer: a JSON route under
`/api/v1` and an HTML route rendered server-side. Both call
`engine.dispatch()`; neither holds logic. The HTML adapter is the product
today; the JSON adapter is the same product for any future consumer.
Deleting `ui/` must never require touching a module.

## 3. Module contract

One module = one business capability, four files:

```
modules/<name>/
├── __init__.py    handle(event, state) -> Result; PERMISSIONS dict
├── contract.py    typed dataclasses; no secrets (guarded)
├── service.py     pure rules; no I/O (import contract enforced)
└── repository.py  all I/O; owns its tables on the shared metadata
```

| Module    | Owns | Notes |
|-----------|------|-------|
| ingest    | source run tracking, row validation, identity resolution | adapters for CSV first; source schemas exist only here |
| ledger    | customer, contract, price_book_entry, order, order_line, delivery, delivery_line, invoice, invoice_line, service_event | the canonical model; nothing downstream may bypass it |
| reconcile | exception drafts | matching rules are pure functions over typed rows |
| scoring   | priced exceptions | every pound figure is a stored formula over named records and the price book |
| exception | exception, assignment, recovery ledger | the system of record for the loop: open, assigned, resolved, recovered |
| analyst   | Q&A sessions, answers | phase 2; LLM narration over retrieval, citation-verified, never computes figures |
| auth      | user_account, session | roles: ops, analyst, cfo, admin |
| audit     | audit_log | append-only, DB-enforced, see §5 |

## 4. The engine

In-process event bus. Routes `<module>.<action>` events, checks the
permission the module declared, appends to the audit trail, and isolates
module crashes: an unhandled exception returns `Result.err` instead of
unwinding anyone else's stack.

## 5. The audit log is append-only

Enforced twice, not promised once: a Postgres trigger raises on UPDATE and
DELETE for every role, and the application role never receives those grants
at all. The migration is the source of truth. `make gate` proves the
application-level half; pg-marked probes prove the database half.

## 6. The compute/narrate boundary

The reconciliation and scoring path is fully deterministic. The analyst
(phase 2) may only narrate what the engine computed: it retrieves exceptions
and records, and its output is verified by a deterministic checker that
requires every citation to resolve and every number quoted to match the
stored figures. A model never prices a leak.

## 7. Rules and their mechanisms

| # | Rule | Enforced by |
|---|------|-------------|
| 7.1 | No module imports a sibling | import-linter independence contract |
| 7.2 | No I/O in service.py | import-linter forbidden contract on httpx/sqlalchemy-engine use in services |
| 7.3 | No module larger than 400 lines | `scripts/check_module_size.py` |
| 7.4 | ARCHITECTURE.md and ROADMAP.md updated with structural change | `scripts/check_doc_freshness.py` |
| 7.5 | No silent failure; errors carry a code and an actionable message | `Result.err` requires a message |
| 7.6 | Fixtures over literals in tests | review |

## 8. Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 async | team default stack |
| Database | Postgres 16 (podman-compose, host port 5433) | append-only audit needs triggers and grants; SQLite cannot express them |
| Tests | pytest, SQLite in-memory for logic, pg-marked probes for DB mechanisms | fast by default, honest where the database is the mechanism |
| Frontend | Jinja2, no build step | server-rendered, demo-robust offline |
| Migrations | Alembic (async) | hand-written where DDL carries policy |
| CI | `make gate` | same command locally and in CI |
