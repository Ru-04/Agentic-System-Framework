# Phase 3 independent QA re-test: delta package

For an independent QA agent. Do not rely on the developer's report. Inspect and test the new implementation.

## Baseline and new commits

- Previously accepted QA baseline: **`4829386`** (independent QA verdict "QA PASSED, eligible for WDS acceptance", on a
  dedicated QA cluster). That verdict does not cover the commits below.
- New commits, oldest first:
  1. `e3c2929`: contact-approval liveness on the database clock (F-2). Migration `0053_contact_approval_clock`; Python
     predicates in `src/webdesk/identity/contacts.py` and `src/webdesk/tokens/service.py`; test file
     `tests/committed/test_contact_approval_expiry.py`.
  2. `60f6cc5`: heartbeat scheduling wording (`src/webdesk/runs/heartbeat.py` docstring only); deterministic fence test
     and delayed-renewal test (`tests/committed/test_durable_execution.py`); real restricted worker-login G-7 tests and
     orphan-login cleanup procedure and tests (`tests/committed/test_worker_login.py`, `tests/support/worker_login.py`).
  3. `969f610`: migration `0054_contact_change_reject_clock` (re-issues `fn_reject_change_with_proof`, which the 0053
     inventory missed). Test catalog updated.
  4. `db844ed`: correction of the `0053` downgrade text. The first downgrade used text parsed from source and did not match
     the live catalog for three routines; the round-trip catalog test caught it. The downgrade now restores the pre-0053
     definitions captured from the live catalog at 0052, using one `SET ROLE` and one `RESET ROLE`. The upgrade text is
     unchanged. `0053` was local, never pushed, and not accepted, so this is a branch-local correction.
  5. The documentation commit that follows this package (governance record, matrix, evidence, this package).

## Exact SQL routines changed (migration `0053`)

Owner `webdesk_guard_owner` for all nine. Only the approval-liveness predicate changes, `now()` becomes
`clock_timestamp()`. The boundary is unchanged: live strictly while `expires_at > clock`.

| Routine | Predicate changed | Previous definition |
|---|---|---|
| `fn_advance_contact_revision` | `expires_at > now()` | `0011_guard_owner_functions` |
| `fn_approve_change_with_proof` | `a.expires_at > now()` | `0026_proof_guarded_contacts` |
| `fn_approve_create_with_proof` | `a.expires_at > now()` | `0026_proof_guarded_contacts` |
| `fn_cancel_change_with_proof` | `a.expires_at > now()` | `0026_proof_guarded_contacts` |
| `fn_reject_create_with_proof` | `a.expires_at > now()` | `0026_proof_guarded_contacts` |
| `fn_issue_ceremony_activation` | `a.expires_at > now()` | `0039_security_closure` |
| `fn_issue_owner_reset_token` | `a.expires_at > now()` | `0028_owner_initiated_reset` |
| `fn_issue_token` | `a.expires_at > now()` | `0014_token_and_insert_guards` |
| `fn_revoke_expired_activation_tokens` | `a.expires_at > now()` | `0014_token_and_insert_guards` |

