# Foundation Phase 2 evidence (Track A, branch `feature/foundation-phase-2`)

Status: **implemented and locally verified; not accepted.** Phase 2 has not been merged, pushed, released or declared
accepted. Independent Phase 2 review is pending, and the Phase 1 independent acceptance is a separate gate.

Base: `3a38685` (branch `feature/increment-1-foundation`). Migration head before this work: `0041_ai_read_v1`.

## 1. Gap matrix (Increment 3 hardening plan, Phase 2: H-10 to H-14)

| ID | Requirement | Implementation | Positive test | Negative test | Status |
|---|---|---|---|---|---|
| H-10 | A refused activation or reset is audited, and the audit survives the refusal | `tokens/service.py` `consume()` audits `token.consume.denied` inside the caller's outer transaction; `auth/service.py` `_denied_token()` writes the row in `activate()` and `reset_password()` handlers | `test_a_refused_activation_is_audited_through_the_production_runner`, `test_a_refused_password_reset_is_audited_through_the_production_runner` | Same tests: the refusal raises, and the row is committed through the production runner (`run_in_transaction`) | Implemented |
| H-11 | No activation token is issued or consumed for an account whose contact approval is not live (approved, unexpired, matching the current email) | `tokens/service.py` `_approval_is_live()` checked in `issue()` (`approval_not_live`) and `consume()`; consume runs in a savepoint and rolls back on refusal | `test_a_live_approval_still_consumes_its_token_once` | `test_no_activation_token_is_issued_after_the_governing_approval_expires`, `test_a_token_is_not_consumed_once_its_approval_has_expired` | Implemented |
| H-12 | Appointment refusals carry the approved status codes: missing or foreign appointment is 403; lapsed or consumed is 409 (F11f, F11h) | `rbac/assign.py` `_appointment_refusal()` and `_map_trigger_refusal()` classify by a state lookup | `test_appointment_refusals_are_403_when_not_held_and_409_when_lapsed` | `test_below_two_an_administrator_grant_needs_an_appointment` now expects 403 `appointment_required` (the earlier 409 expectation contradicted F11f; the test was corrected, not the rule) | Implemented |
| H-13 | An Administrator can reject a pending contact change; the current contact is kept and the reservation is released | Migration `0042` adds proof op `contact.reject.change` and `webdesk_guard.fn_reject_change_with_proof`; `identity/contacts.py` `reject_change()` | `test_an_administrator_rejects_a_contact_change_and_the_current_contact_is_kept` (integration), `test_phase2_identity.py` | Non-Administrator is refused without a proof (`ProofNotIssued`) | Implemented |
| H-14 | An Administrator can revoke a project access grant and a restricted-content grant; each revocation is audited; an account cannot revoke its own grant | Migration `0042` adds proof ops `project.access.revoke`, `restricted.revoke` and guard functions `fn_revoke_project_access_with_proof`, `fn_revoke_restricted_grant_with_proof`; `projects/service.py` `revoke_project_grant()`, `revoke_restricted_grant()` | `test_an_administrator_revokes_a_project_grant_and_the_revocation_is_audited`, `test_an_administrator_revokes_a_restricted_grant_and_a_holder_cannot_revoke_its_own` | `test_a_grant_holder_cannot_revoke_its_own_grant` | Implemented |

## 2. New migration

`migrations/versions/0042_phase2_identity_controls.py` (additive; revisions 0001 to 0041 unchanged).

- Adds three operations to the `operation_proofs` check constraint (29 operations to 32).
- Inserts three `operation_authorization_rules` rows (Administrator, membership not required).
- Replaces the authority function `fn_issue_operation_proof` with the same body and the three operations added to the
  allowlist and to the Administrator list (the 0041 text is embedded for an exact downgrade).
- Creates three guard functions (`SECURITY DEFINER`, pinned `search_path`), revokes PUBLIC execute and grants execute to
  `webdesk_app`.
- Grants `UPDATE` on `project_access_grants` and `restricted_content_grants` to `webdesk_guard_owner` (needed to set
  `revoked_at`; the downgrade revokes it again).
