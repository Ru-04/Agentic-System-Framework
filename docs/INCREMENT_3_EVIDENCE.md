# Increment 3 Evidence (Foundation Hardening)

## Phase 0 (H-00, H-09): negative-test environment and app-role tests

### Baseline
- Increment 2 baseline tag `inc2-acd5c51` is an annotated tag that peels to commit
  `acd5c51cf6955ed4e5e730c592609ec078e691f0`. Created without force. Not pushed.
- Phase 0 commit: `8f49784` (harness and first negative tests). Phase 0 completion work is
  uncommitted at the time of writing.

### Environment (H-00)
- Non-superuser owner `webdesk_test_owner` (NOSUPERUSER), database `webdesk_hardening`.
- Login role `webdesk_app_login` (NOSUPERUSER, LOGIN), member of `webdesk_app`. Negative tests
  connect only as this role. No `SET ROLE` or superuser session performs protected actions.
- Installation runs once through membership of `webdesk_ceremony`. Contacts are activated through
  the real token flow as the login role. Appointments are created as the login role.
- Passwords live only in `.env.hardening.local`, which is git-ignored (`.gitignore` line 11).
- Deviation, recorded for transparency: `ALTER SCHEMA public OWNER TO webdesk_test_owner` was run
  on the disposable `webdesk_hardening` database so the owner could migrate. It affects only that
  database and not the shared development database.

### Test method
- Each negative test runs one protected write as `webdesk_app_login` inside a rolled-back
  savepoint, then reads the protected row before and after.
- A refusal must raise a database error whose SQLSTATE is one of `42501` (insufficient privilege),
  `P0001` (guard trigger), `23514` (check), `23505` (unique) or `23503` (foreign key). Any other
  SQLSTATE raises `RuntimeError` and is reported as an error, not as an expected failure.
- A refused write must leave the protected row unchanged.
- A write the database allows raises `AssertionError`. Only that outcome is accepted by the
  strict xfail marker (`raises=AssertionError`). Setup failures therefore cannot pass as X1.
- Strict xfail: when a fix lands the test reports XPASS as a failure, and the marker must be
  removed in the same change.

### Outcomes (run as `webdesk_app_login`, `tests/hardening/test_app_role_negative.py`)

| Test | Attempt | Expected | Actual | Status | Finding |
|---|---|---|---|---|---|
| N1 | `pending` account set to active by UPDATE | refused | write allowed | XFAIL | X1 |
| N2 | approved `pending_activation` set to active without token | refused | write allowed | XFAIL | X1 |
| N3 | withdrawn (`disabled`) account set to active | refused | write allowed | XFAIL | X1, new finding |
| N4 | Analyst grant rewritten to Administrator | refused | write allowed | XFAIL | X1 |
| N7 | approval `expires_at` extended after decision | refused | write allowed | XFAIL | X1 |
| N8 | approver rewritten to a third distinct user | refused | write allowed | XFAIL | X1 |
| N9 | `contact_revision` bumped without approved change | refused | write allowed | XFAIL | X1 |
| N11 | classification lowered via `webdesk.reassess` session variable | refused | refused | PASS | regression guard |
| N12 | quarantined version `scan_status` set to `clean` | refused | write allowed | XFAIL | X1, new finding |
| N15 | `setup_trust_ceremonies.kind` set to `recover` | refused | refused | PASS | regression guard |
| N16 | `system:project_create` membership inserted for unrelated user | refused | write allowed | XFAIL | X1 |
| N18 | UPDATE on `audit_events` | refused | permission denied (42501) | PASS | regression guard |
| N19 | non-Administrator reassess via service and raw UPDATE | refused | service refused with 403; raw path refused (see N11) | PASS | regression guard |

Totals: 4 passed, 9 xfailed, 0 failed, 0 errors for `tests/hardening`.

Not yet written, from the plan's N1–N19 list: N5, N6, N10, N13, N14, N17. They are outside this
step's scope and remain open for later Phase 0 or Phase 1 work.

### Resolved in this step
- N15 needed no ceremony login. The application role attempts an ordinary UPDATE against the
  install row that the `world` fixture created. The refusal is by the database, and the test passes.
- N19 is refused at the service layer (`ReassessError`, 403). The raw path is the same as N11.
  Both are refused.
- N12 needed a restricted-content grant for the setup Administrator. The second Administrator
  grants it, because an Administrator cannot grant to themselves.

### Corrections to the earlier draft
- The draft used `"n11 line"` setup and an N12 restricted setup without a grant. The N12 setup now
  grants restricted access first, so the quarantine state is real and asserted before the attempt.
- N8 uses a third active user. The requester-differs-from-approver CHECK otherwise produced a false
  refusal that did not test immutability.
- N11 was planned as X1. It was refused on first run and became a regression guard.

### Findings still open (all X1, mapped to H-02 / H-03 and later tasks in the plan)
- N1, N2, N3: account status transitions are not guarded against direct UPDATE.
- N4: role assignment can be rewritten by UPDATE.
- N7, N8: approval history is mutable after decision.
- N9: contact revision is mutable without an approved change.
- N12: quarantine state can be cleared by direct UPDATE. This is a release-blocking intake gap.
- N16: a system membership principal can be inserted for an unrelated user.

### Checks
- `pytest tests/unit tests/hardening` (with `.env.hardening.local` loaded): 170 passed, 9 xfailed.
- `pytest tests/hardening`: 4 passed, 9 xfailed.
- Full suite without `WEBDESK_TEST_DATABASE_URL` in this shell: 172 passed, 9 xfailed, 215 errors.
  All errors come from the missing owner test-database URL. The integration and committed tests
  need that variable, and it is not set in this environment. This is an environment gap, not a code
  failure. The full suite must be re-run with the URL set before the evidence can claim a clean
  full run.
- `ruff check tests/hardening`: passed.
- `mypy --strict src/webdesk`: no issues in 47 source files. Tests are outside the mypy `files`
  setting in `pyproject.toml`, so strict mypy on tests was not run as a gate.
