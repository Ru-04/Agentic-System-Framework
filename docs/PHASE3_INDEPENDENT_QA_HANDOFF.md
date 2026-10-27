# Foundation Phase 3: independent QA handoff

Branch: `feature/foundation-phase-3`. Base: `46e0e14` (committed Phase 2 state). Status: **engineering complete for
the stated scope, ready for independent Phase 3 QA. Not accepted. Not merged. Not pushed.**

Evidence: `docs/PHASE3_ENGINEERING_EVIDENCE.md`. Matrix: `docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md`.
Lifecycle: `docs/PHASE3_JOB_LEASE_LIFECYCLE.md`. Privileges: `docs/PHASE3_WORKER_PRIVILEGE_MATRIX.md`.
Dependencies: `docs/PHASE3_DEPENDENCY_REGISTER.md`. Migration reconciliation: `docs/PHASE3_MIGRATION_RECONCILIATION.md`.

## What to re-test

1. Migration `0050_durable_execution`: upgrade from the base, the downgrade to `0043`, re-upgrade, and the catalog
   comparison (`tests/committed/test_migration_cycle.py`). Check the restored 0031 and 0030 function texts in the
   downgrade.
2. Lease and fencing: `tests/committed/test_durable_execution.py`. The stale-worker, reclaim and checkpoint tests are
   the core of H-22 and the stale-worker requirement.
3. Reaper (H-24): `committed.reap_expired` and `fn_worker_reap_expired`. Check the lock order and the audit rows.
4. Lock order (H-25): the cancellation test with two connections.
5. Crash and restart (H-27): subprocess kill tests; the graceful stop test (Windows break event on this host, SIGTERM
   on POSIX).
6. Clock (H-21): ceremony deadlines now use `clock_timestamp()` (`src/webdesk/ceremony/dbclock.py`); the injected
   window is still a test duration.
7. Worker maintenance (H-26): `src/webdesk/worker/maintenance.py`. The outbox and the sweep run only when their
   configuration is complete; otherwise a `maintenance.disabled` event names the missing setting.
8. Privilege audit (`tests/hardening/test_privilege_audit.py`): the reaper is pinned for `webdesk_worker` only.

## Known limitations (report, do not re-discover)

- Phase 2 remediation is not in this branch. Its migrations `0044` and `0045` join the chain only through the
  reconciliation procedure.
- The base's committed-test clones do not re-apply the `TEMP` revocation of migration `0020`. The migration cycle test
  applies it to its own clone. The Phase 2 branch fixes the general case.
- The intermittent teardown leak seen in the Phase 2 chain (`LeakedSessionError`, a `webdesk_app_login` backend) has
  been reported at namespace teardown. Its root cause is not established. Phase 3 uses fixed database names plus
  per-test names, so it has no namespace teardown.
- Checkpoint and resume: resume applies only to waiting-for-human runs, so a cancelled run cannot be resumed (tested).
  Resume of a parked run is not a worker path.
- Outbox and sweep run only when configured. Production delivery transport and login provisioning are deployment
  dependencies (D-2, D-4).
- The worker does not emit correlation identifiers; it logs job, run, owner, attempt and outcome.
- Renewal is per committed step rather than on a 30-second timer. Each step renews, which is at least as frequent.
- Stuck-job reporting is by reaper audit and logs only; no separate report was built.

## Commands to reproduce

```
alembic upgrade head                      # on a fresh database (WEBDESK_DATABASE_URL)
pytest tests/committed/test_durable_execution.py -s
pytest tests/committed/test_migration_cycle.py
pytest tests/hardening/test_privilege_audit.py
mypy --strict src/webdesk
ruff check src tests migrations
```
