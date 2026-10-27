# Foundation Phase 2: handoff for independent review

Branch: `feature/foundation-phase-2` (local only; not pushed, not merged). Base: `3a38685`.
Evidence: `docs/PHASE2_EVIDENCE.md`. Scope: Increment 3 hardening plan Phase 2, items H-10 to H-14.

## Status

Ready for independent Phase 2 review, not accepted. Caveats the reviewer must weigh:

- Teardown: two earlier full-suite runs failed teardown on different tests with a backend that had no user. The cause
  is not established. The final ordered pass had no teardown errors. A bounded wait (5 seconds) was added and is
  exercised; it absorbs closing sessions and still fails persistent ones (see the evidence, section 6).
- Leftover test databases from earlier failed teardowns remain on the cluster; dropping them was not permitted.
- A temporary probe file may remain untracked in the worktree until removed.


- Implemented and verified locally (ordered pass at `c80b0d5`'s code): full suite 666 passed, 0 failed, 0 errors;
  ruff check clean; mypy strict clean; migration 0043 round trip (head, down to 0042, up) with the downgrade
  matching the 0042 function snapshot. Ruff format: six documented exceptions.
- Not accepted. Phase 2 is not declared accepted. Phase 1 independent acceptance is a separate gate and is not recorded
  here.

## What to review

1. Migration `migrations/versions/0042_phase2_identity_controls.py`: additive; new proof operations, rules, three guard
   functions, one authority function replacement, and `UPDATE` on the two grant tables for `webdesk_guard_owner`.
   Check the downgrade restores the 0041 catalog.
2. H-10 denial durability: `src/webdesk/tokens/service.py` `consume()`, `src/webdesk/auth/service.py` `_denied_token()`.
3. H-11 approval liveness: `_approval_is_live()` in `issue()` and `consume()`; savepoint on consume.
4. H-12 status codes: `src/webdesk/rbac/assign.py` `_appointment_refusal()`.
5. H-13 `reject_change()` in `src/webdesk/identity/contacts.py`.
6. H-14 `revoke_project_grant()` and `revoke_restricted_grant()` in `src/webdesk/projects/service.py`.

## Points needing an explicit reviewer decision

- `tests/committed/test_deadlines.py::test_a_bootstrap_token_is_refused_once_the_appointment_has_expired` now expects
  the H-11 application refusal (`approval_not_live`) instead of the database message. The database refusal remains
  asserted in `tests/integration/test_security_closure.py`.
- `tests/integration/test_role_assignment.py` expects 403 `appointment_required` where it previously expected 409, per
  F11f. Reviewer to confirm this is the approved rule.
- Hardening tests now take their database name from `WEBDESK_HARDENING_OWNER_URL` (previously hard-coded
  `webdesk_hardening`). No assertion changed.

## Not in this phase

H-20 to H-27 (durable execution, Phase 3), H-50 and H-52 (notification and outbox, Phase 6). Not started.

## Commits

See the commit list in the final report of the Track A session. No push, no merge, no release.
