# Increment 3 Evidence (Foundation Hardening)

## Phase 0 (H-00, H-09): negative-test environment and first app-role tests

### Environment (H-00)
- Non-superuser owner `webdesk_test_owner` (NOSUPERUSER), database `webdesk_hardening`.
- Login role `webdesk_app_login` (NOSUPERUSER, LOGIN), member of `webdesk_app`. Negative tests
  connect only as this role. No `SET ROLE` or superuser session is used for protected actions.
- Installation runs once through membership of `webdesk_ceremony`. Contacts are activated through
  the real token flow as the login role.
- Passwords live only in `.env.hardening.local`, which is git-ignored (`.gitignore` line 11).
- Deviation from the plan, recorded for transparency: `ALTER SCHEMA public OWNER TO webdesk_test_owner`
  was run on the throwaway `webdesk_hardening` database so that the owner could migrate. It
  affects only that disposable database.

### Negative tests (H-09), run 2026-10-19 as `webdesk_app_login`
Result: 2 passed, 7 xfailed (strict, `raises=AssertionError`).

| Test | Attempt | Current result | Finding |
|---|---|---|---|
| N1 | pending account set to active by UPDATE | XFAIL (write allowed) | X1 |
| N2 | approved pending_activation set to active without token | XFAIL (write allowed) | X1 |
| N4 | Analyst grant rewritten to Administrator | XFAIL (write allowed) | X1 |
| N7 | approval expiry extended after decision | XFAIL (write allowed) | X1 |
| N8 | approver rewritten to a third distinct user | XFAIL (write allowed) | X1 |
| N9 | contact_revision bumped without approved change | XFAIL (write allowed) | X1 |
| N11 | source classification lowered via `webdesk.reassess` session variable | PASS (refused) | regression guard |
| N16 | `system:project_create` membership inserted for unrelated user | XFAIL (write allowed) | X1 |
| N18 | UPDATE on audit_events | PASS (permission denied) | regression guard |

Not yet written: N3 (disabled account reactivation), N12 (quarantined content marked clean),
N19. N15 is deferred until a ceremony login exists. These are to be added in the next step of Phase 0.

Notes on the test design:
- `_refused` treats a `DBAPIError` as a refusal. Any other outcome raises `AssertionError`, which is the only exception the xfail marker accepts. Setup errors therefore cannot masquerade as expected failures.
- N8 uses a third active user so the refusal is not caused by the requester-differs-from-approver CHECK. An earlier draft used the requester as the new approver, and the CHECK refused it, which proved nothing about immutability.
- N11 was an xfail in the planning draft. It passed on first run, so it was converted to a regression guard.

### Checks
- `pytest tests/hardening`: 2 passed, 7 xfailed.
- `ruff check tests/hardening`: passed.
- `mypy src/webdesk`: no issues in 47 source files.
