# Phase 2 final gate: evidence and status

Branch `feature/foundation-phase-2`. Final remediation commit under test: `111f304` (seven commits on top of `4a9a38d`).
Status: **the three-run gate is not complete.** This document records every run and why each is not counted.

## 1. PostgreSQL outage on localhost:5433 (root cause and recovery)

- Symptom: connections refused on 5433 during the first gate attempt.
- Evidence: the Docker Desktop service (`com.docker.service`) was stopped. All containers on that engine exited with code 255 at 10:01 UTC, including unrelated projects. The Phase 2 container `agenticsystemframework-postgres-1` (image `postgres:16.4`, volume `agenticsystemframework_webdesk_pgdata`) exited with code 255 at the same moment. Its logs show no fault of its own. The daemon was running again at 10:03 UTC.
- Recovery: `docker start agenticsystemframework-postgres-1`, the existing container only, with its existing volume. PostgreSQL ran crash recovery (WAL redo completed) and accepted connections. No cluster was reset or recreated, no configuration changed, no other container touched.
- Classification: environmental (engine stopped), not a database defect. Cause of the engine stop is not established from the logs available here.

## 2. Cross-session interference on the same cluster

The authority login role `webdesk_authority_login` is **cluster-wide**. Any process that sets its password breaks every other process using it.

- Another worktree (`foundation-phase-3`, a separate Claude session) ran `pytest tests/committed/test_ai_read_v1.py` against the same cluster from 15:54 onward, and later two full-suite pytest processes from 15:57 (pids 11124, 35144). Its session reports the root cause as a per-process password reset in `tests/support/authority.py` and says its fix is uncommitted.
- Effect on this sprint: gate runs 1 and 3 failed with `password authentication failed for user "webdesk_authority_login"` (20 and 16 failures, 108 errors each). The owner-reset failures in those runs are the same authority-login error, not an independent owner-reset defect.
- The runner now refuses to start while any other pytest process is running (`run_suite.py`, exit 3).

## 3. Run ledger

| Run | Commit | Namespace | Command | Result | Exit | Counted |
|---|---|---|---|---|---|---|
| gate-1 | 111f304 | `gate-1` | `pytest tests -q` | 20 failed, 553 passed, 108 errors (authority login, cross-session) | 1 | No: overlapped Phase 3 pytest |
| gate-2 | 111f304 | `gate-2` | `pytest tests -q` | 681 passed, 1 warning | 0 | Not counted: no overlap check at start, Phase 3 pytest active from 15:54 |
| gate-3 | 111f304 | `gate-3` | `pytest tests -q` | 16 failed, 557 passed, 108 errors (authority login, cross-session) | 1 | No: overlapped Phase 3 pytest |
| gate-4 | 111f304 | `gate-4` | `pytest tests -q` | refused before start (other pytest running) | 3 | No |
| gate-7 | 111f304 | `gate-7` | `pytest tests -q` | started 15:56:52; its wrapper was stopped; its output ended after ~11 tests, no summary | not obtained | No: Phase 3 full suite started 15:57:06 on the same cluster |

Gates 8 and 9 were not started.

## 4. Gate status

**Not met.** The gate needs three complete sequential passes on the committed SHA with no overlapping database run, exit 0 each. Only one of the runs (gate-2) passed, and it cannot be counted as overlap-free.

