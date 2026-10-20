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


## Phase 1 interim status (verified 2026-10-19 on a freshly recreated `webdesk_integration` database, migrated to `0012_guard_completion`)

Role for every negative test: `webdesk_app_login` (member of `webdesk_app`, NOSUPERUSER). Each
attempt runs inside a savepoint, the protected row is read before and after, and the refusal must
carry an expected SQLSTATE with no row change. SQLSTATE values below were captured per test ID.

| Test ID | Operation (as webdesk_app_login) | Expected | SQLSTATE observed | Status |
|---|---|---|---|---|
| test_n1_pending_contact_cannot_be_activated_by_a_direct_update | UPDATE users status to active from pending_contact_approval | refused | 23514 | PASS |
| test_n2_approved_pending_activation_cannot_become_active_without_a_consumed_token | UPDATE users status to active without consumed token | refused | 23514 | PASS |
| test_n3_a_disabled_account_cannot_be_reactivated | UPDATE users status disabled to active | refused | 23514 | PASS |
| test_n4_an_analyst_grant_cannot_be_rewritten_into_an_administrator_grant | UPDATE role_assignments role | refused | 42501 | PASS |
| test_n7_an_approval_expiry_cannot_be_extended_after_decision | UPDATE user_contact_approvals expires_at after decision | refused | 42501 | PASS |
| test_n8_an_approver_cannot_be_rewritten_after_approval | UPDATE user_contact_approvals approved_by_user_id after decision | refused | 42501 | PASS |
| test_n9_a_contact_revision_cannot_be_bumped_without_an_approved_change | UPDATE users contact_revision | refused | 42501 | PASS |
| test_n10_an_access_grant_cannot_be_moved_to_another_user | UPDATE project_access_grants user_id | refused | 42501 | PASS |
| test_n10_a_restricted_content_grant_cannot_be_moved_to_another_user | UPDATE restricted_content_grants user_id | refused | 42501 | PASS |
| test_n12_quarantined_content_cannot_be_marked_clean | UPDATE source_versions scan_status quarantined to clean | refused | 42501 | PASS |
| test_n13_a_segment_cannot_be_inserted_for_a_quarantined_version | INSERT source_segments for quarantined version | refused | 42501 | PASS |
| test_n14_a_run_snapshot_cannot_reference_another_project | INSERT run_input_snapshots with run from another project | refused | 23514 | PASS |
| test_n17_an_activated_user_cannot_be_withdrawn_or_disabled | UPDATE users status to disabled for active account | refused | 23514 | PASS |
| test_n16_the_system_project_create_principal_cannot_be_inserted_for_an_unrelated_user | INSERT project_memberships with system:project_create | refused | (not refused) | XFAIL (open, H-07 not implemented) |
| N5 (role revocation reactivation) | UPDATE role_assignments revoked_at to NULL | refused | (not written) | BLOCKED (no revocation service yet) |

Other negative tests in tests/hardening: N6, N11, N15, N18 and N19 pass as regression guards
(see the table above in the Phase 0 section).

### Regression suite status (not passing)
- Existing suite on the fresh database: 350 passed, 32 failed, 19 skipped (hardening skips apply
  when the hardening variables are not set), 1 xfailed.
- The 32 failures are fixtures that seed users without an approved approval, that back-date
  decided approval or grant expiry, or that set contact_revision directly. Each is refused by the
  new guards. They must be rebuilt through services; they have NOT been rebuilt yet.

### Still open in Phase 1
- H-03 remainder: appointment consumption and classification reassessment still rely on the
  session variables `webdesk.consume_appointment` and `webdesk.reassess`.
- H-01: table-level UPDATE is not yet revoked; column-level grants are not applied.
- H-07 / N16: `fn_create_project` not implemented.
- N5: role revocation service not implemented.
- Ruff, strict mypy and the Alembic downgrade/upgrade round trip were not re-run for this interim.
- Phase 1 is NOT complete. Nothing from this interim is committed.


## Phase 1 interim status update (migration 0013)

