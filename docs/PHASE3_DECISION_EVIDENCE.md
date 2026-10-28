# Phase 3 decision and implementation evidence

Branch `feature/foundation-phase-3`. This report covers four items closed in the final engineering sprint: D-3 (database-clock
authorization expiry), G-7 (audit correlation UUID), H-26 (dependency classification), and crash-test stability. The matrix
is `docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md`; run totals are in `docs/PHASE3_ENGINEERING_EVIDENCE.md`.

## 1. D-3: the authorization expiry is decided on the database clock

### The conflict that was checked

Two governance statements bear on this decision.

- `P-INC3-TEST-CLOCK-05` (WDS confirmed; `WebDesk_Agentic_Requirement_Platform_Specs/DECISION_REGISTER.md`, `GOVERNANCE.md`,
  `REQUIREMENT_SCHEMA.md`) permits a deterministic injected clock in isolated test profiles, and requires that "time-dependent
  application checks and DB checks must agree on one explicit effective time for tests", with production on the real clock and
  fail-closed. It also says test-controlled time "cannot mutate approved timestamps after issuance", and must not be configurable
  through production inputs.
- H-21 (`docs/INCREMENT_3_HARDENING_PLAN.md`) asks that ceremony deadlines use the same database source, not the injected clock.

The engineering rule given for this sprint is stricter: a security-sensitive expiry decision must use the authoritative
PostgreSQL clock, and an injected clock may control durations and scenarios but must not grant authorization.

**Finding: no conflict.** Both statements are satisfied when the database is the single decision source. The approved text
requires agreement between application and database checks. Moving the grant decision entirely into the database makes them
agree by construction: there is one authoritative time and no application decision on expiry. The injected window (the 24-hour
activation window, GD-003) remains a duration, which the approved rule allows. The approved rule also forbids a test clock that
backdates approved timestamps; this change does not do that.

### What the code did before

`ceremony/install.py` `load_signed_authorization` refused an authorization when `expires_at <= clock.now()`, using the injected
application clock, before any database connection existed. `ceremony/recovery.py` used the same loader. Recovery's own
deadline decisions were already on `database_now`.

### What the code does now

- `load_signed_authorization` verifies the owner signature, the digest, the format and the timezone, and returns the signed
  expiry. It does not compare that expiry with any clock.
- `PreparedInstall.authorization_expires_at` and `RecoveryRequest.authorization_expires_at` carry the signed expiry.
- `apply_install` calls `require_unexpired(conn, expires_at)` first. It refuses with `authorization_expired` when the database
  clock (`clock_timestamp()`) has reached the signed expiry, before any write. The refusal rolls back the nested transaction; the
  CLI then writes `ceremony.install.denied` in a committed transaction (existing `run_in_transaction` behaviour).
- `apply_recovery` checks the same way and refuses with `RecoveryError(409, "authorization_expired")`. The denial is written as
  `ceremony.recover.denied` (existing `_refuse`).
- The injected clock is removed from the install, recovery and CLI paths. `SystemClock` and the `Clock` protocol were removed
  from `ceremony/install.py`.

### Tests

`tests/committed/test_authorization_expiry.py` (6 tests, real signed files, real PostgreSQL):

| Case | Expectation | Result |
|---|---|---|
| Boundary: signed expiry 30 s after the database time | installs | pass |
| Boundary: signed expiry 30 s before the database time | refused `authorization_expired`; no ceremony row; denial audited | pass |
| Clock skew: signed expiry in 2000 (an application clock that says valid is contradicted by the database) | preparation accepts it without a decision; database refuses | pass |
| Far-future signed expiry | decided by the database; installs | pass |
| Database unavailable (unreachable port) | `SQLAlchemyError`; no ceremony row | pass |
| Recovery with a database-expired signed expiry | `RecoveryError(409, "authorization_expired")`; `ceremony.recover.denied` audited | pass |

`tests/unit/test_install_authorization.py` now asserts that preparation reads the signed expiry and does not decide it (10 tests
in that file pass).

