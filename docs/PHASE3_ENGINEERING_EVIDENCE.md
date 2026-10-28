# Phase 3 engineering evidence (durable execution, H-20 to H-27)

Branch `feature/foundation-phase-3`. Committed base `e9d888a`. Requirements matrix:
`docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md`. Demonstration output: `docs/PHASE3_DEMONSTRATION_OUTPUT.txt`.

## Dedicated test cluster

- Compose project `webdesk-phase3-closure`, file `infra/test-clusters/compose.yml` (shared template, unchanged).
- Container `webdesk-phase3-closure-postgres-1`, image `postgres:16.4`, bound to `127.0.0.1:5440`, named volume
  `webdesk-phase3-closure_pgdata`. Health check: healthy.
- Credentials were generated at bootstrap and kept in a session scratch file outside the repository. No password is in a
  tracked file or in this report.
- The existing `webdesk-phase3-test` cluster on `127.0.0.1:5435` (created 16:02 under the shared test-cluster template)
  was **not used**: its owner and approval could not be verified from this session, and its superuser credential was not
  available. Phase 2 cluster on 5434 and the shared cluster on 5433 were **not touched** by the verification runs below.
- Role bootstrap (not in migrations; documented procedure, test-only):
  - `webdesk_integration_owner`: LOGIN, NOSUPERUSER, CREATEDB, CREATEROLE (test provisioning).
  - `webdesk_test_owner`: LOGIN, NOSUPERUSER (hardening owner; member of `webdesk_ceremony`).
  - `webdesk_app_login`: LOGIN, NOSUPERUSER (member of `webdesk_app`).
  - Memberships granted with `INHERIT TRUE, SET TRUE` so that `SET ROLE` works for the test owner (the first grants
    had SET disabled and were refused).
  - Databases: `webdesk_p3c_integration` (owner `webdesk_integration_owner`), `webdesk_p3c_hardening` (owner
    `webdesk_test_owner`). Both migrated to head `0051_worker_fence_diagnostics`.
  - Migrating the hardening database required the superuser (the hardening plan allows this for bootstrap only). Objects it
    created were handed to `webdesk_integration_owner`, the state the `owner_engine` fixture expects. The superuser's
    guard-owner membership, granted by that migration, was removed.

## Authority credential race: root cause

- `tests/support/authority.py` set a fresh random password on the **cluster-wide** `webdesk_authority_login` role in each
  test process, and cached it per process.
