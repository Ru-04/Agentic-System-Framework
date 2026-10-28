# Foundation Phase 3: independent QA handoff

Branch `feature/foundation-phase-3`. Committed base `e9d888a`. Phase 3 commits (oldest first):

| Commit | Content |
|---|---|
| `61de952` | Per-process authority test login role (fixes the shared-password credential race) |
| `b398761` | Lease heartbeat, KEY SHARE step fence, stuck-job diagnostics, correlation keys; migration `0051`; tests |
| `f640322` | Expiry sweep and recovery expiry on the database clock (H-21) |
| `e02edc7` | Closure matrix, lease lifecycle, privilege matrix, evidence report, demonstration output |

Status: **engineering handoff, not accepted, not merged, not pushed.** The verdict is
**PHASE 3 ENGINEERING INCOMPLETE — BLOCKERS REMAIN** (see Blockers). This handoff does not claim independent acceptance.

## Evidence

- Matrix: `docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md`. Evidence: `docs/PHASE3_ENGINEERING_EVIDENCE.md`.
- Lifecycle: `docs/PHASE3_JOB_LEASE_LIFECYCLE.md`. Privileges: `docs/PHASE3_WORKER_PRIVILEGE_MATRIX.md`.
- Demonstration output: `docs/PHASE3_DEMONSTRATION_OUTPUT.txt`.
- Dependencies: `docs/PHASE3_DEPENDENCY_REGISTER.md`. Migration reconciliation: `docs/PHASE3_MIGRATION_RECONCILIATION.md`.

Final full regression on the dedicated cluster `127.0.0.1:5440` (compose project `webdesk-phase3-closure`):
**707 passed, 0 failed, exit 0**, 2026-10-28 11:09:52Z to 11:18:26Z, on the working tree at `b398761`+`f640322`+`e02edc7`
(the docs commit does not change tested code). Ruff check and format policy: clean. Strict mypy: clean.

## Blockers (engineering)

1. **H-21 (decision D-3)**: the pre-database authorization expiry in `ceremony/install.py` (`prepare_install`) compares
   against the injected clock. Moving it to the database clock needs a WDS decision on the approved test-clock rule
   (P-INC3-TEST-CLOCK-05). Contact liveness predicates in `identity/contacts.py` still use `now()`; they are outside the
   H-21 file list, recorded as residual.
2. **G-7 (audit correlation column)**: correlation keys are in worker logs and audit details, not in
   `audit_events.correlation_id` (UUID). Populating the column needs a new guard function (migration), not done.

## Dependencies outside Phase 3 engineering

- **Phase 2 merge join (D-1c)**: Phase 2 remediation migrations `0044` and `0045` are not in this branch. Procedure in
  `docs/PHASE3_MIGRATION_RECONCILIATION.md`; `0050` is not edited. `0051` depends on `0050` only and is unaffected.
- **Phase 2 acceptance (D-1b)** and **Phase 1 acceptance (D-1e)**: not performed.
- **D-2**: production outbox transport and ceremony login are configured by the worker; without them the steps are
  reported as disabled. Belongs to the notification and outbox phase.
- **D-4 / D-5**: production worker login provisioning and the process manager are deployment items.
- **Shared cluster**: the shared PostgreSQL on `127.0.0.1:5433` still holds Phase 3 leftover role
  `webdesk_authority_test_9c007c88774a` (no session attached). It is to be dropped only after Phase 2 releases that cluster.
  The dedicated cluster has no leftover roles.

## What to re-test

1. Lease and fence: `tests/committed/test_durable_execution.py` heartbeat tests (`test_the_heartbeat_*`, `test_a_hung_step_*`,
   `test_renewal_and_step_fencing_race_*`, `test_a_step_that_starts_after_*`).
2. Worker process: `test_the_worker_process_aborts_a_hung_step_and_its_lease_is_recovered` (exit 70); graceful stop (exit 0).
3. Reaper, crash and exhaustion: three-crash test and `test_archive_succeeds_after_a_run_failed_by_attempt_exhaustion`.
4. Stuck report: `test_the_stuck_report_command_exits_1_when_stuck_and_0_when_clear`.
5. Authority isolation: run two test processes against one cluster; the first must still authenticate after the second
   starts. Check no `webdesk_authority_test_*` role remains afterwards.
6. Migration: `tests/committed/test_migration_cycle.py` (head, downgrade through `0051` and `0050` to `0043`, re-upgrade,
   catalog comparison).
7. Privilege audit: `tests/hardening/test_privilege_audit.py` (worker set includes the two 0051 functions).

## Known limitations (report, do not re-discover)

- The correlation key is not in the audit UUID column (G-7).
- The heartbeat interval is measured by the worker's monotonic clock; each renewal stamps database time. The approved text
  says "every 30 seconds of database time".
- Durable-execution crash tests use a 2-second test lease and depend on process start-up time; one run timed out once on a
  loaded machine and passed on rerun. Watch for this flakiness.
- The dedicated cluster bootstrap is test-only and not committed. Its non-default settings (test-owner memberships with
  SET, the hardening owner's objects owned by the integration owner, and the superuser bootstrap migration) are described
  in the evidence report.

## Verdict

PHASE 3 ENGINEERING INCOMPLETE — BLOCKERS REMAIN. The blockers are listed above. This handoff is not an acceptance.
