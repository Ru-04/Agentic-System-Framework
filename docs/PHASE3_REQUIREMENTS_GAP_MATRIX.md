# Phase 3 requirements gap matrix (durable execution)

Base: `46e0e14` (branch `feature/foundation-phase-2`, last committed Phase 2 state). Phase 3 branch:
`feature/foundation-phase-3`. Approved basis: `docs/INCREMENT_3_HARDENING_PLAN.md`, Phase 3 section (H-20 to H-27),
with the Architecture section 7 transitions and the governance decisions referenced there.

Status values: **done** = implemented and tested here; **partial** = implemented with a stated gap; **open** = not
implemented, with the reason; **dependency** = needs an input from another phase or from WDS.

## Approved items H-20 to H-27

| ID | Requirement (approved) | Committed baseline (46e0e14) | Phase 3 change | Test evidence | Status |
|---|---|---|---|---|---|
| H-20 | `claim` commits in its own transaction before execution, so `attempts` is durable | `process_one` claims and executes in one caller transaction | `runs/committed.py` `claim_and_commit` commits the claim before any execution | `test_a_claim_is_committed_before_any_execution`; kill test shows `attempts` durable after a killed worker | done |
| H-21 | Lease times use `clock_timestamp()` in the database; ceremony deadlines use the same source, not the injected clock | Leases use `now()` (transaction start); ceremony deadlines use the injected Python clock | Migration `0050`: claim, renew, finish and requeue use `clock_timestamp()`. Ceremony deadlines not changed. | Lease expiry tests (kill, stale, reclaim) | **partial**: ceremony deadlines open. See dependency D-3. |
| H-22 | Renewal every 30 s of DB time, between committed steps; renewal never a no-op | Renewal once per version parse, extends a dead claim | Each committed step renews in the same transaction as its work; a renewal of an expired or foreign claim is refused (`0050`) | `test_a_stale_worker_cannot_renew_or_complete_after_its_lease_expired_before_any_reclaim` | **partial**: renewal is per step (more frequent than 30 s), not a timer. Acceptable for the approved intent; documented. |
| H-23 | `process_one` commits after claim, after each version parse and after each transition; failure recorded in a fresh transaction | One transaction for the whole intake | Begin, one per version, finish; failure recorded in a fresh transaction (`_record`) | `test_a_committed_execution_parks_the_run_and_completes_the_job`; retry tests | done |
| H-24 | Reaper: expired lease with `attempts >= 3` fails the job and the run (`system_failure`), releases the slot, audited | No reaper; such jobs stayed leased forever | `0050` `fn_worker_reap_expired`; `committed.reap_expired`; audit `job.reaped` and `run.failed` | `test_a_job_with_all_attempts_used...`, `test_the_reaper_leaves_a_job...`, `test_three_crashes...` | done |
| H-25 | `claim` and `cancel_run` lock job then run; no deadlock | `cancel` locked run then jobs (reverse order) | `0050` cancellation locks the run's jobs first | `test_a_cancellation_waits_for_a_claim_without_a_deadlock` (two connections) | done |
| H-26 | `python -m webdesk.worker` runs the job loop, the outbox worker and the expiry sweep; SIGTERM finishes the current step | No entry point | `src/webdesk/worker/` (`__main__`, `loop`): job loop, reaper, SIGTERM/SIGINT/SIGBREAK stop after the step | `test_the_worker_process_stops_gracefully_when_asked_to_stop` | **partial**: the outbox worker and the sweep are not in the loop (dependency D-2). |
| H-27 | Crash and exhaustion tests with real subprocesses and a 2-second test lease: recovery after crash, attempt counting across crashes, reaper after the third crash, slot release, archive and start afterwards | None | Test-only lease and step-delay overrides (test profile only) | `test_a_killed_worker_is_recovered...`; `test_three_crashes_exhaust_the_attempts...` (start of a new run after the slot is released) | done (archive after failure not separately tested; see gap G-4) |

## Sprint areas (section 3 of the sprint brief)