Not changed (out of the WDS ruling's scope, and recorded as such): session, proof, token-lifetime, approval-timestamp
(`approved_at = now()`), reservation (`released_at = now()`), grant (`restricted_grants`) and idempotency `now()` uses. The
Python session check (`auth/service.py`), idempotency (`idempotency/service.py`) and restricted-grant read
(`rbac/sql_store.py`) are unchanged.

The Python approval-liveness predicates changed: `identity/contacts.py` (pending-approval read, and the create-replace
liveness check) and `tokens/service.py` (approved-contact check and pending-change check).

## Migration and rollback behaviour

- `0053` is additive: `down_revision` `0052_audit_correlation`. `0050`, `0051` and `0052` are not edited.
- Upgrade re-issues the nine functions with `CREATE OR REPLACE` under `SET ROLE webdesk_guard_owner`. Owner, grants and
  SECURITY DEFINER settings are kept.
- Downgrade restores the exact prior text of each function, captured from the head of `0052`.
- Verified on a throwaway database: upgrade to `0053`; downgrade to `0052` (approval predicates back to `now()`);
  upgrade to `0053` again; catalog identical to the first upgrade across the nine routines. The database was dropped.
- SHA-256 of `migrations/versions/0053_contact_approval_clock.py` at `db844ed`: `cab2f6dccf29ae90a187a5476dcda62e21c1ce7474567d27ad24386e668510b7`.
- SHA-256 of `migrations/versions/0054_contact_change_reject_clock.py` at `969f610`: `f8e0d3c3483f5d26683c682e161974fcd876f01581ddf71878f5334bf701977f`.

## New F-2 regression tests (`tests/committed/test_contact_approval_expiry.py`)

1. Before-expiry authorization succeeds.
2. Exact-expiry instant is refused (strict comparison).
3. Post-expiry refusal, with a durable denial audit row.
4. Long transaction spanning the expiry: it began before expiry, the expiry passes inside it, and the approval is refused.
   **Against the pre-change code this test fails** (the approval is applied); with the change it passes.
5. Competing concurrent approvals: exactly one succeeds.
6. Real restricted application login: reaches the guard only as far as the operation proof, which refuses it
   (`proof_missing`); cannot write approvals directly.
7. An expired approval does not disturb a live one.
8. The deployed catalog compares approval predicates with `clock_timestamp()`. **Fails on the pre-change code.**
9. Database failure applies nothing.

Test fixture note: the expiry of a PENDING approval is set by the fixture before the test transaction begins. Approved rows
are never changed. This follows the rule that approved timestamps are not changed after issuance.

## Heartbeat clarification (WDS ruling PH3-FC-02)

- Renewal attempts are scheduled at a nominal 30 s (`HEARTBEAT_SECONDS`, capped at lease/4) on a monotonic clock.
- PostgreSQL is authoritative: a renewal stamps `clock_timestamp()` and succeeds only for the caller's own unexpired lease
  on a job still `leased`. A late tick cannot revive an expired lease. Test:
  `test_a_delayed_renewal_after_expiry_is_refused_without_any_reclaim`.
- The KEY SHARE fence (`fn_worker_hold_lease`, migration `0051`), exit code 70 on a stalled step, reaper correctness and
  cancellation/crash-recovery semantics are unchanged.

## Deterministic fence test (PH3-FC-03)

- `test_the_step_fence_blocks_reclaim_while_a_step_holds_the_job_after_its_lease_expired`: a step's open transaction keeps
  the job fenced after the lease expires; the rival claim is refused until that transaction ends.
- Important correction to earlier evidence: the earlier "fence removal" mutation only removed the Python `raise`. The SQL
  function still took the lock, so it did not remove the fence. The correct mutant makes `hold()` return without calling
  the SQL function. With that mutant, four tests fail, including this one.

## Cleanup rules and limitations (PH3-FC-04)

- Normal test completion removes the per-process worker login (`atexit`, through the maintenance database).
- A hard-killed test process may leave its login. Removal is by the procedure in `tests/support/worker_login.py`:
  `find_orphan_worker_test_logins` and `purge_orphan_worker_test_logins` (dry run by default). A login is a candidate only
  if its name matches `webdesk_intake_test_<12 hex>`, its only membership is `webdesk_worker`, it has no active session,
  and it is not this process's login. Logins with a live session are never removed. Removal is only on a cluster the operator
  has authorized for test cleanup. Failed drops are reported, never forced.
- Tests: `test_the_cleanup_removes_an_exact_orphan_and_keeps_its_dry_run_report`,
  `test_the_cleanup_never_touches_a_login_with_a_live_session`,
  `test_the_cleanup_never_touches_a_login_with_extra_membership_or_another_name`.

## G-7 with a real restricted worker login

`tests/committed/test_worker_login.py` now connects with the worker login's own password (not `SET ROLE`) and checks: a
valid correlated write (read back through the owner, because the worker has no SELECT on the audit table); refusal of a
NULL correlation (`23514`); refusal of a human actor (`23514`); refusal of an account-named actor (`23514`); refusal of a
direct audit insert (`42501`); refusal of reads and writes of `users` and of a delete on `workflow_jobs` (`42501`); refusal
of an approval guard call (`42501`).

## Full regression and static evidence

See `docs/PHASE3_ENGINEERING_EVIDENCE.md` (final section) and `docs/PHASE3_DECISION_EVIDENCE.md` (sections 8 to 10).
Commands, PostgreSQL identity, timestamps and totals are recorded there.

## Open items for the reviewer to judge

- Whether the approval-liveness scope (nine routines, plus four Python predicates) matches the WDS ruling. The unchanged
  `now()` uses listed above are the boundary of that scope.
- The F-4 limitation for hard-killed test processes is accepted by WDS (PH3-FC-04). Confirm the purge rules match it.
- WDS-assigned decision identifiers, the authorization timezone and the approver attestation are outstanding (see
  `docs/PHASE3_GOVERNANCE_RECORD.md`).

## Final state for the independent reviewer (closure of 29 October 2026)

- Final implementation commit: `db844ed`. Full regression on it: 744 passed, 0 failed, 0 errors, 0 skipped.
- Documentation commit: the commit that adds this section (documentation only; it does not change tested code).
- Commits after the prior QA baseline `4829386`, in order: `e3c2929` (0053), `60f6cc5` (heartbeat wording, F-3 and F-4
  tests, G-7 real-login tests), `969f610` (0054), `db844ed` (0053 downgrade correction).
- Reviewer must check the SHAs above, run from an independent checkout on an isolated PostgreSQL cluster, and not rely on
  this developer's report. Developer verification on the Phase 3 development cluster is not independent QA.
- Specific reproduction for the reviewer: run the F-2 suite against a checkout at `4829386` (expect the long-transaction
  test and the catalog test to fail) and against `db844ed` (expect all nine to pass).
- Specific reproduction for the 0053 downgrade: upgrade to head, downgrade to `0052_audit_correlation`, compare
  `pg_get_functiondef` of the nine routines with the 0052 state, re-upgrade.
