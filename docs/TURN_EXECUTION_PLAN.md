# Helix Turn-by-Turn Execution Plan

## Purpose
This document defines the delivery unit for implementation work on
`docs/RISK_MITIGATION_PLAN.md`.

Rule:
1. One turn should map to one focused implementation target.
2. One turn should end with one commit message.
3. Every turn should pass quality gates before completion.

## Working Unit Per Turn
Each turn follows this cycle:
1. Select one target from this document.
2. Implement only the scoped changes for that target.
3. Update specs/docs if behavior or format changes.
4. Run quality gates (`ruff`, `pytest`).
5. Commit with the planned message.
6. Report results and next turn.

## Commit Convention
Use one commit per turn with this format:
- `type(scope): short summary`

Recommended `type` values:
- `feat`, `fix`, `docs`, `test`, `perf`, `chore`

## Turn Plan
| Turn | Risk / Ticket | Scope | Main Deliverables | Commit Message (Suggested) |
|---|---|---|---|---|
| 0 | Baseline | Stabilize current working tree before mitigation sequence | Cleanup status, ensure tests/lint green | `chore: stabilize baseline before risk-mitigation sequence` |
| 1 | R-01 / HLX-R01-1 | Strict restoration verification | `verify --strict`, tests for strict mode | `feat(verify): add strict reconstruction verification mode` |
| 2 | R-01 / HLX-R01-2 | Genome backup and restore flow | `genome snapshot/restore` CLI + tests + README runbook | `feat(genome): add snapshot and restore commands` |
| 3 | R-02 / HLX-R02-1 | Cryptographic integrity extension | Section SHA-256 in seed integrity + parser checks + tests | `feat(format): add section sha256 integrity checks` |
| 4 | R-02 / HLX-R02-2 | Signature verification (optional) | Signature section, `verify --require-signature`, test vectors | `feat(verify): add optional seed signature verification` |
| 5 | R-03 / HLX-R03-1 | Seed encryption support | `--encrypt` encode/decode flow + tests | `feat(security): add optional seed encryption flow` |
| 6 | R-03 / HLX-R03-2 | Metadata minimization and warnings | `--manifest-private`, publish warning path, threat-model docs | `feat(security): add private-manifest mode and publish warnings` |
| 7 | R-04 / HLX-R04-1,2 | IPFS reliability hardening | fetch retry/backoff, optional fallback, `pin-health` command | `feat(ipfs): add retry logic and pin health checks` |
| 8 | R-05 / HLX-R05-1 | Operational diagnostics | `helix doctor`, error codes, troubleshooting docs | `feat(ops): add doctor command and actionable error codes` |
| 9 | R-06 / HLX-R06-1 | Compatibility governance | fixture-based compatibility tests, policy docs | `test(format): add compatibility fixture regression coverage` |
| 10 | R-07 / HLX-R07-1 | Performance regression guardrails | benchmark gate scripts and CI guidance | `perf(ci): add benchmark gates for dedup and throughput` |
| 11 | R-08 / HLX-R08-1 | Packaging and pricing draft | OSS vs paid feature matrix and GTM notes | `docs(product): define packaging and pricing draft` |

## Progress Markers
Completed turns:
- [x] Turn 1: `feat: add strict verify mode for full reconstruction checks` (`c4dcfec`)
- [x] Turn 2: `feat: add genome snapshot and restore commands` (`055aa46`)
- [x] Turn 3: `feat: add section sha256 integrity checks to HLX1` (`444f13f`)
- [x] Turn 4: `feat: add optional seed signature verification`
- [x] Turn 5: `feat: add optional seed encryption flow`
- [x] Turn 6: `feat(security): add private-manifest mode and publish warnings`
- [x] Turn 7: `feat(ipfs): add retry logic and pin health checks`
- [x] Turn 8: `feat(ops): add doctor command and actionable error codes`
- [x] Turn 9: `test(format): add compatibility fixture regression coverage`

Pending turns:
- [ ] Turn 10
- [ ] Turn 11

## Definition of Done (Per Turn)
A turn is complete only when all are true:
1. Scoped implementation is done.
2. Related tests are added/updated and passing.
3. Docs are updated if behavior/spec changed.
4. `ruff check .` passes.
5. `pytest` passes.
6. Commit is created with the planned message.

## Operating Rule for Future Work
Before starting any implementation turn:
1. Read this file.
2. Read `docs/RISK_MITIGATION_PLAN.md`.
3. Execute exactly one turn scope unless explicitly instructed otherwise.