Existing suites that exercise installation, recovery, denial branches, role assignment and deadlines were run after the change:
132 passed in the first group, and the full regression (see the engineering evidence report) includes them.

Single-use operation proofs are not touched by this change. The proof tests in `tests/hardening` (17 in the privilege audit, and
the hardening suite) pass on the final commit.

## 2. G-7: the audit correlation UUID is persisted

### Before

`audit_events.correlation_id` is a UUID column (migration 0001). Worker events went through `fn_worker_record_audit`, which never
populated it. Each job's correlation existed only as the string `<run>/<job>/<attempt>` in the redacted details.

### Implementation

- Migration `0052_audit_correlation` (additive; `down_revision` `0051_worker_fence_diagnostics`). It adds
  `webdesk_guard.fn_worker_record_audit_correlated(actor_type, actor_id, event_type, outcome, error_class, record_refs, details,
  correlation uuid)`. It keeps every guard of the existing function (migration 0039): only `system` events, and no actor identifier
  that names an account. It adds: a NULL correlation is refused (`worker audit requires a correlation identifier`). The function
  is owned by `webdesk_guard_owner`, is `SECURITY DEFINER` with a fixed search path, and is executable by `webdesk_worker` only.
  No existing function, grant or migration was rewritten.
- `runs/jobs.py`: `correlation_uuid(run, job, attempt)` is `uuid5` of the existing string key. The logs keep the string; the audit
  column stores the UUID. The UUID is deterministic, so a log line and an audit row can be matched.
- `audit/service.py` `record_worker_event(..., correlation_id: uuid.UUID | None)`. A non-UUID value is refused in Python before any
  database call (`ValueError`). `None` is used only for events without a job, and goes to the existing function.
- Propagation: `run.parked` (finish), `run.failed` (permanent refusal and reaper), `job.reaped` (reaper), and `job.requeued`
  (retryable recovery, new).

### Decision: a stale worker writes no audit row

The approved rule (H-22, H-23) is that a worker whose lease is lost writes nothing further. A denial record written by that
worker would be a write. The stale worker's refusal is therefore reported through the structured log (`job.outcome` with
`outcome: lease_lost` and the correlation key), not through the database. The test
`test_a_stale_worker_writes_no_audit_row_under_the_lost_claim` pins this.

### Evidence

- Correlation on each job-path event: `test_a_parked_run_audit_row_stores_the_claim_correlation_uuid`,
  `test_a_retryable_failure_is_audited_as_a_requeue_with_the_same_correlation`,
  `test_a_permanent_refusal_is_audited_as_a_failed_run_with_its_correlation`,
  `test_the_reaper_audit_rows_carry_the_correlation_of_the_exhausted_attempt`.
- Guards: `test_the_database_refuses_a_worker_audit_row_without_a_correlation`,
  `test_the_database_refuses_human_actors_and_account_named_workers`.
- Privilege and ownership: `test_only_the_worker_role_may_execute_the_correlated_audit_function` (owner
  `webdesk_guard_owner`; `webdesk_app` denied). The privilege audit pins the new function for `webdesk_worker` only
  (`tests/hardening/test_privilege_audit.py`, 17 passed).
- Malformed input: `test_a_malformed_correlation_is_refused_before_any_database_write`.
- Stale worker: `test_a_stale_worker_writes_no_audit_row_under_the_lost_claim`.
- Redaction: the details carry only the correlation key, counts and outcome classes (the same redaction path as before).

### Bootstrap note

The hardening database `webdesk_p3c_hardening` was migrated to `0052` as the cluster superuser, the same bootstrap path used for
`0051`. The migration created the function owned by `webdesk_guard_owner`. The superuser holds no guard-owner membership
afterwards (checked: 0).

## 3. H-26 dependency classification

H-26 asks the worker to run the job loop, the outbox worker and the expiry sweep, and to stop on SIGTERM after the current step.
Each remaining external item is classified below. No production credential, transport or secret was invented.

