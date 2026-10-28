# Foundation Phase 3: independent QA handoff

Branch `feature/foundation-phase-3`. Committed base `e9d888a`. Tested commit: `b509900` (the last code commit).
Engineering verdict: **PHASE 3 ENGINEERING COMPLETE — READY FOR INDEPENDENT QA.** This is not an acceptance.
Not merged, not pushed, not deployed.

## Commits since the base (oldest first)

| Commit | Content |
|---|---|
| `61de952` | Per-process authority test login role (shared-password credential race) |
| `b398761` | Lease heartbeat, step fence, stuck-job diagnostics, correlation keys; migration `0051` |
| `f640322` | Expiry sweep and recovery on the database clock (H-21) |
| `e02edc7` | Closure matrix, lease lifecycle, privilege matrix, evidence report, demonstration output |
| `dacba6b` | Independent QA handoff (first version) |
| `efd0407` | Signed-authorization expiry decided on the database clock (D-3); no migration |
| `ec8eaf0` | Removal of an unused test helper |
| `3f49486` | Audit correlation UUID persisted in `audit_events.correlation_id` (G-7); migration `0052` |
| `45379ee` | Crash and restart test synchronisation (explicit worker events, process-keyed reader) |
| `b509900` | H-26 maintenance orchestration test with the test-profile capture sink |

## Final verification (dedicated cluster `127.0.0.1:5440`, tree `b509900`)

| Run | Command | Result | Exit |
|---|---|---|---|
| Full Foundation regression | `pytest -q` | 723 passed, 0 failed (08:44; 2026-10-28 12:13:42Z to 12:22:30Z) | 0 |
| AI Read v1 | `pytest tests/committed/test_ai_read_v1.py` | 28 passed | 0 |
| D-3 expiry boundary and skew | `pytest tests/committed/test_authorization_expiry.py` | 6 passed | 0 |
| Install unit tests | `pytest tests/unit/test_install_authorization.py` | 10 passed | 0 |
| Privilege audit (restricted login) | `pytest tests/hardening/test_privilege_audit.py` | 17 passed | 0 |
| Durable execution, heartbeat, fencing, G-7, crash | `pytest tests/committed/test_durable_execution.py` | 45 passed | 0 |
| Migration cycle and catalog | `pytest tests/committed/test_migration_cycle.py` | 1 passed | 0 |
| Crash subset repeatability | same subset, seven consecutive runs | 7 of 7 passed | 0 each |
| Synthetic demonstration | `pytest ... -s -k phase3_demonstration` | 2 passed; output in `docs/PHASE3_DEMONSTRATION_OUTPUT.txt` | 0 |
| Ruff check | `ruff check src tests migrations` | all checks passed | 0 |
| Ruff format policy | `ruff format --check` on changed files (34) | already formatted | 0 |
| Strict mypy | `mypy --strict src/webdesk` | 64 files, no issues | 0 |

Earlier failing runs were investigated and are explained in `docs/PHASE3_ENGINEERING_EVIDENCE.md`: the shared authority password
race, bootstrap artefacts of the new cluster, and an integration base database that had to be migrated to `0052`.

## What to re-test

1. Heartbeat and fence: `tests/committed/test_durable_execution.py` tests named `test_the_heartbeat_*`,
   `test_a_renewal_is_refused_*`, `test_a_heartbeat_of_a_reclaimed_lease_*`, `test_a_hung_step_*`,
   `test_renewal_and_step_fencing_race_*`, `test_a_step_that_starts_after_*`. Detection check: `docs/PHASE3_DECISION_EVIDENCE.md` section 4.
2. Crash and restart: killed-worker recovery, three-crash exhaustion, hung-step abort (exit 70), graceful stop (exit 0).
3. D-3: `tests/committed/test_authorization_expiry.py`. Decision and rationale: `docs/PHASE3_DECISION_EVIDENCE.md` section 1.
   Check that no install or recovery refusal depends on an application clock.
4. G-7: migration `0052`; tests named `*correlation*`, `test_the_database_refuses_*`, `test_only_the_worker_role_*`.
   Check that the function is owned by `webdesk_guard_owner` and executable only by `webdesk_worker`.
5. Maintenance: `test_maintenance_orchestration_*` and `test_optional_maintenance_steps_*`.
6. Migration: `0050` (unchanged), `0051`, `0052`. Head is `0052_audit_correlation`.

## Dependencies outside Phase 3 engineering (merge and production)

- **Phase 2 merge join (D-1c)**: the Phase 2 remediation migrations `0044` and `0045` are not in this branch. Reconciliation is
  documented in `docs/PHASE3_MIGRATION_RECONCILIATION.md` and is a separate reviewed commit. Only `0050`'s `down_revision` changes.
- **Phase 2 and Phase 1 acceptance (D-1b, D-1e)**: not performed here.
- **Production outbox transport and its credentials (D-2)**: later-phase (notification and outbox phase, H-50/H-52) and
  operator-provided. The Phase 3 interface is in place; the test profile uses the capture sink.
- **Production worker login, outbox encryption key, sweep ceremony login, process manager (D-4, D-5)**: deployment items.
- **Shared cluster 5433**: leftover role `webdesk_authority_test_9c007c88774a` (no attached session), held until Phase 2 releases
  the cluster. The dedicated Phase 3 cluster has no leftover roles.

## Known limitations (report, do not re-discover)

- Contact liveness predicates in `identity/contacts.py` still use `now()`. They are outside the H-21 file list, so they are a
  residual rather than a gap in the listed requirements.
- A stale worker that has lost its lease writes no audit row (the approved fence rule). Its refusal appears only in the log.
- The heartbeat interval is measured on the worker's monotonic clock; each renewal stamps database time. The approved text says
  "every 30 seconds of database time".
- The integration base and hardening databases must be migrated to head before the rolled-back and hardening suites run. A
  stale integration base produced 12 failures in one run.
- The dedicated cluster bootstrap is test-only and not committed. Its non-default settings (test-owner memberships with SET, the
  hardening objects owned by the integration owner, and the superuser bootstrap migration) are described in the evidence report.

## Verdict

PHASE 3 ENGINEERING COMPLETE — READY FOR INDEPENDENT QA. Engineering evidence covers H-20 to H-27 as scoped. Independent review and
acceptance remain open.

## QA remediation (F-1, F-2)

- F-1 (MINOR, fixed): the privilege audit depended on test order (a worker test login created by another module). Fixed in
  `071e228` by a per-process test worker login from one helper (`tests/support/worker_login.py`). Verified alone, after the
  durable file, and in the full suite on a fresh cluster (723 passed). Re-test: run the audit first on a fresh cluster.
- F-2 (MINOR, disposition only): contact-liveness `now()` in `identity/contacts.py`. Database time, outside H-21's explicit
  file list. No semantic change. WDS decision needed on whether H-76 covers it. Details: `docs/PHASE3_DECISION_EVIDENCE.md`
  section 6.
- F-7 (INFORMATIONAL): worker-role probes used `SET ROLE` from the integration owner, not a worker login. See the decision
  evidence, section 7.
- Verdict for this remediation: PHASE 3 QA REMEDIATION COMPLETE — READY FOR INDEPENDENT RE-TEST. Not an acceptance.

