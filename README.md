# Seamly

> Intelligence at the seams between your systems.

Mid-market UK companies run finance in one system and operations in another:
orders in the ERP, deliveries in the haulier's records, project work in a
spreadsheet. Money leaks in the gaps, and most companies cannot say how much.

Seamly sits above the existing systems, reconciles what each one claims
against the others, prices every disagreement in pounds from the contract
price book, routes it to a named owner, and answers leadership's questions
with citations back to the records. It replaces nothing; it watches
everything.

## Status

Foundation phase. The first slice loads a synthetic UK mid-market dataset
(ERP orders and invoices, haulier deliveries, service work), runs the
reconciliation rule pack, prices every exception from the price book, and
serves a CFO board with drill-down to the underlying records.

See [ARCHITECTURE.md](ARCHITECTURE.md) before touching the code, and
[PROBLEM.md](PROBLEM.md) for the market hypothesis this build is testing.

## Quick start

```bash
uv sync              # or: make setup
make db-up           # Postgres 16 on localhost:5433 (podman-compose)
make migrate         # schema + append-only audit trigger
make serve           # http://localhost:8010
```

## Run the demo

```bash
make demo            # db + migrations + auto-seeded server on :8010
```

Open http://localhost:8010, click **Enter the demo as CFO**. The board
opens seeded with a synthetic UK manufacturer: 7 exceptions, 15,110
pounds at risk. Mangled the data mid-demo? `make demo-reset` wipes and
reseeds. Switch the demo to the food vertical with
`SEAMLY_FIXTURE_DIR=data/fixtures/food make demo` (10 exceptions,
95,405 pounds, including a rejected batch shipped after its hold).

### The 60-second walkthrough

1. Board: money at risk, top exceptions, at-risk by rule and by customer.
2. Drill into a customer, then an exception: every pound shows its
   arithmetic and the exact records behind it.
3. Assign it to an owner, resolve it with a credit note: the recovery
   total moves. The weekly digest writes itself from the same store.
4. Ask the analyst a question: answers cite the exceptions they used,
   and figures are verified against the data or the answer is discarded.

## Tests and gates

```bash
make test            # full suite, SQLite in-memory, no daemon needed
make gate            # lint, types, size guard, doc freshness, analyst eval
make demo-reset      # wipe and reseed the demo data
```

## Layout

```
src/seamly/
├── app.py            composition root, the only place both adapters meet
├── engine.py         in-process event bus: route, permit, audit
├── common/           types, errors, db plumbing
├── modules/
│   ├── ingest/       source adapters, validation, identity resolution
│   ├── ledger/       canonical model: orders, deliveries, invoices, price book
│   ├── reconcile/    matching rules, pure, no I/O
│   ├── scoring/      pound-impact rules, pure, no I/O
│   ├── exception/    exception store, ownership, recovery ledger
│   ├── analyst/      read-only Q&A over exceptions, citation-verified
│   ├── auth/         sessions and roles
│   └── audit/        append-only audit log, enforced in the database
├── api/              JSON adapter (/api/v1)
└── ui/               HTML adapter (Jinja2, no build step)
data/fixtures/        synthetic datasets with planted discrepancies
docs/domain/          rule packs: general order-to-cash, food vertical
docs/discovery/       UK market interview template and notes
```

## The rules that make it trustworthy

- The engine computes, the LLM narrates. No pound figure is ever generated
  by a model; every figure is a deterministic formula over named records and
  the price book.
- Every exception carries the records that triggered it and the arithmetic
  that priced it. Drill-down is a trust feature, not navigation.
- The audit log cannot be updated or deleted, by any role, enforced by a
  database trigger and missing grants, not by promises.
- CSV-first is the product strategy: most mid-market revenue is still
  managed in spreadsheets, so that is where onboarding starts.