Migration 0013 (H-03) is applied and verified: appointment consumption is done only by
webdesk_guard.fn_consume_appointment and classification reassessment only by
webdesk_guard.fn_reassess_classification (which checks an active Administrator actor). The session
variables webdesk.consume_appointment and webdesk.reassess no longer appear in src or tests.
Verified as webdesk_app_login on a fresh database (webdesk_negative): 18 passed, 1 xfailed (N16).
The regression suite on a fresh integration database is at 32 failed, 350 passed (unchanged).

### Newly confirmed bypasses (probed as webdesk_app_login, rolled back, NOT yet fixed)
- F-NEW-1: INSERT INTO users with status active is accepted. Application code only inserts
  pending_contact_approval, so an insert guard can close this without affecting the application.
- F-NEW-2: INSERT INTO account_activation_tokens for an existing user is accepted, and the same
  role can then UPDATE consumed_at to now(). That satisfies the activation guard without token
  delivery. Combined with an approved pending_activation account, this is an account-activation
  and password-reset path. This needs token issuance and consumption moved behind guard-owner
  functions, and a column-level UPDATE restriction on consumed_at. It is release-blocking.

Both must be fixed before Phase 1 can be declared complete.


## Phase 1 update: F-NEW-1 and F-NEW-2 fixed (migration 0014)

Role for both tests: webdesk_app_login. Verified on a freshly migrated database (webdesk_negative).

| Test ID | Operation (as webdesk_app_login) | Expected | Actual | Status |
|---|---|---|---|---|
| test_n20_an_account_cannot_be_inserted_directly_as_active | INSERT INTO users with status active | refused | refused by users_insert_guard (insufficient_privilege, 42501) | PASS |
| test_n21_activation_tokens_cannot_be_inserted_or_consumed_directly | INSERT INTO account_activation_tokens | refused | permission denied for table (42501) | PASS |

Token issuance, delivery marking, consumption and revocation now run only through
webdesk_guard.fn_issue_token, fn_mark_token_sent, fn_consume_token, fn_revoke_tokens and
fn_revoke_expired_activation_tokens (SECURITY DEFINER, owned by webdesk_guard_owner). The
application roles lost direct INSERT and UPDATE on account_activation_tokens. Consumption requires
the token secret hash, not the token ID.

Hardening suite as webdesk_app_login on webdesk_negative: 20 passed, 1 xfailed (N16).

Regression suite: this step raised the failure count (174 failed, 26 errors on a fresh integration
database). The cause is existing fixtures that insert active users or write tokens directly, which
the new guards now refuse. Those fixtures must be rebuilt through services before Phase 1 can be
declared complete. Nothing from this step is committed.


## Phase 1 fixture rebuild: status (not complete)

Shared helpers added: tests/support/people.py (install_administrators, new_active_user) and
tests/support/activation.py (activate_user now runs the service calls as webdesk_app). The helper
has its own test (tests/integration/test_people_support.py, PASS).

tests/integration/test_role_assignment.py: 6 of 10 pass after the rebuild (seeded admins and
back-dated expiries removed; the direct Administrator INSERT in
test_recovery_is_refused_when_two_administrators_are_effective replaced by the install
appointment).

BLOCKED (not passing; not weakened):
- test_recovery_appointment_lets_the_survivor_grant_administrator_once
- test_expired_appointment_cannot_be_used
- test_second_recovery_is_refused_while_a_replacement_is_reserved
- test_replacement_recovery_creates_a_pending_activation_contact_with_an_appointment
Reason: a recovery appointment is refused when two Administrators are effective
(coverage_sufficient) and, with one Administrator, while the second installation contact still
holds a live installation appointment (replacement_reserved). No service path produces a
non-Administrator contact without a live installation appointment. Resolving this needs a decision
(for example, an injected installation clock that does not also expire the first contact).

Regression suite on a fresh database: 153 failed, 9 errors, 221 passed. About 140 of these come
from test helpers that insert active users directly (INSERT INTO users ... active), which the
insert guard (migration 0014) now refuses. They are spread over roughly 19 test files and need the
same rebuild.

Phase 1 is NOT complete. Nothing from this rebuild is committed.


## Phase 1 fixture rebuild: progress (2026-10-20)

Fresh integration database (webdesk_integration, migrated to 0014), full suite:
44 failed, 9 errors, 330 passed, 21 skipped, 1 xfailed. Down from 153 failed before the rebuild.

