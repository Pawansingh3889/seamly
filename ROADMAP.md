# Seamly — Roadmap

> **Last updated:** 28 August 2026
> **Update rule:** updated with every structural change, together with
> ARCHITECTURE.md.

Position: product foundation first; the Tata Varsity Pitch submission
(18 October 2026) is a milestone of the product, not the goal. The first
product slice doubles as the competition demo.

## Phase 1 — Foundation (current)

Repo, contracts, fixtures, and the deterministic core:

- [x] Skeleton, docs, project config
- [ ] Canonical schema and migrations, append-only audit trigger
- [ ] Generic UK mid-market fixtures with planted discrepancies
- [ ] ingest: CSV adapters, validation, identity resolution
- [ ] reconcile: rule pack R01-R07 over typed rows
- [ ] scoring: pound-impact from the contract price book
- [ ] exception store with status, owner, recovery ledger
- [ ] golden tests: fixtures to priced exceptions, engine to audit rows

## Phase 2 — Loop and board

- [ ] CFO board: enterprise pound-at-risk, top exceptions, recovery YTD
- [ ] Drill-down: board to business unit to customer/order to records
- [ ] Ops worklist: today's exceptions by owner
- [ ] Weekly digest generated from the recovery ledger
- [ ] JSON API parity for the same capabilities

## Phase 3 — Analyst

- [ ] Retrieval over exceptions and records
- [ ] Narration with mandatory citations
- [ ] Deterministic verifier: citations resolve, numbers match the store
- [ ] LLM endpoint behind config (local or hosted)

## Phase 4 — Competition milestone (18 October 2026)

- [ ] 60-second video: question to cited answer to priced exceptions
- [ ] Form answers in the six-question judging structure
- [ ] Submitted on the Simply Do platform with buffer time

## Phase 5 — Discovery (parallel)

- [ ] 10-15 interviews: UK mid-market CFOs, finance managers, ops leads
- [ ] Findings logged in docs/discovery/, PROBLEM.md updated
- [ ] Rule pack priorities adjusted to the verified bottleneck

## Phase 6 — Verticals and connectors (post-October)

- [ ] Food vertical pack polished (batches, yields, rejected batches)
- [ ] Sage/Xero/NetSuite connectors behind the same adapter interface
- [ ] GS1 EPCIS 2.0 event emission for traceability-linked verticals
- [ ] Digital Product Passport generation on the open-dpp/Tractus-X model