| Area | Requirement | Status | Evidence / note |
|---|---|---|---|
| A | Durable jobs across restarts; states queued, leased, completed, failed, cancelled, waiting for human | done | Existing `workflow_jobs` vocabulary (`0007`) is used. No new states added. |
| A | Waiting-for-human cannot be claimed | done | `test_a_job_waiting_for_a_human_is_not_claimable_by_a_worker` |
| B | Two workers cannot claim the same job | done | `test_two_workers_racing_for_one_queued_job_get_exactly_one_claim` (threads, two connections) |
| B | Stale worker cannot complete after losing ownership | done | `test_a_worker_that_lost_its_claim_to_a_reclaim_writes_nothing`; `test_a_stale_worker_cannot_renew_or_complete...` |
| B | Renewal cannot extend an invalid or revoked claim | done | Renewal requires an unexpired lease owned by the caller (`0050`); tested above |
| B | Concurrent claims and renewals are consistent | partial | Claim race tested. Concurrent renewal races not separately tested (gap G-6). |
| C | Recovery after worker termination, process restart, lease expiry, rollback, timeout, partial execution, retryable vs permanent | done (termination, restart, expiry, rollback, retryable/permanent) | Kill tests; `test_retryable_failures_requeue...`; `test_a_permanent_refusal...`. Partial execution: the killed worker had executed nothing durable beyond its claim (steps commit separately). |
| D | Idempotent execution boundaries; no duplicate committed effects | partial | Each committed step is single-purpose; the claim fences the owner. Duplicate parse effects are prevented by the version status guard (existing). Exactly-once external side effects are not claimed. |
| E | Durable checkpoints scoped to run and job; stale worker cannot overwrite a newer checkpoint | partial | The checkpoint is written in the finish transaction, which first renews the lease (a stale worker is refused before it writes). No separate overwrite test (gap G-3). |
| E | Cancellation prevents further transitions; human-wait cannot be bypassed | done | `test_a_worker_whose_run_was_cancelled_cannot_complete_the_job`; human-wait test above |
| E | Run and project revision checks remain enforced | done (existing guards) | Start and cancel guards check revisions (existing tests). |
| F | Dedicated worker privileges; least-privilege functions; explicit EXECUTE | done | `docs/PHASE3_WORKER_PRIVILEGE_MATRIX.md`; privilege audit pins the reaper for `webdesk_worker` |
| F | No direct write beyond worker responsibilities | done | Worker writes only through guard functions (existing `0031` model); the reaper is a guard function. |
| G | Observability: identifiers, attempts, worker identity, transitions, failure classes, recovery decisions | partial | JSON event lines (`job.claimed`, `job.outcome`, `job.reaped`) with identifiers and outcome classes; audit rows for reaping. Correlation IDs not added (gap G-7). Stuck-job diagnostics not added (gap G-8). |
| G | No credentials, restricted content or payloads in logs | done | Worker logs carry identifiers, counts and classes only. |

## Gaps and open items

- **G-3 checkpoint overwrite**: no test that a stale worker cannot overwrite a newer checkpoint. The structure prevents it (the write follows a lease renewal in one transaction), but the claim is not tested in isolation.
- **G-4 archive after failure**: the start after the slot is released is tested; archiving a project after a failed run is not.
- **G-6 concurrent renewal**: renewal races are not tested with two connections.
- **G-7 correlation identifiers**: not added. The job, run and attempt identifiers are logged; a correlation key is not.
- **G-8 stuck-job diagnostics**: the reaper and the logs identify expired and failed jobs. A query or report for stuck or repeatedly failing jobs is not built.
- **D-2 outbox and sweep in the worker**: not wired (needs a transport and the ceremony role).
- **D-3 ceremony deadlines on the database clock**: H-21 asks for ceremony deadlines to use the database clock, but the approved test-clock rule (P-INC3-TEST-CLOCK-05) allows an injected clock in tests. This needs a WDS decision on how the injected window and the database clock combine.
