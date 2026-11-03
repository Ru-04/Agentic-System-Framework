# Sprint 8 status (S8-09 to S8-14 continuation)

**Scope of this record:** the Sprint 8 items remaining after the approved subset. This is not a Sprint 8 completion record. WDS has not declared Sprint 8 complete, and this document does not do so.
**Baseline:** the verified subset is at `cde1d62`. Credential item T-31 is CLOSED on owner confirmation (`CREDENTIAL_EXPOSURE_RECORD_2026-11-03.md`).

## Status by requirement

| ID | Class (matrix) | Status | Evidence and limits |
|---|---|---|---|
| S8-09 | AMBER | **Measured baseline recorded, no threshold** | `tests/perf/test_s8_09_outbox_baseline.py`; numbers below. No SLO is approved, so no pass/fail threshold is set. Single worker, in-process transport, one dataset. |
| S8-10 | AMBER | **Partial, existing coverage only** | Payload limits: `tests/unit/test_upload_body_bound.py` (20 MiB upload, `routes.py` line 53); `tests/committed/test_ai_read_v1.py` line 529 (AI content 10 MiB, `413 response_too_large`). Bounded claim batches and lease exclusion: `tests/sprint8/test_s8_07_08_replay_and_fencing.py`. **Not done:** a concurrency and capacity harness under load. Final capacity conclusions need S6-INT. |
| S8-11 | AMBER | **Partial, existing coverage only** | Correlation keys: `tests/committed/test_durable_execution.py` line 958 onward (migration `0052`). Redaction: `tests/unit/test_audit_redaction.py`. **Not done:** the runbook. Its full content needs S6-INT. |
| S8-12 | RED | **Not started (correct per matrix)** | Restore rehearsal needs permitted snapshots on the final schema. The final migration list is open (OPEN-18). No measured RPO or RTO exists. |
| S8-13 | AMBER | **Gate script delivered; CI platform not verified** | `scripts/s8_qa_gate.sh` runs ruff, format, strict mypy, the Sprint 8 gate in unit or database mode, the database security regression, and the unit regression. Run end to end in database mode on the working tree based on `cde1d62` (plus the changes in this continuation): gate exit 0. **Not done:** no CI configuration exists in this repository (no `.github`). Mandatory checks in isolated CI infrastructure are BLOCKED until WDS approves a CI platform and a runner. |
| S8-14 | RED | **Not started (correct per matrix)** | The UAT readiness package depends on S6, S7 and S8 completion. None of those is complete. |

Items S8-03 to S8-06 are outside the instructions for this continuation and are not addressed here.

## S8-09 measured baseline

Dataset: 200 `outbox_notices` rows for one active account, claimed as one batch and delivered sequentially by one worker. Transport: in-process counting transport, no network. Database: PostgreSQL 16.4 in a Docker container on `127.0.0.1:55808`. Host: Windows 11, Python 3.12.10, 16 logical CPUs. Each run asserts that every notice was sent exactly once, keyed by its notice ID.

| Run | p50 per notice (ms) | p95 (ms) | max (ms) | Throughput (notices/s) |
|---|---|---|---|---|
| 1 | 99.68 | 137.44 | 154.83 | 10.05 |
| 2 | 105.33 | 142.17 | 159.99 | 9.35 |
| 3 | 108.11 | 147.46 | 165.16 | 9.13 |

These are measurements, not thresholds. They include the worker's transactional database round trips for each notice, which is the dominant cost. They are not a production capacity claim, and they do not measure the email transport. Repeat runs vary by about 8%. All three runs used the same command, by the engineering session, on the same cluster.

## Blockers (not verified, not reported as passed)

1. **OPEN-11 workspace identity.** Owner: WDS decision. No entity exists to test against.
2. **S6-INT specialist execution path and run-level recovery.** Owner: Sprint 6 integration. Two placeholder tests remain BLOCKED.
3. **S8-12 restore rehearsal.** Needs the final schema (OPEN-18) and permitted snapshots.
4. **S8-13 CI infrastructure.** Needs a WDS-approved CI platform and runner.
5. **S8-14 UAT readiness.** Needs S6, S7 and S8 complete.

## Standing constraints kept
- No threshold is set for any performance measurement (S8-09).
- No production infrastructure was used. All database work ran on dedicated scratch clusters.
- No password or credential value appears in any file in this repository.
