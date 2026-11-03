# Sprint 8 status (requirement matrix S8-01 to S8-14)

**Scope of this record:** the status of every Sprint 8 requirement at the current repository state. It is not a Sprint 8 completion record. WDS has not declared Sprint 8 complete, and this document does not do so.
**Credential item:** T-31 is CLOSED BY WDS MANAGEMENT ATTESTATION. No independent technical evidence is in the repository (`CREDENTIAL_EXPOSURE_RECORD_2026-11-03.md`).

Status words: **Done** means implemented and verified in this repository, with the evidence named. **Partial** means some of the requirement is verified and a named part is not. **Draft** means written but not accepted. **RED** means a mandatory dependency is absent, per the dependency matrix. **BLOCKED** means a test or step cannot be verified until a named dependency exists.

## 1. Requirement matrix

| ID | Matrix class | Status | Evidence (in repository) | Not done, and why |
|---|---|---|---|---|
| S8-01 | GREEN | **Done (document)** | `docs/governance/sprint8/S8_01_THREAT_MODEL_REGISTER.md`; independent review and re-check recorded in its history | Independent re-review of the 13 corrections not in the re-check. OPEN-11 and specialist boundaries stay UNKNOWN or NOT IN REPO by design |
| S8-02 | AMBER | **Partial** | Unit: 18 passed. Database: 10 passed, 2 BLOCKED (`tests/sprint8/test_s8_02_fail_closed_db.py`). Independent QA passed on `976f255`; fixes re-checked at `0f474b0` | Workspace read (OPEN-11) and specialist path (S6-INT) are BLOCKED. Final cross-workstream misuse tests need S6-INT |
| S8-03 | AMBER | **Partial** | Migration cycle and catalog tests: 2 passed on the dedicated cluster (this continuation). Single alembic head: `0059_int_mark_inputs_fence` (verified). Privilege audit and restricted-login negative suites exist (`tests/hardening/test_privilege_audit.py`, `tests/hardening/test_app_role_negative.py`); they were **not executed** in this continuation | Restricted-role matrix on the final schema needs OPEN-18. Production identities and secrets are not provisioned (`PRODUCTION_BOUNDARY.md` §4). Scratch-superuser grants used by the test setup are not a production configuration |
| S8-04 | AMBER | **Partial** | Redaction: `tests/unit/test_audit_redaction.py` (passed in the 312-test unit regression). Sensitive-data path to prompts: AI content limit and restricted/quarantined exclusion (`tests/committed/test_ai_read_v1.py`, passed in the 132-test regression) | Report and export authorization needs Sprint 7 (not built). Retention policy is not approved |
| S8-05 | AMBER | **Partial** | `ai-read/v1` contract regression: `tests/committed/test_ai_read_v1.py` (passed in the 132-test regression) | Seven-specialist and v1.1 regression needs S6-INT (BLOCKED) |
| S8-06 | AMBER | **Partial** | Injected faults on the durable execution path: heartbeat, hung step, lease expiry (`tests/committed/test_durable_execution.py`, passed in the 132-test regression). Owner-reset fault injection (`tests/committed/test_owner_reset_fault_injection.py`) exists and was **not executed** here | Integrated resilience conclusions need S6-INT. Specialist partial-result and external-evidence faults do not exist in this repository |
| S8-07 | AMBER | **Partial** | Replay, retry idempotency, dead letter, live-lease exclusion on the outbox worker: `tests/sprint8/test_s8_07_08_replay_and_fencing.py` (5 passed). Attempt bound and backoff: `tests/integration/test_outbox_worker.py` | Final workflow duplicate tests need S6-INT (BLOCKED). Transport must honour the idempotency key (`T-21`) |
| S8-08 | AMBER | **Partial** | Fencing and stale-claim replay (`tests/sprint8/test_s8_07_08_replay_and_fencing.py`, 5 passed); job-level fencing (`tests/committed/test_durable_execution.py`, passed in the 132-test regression) | Run-level interrupted-run recovery needs S6-INT (BLOCKED, one placeholder) |
| S8-09 | AMBER | **Measured baseline, no threshold** | `tests/perf/test_s8_09_outbox_baseline.py`; three runs, figures below | No approved SLO, so none is set or checked |
| S8-10 | AMBER | **Partial: measured concurrency harness added** | Concurrency harness with 1 and 4 workers: each of 200 notices sent exactly once; figures below (`tests/perf/test_s8_10_concurrent_outbox.py`). Payload limits: `tests/unit/test_upload_body_bound.py` (20 MiB), `tests/committed/test_ai_read_v1.py` line 529 (10 MiB) | No capacity threshold is approved. Capacity conclusions under production load need S6-INT and an approved target |
| S8-11 | AMBER | **Draft runbook** | `docs/governance/sprint8/S8_11_OPERATIONS_RUNBOOK.md`: detection, triage, recovery, each marked as tested or not rehearsed. Correlation keys: `tests/committed/test_durable_execution.py` (line 958 onward) | Not accepted. No alerting or paging is wired. The worker is not under a real supervisor. Full runbook drills need S6-INT |
| S8-12 | RED | **Partial: rehearsal on the current head** | `tests/recovery/test_s8_12_restore_rehearsal.py`; three runs passed; `docs/governance/sprint8/S8_12_RESTORE_REHEARSAL.md` | Final-schema rehearsal is BLOCKED on OPEN-18. No approved RPO or RTO. No backup schedule |
| S8-13 | AMBER | **Partial: gate script run end to end** | `scripts/s8_qa_gate.sh` (exit 0 in database mode on the working tree). `tests/sprint8/conftest.py` gate modes | No CI configuration exists in the repository (no `.github`). CI execution is BLOCKED until WDS approves a platform and runner. Traceability to S6 and S7 controls needs those workstreams |
| S8-14 | RED | **Draft, NOT READY** | `docs/governance/sprint8/S8_14_UAT_READINESS_DRAFT.md` | Depends on S6, S7 and final Sprint 8 QA. No UAT entry is recommended |