- Downgrade removes the functions, the rules and the proof rows for the new operations, restores the 29-operation
  constraint and the 0041 authority text.

Round-trip check: see section 5.

## 3. Modified services

| File | Change |
|---|---|
| `src/webdesk/tokens/service.py` | H-11 liveness check in `issue()` and `consume()`; savepoint around consume; denial audit |
| `src/webdesk/auth/service.py` | `_denied_token()` audit in activation and reset refusals (H-10) |
| `src/webdesk/rbac/assign.py` | Appointment refusal classification (H-12) |
| `src/webdesk/identity/contacts.py` | `reject_change()` (H-13) |
| `src/webdesk/projects/service.py` | `revoke_project_grant()`, `revoke_restricted_grant()` (H-14) |

## 4. Tests

New or changed test code:

- `tests/committed/test_phase2_identity.py` (new): H-10, H-11, H-12 through the production runner and committed data.
- `tests/integration/test_contact_lifecycle.py`: H-13.
- `tests/integration/test_projects.py`: H-14.
- `tests/integration/test_role_assignment.py`: F11f status-code correction (403, was 409).
- `tests/hardening/test_privilege_audit.py`: the three new functions are pinned to the application role.
- `tests/committed/test_deadlines.py`: the bootstrap token refusal after the approval window now asserts the H-11 refusal
  (`approval_not_live`). The database-level ceremony refusal is still asserted by
  `tests/integration/test_security_closure.py`.
- `tests/hardening/test_source_read_authorization.py` and `tests/hardening/test_privilege_hardening.py`: these hard-coded the
  database name `webdesk_hardening` for their owner-role state changes, while the login engine used the database named in
  `WEBDESK_HARDENING_OWNER_URL`. In a separate-database run the state change landed in another database, so the tests
  did not see it. They now take the database name from `WEBDESK_HARDENING_OWNER_URL`. No assertion was changed.

Results: see section 6.

## 5. Migration round trip

Script: `scratchpad/p2_mig.py` (run through `scratchpad/p2final.sh`, which exports `S`). Checks: head catalog, downgrade
by one step, upgrade again, and catalog equality through `pg_get_functiondef` snapshots.

## 6. Verification results

Run order: rebuild of the Phase 2 databases (`webdesk_p2_integration`, `webdesk_p2_hardening`) to head, then the full
suite, ruff, mypy and the round trip. Exit codes are from `scratchpad/p2final/status`.

| Step | Result | Exit |
|---|---|---|
| Rebuild of `webdesk_p2_integration` and `webdesk_p2_hardening` to head | ok | 0 |
| Full suite (`pytest tests`) | 659 passed, 0 failed, 0 errors (1 warning, DeprecationWarning from starlette) | 0 |
| Ruff check (`src tests migrations`) | All checks passed | 0 |
| Ruff format `--check` | 6 files would be reformatted, exactly the documented exceptions in `docs/RUFF_FORMAT_EXCEPTIONS.md` (0017, 0019, 0020, 0040, `test_privilege_hardening.py`, `test_reassessment.py`) | 1 (documented exceptions only) |
| Mypy strict (`src/webdesk`) | no issues, 57 source files | 0 |
| Migration round trip (head, down -1, up) | head catalog (106 functions) and post-round-trip catalog byte-identical (`cmp` of snapshots) | 0 |

Failures found in the first pass and their fixes are listed in section 4 (test-only changes; no Phase 1 assertion weakened).

## 7. Deferred (not in Phase 2 scope)

Per the approved hardening plan these are separate phases and are **not** implemented here:

- H-20 to H-27 durable execution: Phase 3.
- H-50 and H-52 notification and outbox lifecycle, administrator installation and recovery invariants: Phase 6.
- Session revocation correctness beyond the existing controls: Phase 6 scope as mapped in the plan.

No Phase 3 work was started.

## 8. Known limits

- The ruff format exceptions are unchanged: six files (`docs/RUFF_FORMAT_EXCEPTIONS.md`). Migration 0042 is formatted.
- The test databases are separate (`webdesk_p2_*`). Shared databases of other sessions were not modified.
