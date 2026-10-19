# Increment 3 Evidence (Foundation Hardening)

## Phase 0 (H-00, H-09): negative-test environment and app-role tests

### Baseline
- Increment 2 baseline tag `inc2-acd5c51` is an annotated tag that peels to commit
  `acd5c51cf6955ed4e5e730c592609ec078e691f0`. Created without force. Not pushed.
- Phase 0 commits: `8f49784` (harness and first negative tests), `dac1131` (N3, N12, N15, N19
  and evidence). The N5, N6, N10, N13, N14 and N17 additions described below are uncommitted at
  the time of writing.

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
- Each negative test runs one protected write as `webdesk_app_login` inside a savepoint, then
  reads the protected row before and after. The savepoint is rolled back.
- A refusal must raise a database error whose SQLSTATE is one of `42501` (insufficient privilege),
  `P0001` (guard trigger), `23514` (check), `23505` (unique) or `23503` (foreign key). Any other
  SQLSTATE raises `RuntimeError` and is reported as an error, not as an expected failure.
- Where a test names an expected message, the refusal text must contain it. A refusal for another
  reason raises `RuntimeError`.
- A refused write must leave the protected row unchanged.
- A write the database allows raises `AssertionError`. Only that outcome is accepted by the strict
  xfail marker (`raises=AssertionError`). Setup failures therefore cannot pass as X1.
- Strict xfail: when a fix lands the test reports XPASS as a failure, and the marker must be
  removed in the same change.

### Outcomes (run as `webdesk_app_login`, `tests/hardening/test_app_role_negative.py`)

| Test | Attempt | Expected | Actual | Status | Finding |
|---|---|---|---|---|---|
| N1 | `pending` account set to active by UPDATE | refused | write allowed | XFAIL | X1 |
| N2 | approved `pending_activation` set to active without token | refused | write allowed | XFAIL | X1 |
| N3 | withdrawn (`disabled`) account set to active | refused | write allowed | XFAIL | X1, new finding |
| N4 | Analyst grant rewritten to Administrator | refused | write allowed | XFAIL | X1 |
| N6 | consumed installation appointment reused via `set_config` and INSERT | refused, message contains "consumed" | refused | PASS | regression guard |
| N7 | approval `expires_at` extended after decision | refused | write allowed | XFAIL | X1 |
| N8 | approver rewritten to a third distinct user | refused | write allowed | XFAIL | X1 |
| N9 | `contact_revision` bumped without approved change | refused | write allowed | XFAIL | X1 |
| N10a | project access grant `user_id` moved to another user | refused | write allowed | XFAIL | X1, new finding |
| N10b | restricted content grant `user_id` moved to another user | refused | write allowed | XFAIL | X1, new finding |
| N11 | classification lowered via `webdesk.reassess` session variable | refused | refused | PASS | regression guard |
| N12 | quarantined version `scan_status` set to `clean` | refused | write allowed | XFAIL | X1, new finding |
| N13 | segment inserted for a quarantined version | refused | write allowed | XFAIL | X1, new finding |
| N14 | run snapshot inserted with a run from another project | refused | write allowed | XFAIL | X1, new finding |
| N15 | `setup_trust_ceremonies.kind` set to `recover` | refused | refused | PASS | regression guard |
| N16 | `system:project_create` membership inserted for unrelated user | refused | write allowed | XFAIL | X1 |
| N17 | active user disabled by UPDATE (service withdraw is refused) | refused | service refused (403/409); raw UPDATE allowed | XFAIL | X1, new finding |
| N18 | UPDATE on `audit_events` | refused | permission denied (42501) | PASS | regression guard |
| N19 | non-Administrator reassess via service and raw UPDATE | refused | service refused with 403; raw path refused (see N11) | PASS | regression guard |

Totals for `tests/hardening`: 5 passed, 14 xfailed, 0 failed, 0 errors (19 test items).

### Blocked
- **N5** (`UPDATE role_assignments SET revoked_at = NULL` after revocation) is not written.
  The application has no role-revocation service (`src/webdesk/rbac` exposes assign only). A
  revoked row can therefore only be created by a direct UPDATE, which is the bypass under test.
  Setting it up through the owner or ceremony role would be a simulated application mutation,
  which is not allowed. N5 needs a decision on a revocation service before it can be tested.

### Not in the plan's N1–N19 list
- None. All 19 plan items are now present, except N5, which is blocked as described above.

### Resolved in this step
- N15 needed no ceremony login. The application role attempts an ordinary UPDATE against the
  install row that the `world` fixture created.
- N19 is refused at the service layer (`ReassessError`, 403). The raw path matches N11.
- N6 uses the consumed appointment from the installation ceremony, and the refusal text
  is checked for "consumed".

### Findings still open (all X1)
- Account status (N1, N2, N3, N17): direct UPDATE can activate a pending or disabled account, and
  can disable an active account. N17 is release-relevant because it bypasses the withdrawal rule.
- Role assignments (N4): an Analyst grant can be rewritten to Administrator.
- Approval history (N7, N8): expiry and approver are mutable after decision.
- Contact revision (N9): bumped without an approved change.
- Access grants (N10a, N10b): a grant can be moved to another user.
- Intake and quarantine (N12, N13): quarantined content can be marked clean, and segments can be
  inserted for quarantined versions. Release-blocking for the intake layer.
- Run snapshots (N14): a snapshot can reference a run from another project. Cross-project leak.
- System membership (N16): a `system:project_create` membership can be inserted for an unrelated
  user.

### Checks
- `pytest tests/hardening` (with `.env.hardening.local` loaded): 5 passed, 14 xfailed.
- `pytest tests/unit tests/hardening`: 171 passed, 14 xfailed.
- `ruff check tests/hardening`: passed.
- `mypy --strict src/webdesk`: no issues in 47 source files. Tests are outside the mypy `files`
  setting in `pyproject.toml`.
- Full suite against `webdesk_hardening`: not a valid run. 153 failed and 31 errors, caused by
  (a) the existing integration and committed suites assuming a superuser owner that can create
  databases and roles (`permission denied to create database`, `permission denied to set role
  "webdesk_app"`), and (b) the hardening database already holding an installation
  (`install_already_closed`). These suites must run against the project's own owner test database,
  whose URL is not available in this environment (no `.env` file). The full run remains unverified.