Rebuilt through services (all pass): test_tokens.py (10; the contact-revision test now changes the
contact through request_change and approve_change), test_auth_lifecycle.py, test_intake_db.py,
test_runs_db.py, test_reassessment.py, test_phase_e.py, test_projects.py, test_gap_closure.py (most),
test_contact_lifecycle.py (most), test_intake_schema.py (most), test_rbac_sql.py (most). Shared
helpers: tests/support/people.py (administrators_for, active_user, user_in_state).

Still failing, with the reason:
- test_gate1_schema.py (20): raw psycopg schema tests that build users with direct SQL. The guard
  now refuses those inserts for every role. Needs the module moved onto the SQLAlchemy services.
- test_outbox_worker.py (7): helper inserts a committed active user through its own engine. Its
  rows are committed, so it cannot build an approved account without installing into the shared
  database. Needs the committed-database fixtures (tests/committed).
- test_role_assignment.py (4): BLOCKED. Recovery-appointment states are not constructible under the
  current rules (see the earlier status entry).
- test_denial_branches.py (6), test_phase_a.py (2), test_install_ceremony.py (1),
  test_gap_closure.py (1), test_rbac_sql.py (1), test_intake_schema.py (1),
  committed/test_committed_phase_a.py (1), and 9 errors: not yet examined in detail.

Phase 1 is NOT complete. Nothing from this rebuild is committed.


## Phase 1 status (2026-10-20, verified on a freshly recreated database)

Migrations: 0012 (guard completion), 0013 (appointment and reassessment guard functions), 0014
(account and token insert guards; token functions), 0015 (project creation: fn_create_project and
the system-membership guard; direct project INSERT removed from application roles), 0016 (role
revocation: fn_revoke_role; direct UPDATE on role_assignments removed from application roles).
Alembic: upgrade head, downgrade to 0012, upgrade head -> PASS (guard-schema drops run as
webdesk_guard_owner).

Hardening, as webdesk_app_login on a fresh negative database: 22 passed, 0 xfailed. Converted to
normal tests: N16 (project creation principal), N5 (revoked assignment cannot be reactivated, added).

Full regression on a fresh integration database: 35 failed, 9 errors, 341 passed, 22 skipped,
1 xfailed.

Remaining, with the reason:
- test_gate1_schema.py (20 failed): raw psycopg schema tests that build users directly. Not
  refactored (D2 not done).
- test_outbox_worker.py (7 failed): commits rows through its own engine (D3 not done).
- committed/test_committed_runs.py (2 errors), committed/test_http_intake.py (7 errors): direct
  active-user inserts in committed-database fixtures (D3 not done).
- test_role_assignment.py (4 failed): BLOCKED (D1 conflict, see earlier entry). The four tests need
  a live installation appointment to be absent while a non-Administrator exists, which no service
  path produces.
- test_phase_a.py sweep test (1 failed): BLOCKED. It needs an approval that expires while the
  contact is still pending, which the fixed 24-hour installation window does not allow.
- test_gap_closure.py sweep test (1 failed): its back-dated appointment expiry is refused by the
  decision-immutability guard. Rebuild using an injected-clock recovery ceremony (not done).
- test_install_ceremony.py reserved-contact test (1 failed): seeds a reservation directly (not done).
- test_denial_branches.py zero-Administrator recovery test (1 xfail): BLOCKED on H-14 disable
  service, which is not implemented.

Not complete: least-privilege column-level grants (H-01) are not yet applied, and the xfail for the
zero-Administrator recovery is still open. Phase 1 is NOT complete. Nothing from this step is
committed.


## Phase 1 status update (2026-10-20, later): H-01 slice and hardening

Migration 0017_least_privilege_grants (H-01 slice): table-level UPDATE revoked from webdesk_app and
webdesk_ceremony on users, user_contact_approvals, contact_reservations, sessions, projects,
project_memberships, project_access_grants and restricted_content_grants; column-level UPDATE granted
only on the columns the documented flows change. Not yet restricted (documented remaining scope):
sources, source_versions, workflow_runs, workflow_jobs, outbox_notices, idempotency_keys.

Hardening as webdesk_app_login on a fresh negative database: 24 passed, 0 xfailed. New tests:
N22 (identity column not updatable), N23 (approval request field not updatable).

