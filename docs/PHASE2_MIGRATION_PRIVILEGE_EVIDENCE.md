# Phase 2 migration and privilege evidence (0042 to 0045)

Scope: the four additive migrations of Phase 2, their privileges and their verification. Historical revisions (0001 to
0041) were not rewritten. Their committed text is unchanged.

## 1. Migrations

| Revision | Purpose | Effective privileges and rules |
|---|---|---|
| `0042_phase2_identity_controls` | H-13 contact-change rejection; H-14 project and restricted grant revocation | Operations `contact.reject.change`, `project.access.revoke`, `restricted.revoke` added to the proof check constraint and the authority allowlist, with Administrator rules (`operation_authorization_rules`, membership not required). Functions `fn_reject_change_with_proof`, `fn_revoke_project_access_with_proof`, `fn_revoke_restricted_grant_with_proof` (SECURITY DEFINER, owner `webdesk_guard_owner`, `search_path = pg_catalog, public`); EXECUTE for `webdesk_app` only. Guard owner granted UPDATE on the two grant tables (table-wide at 0042). |
| `0043_phase2_review_fixes` | QA review: explicit Administrator clause for the Phase 2 operations; column-scoped grant update | `fn_validate_operation_proof` Administrator list includes the three Phase 2 operations. Guard owner UPDATE narrowed to `revoked_at` on both grant tables. |
| `0044_grant_revocation_lock` | QA F-01: serialized, conflict-reporting grant revocation | Both revocation functions: read the grant (no lock), consume the proof, refuse self-revocation, lock the grant `FOR UPDATE`, refuse an already-revoked grant (`grant_already_revoked`, SQLSTATE 23514), revoke with a guarded update and check the affected-row count. Owner and grants unchanged. |
| `0045_change_expiry_on_demand` | QA F-07: an expired pending change does not block a new request | `fn_request_change_with_proof` gains an optional `p_window interval DEFAULT '24 hours'` (the four-argument form is removed; the 0026 text is restored by the downgrade). `fn_expire_stale_change_for_email(text)` (SECURITY DEFINER, EXECUTE for `webdesk_app`) applies the sweep's transition for one address and releases its reservations. |

Downgrades restore the prior function text exactly (for 0042 to 0045 the function bodies are embedded in each
downgrade, copied from the migration that introduced them), revoke the new grants, and delete the rule and proof rows
introduced by 0042.

## 2. Verification method

`tests/committed/test_migration_catalog.py` (run in the full suite):

1. `reference`: a new, empty database migrated directly to `0041_ai_read_v1`.
2. `round_trip`: a clone of the head template, downgraded to `0041_ai_read_v1` (a multi-step downgrade across 0042 to
   0045), then upgraded to head.
3. `head`: a clone of the head template, unchanged.

The catalogs compared (all read from the live database, not from source):

- tables (owner, ACL, kind, row security), columns (type, nullability, default);
- column ACLs and table ACLs;
- constraints (definition, including the proof-operation check), indexes;
- triggers (definition);
- functions in `public`, `webdesk_guard`, `webdesk_authority` and `webdesk_worker`: identity arguments, owner, ACL,
  security-definer flag, `proconfig` (search path), and full definition;
- schema ACLs; role memberships;
- the rows of `operation_authorization_rules` (data invariant).

Checks:

- `reference` equals `round_trip` after the downgrade (`_diff(...) == []`).
- `head` equals `round_trip` after the re-upgrade.
- **Negative control:** `head` must differ from `reference`. The comparison therefore sees the 0042 to 0045 changes.

Every migration step runs the committed revision text. Nothing is rewritten.

## 3. Results

Recorded in `docs/PHASE2_EVIDENCE.md`, section "QA remediation: verification" (exit codes and totals of the final runs).

## 4. Limits

- The catalog covers the schemas named above. Other schemas are not compared.
- Row data is compared only for `operation_authorization_rules`. Data invariants of other tables are covered by the
  committed tests, not by this comparison.
- The test starts from a fresh database, so it does not verify an upgrade of a database that holds production data.
- Grants held by roles outside the cluster (for example login roles) are not part of the catalog; their privileges
  are covered by `tests/hardening/test_privilege_audit.py`.

## 5. Privilege audit

`tests/hardening/test_privilege_audit.py` (17 tests) pins, per role, the exact set of guard and authority functions
the role may execute (`APP_EXECUTE` now includes `fn_expire_stale_change_for_email`, deliberately, by 0045). It runs
against the run's own hardening database. Before the namespace fix it ran against a shared database at head 0043 and
could not see 0044 or 0045; see `docs/TEST_DATABASE_ISOLATION.md` section 1.