Blocking dependency: pids 11124 and 35144 (Phase 3 session's full-suite runs on localhost:5433). Their owner has asked the user to decide whether to stop them. Until they end, any run here is contaminated.

## 5. Other unfinished items

- Owner-reset intermittent failure: its cause is now attributed to the cross-session password reset (section 2), but this is not proven from a clean run. The diagnostic in `src/webdesk/authority/server.py` (exception class and SQLSTATE) is in place and has not been exercised by a clean gate run.
- Migration catalog, privilege audit, AI Read Contract v1 regression: not re-run on `111f304` in a clean window.
- Namespace leftovers: runs gate-1 to gate-7 may have left labelled `wdst_gate-*` databases on the cluster. Not verified and not dropped (standing rule: no database deletion without owner approval).

## 6. Commits in this sprint

- `4a9a38d` teardown leak (NullPool) and owner-reset diagnostic.
- `5bb7d8b` F-01 grant revocation (migration 0044).
- `5ad75d7` F-05 and F-07 contact races and expiry (migration 0045).
- `c1d1025` F-04 recovery 403.
- `d470529` F-08 denial audits.
- `4148dca` F-10 catalog and privilege evidence.
- `1603bd5` F-03, F-12, F-13 namespaces and engine disposal.
- `111f304` F-06, F-09, F-11 documents.

Each commit was made from a file group. Intermediate commits were not each verified by a full run; the final SHA is the only one under gate.

## 7. Attempts on `250f90a` (latest)

| Run | Namespace | Command | Result | Exit | Counted |
|---|---|---|---|---|---|
| final-gate-1 | `final-gate-1` | `pytest tests -q` | 681 passed, 1 warning | 0 | No: poll showed a foreign pytest process during the window (main checkout, pid 1260, started 16:04:23) |
| final-gate-2 | — | refused before start (foreign pytest, pid 1260) | — | 3 | No |
| clean-gate-1 | `clean-gate-1` | `pytest tests -q` | 681 passed, 1 warning, 375.6 s | 0 | No: poller saw foreign pytest at 16:13 (35 samples) |

Cause of the remaining overlap: the main checkout (`D:\WDS\Agentic System FrameWork`) repeatedly runs `pytest tests/committed/test_ai_read_v1.py` and full-suite pytest against the same cluster (for example pids 9300 and 7988, started 16:22:24). These are not owned by this sprint and were not terminated.

Current counted result: **zero clean runs of three**. The gate is not met.

Checks run without the database on `250f90a`: `ruff check src tests migrations` passes; `ruff format --check` reports only the five documented exception files; `mypy --strict src/webdesk` passes. Git status: clean.

Not run on a clean window: migration 0042-to-head catalog comparison, privilege audit, AI Read Contract v1 regression.

## 8. Three-run gate on the dedicated cluster (counted)

Cluster: `webdesk-p2-postgres` at `127.0.0.1:55442`, system identifier `7701671162267615270`. Topology and provisioning: `docs/PHASE2_DEDICATED_TEST_CLUSTER.md`.
Code under test: commit `3ffdbbc` (code unchanged since `111f304`; the later commit only adds the git-ignore entry for the local secrets file). Command for each run: `pytest tests -q -p no:cacheprovider` through the runner, with `WEBDESK_TEST_RUN_ID` set per run.

| Run | Namespace (run id) | Start | Finish | Result | Exit | Leftover namespace DBs | Attached sessions after teardown |
|---|---|---|---|---|---|---|---|
| 1 | `p2-final3-1` | 16:49:14 | 16:55:47 | 681 passed, 1 warning | 0 | none | 0 |
| 2 | `p2-final3-2` | 16:55:48 | 17:02:39 | 681 passed, 1 warning | 0 | none | 0 |
| 3 | `p2-final3-3` | 17:02:40 | 17:09:52 | 681 passed, 1 warning | 0 | none | 0 |

Failures, errors, teardown leaks: 0 in each run. No `LeakedSessionError`, no `INTERNALERROR`.

Runs that do not count, for the record:
- Earlier attempts on `dedicated` before provisioning was complete: `p2-focus-a` (focused set, 29 failed, 10 errors: `SET ROLE` denied, integration owner had no SET option on the group roles), `p2-focus-b` (same cause, not fixed yet), `p2-final-1` (677 passed, 4 errors: worker-login ALTER denied, the worker login was pre-created as superuser), `p2-final2-1` (680 passed, 1 failed: duplicate `webdesk_worker` membership row from my superuser grant).
- Each of those was a provisioning defect fixed in the cluster, not in the code. The fixes are listed in `docs/PHASE2_DEDICATED_TEST_CLUSTER.md`.

Focused set on the dedicated cluster, before the full runs: `p2-focus-c` (73 tests: concurrency, change expiry, identity, recovery status codes, guards, projects, privilege audit, privilege hardening, migration catalog): 73 passed, exit 0.

Checks on `3ffdbbc`: `ruff check src tests migrations` passed; `ruff format --check` reports exactly the five documented exception files; `mypy --strict src/webdesk` passed (57 files).

Coverage: the AI Read Contract v1 tests (`tests/committed/test_ai_read_v1.py`), the migration catalog and downgrade/re-upgrade test (`tests/committed/test_migration_catalog.py`), the privilege audit and restricted-login tests (`tests/hardening/`), and the owner-reset tests (`tests/integration/test_owner_reset.py`) all run inside each full pass above. Their individual results are not separately recorded beyond the totals.

Status: the three-run gate on the dedicated cluster is met for `3ffdbbc`. Independent QA has not accepted the work, and no WDS acceptance is claimed.

## 9. Final gate after QA remediation (D1, D2, D3), code `ad28ac0`

Cluster: dedicated `webdesk-p2-postgres` at `127.0.0.1:55442`, system identifier `7701671162267615270`. Each run uses a unique namespace and runs sequentially; no foreign pytest process touched this cluster.

| Run | Namespace | Start | Finish | Result | Exit | Leftover namespace DBs | Attached sessions |
|---|---|---|---|---|---|---|---|
| Full 1 | `fix-gate-1` | 18:55:05 | 19:01:40 | 688 passed, 1 warning | 0 | none | 0 |
| Full 2 | `fix-gate-2` | 19:01:41 | 19:08:26 | 688 passed, 1 warning | 0 | none | 0 |
| Full 3 | `fix-gate-3` | 19:08:27 | 19:14:52 | 688 passed, 1 warning | 0 | none | 0 |
| Owner reset x10 | `fix-or-1` to `fix-or-10` | — | — | 10 passed each | 0 each | — | — |

The 688 total is the previous 681 plus five owner-reset fault-injection cases and two restricted-login contact-window cases.

Focused runs before the gate: the D2 negative tests with change-expiry, concurrency, privilege audit and migration catalog, 28 passed (`d2-focus`, exit 0). The D1 fault module against the fixed handler: 5 passed, and the earlier negative control (old handler): 4 failed, 1 passed (`d1-neg`, exit 1 as expected). The concurrency module three times in a row: 5 passed each, exit 0 (`d3-conc-1` to `d3-conc-3`).

Static checks on `ad28ac0`:
- `ruff check src tests migrations`: all checks passed.
- `ruff format --check src tests migrations`: 5 files, exactly the documented exception list (the new `0046` migration was formatted).
- `mypy --strict src/webdesk`: `mypy 1.11.2`, 57 source files, "Success: no issues found", exit 0.

Migration: `0046_fixed_contact_change_window` applied to the dedicated base database (`alembic upgrade head`, exit 0). Downgrade and re-upgrade are exercised by the migration catalog test, which passed in every full run.
