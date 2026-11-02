# Phase 3 requirements gap matrix (durable execution, H-20 to H-27)

Phase 3 branch: `feature/foundation-phase-3`. Committed base: `e9d888a`; the working tree is described in the evidence
report (`docs/PHASE3_ENGINEERING_EVIDENCE.md`). Approved basis: `docs/INCREMENT_3_HARDENING_PLAN.md`, Phase 3 section,
with the Architecture section 7 transitions.

Status values: **done** = implemented and tested on a dedicated PostgreSQL cluster; **partial** = implemented with a
stated gap; **dependency** = needs an input from another phase, a WDS decision, or deployment.

## Approved items H-20 to H-27

| ID | Approved requirement (summary) | Implementation | Test evidence | Status |
|---|---|---|---|---|
| H-20 | `claim` commits in its own transaction before execution, so `attempts` is durable | `runs/committed.py` `claim_and_commit`; `fn_worker_claim_job` (0031, clock 0050) | `test_a_claim_is_committed_before_any_execution`; kill test shows `attempts` durable | done |
| H-21 | Lease times on database clock; ceremony deadlines on the same source | Leases, reaper, cancel: `clock_timestamp()` (0050, 0051). Expiry sweep (`identity/sweep.py`) and recovery expiry predicate (`ceremony/recovery.py`) now `clock_timestamp()`. Ceremony deadlines in `ceremony/install.py` and `recovery.py` use `database_now`. | lease tests; sweep and recovery run under the regression | done for the signed-authorization expiry (D-3 closed: decided in the database transaction against `clock_timestamp()`; `docs/PHASE3_DECISION_EVIDENCE.md` section 1). Residual: contact liveness predicates in `identity/contacts.py` are outside the H-21 file list and still use `now()`. |
| H-22 | Renew lease every 30 s of database time, between committed steps; never a no-op | `runs/heartbeat.py`: background thread renews every 30 s (cap: lease/4), the renewal stamps `clock_timestamp()` and is refused unless the caller's lease is live and the job is still `leased`. Each step first calls `fn_worker_hold_lease` (`0051`), which takes `FOR KEY SHARE` on the job, so reclaim cannot take it while a step runs and the heartbeat's update is not blocked. Stall limit 600 s: a hung step stops renewal and the worker process exits with code 70. | `test_the_heartbeat_keeps_the_lease_alive_through_a_step_that_commits_nothing`; `test_the_lease_expires_and_is_reclaimable_once_the_heartbeat_stops`; `test_a_renewal_is_refused_after_cancellation_and_the_heartbeat_stops`; `test_a_heartbeat_of_a_reclaimed_lease_is_refused_and_writes_nothing`; `test_a_hung_step_stops_renewal_reports_a_stall_and_frees_the_job`; `test_a_database_error_during_renewal_is_reported_by_class_and_retried`; `test_renewal_and_step_fencing_race_without_deadlock_or_lost_updates`; `test_a_step_that_starts_after_its_lease_expired_writes_nothing`; `test_heartbeat_interval_never_exceeds_a_quarter_of_the_lease`; `test_the_worker_process_aborts_a_hung_step_and_its_lease_is_recovered` | done. The interval is measured by the worker's monotonic clock; each renewal stamps database time. |
| H-23 | `process_one` commits after claim, after each version parse and each transition; failure recorded in a fresh transaction | `committed.execute_committed`: begin, one per version, finish; `_record` in a fresh transaction | `test_a_committed_execution_parks_the_run_and_completes_the_job`; retry tests | done |
| H-24 | Reaper: expired lease with attempts ≥ 3 fails the job and run (`system_failure`), releases the slot, audited | `fn_worker_reap_expired` (0050); `committed.reap_expired`; audit `job.reaped` and `run.failed` with correlation key | `test_a_job_with_all_attempts_used...`; `test_three_crashes_exhaust_the_attempts...` | done |
| H-25 | `claim` and `cancel_run` lock job then run; no deadlock | 0050 cancel locks jobs first; step fence locks job only before run | `test_a_cancellation_waits_for_a_claim_without_a_deadlock` (two connections) | done |
| H-26 | `python -m webdesk.worker` runs the job loop, outbox worker and expiry sweep; SIGTERM finishes the current step | `worker/__main__.py`, `worker/loop.py`, `worker/maintenance.py`: loop, reaper, heartbeat, maintenance steps enabled only when fully configured (otherwise a named `maintenance.disabled` event); SIGTERM/SIGINT/SIGBREAK stop after the step; `--report-stuck` | `test_the_worker_process_stops_gracefully_when_asked_to_stop`; `test_a_failing_maintenance_step_is_reported_and_the_job_loop_continues`; `test_optional_maintenance_steps_are_disabled_with_a_named_reason_when_unconfigured`; demonstration step 6 | done for the Phase 3 interface, orchestration and non-production behaviour. Production dependencies are classified in `docs/PHASE3_DECISION_EVIDENCE.md` section 3: transport and credentials (later-phase or operator-provided), not Phase 3 implementation. |
| H-27 | Crash and exhaustion tests with real subprocesses and a 2-second test lease: recovery, attempt counting, reaper after third crash, slot release, archive and start afterwards | Test-only lease and step-limit overrides (test profile only) | `test_a_killed_worker_is_recovered_after_lease_expiry_and_attempts_are_counted`; `test_three_crashes_exhaust_the_attempts_and_the_reaper_releases_the_slot`; `test_archive_succeeds_after_a_run_failed_by_attempt_exhaustion`; `test_phase3_demonstration_*` | done |

