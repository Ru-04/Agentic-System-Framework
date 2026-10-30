# Phase 5 (X7) final QA closure

Scope: INCREMENT_3_HARDENING_PLAN.md Phase 5, H-40 (supersession marks stale), H-41 (in-flight check
excludes superseded versions), H-42 (archive and start serialized by the project-row lock).

## Commits

| SHA | Purpose |
| --- | --- |
| 3a38685 | Parent baseline (feature/increment-1-foundation) |
| b86be7c | H-40, H-41, H-42 implementation and 10 X7 tests (migration 0042) |
| 34ac004 | QA medium defect: worker intake overwrote the `superseded` reason (migration 0043, regression test) |
| 8fac895 | QA finding 4: lock-wait helper pinned to the blocked backend PID (test only) |
| f001b9d | Hardening fixture: expired-grant setup uses the hardening owner (test only) |

Final code SHA: **f001b9d**. Independent QA reviewed **f001b9d**.

## Verification

Developer (webdesk-p5-postgres, port 5480, PostgreSQL 16.4):
- Full suite on f001b9d: 660 passed, 0 failed, 0 skipped, exit 0.
- X7 tests: 11 passed. Hardening: 210 passed, exit 0.
- Ruff check and format on changed files: pass. mypy --strict src/webdesk: pass.

Independent QA (webdesk-p5-qa-postgres, port 5481, PostgreSQL 16.4, separate checkout):
- Full suite on f001b9d: 660 passed, 0 failed, 0 skipped, exit 0.
- X7 tests: 11 passed, exit 0. Hardening: 210 passed, exit 0.
- Ruff, format and mypy: exit 0.
- Verdict: **QA PASSED — eligible for WDS Phase 5 acceptance** (assessment only).

Mutation evidence:
- Reverting the 0043 guard (restoring the unguarded 0031 mark) makes
  `test_h40_the_superseded_reason_survives_worker_intake` fail, observed on both clusters.
- Removing the H-41 superseded clause makes `test_h41_a_superseded_pending_version_does_not_make_the_run_stale` fail.
- Race tests verified against real PostgreSQL locks, waiting on the blocked backend's PID.

## Findings and dispositions

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 1 | Medium | Worker intake overwrote the `superseded` stale reason | **Fixed** in 34ac004 (migration 0043). Verified by the independent reviewer. |
| 2 | Low | Denial audit not asserted in the start-first race test | **Fixed** in 34ac004. |
| 3 | Low | No HTTP route or CLI calls `archive_project` | **Accepted as an X7 scope limitation, pending WDS confirmation.** See below. |
| 4 | Low | Lock-wait helper matched any lock waiter | **Fixed** in 8fac895 (blocked-backend PID). Re-verified. |
| 5 | Low | Worker stale mark has no lease or owner check | **Pre-existing, cross-phase security dependency (Phase 3).** Not closed by Phase 5. See below. |

### Finding 3: archive has no external entry point

- Evidence: `archive_project` has no caller in `src` other than its definition. The only exposed start path is
  `api/routes.py:249`, which calls `runs.start_run` inside `run_in_transaction`.
- H-42 names `projects/service.py` and `runs/service.py` as its primary code, and requires serialization by the
  project-row lock. Both services enforce it: `archive_project` locks, rechecks active runs and raises
  `ProjectServiceError(409, "active_run_exists")`; `start_run` locks and raises `project_archived` or
  `revision_conflict`.
- Limitation: no endpoint in this commit returns a 409 for a refused archive. The 409 is the service contract only.
  No Phase 5 acceptance criterion mandates an HTTP or CLI interface.
- Proposed disposition: accept as a scope limitation. **WDS to confirm.**

### Finding 5: worker stale mark without lease check

- Function: `webdesk_guard.fn_worker_mark_inputs_changed(uuid)`, created by migration 0031 (Phase 3 worker
  migration). Owner `webdesk_guard_owner`, `SECURITY DEFINER`. Phase 5 changes the body in 0043 (adds
  `is_stale = false`), keeps owner and grants, and changes nothing else.
- EXECUTE: `webdesk_worker` (group role) and, through it, `webdesk_intake_worker_login`. Also the owner and
  administrative roles. `webdesk_app` has no EXECUTE.