- Two processes against one PostgreSQL server therefore invalidated each other. The second process's `ALTER ROLE`
  made the first process's authority refuse every login (`password authentication failed for user
  "webdesk_authority_login"`). The API surfaced this as 403 `request_refused`, and in some tests as 401.
- Reproduced twice: once in a two-process probe (the first process's cached password stopped working after the second
  provisioned); and in the Phase 2 session's gate runs.
- **Clean-baseline reproduction**: committed `e9d888a` exported to a scratch copy, `tests/committed/test_ai_read_v1.py`:
  15 failed, 13 passed. The Phase 3 tree on the shared cluster reported 17 failed, 11 passed. The failure is pre-existing;
  Phase 3 changed neither the authority nor the role.

## Fix (uncommitted at the time of writing; see commit list)

- `tests/support/authority.py`: each test process creates its own login role `webdesk_authority_test_<random>`, a member of
  `webdesk_authority` with the same non-privileged attributes as the shipped role, and drops it at process exit.
- The shipped `webdesk_authority_login` role, migration 0023 and the privilege-audit assertion about it are unchanged.
- Verified on the dedicated cluster: two independent processes, the first still authenticates after the second provisions
  (an inline probe script, not committed; no credential values printed). No `webdesk_authority_test_*` role or
  session was left after the runs (checked: 0 and 0).
- Cleanup is process-scoped: the role is dropped at exit only if it still exists; a failed drop is reported, not
  retried against another process's role.

## Runs (dedicated cluster `127.0.0.1:5440`, `WEBDESK_ENV=test`)

| Run | Command | Timestamp (UTC) | Result | Exit |
|---|---|---|---|---|
| AI Read v1 (first, after fix, shared cluster 5433; superseded by the dedicated-cluster run) | `pytest tests/committed/test_ai_read_v1.py -q` | 2026-10-28 | 28 passed | 0 |
| AI Read v1 (dedicated cluster) | `pytest tests/committed/test_ai_read_v1.py -q` | 2026-10-28 | 28 passed | 0 |
| Full Foundation regression (first on dedicated cluster) | `pytest -q` | 10:58:15Z to 11:07:39Z | 705 passed, 2 failed (environment: privilege bootstrap, see below) | 1 |
| Full Foundation regression (final) | `pytest -q` | 11:09:52Z to 11:18:26Z | **707 passed**, 1 warning | **0** |
| Synthetic durable-execution demonstration | `pytest tests/committed/test_durable_execution.py -q -s -k phase3_demonstration` | 2026-10-28 | 2 passed | 0 |
| Ruff check | `ruff check src tests migrations` | final tree | all checks passed | 0 |
| Ruff format policy | `ruff format --check` on changed files only (18 files) | final tree | already formatted | 0 |
| Strict mypy | `mypy --strict src/webdesk` | final tree | 64 files, no issues | 0 |

The two failures of the first dedicated-cluster run were bootstrap artefacts, fixed without changing any test or guard:
the superuser held the guard-owner membership left by the migration (privilege audit), and the hardening tables were owned
by the superuser, so the test owner could not update grant rows. Both were corrected in the cluster and the final full run
passed.

The tree tested is the working tree at the time of the final run (HEAD `e9d888a` plus the uncommitted changes listed under
"Commits"). The worktree was not changed during the final run.

## Concurrency and worker tests (in the final regression)

- Real PostgreSQL, two connections: competing claim refusal; cancellation waits for a claim without deadlock; renewal and
  step-fence race (four renewers, two holders, no deadlock, all renewals accepted).
- Subprocess tests: SIGKILL recovery and attempt counting; three-crash exhaustion and reaper; graceful stop (exit 0);
  hung-step abort (exit 70) with lease recovery.
- Stale-worker refusals: lease lost after expiry; reclaimed lease writes nothing; checkpoint overwrite refused; cancelled
  run cannot complete or resume.

## Privilege and migration evidence

- `tests/hardening/test_privilege_audit.py` (17 tests) passed on the dedicated cluster in the final run. The worker
  execute set now includes `fn_worker_hold_lease` (0051) and `fn_worker_stuck_jobs` (0051); the reaper (0050) remains
  worker-only.
- Migration cycle: `tests/committed/test_migration_cycle.py` passed in the final run. It clones the head template,
  downgrades through 0051 and 0050 to 0043, re-upgrades, and compares the catalog against the head reference.
- Revision IDs: `0050_durable_execution` is unchanged (committed; not edited). `0051_worker_fence_diagnostics`
  (`down_revision` 0050) adds two guard functions and their grants only. The revision string fits the 32-character
  `alembic_version` column.

## Demonstration

Output: `docs/PHASE3_DEMONSTRATION_OUTPUT.txt`. Both narrated tests pass: a claim, a SIGKILL interruption, a competing
worker refused, lease recovery, a stale worker refused, completion; a heartbeat keeping a lease alive through a step with no
commit, the abrupt-stop stuck report, retry exhaustion to a reaper failure with the slot released, and a graceful SIGTERM
during a step ending with exit 0.

## Commits

Recorded in the QA handoff after the commits are made.

## Known limitations (carried into the QA handoff)

- H-21 ceremony authorization expiry in `prepare_install` still uses the injected clock (decision D-3).
- The audit `correlation_id` UUID column is not populated by the worker audit function (G-7); the key is in logs and
  audit details.
- Production outbox transport, ceremony login provisioning and process manager remain deployment or later-phase
  dependencies (D-2, D-4, D-5).
- Phase 2 remediation migrations `0044` and `0045` are not in this branch. See the reconciliation procedure.
