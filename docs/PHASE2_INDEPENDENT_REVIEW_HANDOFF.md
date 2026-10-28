# Foundation Phase 2: handoff for independent review

Branch: `feature/foundation-phase-2` (local only; not pushed, not merged). Base: `3a38685`.
Evidence: `docs/PHASE2_EVIDENCE.md`. Scope: Increment 3 hardening plan Phase 2, items H-10 to H-14.

## Status

Remediation of the independent QA report (findings F-01 to F-13) is implemented on this branch and is **ready for
independent QA re-test**. It is not accepted and not closed by the implementing team.

- Finding-by-finding matrix: `docs/PHASE2_QA_REMEDIATION_MATRIX.md`.
- Engineering evidence, verification runs and exit codes: `docs/PHASE2_EVIDENCE.md` (section "QA remediation").
- Migrations and privileges: `docs/PHASE2_MIGRATION_PRIVILEGE_EVIDENCE.md` (0042 to 0045).
- Database isolation and cleanup prerequisites: `docs/TEST_DATABASE_ISOLATION.md`.
- Governance records (status codes, acknowledgement, test window, expiry rule, token delivery scope):
  `docs/PHASE2_GOVERNANCE_CLARIFICATION.md`.

Limits the re-tester must weigh:

- **Teardown (F-02).** The cause of the earlier intermittent sessions attached to disposable databases is not
  established. A bounded five-second wait and a detailed report were added. The wait does not conceal a persistent
  connection (demonstrated). Repeatability is shown over the sequential runs recorded in the evidence, which is not
  proof of deterministic cleanup.
- **Leftover databases (F-12).** Earlier leftovers were not deleted (the cleanup was denied and is not bypassed).
  Namespaced runs clean up their own labelled databases. Leftovers need an owner decision under the prerequisites in
  `docs/TEST_DATABASE_ISOLATION.md`.
- **Token delivery (F-06).** Not implemented here; belongs to the notification and outbox phase.
- **Sweep scheduling.** The expiry sweep is still not scheduled in production; the on-demand expiry (F-07) covers the
  contact-change case only.
- Phase 1 independent acceptance is a separate gate and is not recorded here.

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
