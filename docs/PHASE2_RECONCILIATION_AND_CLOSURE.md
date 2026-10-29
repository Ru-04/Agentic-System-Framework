# Phase 2 reconciliation and closure (engineering)

Branch `feature/foundation-phase-2`. Candidate code SHA: `00ec194` (code). Candidate HEAD: `86c1316` (docs only on top of `00ec194`). Verdict is in section 7.

## 1. Git history

Verified read-only (`git merge-base --is-ancestor`, `git log --graph --all`):

- The development line is linear: `3ffdbbc` → `5ac26a1` → `a7d9460` (D1) → `e03949c` (D2) → `ad28ac0` (D3) → `687c548` (evidence) → `142fecd` (D4) → `513a218` (authority harness) → `2030ebf` (gate evidence) → `00ec194` (NoResultFound) → `86c1316` (evidence).
- The QA branch `claude/p2-independent-qa-e1b03d` adds one commit, `c13781a` (independent QA report), on top of `5ac26a1`. It has no code. Merge base with HEAD: `5ac26a1`.
- No conflicting or duplicate patches. Nothing is cherry-picked. There are no diverged implementations to reconcile.
- Phase 3 commits (`f1f2a74`, `071e228`, `4829386`, `e3c2929`, `60f6cc5`) sit on a separate line from `46e0e14`. They are not part of Phase 2 and are not merged here.

Integration strategy: no merge is needed. The linear line is the single authoritative baseline. The QA report is kept on its own branch.

## 2. Requirements and QA-finding reconciliation

| Item | Source commit | Files | Disposition |
|---|---|---|---|
| F-01 grant revocation | `5bb7d8b` (in `4a9a38d` line) | migration 0044, projects service | KEEP (already present) |
| F-02 teardown leak | `4a9a38d` | `tests/hardening/test_source_read_authorization.py` (NullPool) | KEEP (already present) |
| F-03/F-12/F-13 namespaces and disposal | `1603bd5` | `tests/conftest.py`, `tests/support/*` | KEEP (already present) |
| F-04 recovery 403/409 | `c1d1025` | `ceremony/recovery.py` | KEEP (already present) |
| F-05/F-07 contacts, expiry | `5ad75d7` | migration 0045, contacts service | KEEP (already present) |
| F-08 denial audit | `d470529` | auth and tokens services | KEEP (already present) |
| F-10/F-09/F-11 evidence | `4148dca`, `111f304` | catalog test, governance docs | KEEP (already present) |
| D1 owner-reset exception boundary | `a7d9460` | `authority/server.py`, fault tests | KEEP |
| D2 approval window | `e03949c` | migration 0046, restricted-login tests | KEEP |
| D3 concurrency determinism | `ad28ac0` | `test_phase2_concurrency.py` | KEEP |
| D4 application attribution | `142fecd` | `tests/support/app_name.py`, conftest | KEEP (verified by the focused run) |
| Authority harness (ephemeral port, startup report) | `513a218` | `tests/hardening/conftest.py`, `tests/support/authority_start.py` | KEEP (verified by the focused run) |
| NoResultFound | `00ec194` | `test_ceremony_and_public_execute.py` (requests `world`) | KEEP (assertions unchanged; passes alone) |

No change was excluded. Nothing was superseded.

## 3. Test-cluster state

- Dedicated cluster `webdesk-p2-postgres` at `127.0.0.1:55442`, system identifier `7701671162267615270`. The container was restarted once after a Docker engine restart (same volume, no reset).
- Before the runs: no active sessions on `wdst_%` databases, no competing pytest process on this cluster.
- Leftover databases: the four `wdst_p2_focus_*` databases from my failed `p2-focus-a` and `p2-focus-b` runs were dropped. Their names matched the `leftover_dbs` lines my own runner printed, and each was owned by `webdesk_integration_owner`. None had attached sessions. The cluster now has no `wdst_%` databases.
- Not touched: 5433, 5434, 5440, 55434, the Phase 3 and Phase 4 containers, PID 11500, and role `webdesk_authority_test_9c007c88774a`.

## 4. Blocker A: Windows authority-child startup (unresolved)

- Symptom (from `513a218` and the QA evidence): the authority child exited before its start line in gate runs `p2fix-full1` and `p2gate-1`, with exit `0xC0000142` (DLL initialization failure) and empty stderr.
- Harness defects found and fixed in `513a218`: a probe-then-release port race (now an ephemeral port reported by the child), and uncaptured stderr (now captured and reported with the exit code).
- Reliability evidence on this candidate: focused startup tests pass (`tests/unit/test_authority_start.py`); three full passes on `86c1316` show no startup failure (693 passed each).
- Classification: **D. Unresolved.** No reproduction of the 0xC0000142 exit was obtained after `513a218`, and the component that blocked it has not been identified. The Windows Code Integrity event recorded at the time names a different worktree's `pytest.exe` and cannot be attributed to the child. The PostgreSQL password race does not explain a pre-database DLL failure and is not used as the explanation.
- Consequence: the three clean passes are evidence of the current code, not proof that Windows startup is reliable. The limitation must be stated with any counted result.

## 5. Blocker B: NoResultFound (resolved)

- Test: `test_a_login_role_cannot_disable_an_account_by_naming_a_real_administrator`.
- Root cause: a fixture defect. The test requested only `conn` and read two Administrators that only the session `world` fixture installs, so it passed only when another test had run first.
- Fix (`00ec194`): the test requests `world`. No assertion changed. Passes alone and in the full suite.

## 6. Verification

Focused run `s2-focus` on the dedicated cluster, code `00ec194`: 90 passed, exit 0. Covers the authority-start unit tests, the NoResultFound test file, D1 fault injection, D2 window tests, D3 concurrency, D4 attribution, the privilege audit, the migration catalog and AI Read v1.

Counted full runs on `86c1316` (code `00ec194`), dedicated cluster, namespaces `s2-gate-1` to `s2-gate-3`:

| Run | Start | Finish | Result | Exit | Leftover DBs | Attached sessions |
|---|---|---|---|---|---|---|
| 1 | 18:45:07 | 18:51:50 | 693 passed, 1 warning | 0 | 0 | 0 |
| 2 | 18:51:51 | 18:58:20 | 693 passed, 1 warning | 0 | 0 | 0 |
| 3 | 18:58:21 | 19:05:17 | 693 passed, 1 warning | 0 | 0 | 0 |

Static checks were run earlier on `00ec194` by the QA session (ruff lint passes; the format check lists exactly the five documented exceptions; `mypy --strict src/webdesk` exit 0, mypy 1.11.2, 57 files). Re-run on `86c1316` before the final commit.

## 7. Verdict

**PHASE 2 ENGINEERING INCOMPLETE — SPECIFIC BLOCKERS REMAIN.**

- Blocker A (Windows authority-child startup, 0xC0000142) is not root-caused. Classification D, unresolved.
- F-09 governance acknowledgement record is missing from the repository (`docs/PHASE2_GOVERNANCE_CLARIFICATION.md` section 4).
- F-06 is a Phase 6 production dependency (H-50, H-52), not a Phase 2 acceptance criterion.
- Independent QA has not run on the final SHA. The QA session's report (`c13781a`) was against `5ac26a1`. The author-led runs in this document are not independent QA.
- No WDS acceptance is claimed. Nothing was pushed, merged or deployed.