Full regression on a fresh integration database after 0017: 35 failed, 9 errors, 341 passed,
22 skipped, 1 xfailed. No regression from the grant change; the failures are unchanged from the
previous entry (see the list there).

Not done in this turn:
- D2 (test_gate1_schema.py refactor, 20 failing tests): not started in code. The module builds
  users, ceremonies, approvals, projects and admins by raw SQL under ceremony and application roles,
  and its psycopg-only connection cannot share state with the SQLAlchemy services. A faithful
  refactor is test-by-test; it is the next block.
- D3 (test_outbox_worker.py, 7 failing; committed fixtures, 9 errors): not started in code.
- D1: the four recovery-appointment tests (test_role_assignment.py), the gap-closure sweep test, the
  install reserved-contact test and the phase-A sweep test remain as recorded above, with their
  conflicts documented in the earlier entries. Each needs the decision recorded there.
- H-14: the disable service is not implemented. The zero-Administrator recovery test
  (test_denial_branches.py) stays an xfail until it exists. This is a missing authorized operation,
  not a specification conflict: REQUIREMENT_SCHEMA section 3.1 allows active to disabled, and
  GOVERNANCE section 11 requires the operation to be Administrator-only, audited, and to refuse
  self-action. The smallest resolution is a guard-owner function plus an audited service; it has
  not been added in this turn.

Phase 1 is NOT complete. Nothing from this turn is committed.


## Phase 1 verification (2026-10-20, final for this request)

Environment: PostgreSQL 16.4 in Docker. Integration database `webdesk_integration` and negative
database `webdesk_negative` recreated fresh before each run. Owner role `webdesk_integration_owner`
(CREATEDB, CREATEROLE, not superuser). Application role `webdesk_app` and login role
`webdesk_app_login` (member of webdesk_app).

Migrations added in this step: 0017 (least-privilege, slice 1), 0018 (Administrator disable, H-14),
0019 (least-privilege, intake/workflow/outbox/idempotency). Previously added: 0012-0016.

Alembic cycle, verified: upgrade head -> downgrade 0001_gate1_foundation -> upgrade head: PASS.
Downgrade to base is NOT verified: the first revision drops the cluster roles webdesk_app and
webdesk_ceremony, which the integration owner (correctly) cannot drop because other databases in this
cluster depend on them. This is an environment limitation, not a migration defect.

Restricted-role hardening (webdesk_app_login, fresh webdesk_negative): 26 passed, 0 xfailed.
Includes N5 (revoked assignment cannot be reactivated), N16 (system project-create principal refused),
N22/N23 (identity and approval-request columns), N24 (idempotency records immutable by the application),
N25 (ingested source identity columns).

Full regression (fresh webdesk_integration): 382 passed, 26 skipped (the hardening tests, which run
separately with their own variables), 8 xfailed. No failures, no errors.

Ruff (src, tests, migrations): passed. mypy --strict src/webdesk: passed (49 files).

The 8 xfailed tests are documented governance blocks, each with its exact refusal class and reason in the test:
- tests/integration/test_denial_branches.py: zero-Administrator recovery (governance: the last-Administrator
  rule of migration 0018 and the zero-Administrator recovery scenario conflict; see below).
- tests/integration/test_gap_closure.py: sweep expires an unconsumed appointment (installation refused with an
  injected past clock; recovery route needs one Administrator and a contact with no live appointment).
- tests/integration/test_install_ceremony.py: reserved contact refuses the install (unreachable precondition).
- tests/integration/test_phase_a.py: install contact that missed its deadline (activation requires a live approval).
- tests/integration/test_role_assignment.py (4): recovery appointments (coverage_sufficient / replacement_reserved).

### Governance decisions requested (not implemented)
1. Zero-Administrator recovery. The approved recovery behaviour (test EVAL-F11h) expects a recovery to be
   possible when no Administrator is active. The H-14 disable service refuses to disable the last active
   Administrator, and revocation (N5 service) refuses the same. These rules are the smallest safe reading of
   GOVERNANCE section 11 and are my addition, not an approved sentence. Decision needed: may the last active
   Administrator be disabled or revoked, and by whom, so that recovery can be exercised? Until decided,
   the zero-Administrator recovery test stays blocked.