## Review coverage (sprint section C)

| Area | Requirement | Status | Evidence / note |
|---|---|---|---|
| A | Durable jobs across restarts; states queued, leased, completed, failed, cancelled, waiting for human | done | Existing `0007` vocabulary; no new states |
| A | Waiting-for-human cannot be claimed | done | `test_a_job_waiting_for_a_human_is_not_claimable_by_a_worker` |
| B | Two workers cannot claim the same job | done | `test_two_workers_racing_for_one_queued_job_get_exactly_one_claim` |
| B | Stale worker cannot complete after losing ownership | done | `test_a_worker_that_lost_its_claim_to_a_reclaim_writes_nothing`; fence tests above |
| B | Renewal cannot extend an invalid or revoked claim | done | Renewal requires an unexpired lease owned by the caller and status `leased` |
| B | Concurrent claims and renewals are consistent (G-6) | done | `test_renewal_and_step_fencing_race_without_deadlock_or_lost_updates` |
| C | Recovery after termination, restart, expiry, rollback, timeout, retryable vs permanent | done | Kill, stall-abort, backoff and permanent-refusal tests |
| D | Idempotent execution boundaries; no duplicate committed effects | partial | Single-purpose committed steps; claim fences the owner; parse status guard. Exactly-once external side effects are not claimed. |
| E | Checkpoints scoped to run and job; stale worker cannot overwrite a newer checkpoint (G-3) | done | `test_a_stale_worker_cannot_overwrite_the_checkpoint_of_its_successor`; the finish fence precedes the insert |
| E | Cancellation prevents further transitions; human wait cannot be bypassed | done | `test_a_worker_whose_run_was_cancelled_cannot_complete_the_job`; `test_a_cancelled_run_cannot_be_resumed` |
| F | Dedicated worker privileges; least-privilege functions; explicit EXECUTE | done | `docs/PHASE3_WORKER_PRIVILEGE_MATRIX.md`; privilege audit pins the worker set, including `fn_worker_hold_lease` and `fn_worker_stuck_jobs` |
| G | Observability: identifiers, attempts, worker identity, transitions, failure classes | done | JSON event lines carry `correlation_id` (`<run>/<job>/<attempt>`). Migration `0052` persists its UUID (`uuid5`) in `audit_events.correlation_id` for parked, failed, requeued and reaped events (G-7; `docs/PHASE3_DECISION_EVIDENCE.md` section 2). |
| G | Stuck-job diagnostics (G-8) | done | `fn_worker_stuck_jobs` (0051); `committed.stuck_jobs`; `python -m webdesk.worker --report-stuck` exits 1 when a job is stuck; `test_the_stuck_report_*` |
| G | No credentials, restricted content or payloads in logs | done | Logs carry identifiers, counts and outcome classes only; heartbeat failures report the exception class only |

## Gaps and dependencies

- **D-3 (closed)**: signed-authorization expiry is decided on the database clock. See `docs/PHASE3_DECISION_EVIDENCE.md`.
- **G-7 (closed)**: audit correlation UUID persisted by migration `0052`.
- **H-26 dependencies**: classified in `docs/PHASE3_DECISION_EVIDENCE.md` section 3. Production outbox transport and
  credentials, the sweep ceremony login, the worker login and the process manager are operator or later-phase items.
- **Residual**: `identity/contacts.py` liveness predicates use `now()` (outside the H-21 file list).
- **Merge dependencies (D-1a to D-1e)**: unchanged; see `docs/PHASE3_DEPENDENCY_REGISTER.md` and
  `docs/PHASE3_MIGRATION_RECONCILIATION.md`. The reconciliation is a documented procedure, not an executed change.