| Item | Class | Evidence and status |
|---|---|---|
| Job loop, reaper, claim, retry and backoff, error classification, SIGTERM stop, restart recovery | Phase 3 implementation | Implemented and tested (crash, restart, stall-abort, graceful stop). |
| Maintenance orchestration (sweep and outbox run between iterations when configured; named `maintenance.disabled` otherwise) | Phase 3 implementation | Implemented. |
| Outbox and sweep under a complete test-profile configuration (capture sink) | Verified mock / test integration | `test_maintenance_orchestration_runs_the_sweep_and_outbox_with_the_test_capture_sink`. The capture sink is refused outside `WEBDESK_ENV=test`. Outbox behaviour (leases, fencing, backoff, dead letter) is covered by `tests/integration/test_outbox_worker.py`. |
| Production outbox delivery transport (SMTP or other) | Later-phase dependency (notification and outbox phase, H-50/H-52) | No production transport is implemented in Phase 3. The interface is the existing `EmailTransport` protocol. |
| SMTP credentials and their verification gates | Missing production credentials or transport configuration | Not invented. `smtp_config_from_env` refuses without its gates. |
| Outbox login (`WEBDESK_OUTBOX_DATABASE_URL`), encryption key (`WEBDESK_OUTBOX_ENCRYPTION_KEY`), dead-letter threshold | Missing production credentials or configuration | Operator-provided per environment. Not invented. |
| Ceremony login for the sweep (`WEBDESK_CEREMONY_DATABASE_URL`) | Missing production credentials or configuration | Operator-provided. The sweep runs when set. |
| Worker login (`WEBDESK_WORKER_DATABASE_URL`) and a process manager | Missing production credentials or configuration (D-4, D-5) | Deployment checklist. |

## 4. Crash-test stability

### Cause of the earlier failure

The crash tests waited for a claim by polling the database with a 60-second cap, and read worker stdout through a reader keyed by
process ID. Windows reuses process IDs. A later worker could inherit an earlier worker's queue and wait for an event that never
reached it. This was observed once in five runs of the crash subset (the failing wait was for `job.claimed`).

### Change

Each worker process has one stdout reader, keyed by the process object. Tests wait for the worker's own `job.claimed` line for the
expected owner. The worker prints that line after its claim transaction commits, so the lease is then visible. The lease expiry
is still measured on the database clock with a bounded wait. Production code, lease length, and timing were not changed.

### Repeatability

| Run | Subset | Result |
|---|---|---|
| Before the stdout-keying fix, five runs | killed worker, three-crash exhaustion, hung-step abort, graceful stop, demonstration | 4 of 5 passed; the one failure was the PID-reuse cause above |
| After the fix, seven consecutive runs, dedicated cluster (run times were not recorded per run) | same subset | 7 of 7 passed (52 to 59 s each) |
| Demonstration alone, three runs | heartbeat demonstration | 3 of 3 passed |

### Detection check

The tests were checked for the failures they must catch. A clean copy of the committed tree was built in a scratch directory, and
one defect was injected at a time (the worktree was not changed).

| Injected defect | Expected detection | Result |
|---|---|---|
| Clean copy (control) | all selected tests pass | 5 of 5 passed |
| M1: step fence removed (stale worker can write) | step-start lease test fails | 1 failed: `test_a_step_that_starts_after_its_lease_expired_writes_nothing` |
| M2: renewal ignores lease ownership (lost lease not detected) | renewal refusal tests fail | 2 failed: cancelled-renewal and reclaimed-lease tests |
| M3: reaper disabled (crash recovery does not release the slot) | three-crash exhaustion test fails | 1 failed: `test_three_crashes_exhaust_the_attempts_and_the_reaper_releases_the_slot` |
| M4: exhaustion never terminal (retry exhaustion not failed) | retry-then-terminal test fails | 1 failed: `test_retryable_failures_requeue_with_backoff_then_end_in_a_terminal_failure` |

Results are in the scratch file `mutation_results.txt` (outside the repository).