2. Recovery appointments and installation deadlines. A recovery appointment requires a single active
   Administrator and a contact with no live installation appointment; an installation with an injected past
   clock is refused by the activation rule. Decision needed: an approved installation or recovery window that
   tests can inject, or an accepted test-only state definition, without introducing a production bypass.

### Not done in this step
- D2 (test_gate1_schema.py) is refactored and passing (22 tests).
- D3 (outbox and committed fixtures) is refactored: per-test databases from a migrated template; the lease is a
  configurable parameter so expired leases are produced in real time (no protected column is written).
- H-01 is complete for all listed intake, workflow, outbox and idempotency tables, in migrations 0017 and 0019.
- H-14 disable service is implemented (migration 0018, src/webdesk/identity/disable.py, tests/integration/test_disable_user.py).

Phase 1 is NOT yet declared complete: the 8 governance blocks need a WDS decision (exclusions must be separately
approved). Nothing from this step is committed.

## Phase 1 final verification (governance decisions GD-001 to GD-003 applied)

Governance decisions are recorded in docs/GOVERNANCE_DECISION_REGISTER.md. They resolve the eight
governance blocks listed in the previous section. No test is waived: each is restored and passes.

Resolution of the eight blocks
- Zero-Administrator recovery (test_denial_branches.py): the zero-Administrator state is produced by an
  external-state test fixture (external_loss_of_access, tests/support/people.py), and the in-application
  recovery refusal zero_active_administrators is asserted, with its audit event. Under GD-002 this is the
  required behaviour.
- Recovery appointments (4 tests) and the expired-appointment sweep (gap closure) and the phase-A token sweep:
  these need real time between transactions. They moved to tests/committed/test_deadlines.py, where
  installation and recovery run with an injected, test-only activation window (GD-003) on isolated committed
  databases, and expiry is checked in a new transaction. Test IDs changed for these five; assertions preserved.
- Reserved contact before installation (test_install_ceremony.py): a test-only database fixture
  (reserve_contact_fixture) represents the reservation; the installation refusal database_refused is asserted.

Injection points added (GD-003): apply_install and apply_recovery accept activation_window (default 24 hours,
never passed by production code).

Final results, fresh databases
- Full regression, fresh webdesk_integration (migrated to 0019): 388 passed, 26 skipped (the restricted-login
  hardening tests, run separately with their own variables), 0 failed, 0 errors, 0 xfailed.
- Restricted-login hardening, webdesk_app_login, fresh webdesk_negative: 26 passed, 0 xfailed.
- Ruff (src, tests, migrations): passed. mypy --strict src/webdesk: passed (49 files).
- Alembic: upgrade head; downgrade 0001_gate1_foundation; upgrade head: passed.
  Downgrade to base is not run: the first revision drops the cluster roles webdesk_app and webdesk_ceremony,
  which other databases in this cluster use and the integration owner is not permitted to drop.

Phase 1 scope status
- X1 database bypasses: all listed negative tests pass as webdesk_app_login (N1-N25 at the time of this entry;
  see the hardening file).
- H-01 least-privilege column grants: migrations 0017 and 0019 cover the identity, approval, session, grant,
  intake, workflow, outbox and idempotency tables.
- H-14 disable service: migration 0018, src/webdesk/identity/disable.py, tests/integration/test_disable_user.py.
- Phase 2 has not been started.

## Amendment A2 (R1-R4, N1-N2, P-INC3-ACTOR-SESSION-06): status 2026-10-20

Status: NOT IMPLEMENTED. The A2 package (Updated Decision Register, PHASE1_R4_OPTION_A_IMPLEMENTATION_CONTRACT.md,
PHASE1_R1_R4_CLAUDE_CODE_HANDOFF.md, and the governance amendments) was not available in the repository,
in Downloads, or in the request text. The R1-R4 and N1-N2 definitions therefore could not be read, and no
implementation was started against an unknown contract. The repository decision register does not contain
P-INC3-ACTOR-SESSION-06.

