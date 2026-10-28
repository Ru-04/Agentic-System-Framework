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
