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
- P2: strategic hardening and commercial readiness.

## Risk Register and Mitigation Summary
| ID | Priority | Risk | Primary Control | Success KPI |
|---|---|---|---|---|
| R-01 | P0 | Genome欠損で復元不能 | strict verify + genome snapshot/restore | DR演習で復元成功率100% |
| R-02 | P0 | CRC中心で改ざん耐性が弱い | section SHA-256 + optional signature | 改ざんケース検知率100% |
| R-03 | P0 | seed公開時の情報漏えい | encryption + manifest minimization | 鍵なし復号不可、メタ露出最小化 |
| R-04 | P1 | CIDがあっても取得不能 | pin strategy + fetch retry/fallback | fetch成功率99.9%以上 |
| R-05 | P1 | 運用環境差で失敗しやすい | helix doctor + actionable errors | 一次切り分け時間50%短縮 |
| R-06 | P1 | 将来の互換性破壊 | compatibility policy + fixture tests | 旧seed回帰テスト常時緑 |
| R-07 | P2 | 性能/コスト劣化 | benchmark gates + storage tuning | 閾値割れPRの自動検知 |
| R-08 | P2 | 商用差別化不足 | packaging/pricing + managed features | 有料PoC成約率の可視化 |

## Detailed Mitigation Plans

### R-01 (P0) Genome欠損で復元不能
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

### R-02 (P0) 改ざん耐性不足
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

### R-03 (P0) 機密性リスク
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

### R-04 (P1) IPFS可用性
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

### R-05 (P1) 運用失敗率
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

### R-06 (P1) 互換性管理
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

### R-07 (P2) 性能/コスト
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

### R-08 (P2) 商用化リスク
Objective:
- Define a monetizable product boundary without weakening OSS core.

Implementation plan:
1. Define free vs paid feature matrix.
2. Specify managed add-ons: RBAC, audit logs, SLA, policy enforcement.
3. Run structured discovery with pilot users.

Deliverables:
- Packaging/pricing draft.
- Pilot interview template and scoring rubric.

Acceptance criteria:
- Approved packaging plan with measurable GTM hypotheses.

## Execution Roadmap
### Phase A (Weeks 1-3)
- Execute R-01, R-02, R-03.
- Outcome target: restoration safety and tamper/confidentiality baseline.

### Phase B (Weeks 4-6)
- Execute R-04, R-05, R-06.
- Outcome target: operations reliability and compatibility governance.

### Phase C (Weeks 7-9)
- Execute R-07, R-08.
- Outcome target: scalable performance management and commercial readiness.

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
| HLX-R08-1 | R-08 | product | M | feature/pricing matrix approved |

## Governance and Review Cadence
- Weekly risk review: status, blockers, KPI trend.
- Biweekly architecture review: format/compatibility and security deltas.
- Monthly DR drill: restore, verify, and publish/fetch reliability drill.
