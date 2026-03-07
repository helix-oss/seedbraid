# Helix Risk Mitigation Plan

## Scope
This document turns Helix risk findings into prioritized, executable plans.

Execution tracking:
- Turn-level delivery and commit sequence are defined in `docs/TURN_EXECUTION_PLAN.md`.

Baseline assumptions:
- HLX1 + CDC + Genome + IPFS publish/fetch are already implemented.
- This plan prioritizes lossless restoration and operational reliability first.

## Prioritization Method
Priority is based on:
- Impact: effect on data safety, security, and production continuity.
- Likelihood: probability under normal operator behavior.
- Detectability: how quickly operators notice and recover.

Priority scale:
- P0: immediate execution, blocks reliable production use.
- P1: next wave, materially reduces operational incidents.
- P2: strategic hardening and long-term OSS sustainability.

## Risk Register and Mitigation Summary
| ID | Priority | Risk | Primary Control | Success KPI |
|---|---|---|---|---|
| R-01 | P0 | Unrecoverable restoration due to missing genome | strict verify + genome snapshot/restore | 100% restore success in DR drills |
| R-02 | P0 | Weak tamper resistance (CRC-centric) | section SHA-256 + optional signature | 100% tamper detection rate |
| R-03 | P0 | Information leakage on seed publication | encryption + manifest minimization | Decryption impossible without key; metadata exposure minimized |
| R-04 | P1 | Retrieval failure despite valid CID | pin strategy + fetch retry/fallback | Fetch success rate >= 99.9% |
| R-05 | P1 | Operational failures due to environment differences | helix doctor + actionable errors | 50% reduction in initial triage time |
| R-06 | P1 | Future backward-compatibility breakage | compatibility policy + fixture tests | Legacy seed regression tests always green |
| R-07 | P2 | Performance/cost degradation | benchmark gates + storage tuning | Auto-detection of threshold-violating PRs |
| R-08 | P2 | Insufficient OSS sustainability | support/donation guidance + maintainer workflow | Sustainability metrics visible |

## Detailed Mitigation Plans

### R-01 (P0) Unrecoverable restoration due to missing genome
Objective:
- Prevent decode failures caused by missing referenced chunks.

Implementation plan:
1. Add `helix verify --strict` mode that must reconstruct and SHA-256 match.
2. Add `helix genome snapshot` and `helix genome restore` commands.
3. Record genome identity metadata in manifest for non-portable seeds.
4. Add DR test suite: missing chunk, full restore, hash-verified decode.

Deliverables:
- New CLI commands and tests.
- Runbook section in `README.md` with backup/restore workflow.

Acceptance criteria:
- Simulated loss of genome can be recovered from snapshot with zero data loss.

### R-02 (P0) Insufficient tamper resistance
Objective:
- Strengthen seed tamper detection beyond CRC.

Implementation plan:
1. Extend integrity section with per-section SHA-256 digests.
2. Add optional signature section (Ed25519).
3. Add key management docs and `verify --require-signature` option.
4. Add tamper test vectors for modified section payloads and swapped sections.

Deliverables:
- Updated `docs/FORMAT.md` and parser.
- Verification options and test vectors.

Acceptance criteria:
- Any modified section causes verification failure in cryptographic mode.

### R-03 (P0) Confidentiality risk
Objective:
- Reduce plaintext leakage when sharing/publishing seeds.

Implementation plan:
1. Add optional seed payload encryption (`--encrypt`).
2. Add private-manifest mode (`--manifest-private`) to minimize metadata.
3. Add warning path in `publish` when unencrypted seed is published.
4. Document policy profiles: internal-only, partner-share, public-distribution.

Deliverables:
- Encryption format extension and CLI options.
- Updated threat model and operator guidance.

Acceptance criteria:
- Encrypted seed cannot be decoded without key material.

### R-04 (P1) IPFS availability
Objective:
- Improve retrieval reliability across nodes and time.

Implementation plan:
1. Promote pin-first workflow and multi-node pin policy.
2. Add `helix pin-health <cid>` checks.
3. Add `fetch` retry/backoff and optional gateway fallback.
4. Add periodic CID health checks in operations guide.