Finding confirmed by probe (restricted login role webdesk_app_login, rolled back):
- R4 (release-blocking, open): webdesk_app holds INSERT on sessions (migration 0001 grant). A row inserted with
  a chosen token hash for an active user is accepted by webdesk.auth.service.validate_session, so the compromised
  application role can authenticate as any active user. Test: tests/hardening/test_app_role_negative.py::
  test_n26_a_forged_session_row_is_not_accepted_as_authentication, a strict xfail with this reason.

Current actor binding (inspected): src/webdesk/api/routes.py::current_actor takes the bearer token and calls
webdesk.auth.service.validate_session through the application engine. Session rows are looked up by SHA-256 of the
token, with live, epoch and status checks. Nothing binds the session row to a trusted authentication authority, so
row creation is the trust boundary, and the application role controls it.

Design direction (to be aligned with A2 before implementation): session rows are created only by a
separate authentication-authority role after password verification; the application role has no INSERT or
UPDATE on sessions and no EXECUTE on the issuing function; the token is returned once and only its hash is stored;
revocation and epoch changes are enforced in the database; the authority role is not reachable from the
application connection.

Not done: R1, R2, R3, R4 implementation; N1, N2 implementation; the Amendment A2 governance register update.

## Amendment A2 implementation (R1, R2, R3, N1, N2) and R4 status (2026-10-20)

Specifications: the A2 package was extracted and applied to the repository governance documents
(DECISION_REGISTER.md, GOVERNANCE.md, REQUIREMENT_SCHEMA.md, ARCHITECTURE.md, EVALUATION_PLAN.md, plus the
A2 contract, handoff and README). Historical decisions are kept; the EVAL-F11i wording was replaced by the A2
text, and the earlier wording remains in git history.

Migration 0020_r1_r2_n1_hardening (forward only; 0001 to 0019 untouched):
- R1: every SECURITY DEFINER function (webdesk_guard schema) runs with search_path = pg_catalog, public;
  TEMP revoked from PUBLIC, webdesk_app and webdesk_ceremony on the database.
- R2: approval deadlines and ceremony activation deadlines are at most 24 hours after their creation or start
  time (trigger on insert and update); creation and start times are immutable.
- N1: contact reservations are released only by webdesk_guard.fn_release_reservations, in three contexts:
  terminal approval, a withdrawal in the same transaction, and an approved contact change. The runtime login
  can no longer set released_at directly.
Services switched to the guard function: identity/contacts.py (cancel, withdraw, contact change) and
identity/sweep.py. Installation and recovery stamp ceremony start and approval creation with the service clock
so the 24-hour bound is exact.

R3: test_recovery_is_refused_with_coverage_sufficient_and_audited restored (EVAL-F11f): denial with reason
coverage_sufficient, and the ceremony.recover.denied audit row asserted.

N2: docs/DEPLOYMENT_CHECKLIST.md section "PostgreSQL 16 role and privilege setup"; test N30 asserts the runtime
login is not a superuser and cannot create roles, databases or public-schema objects.

Restricted-login tests added (webdesk_app_login, fresh negative database):
- N27 arbitrary reservation release refused: PASS (42501)
- N28 temporary object creation refused: PASS (42501)
- N29 25-hour approval deadline refused: PASS (23514)
- N30 runtime login role attributes and public-schema creation refused: PASS (42501)

R4 (verified-session actor binding, Option A): NOT IMPLEMENTED. Probed finding: webdesk_app holds INSERT on
sessions and INSERT, UPDATE, DELETE on credentials; a forged session row is accepted (N26, strict xfail, release-
blocking). The Option A design requires an authority role, bounded proofs and key custody that are policy
choices; per the contract they must be proposed and approved before the security-sensitive change. See the
proposal in the reply. EVAL-F11j is not yet implemented.

Verification (fresh databases, final):
- Full regression, fresh webdesk_integration: 389 passed, 31 skipped (hardening tests run separately),
  0 failed, 0 errors.
- Restricted-login hardening, fresh webdesk_negative: 30 passed, 1 xfailed (N26, R4).
- Alembic: upgrade head, downgrade 0001_gate1_foundation, upgrade head: passed.
- Ruff (src, tests, migrations): passed. mypy --strict src/webdesk: passed (49 files).

Phase 1 is NOT complete: R4 and EVAL-F11j remain open. The verified changes are committed separately.