## 2. S8-09 measured baseline (observed, not accepted)

Dataset: 200 `outbox_notices` rows for one active account, delivered by one worker. Transport: in-process, no network. Database: PostgreSQL 16.4 in a Docker container on `127.0.0.1:55808`. Host: Windows 11, Python 3.12.10, 16 logical CPUs. Each run asserts that every notice was sent exactly once.

| Run | p50 per notice (ms) | p95 (ms) | max (ms) | Throughput (notices/s) |
|---|---|---|---|---|
| 1 | 99.68 | 137.44 | 154.83 | 10.05 |
| 2 | 105.33 | 142.17 | 159.99 | 9.35 |
| 3 | 108.11 | 147.46 | 165.16 | 9.13 |
| QA re-run on `d36834a` (one run) | 105.95 | 135.87 | 178.54 | 9.46 |

## 3. S8-10 concurrency measurement (observed, not accepted)

Dataset: 200 notices. Workers are threads, each with its own worker object, sharing one database.

| Workers | Wall time (s) | Throughput (notices/s) | Sent exactly once | Per-worker split |
|---|---|---|---|---|
| 1 | 23.10 | 8.66 | yes | 200 / 0 / 0 / 0 |
| 4 | 6.13 | 32.65 | yes | 50 / 50 / 50 / 50 |

Four workers were about 3.8 times faster than one on this host, with no duplicate sends. These are measurements. They are not an accepted capacity figure.

## 4. S8-12 rehearsal (observed, current head only)

| Run | Dump (s) | Restore (s) | Tables | Rows | Revision |
|---|---|---|---|---|---|
| 1 | 0.358 | 1.868 | 32 | 62 | `0059_int_mark_inputs_fence` |
| 2 | 0.350 | 2.013 | 32 | 62 | `0059_int_mark_inputs_fence` |
| 3 | 0.363 | 1.857 | 32 | 62 | `0059_int_mark_inputs_fence` |

## 5. Blockers (not verified, not reported as passed)

1. **OPEN-11 workspace identity.** Owner: WDS decision. One placeholder test (`test_sprint8/test_s8_02_fail_closed_db.py`, workspace read).
2. **S6-INT specialist execution path.** Owner: Sprint 6 integration. One placeholder test.
3. **S6-INT run-level recovery.** Owner: Sprint 6 integration. One placeholder test (`test_s8_07_08_replay_and_fencing.py`).
4. **OPEN-18 final migration list.** Owner: WDS decision. Blocks the final-schema rehearsal (S8-12) and the final restricted-role matrix (S8-03).
5. **CI platform and runner.** Owner: WDS decision. Blocks CI execution (S8-13).
6. **Sprint 7 review and reporting.** Owner: Sprint 7. Blocks S8-04 export authorization and S8-14.

## 6. Standing constraints kept
- No threshold is set for any performance measurement (S8-09, S8-10).
- No production infrastructure was used. All database work ran on dedicated scratch clusters.
- No password or credential value appears in any file in this repository.
- Nothing is pushed or merged to a protected branch. This record makes no deployment claim.