Deliverables:
- New health command and resilient fetch behavior.
- Updated README operational section.

Acceptance criteria:
- Controlled outage simulation still meets fetch success target.

### R-05 (P1) Operational failure rate
Objective:
- Make failures self-diagnosable for non-expert operators.

Implementation plan:
1. Add `helix doctor` to inspect ipfs CLI, IPFS_PATH, genome path, write perms, compression support.
2. Standardize error codes and next-action messages.
3. Add troubleshooting matrix in README.

Deliverables:
- Doctor command output schema.
- Error catalog document.

Acceptance criteria:
- Top 10 failure scenarios are diagnosable from doctor + one command.

### R-06 (P1) Compatibility management
Objective:
- Avoid accidental breakage of existing seeds when evolving format.

Implementation plan:
1. Add compatibility policy to `docs/FORMAT.md` and `docs/DESIGN.md`.
2. Freeze fixture seeds for regression tests.
3. Require migration command for any breaking format change.

Deliverables:
- Compatibility policy sections.
- Fixture-based CI tests.

Acceptance criteria:
- Historical fixtures continue parsing and verifying in CI.

### R-07 (P2) Performance/cost
Objective:
- Keep dedup ratio and throughput stable as code evolves.

Implementation plan:
1. Add benchmark gates for throughput, dedup ratio, seed size.
2. Tune SQLite defaults and maintenance recommendations.
3. Add chunking presets for workload classes.

Deliverables:
- Benchmark scripts integrated in CI workflow.
- Performance baseline report.

Acceptance criteria:
- PRs exceeding regression budget are blocked.

### R-08 (P2) OSS sustainability risk
Objective:
- Define a sustainable OSS support boundary without restricting OSS core.

Implementation plan:
1. Define support channels and maintainer operation model for OSS users.
2. Publish donation/sponsorship guidance and contribution expectations.
3. Track adoption + support signals to prioritize maintenance work.

Deliverables:
- Support/donation guidance draft.
- Maintainer support workflow and triage rubric.

Acceptance criteria:
- Approved support plan with measurable sustainability hypotheses.

## Execution Roadmap
### Phase A (Weeks 1-3)
- Execute R-01, R-02, R-03.
- Outcome target: restoration safety and tamper/confidentiality baseline.

### Phase B (Weeks 4-6)
- Execute R-04, R-05, R-06.
- Outcome target: operations reliability and compatibility governance.

### Phase C (Weeks 7-9)
- Execute R-07, R-08.
- Outcome target: scalable performance management and OSS sustainability readiness.

## Suggested Engineering Tickets
| Ticket | Risk | Type | Estimate | Definition of Done |
|---|---|---|---|---|
| HLX-R01-1 | R-01 | CLI + codec | M | strict verify and failing fixtures merged |
| HLX-R01-2 | R-01 | storage ops | M | snapshot/restore commands + docs |
| HLX-R02-1 | R-02 | format | M | section SHA-256 serialized and verified |
| HLX-R02-2 | R-02 | crypto | M | optional signature verify passes tests |
| HLX-R03-1 | R-03 | crypto | L | encryption/decryption path integrated |
| HLX-R03-2 | R-03 | docs | S | threat policy profiles published |
| HLX-R04-1 | R-04 | ipfs | M | fetch retry/fallback + tests |
| HLX-R04-2 | R-04 | ipfs | S | pin-health command output validated |
| HLX-R05-1 | R-05 | diagnostics | M | doctor command with checks and codes |
| HLX-R06-1 | R-06 | test | S | compatibility fixtures in CI |
| HLX-R07-1 | R-07 | perf | M | benchmark thresholds enforced |
| HLX-R08-1 | R-08 | docs | M | support/donation guidance approved |

## Governance and Review Cadence
- Weekly risk review: status, blockers, KPI trend.
- Biweekly architecture review: format/compatibility and security deltas.
- Monthly DR drill: restore, verify, and publish/fetch reliability drill.