- Caller: `runs/jobs.py` (`execute_intake`), reached only from `process_one` after a claim. The function itself
  does not check the lease or owner.
- Phase 5 neither introduces nor widens this path. H-40 calls `fn_mark_downstream_stale` from the admission
  guard, not this function. H-41 only reads. 0043 narrows the effect: the function can no longer overwrite an
  existing stale reason.
- Residual risk, unchanged by Phase 5: a worker login can mark any run stale by UUID, and a worker whose lease
  expired between the renewal at `jobs.py:159` and the mark can still set the flag. This is an integrity and
  availability issue, not a read or privilege escalation. The job-owner check at finish still detects the lost lease.
- **Not declared safe.** Required Phase 3 remediation: require the caller's lease owner and job id inside the
  guard, as the other worker functions do. Owner: Phase 3 (durable execution, worker fencing).

## Hardening failures: investigation and classification

Both failures on the developer and independent clusters came from the test environment, not from Phase 5 code.

1. `test_the_guard_owner_is_not_a_login_role_and_no_login_holds_it`: the hardening migration was run as
   `webdesk_test_owner`. Migration 0011 runs `GRANT webdesk_guard_owner TO CURRENT_USER`, which gave the test owner
   guard-owner membership. Fix: migrate `webdesk_hardening` as the superuser, then reassign user relations to
   `webdesk_test_owner`. Class C (QA setup). No assertion changed.
2. `test_an_expired_grant_is_refused`: the `owner_engine` fixture connected as the integration owner to a database
   and tables owned by `webdesk_test_owner`, and the setup UPDATE was refused. Fix: the fixture now uses
   `WEBDESK_HARDENING_OWNER_URL` (commit f001b9d). Class C (QA setup). Assertions unchanged; the restricted login
   remains the only role under test.
3. 108 skips on the developer cluster: `WEBDESK_INTEGRATION_OWNER_URL` was unset. Class C (developer setup).
   After setting it, the hardening suite runs 210 tests with 0 skipped.

## Dependency register

| Dependency | Owner | Status |
| --- | --- | --- |
| Finding 5: lease/owner check for `fn_worker_mark_inputs_changed` | Phase 3 | Open, cross-phase security dependency |
| Phase 3 lock order (H-25, job then run) vs. H-42 (project then run) | Phase 3 and Phase 5 | Not verified in this sprint beyond the X7 race tests; integration test required |
| `start_run` now bumps `projects.revision` (H-42) | Phase 2/4 interface owners | Contract change; their integration tests must accept it |
| Migration ancestry: 0042 and 0043 on top of 0041 | Integration | Reconciliation required before any merge |

## Acceptance status

- Engineering: complete at f001b9d.
- Independent QA: **PASSED** on f001b9d.
- WDS formal acceptance: **GRANTED for the standalone X7 scope**, decision dated 30 October 2026
  (Asia/Kolkata), accepted implementation commit f001b9d, documentation commit 3d7e789. The decision text was
  supplied in chat by the user and is not verified against an authoritative register.
- Dispositions recorded by WDS: Finding 3 accepted as a scope limitation (service-layer H-42 only). Finding 5
  assigned to Phase 3 as a required cross-phase security and fencing dependency; the function is not declared
  secure.
- Governance gaps: the approver identity, signature, approval channel and artifact hashes are not in the
  repository. They must be obtained through the approved governance process. None have been invented here.
- Cross-phase integration: **PENDING**. Acceptance does not cover deployment, unreviewed merges or
  waiver of Phase 3 security or fencing requirements.
- Branch `feature/foundation-phase-5` is not merged or deployed.

## Resources

- Developer cluster: container `webdesk-p5-postgres`, port 5480. Retained.
- QA cluster: container `webdesk-p5-qa-postgres`, port 5481. Retained.
- QA checkout: `D:\WDS\qa-x7-b86be7c` (detached worktree). Retained for evidence.
- Cleanup, when authorized by the owner: remove the QA checkout with `git worktree remove`, stop and remove the
  two containers, and delete the volumes only with explicit owner approval.
