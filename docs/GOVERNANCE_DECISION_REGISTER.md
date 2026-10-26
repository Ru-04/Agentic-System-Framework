# Governance Decision Register (WebDesk Increment 3)

Each decision below was made by the WDS governance owner and is recorded here so that specifications,
code and tests can be aligned to it. A decision is binding for Increment 3 until a later register entry
supersedes it. Decisions do not alter the approved v0.3.10 Foundation specification.

## GD-001 Last Administrator: self-disable and last-Administrator disable or revocation

- **Decision:** Ordinary in-application self-disable is prohibited. Disabling or revoking the last
  active Administrator is prohibited. A zero-Administrator state may arise only through external loss of
  access, and only the approved offline recovery applies to it. In-application recovery from zero active
  Administrators is refused.
- **Implementation:** `webdesk_guard.fn_disable_user` (migration 0018) and `webdesk_guard.fn_revoke_role`
  (migration 0016) each refuse self-action and the last active Administrator in the database. The services
  `identity/disable.py` and `rbac/revoke.py` check the same rules first, so each refusal is audited.
- **Tests:** `tests/integration/test_disable_user.py`; `tests/integration/test_role_revocation.py`;
  `tests/integration/test_denial_branches.py::test_recovery_with_zero_active_administrators_is_refused_and_audited`
  (zero-Administrator state created by an external-state fixture, then the recovery refusal is asserted).
- **Test fixture scope:** the external-state fixture (`tests/support/people.py::external_loss_of_access`)
  is test-only. It represents an account losing access outside the application. It is not reachable from
  any production code path.

## GD-002 Zero-Administrator recovery

- **Decision:** Recovery from a zero-Administrator state is available only through the approved offline
  recovery procedure. The in-application recovery service refuses it with `zero_active_administrators`,
  and that refusal is audited.
- **Implementation:** `ceremony/recovery.py` (unchanged refusal); audit event `ceremony.recovery.denied`.
- **Tests:** as GD-001.

## GD-003 Test deadlines: injectable clocks and windows

- **Decision:** Isolated, test-only injectable clocks and database fixtures are approved to verify the expiry
  of installation and recovery approvals. There must be no production bypass.
- **Implementation:**
  - `apply_install(..., activation_window=...)` and `apply_recovery(..., activation_window=...)` accept a
    deadline window. The default is the approved 24-hour window. The production command-line path passes no
    window, so production always uses 24 hours.
  - The `clock` parameter already present on both services supplies the reference time. Tests may inject it.
- **Tests:** deadline and expiry tests use short windows (seconds) and a real wait, so the database clock
  and the service clock agree. No protected column is back-dated.
- **Limits:** no window can be set through configuration, the command line, or the HTTP layer.

## Consequences for the eight blocked tests

The eight tests in the Phase 1 evidence (zero-Administrator recovery, recovery appointments (4), the sweep of an
unconsumed appointment, the reserved-contact installation, and the install contact past its deadline) are
restored and must pass under GD-001 to GD-003. None is waived.

## P-INC3-PHASE1-CLOSE-07 — proof rollback semantics and password-reset policy (WDS direction, recorded; not an approved spec change)

Recorded from WDS's direction for the Phase 1 closure. This entry does not edit the approved baseline or Amendment A2.

### 1. Operation proofs: exactly-once committed semantics (adopted)

- A proof is consumed by a privileged mutation inside the same database transaction. A successfully committed
  privileged operation consumes its proof permanently.
- If the transaction rolls back, the mutation rolls back with it, and the proof may be used again while it is unexpired
  and the session is still valid and authorized.
- Concurrent attempts cannot produce more than one committed operation (row lock on the proof).
- Denial audit events are written in a savepoint and committed by the transaction runner, so they survive refusal.
- No detached (independently committed) consumption is implemented.
- **Interpretation check against Amendment A2:** A2 requires single-use operation proofs. This entry reads "single-use" as
  "one committed privileged operation per proof". If WDS intends "burn the proof even when the transaction rolls back",
  that is a conflict. It would require a detached commit, which this entry excludes. WDS should confirm the reading.

### 2. Password reset (conformance gap identified; correction required)

- **Approved policy (GOVERNANCE.md, secure credential activation and reset):** "Approved active account owners may request
  reset" through a privately delivered random single-use 30-minute token stored as a hash. No Administrator can view a
  token. Onboarding stays disabled without tested transport.
- **Current implementation (up to 0027):** reset-token issuance requires an Administrator-issued proof. That is stricter
  than the approved policy, which allows self-service. It does not provide the self-service pathway, so it does not
  conform.
- **Required correction (not yet implemented):**
  - **A. Self-service:** the trusted authentication authority, and only the authority, issues a reset token for an active
    account, delivered to the approved contact. The response is neutral and does not reveal whether the account exists.
    Rate limits and replay protection apply. The application role cannot generate a usable token. This pathway needs a
    tested transport. Until one is approved, it stays disabled outside the test profile.
  - **B. Administrator-assisted:** an Administrator may trigger the same delivery, through an operation-specific proof and
    audit. The Administrator never sees or sets the secret.
- **WDS confirmation needed:**
  - The governance phrase "Administrators MUST NOT ... reset user credentials" must be reconciled with pathway B. The
    reading proposed here is: pathway B triggers delivery only, with no secret, no password choice and no viewing.
  - The approved production transport for reset delivery does not exist yet. Pathway A cannot be enabled in production
    until it does.

## P-INC3-PHASE1-CLOSE-08 — WDS decisions 1-5 (2026-10-22): implemented status

1. **Active account owners may initiate their own password resets.** Implemented in the authority
   (`POST /v1/reset/request`, migration 0028). Neutral reply; rate-limited (5 per contact and 100 per IP in 15
   minutes); token only for an active account with a verified delivery transport; delivered to the approved contact.
2. **Administrators may trigger notification only.** Implemented through the operation-proof path
   (`account.reset.issue`). The Administrator never receives the secret and cannot choose the password.
3. **Provider-independent private transport; SMTP first.** `EmailTransport` is provider-independent. `SmtpTransport`
   exists and is disabled by default (`WEBDESK_RESET_DELIVERY=disabled`). It refuses to run until
   `WEBDESK_SMTP_VERIFIED=true`, which must be set only after delivery to the approved contact is tested. The capture
   sink exists only in the test profile. **No delivery is enabled in this repository.**
4. **Exactly-once committed-operation semantics.** A rolled-back mutation may be retried with the same unexpired proof;
   a committed privileged mutation consumes its proof permanently. Tests: `tests/hardening/test_proof_rollback.py`.
5. **Continue remaining Phase 1 security work.** The run and intake authorization work (source upload, run start,
   cancel, retry, resume, reparse, job scheduling) is NOT complete. See the evidence file for the verified state.

**Narrowings applied (migration 0029):** `webdesk_ceremony` lost UPDATE on `users.normalized_email` and
`users.revision`, and EXECUTE on `fn_advance_contact_revision`, `fn_revoke_tokens` and `fn_revoke_user_sessions`.
`fn_consume_appointment` stays: the appointment trigger on `role_assignments` calls it with the caller's rights.

**Outbox:** the application role's UPDATE on `outbox_notices` is limited to delivery-state columns (status, lease,
attempts, timestamps, error class). It cannot change recipients, purposes, payloads or ciphertext, and cannot create
notices. A separate worker role was NOT created; this is recorded as a residual.

**Privilege audit (fresh hardening database, final code):**

```
## table writes by role (table level)
webdesk_app|audit_events|INSERT
webdesk_app|audit_tombstones|INSERT
webdesk_app|dependency_edges|INSERT
webdesk_app|idempotency_keys|INSERT
webdesk_app|rate_limit_events|INSERT
webdesk_app|run_input_snapshots|INSERT
webdesk_app|source_segments|INSERT
webdesk_app|source_versions|INSERT
webdesk_app|sources|INSERT
webdesk_app|workflow_checkpoints|INSERT
webdesk_app|workflow_jobs|INSERT
webdesk_app|workflow_runs|INSERT
webdesk_authority|audit_events|INSERT
webdesk_authority|credentials|INSERT,UPDATE
webdesk_authority|operation_proofs|INSERT
webdesk_authority|rate_limit_events|INSERT
webdesk_authority|sessions|INSERT,UPDATE
webdesk_ceremony|audit_events|INSERT
webdesk_ceremony|contact_reservations|INSERT
webdesk_ceremony|role_assignments|INSERT
webdesk_ceremony|setup_trust_ceremonies|INSERT,UPDATE
webdesk_ceremony|user_contact_approvals|INSERT
webdesk_ceremony|user_withdrawals|INSERT
webdesk_ceremony|users|INSERT
## column-level UPDATE/INSERT by role
webdesk_app|outbox_notices|attempt_count,available_at,delivered_at,last_error_class,lease_expires_at,lease_owner,status
webdesk_app|projects|revision,updated_at
webdesk_app|source_versions|extraction_version,parse_error,parse_status,revision,unprocessed_attachments
webdesk_app|sources|revision
webdesk_app|workflow_jobs|attempts,available_at,job_status,last_error_class,lease_expires_at,lease_owner,updated_at
webdesk_app|workflow_runs|failure_class,input_revision_hash,is_stale,parked_at,revision,stale_at,stale_reason,state,status,updated_at
webdesk_authority|credentials|password_hash,updated_at,user_id
webdesk_authority|sessions|expires_at,issued_at,last_seen_at,revoked_at,session_epoch_at_issue,session_id,session_token_hash,user_id
webdesk_authority|users|revision,session_epoch,status
webdesk_ceremony|setup_trust_ceremonies|activation_deadline,authorized_user_ids,ceremony_id,closed_at,completed_at,deployment_operator_id,effective_admin_count_at_start,independent_verifier_id,kind,owner_approval_ref,owner_identity_ref,signed_authorization_digest,started_at,status
webdesk_ceremony|user_contact_approvals|approved_at,approved_by_user_id,proof_ref,revision,status
webdesk_ceremony|users|status
## SECURITY DEFINER functions executable by app / ceremony / authority
webdesk_authority.fn_issue_operation_proof|webdesk_authority|webdesk_authority
webdesk_guard.fn_add_membership_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_approve_change_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_approve_create_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_archive_project_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_assign_role_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_cancel_change_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_consume_appointment|webdesk_guard_owner|webdesk_ceremony
webdesk_guard.fn_consume_token|webdesk_guard_owner|webdesk_app webdesk_authority
webdesk_guard.fn_create_project_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_disable_user_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_grant_access_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_grant_restricted_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_issue_activation_token|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_issue_owner_reset_token|webdesk_guard_owner|webdesk_authority
webdesk_guard.fn_issue_reset_token_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_mark_token_sent|webdesk_guard_owner|webdesk_app webdesk_authority
webdesk_guard.fn_proof_actor|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_reassess_classification_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_reject_create_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_release_reservations|webdesk_guard_owner|webdesk_app webdesk_ceremony
webdesk_guard.fn_request_change_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_request_create_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_request_replacement_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_revoke_expired_activation_tokens|webdesk_guard_owner|webdesk_app webdesk_ceremony
webdesk_guard.fn_revoke_membership_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_revoke_role_with_proof|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_revoke_user_sessions|webdesk_guard_owner|webdesk_app
webdesk_guard.fn_withdraw_with_proof|webdesk_guard_owner|webdesk_app

```

## P-INC3-PHASE1-CLOSE-09 — WDS final decisions 1-8 (approved 2026-10-23): implementation status

This entry records the eight WDS decisions as implemented after the baseline (commit 9bb7835, 516 passing tests). It does not modify any
earlier approval. Each decision names the commits, migrations and tests that implement it. Where the implementation departs from the
decision's wording, the departure is stated.

### Decision 1 — Rollback and single-use proofs (exactly-once committed operation)

- Implemented. A proof is consumed in the same transaction as the mutation it authorizes. A rollback restores the proof to unspent while
  it is unexpired. A committed use spends it for every later attempt (`proof_spent`).
- Concurrency: a second concurrent use waits on the proof row. If the first commits, the second is refused; if the first rolls back, the
  second may use the proof (`tests/hardening/test_proof_rollback.py`, rb_04 and rb_06).
- Denial audit: a refusal is written by the authority or the guard, and the transaction runner commits it.
- Commits: 8a2c273 (rb_06). Earlier semantics: migrations 0024 to 0030.

### Decision 2 — Password reset

- Implemented (migration 0036). An account owner's reset proof is issued to that account. `fn_issue_reset_token_with_proof` refuses any
  other actor (`reset_not_self`). An Administrator's reset for another account is refused by the database, including on a direct call.
- Administrator-triggered reset is notification-only: `account.reset.notify` (Administrator) returns the approved contact address of an
  active account and creates no token. `tokens.notify_reset` sends a notice that carries no secret.
- Real delivery stays disabled by default (`WEBDESK_RESET_DELIVERY=disabled`). The SMTP adapter requires every gate, including
  `WEBDESK_SMTP_VERIFIED=true`. No real delivery is enabled in this repository.
- Tests: `tests/hardening/test_reset_policy.py` (6 cases), `tests/hardening/test_eval_f11j_extended.py` (f11j_21, f11j_22),
  `tests/integration/test_owner_reset.py`, `tests/integration/test_tokens.py`.
- Commit: 0070ee3.

### Decision 3 — Source-content read security

- Implemented (migration 0037, `src/webdesk/intake/read_access.py`, interface `source-read/v1`). A read needs a session token and a grant
  that the authority issued for one source version. Identity comes from the session, verified in the database. No caller-supplied actor
  is accepted.
- A grant lasts 60 seconds (at most five minutes) and is bound to one session, one account and one source version. Expiry, revocation,
  logout and membership removal all end its use. Permission and quarantine are checked again at every read.
- The SOURCE_READ matrix is enforced in SQL (`fn_can_read_source_version`). Quarantined content is never granted or read.
- Direct database reads of `storage_key`, `content_hash`, `text_content` and `text_content_hash` are refused. The application role keeps
  SELECT on the other columns.
- Denial audit: `source.content.denied` with the account named, and `source.read.grant.denied` on the authority path.
- Tests: `tests/hardening/test_source_read_authorization.py` (13 cases), `tests/support/reads.py`.
- Commit: 2a37ef1.

### Decision 4 — SQL authorization

- Implemented in two parts. Migration 0035 adds `operation_authorization_rules`, derived from the permission matrix, and enforces it in
  `fn_validate_operation_proof`, which every proof consumption passes through. Migration 0037 enforces SOURCE_READ in SQL.
- PostgreSQL enforces: the actor is an active account; it holds an active role that the operation's rule names; for assigned operations,
  an active membership on the resource project; for reads, membership, the source.read grant, restricted grants and quarantine.
  Approval separation (`self_approval`) and the workflow-state checks of each wrapper are also in SQL (migrations 0026 and 0030).
- Remains in Python, by design: archive state, revision checks, the classification floor, and the content rule for Administrator source
  access (the database enforces the role there; the content grant is checked in the service). The authority decides whether a session is
  valid before it issues a proof.
- Bypass found and fixed: `fn_disable_user` was executable by PUBLIC (migration 0034). It is now owner-only.
- Tests: `tests/hardening/test_sql_authorization.py` (5), `tests/hardening/test_ceremony_and_public_execute.py`,
  `tests/hardening/test_privilege_audit.py`.
- Commits: 6502518, 5d79269, 469f10f.

### Decision 5 — Outbox worker

- Implemented (migration 0033). The `webdesk_outbox` identity holds no table write. Its transitions are guard functions: claim, renew,
  open the sealed prior address for the leased notice only, sent, dead-letter and retry. Each fences on the lease owner and status.
- The application role lost UPDATE on the outbox delivery-state columns and keeps SELECT.
- `OutboxWorker.deliver` renews the lease first, so a reclaimed worker reports `lease_lost` and writes nothing.
- Tests: `tests/hardening/test_outbox_identity.py` (11 cases); the existing outbox suites pass unchanged.
- Commit: b98a934.

### Decision 6 — Ceremony least privilege

- Implemented (migrations 0029, 0034 and 0038). The ceremony role has the three guard functions its flows call (appointment consumption
  for installation and recovery, and the reservation release and token revocation of the expiry sweep).
- Writes are limited to the flow columns: ceremonies (insert and the close columns), users (insert four columns; status), contact
  reservations, approvals (insert nine columns; status and revision), and role assignments (the bootstrap and appointment columns). Reads
  are limited to the tables those flows read. `user_withdrawals` INSERT was removed (0038).
- The approved zero-Administrator recovery and the no-self-approval rules are unchanged. The ceremony role cannot be assumed by a login
  role (tested).
- Tests: `tests/hardening/test_ceremony_and_public_execute.py` (24), `tests/hardening/test_privilege_audit.py`, and the existing
  installation, recovery and appointment tests.
- Commits: 6502518, 469f10f.
- Residual: the ceremony CLI declares an operator and a verifier identifier that are recorded in the audit. They are not authenticated
  here; the production authority and operator custody (decision 7) must authenticate them.

### Decision 7 — Production authority

- Documented, and production deployment is blocked. `docs/PRODUCTION_BOUNDARY.md` lists each dependency and blocker: trusted authority
  deployment, signing-key custody, authenticated transport, separate database identities, worker deployment and isolation, the approved
  email transport, and operational monitoring and recovery.
- No production service was deployed. No readiness claim is made.

### Decision 8 — Intake worker identity

- Implemented and tested. A dedicated LOGIN role, a member of `webdesk_worker` and of nothing else, runs the intake worker. The test
  provisions the login with a password, verifies its memberships and attributes, runs the intake worker through it, and refuses direct
  writes, human wrappers and role changes.
- The worker login is not created by a migration, because migrations hold no secrets. Deployment must provision it (see
  `docs/PRODUCTION_BOUNDARY.md`).
- Tests: `tests/committed/test_worker_login.py` (4 cases).
- Commit: 9306a06.

### Final verification (2026-10-23, fresh databases)

- Full regression suite: 597 passed, 0 failed, 0 skipped.
- Restricted-login hardening folder: 197 passed. EVAL-F11j (both files): 37 passed.
- Reset policy (`test_reset_policy`, owner reset, tokens): 21 passed.
- Source-read security (authorization, intake, phase E, HTTP intake): 46 passed.
- Worker and ceremony privileges (audit, ceremony, outbox identity, worker login, installation and appointment): 66 passed.
- Proof replay, rollback and concurrency (proof rollback, SQL authorization, release boundary): 39 passed.
- Ruff: clean (src, tests, migrations). Strict mypy: clean (56 source files).
- Alembic: head to 0029 and back to head on a fresh database, and each of 0030 to 0038 round-trips on its own. A full downgrade to
  base is not possible on this shared cluster: migration 0001 drops roles that other databases hold (pre-existing, not changed).
- Privilege audit (catalog, final state): `docs/PRIVILEGE_AUDIT_2026-10-23.txt`. No PUBLIC EXECUTE on any guard, authority or public function.

### Residual risks recorded for the reviewer

1. The authority's HTTP transport is loopback and shares a bearer secret; it is not authenticated beyond that (decision 7).
2. Authorization for proof operations is enforced in SQL for role and membership, and for reads in full. The per-resource business rules remain
   in Python (above).
3. The ceremony operator and verifier identifiers are declared, not authenticated.
4. The login-rate limiter is per client address and stored in the database. Repeated runs against one database can exhaust it; the test
   suites reuse sessions to avoid this.
5. Full downgrade to base is not supported on a shared cluster (migration 0001).

## P-INC3-PHASE1-REVIEW-FIX-10 — Independent review findings F1-F4: fixes, exceptions and residuals (2026-10-26)

This entry records the closure of the four findings from the independent Phase 1 acceptance review of 640287e. It does not modify
any earlier approval. Commit 4340350 carries the fixes. The changes made after it are listed under "Follow-up changes" below and
are not yet committed at the time of writing.

### Findings and fixes

| Finding | Severity | Fix | Migration | Reproduction |
| --- | --- | --- | --- | --- |
| F1 Application login could mint and supersede activation tokens | High | Activation issuance needs an `account.activation.issue` proof held by an active Administrator (`fn_issue_activation_with_proof`). The caller-supplied function is dropped. Bootstrap uses `fn_issue_ceremony_activation` (ceremony role only; see below). | 0039 | `tests/hardening/test_review_reproduction.py` (4 cases, restricted login) |
| F2 Worker identities could write human-attributed audit rows | Medium | `fn_worker_record_audit` accepts `system` events only and refuses an actor identifier that names an account (R-F2 below). | 0039 | `tests/integration/test_security_closure.py` (worker role) |
| F3 Self-assignment refused only in Python | Medium | `fn_assign_role_with_proof` refuses `actor = target` in SQL (`self_assignment`). The Python check stays as a second layer. | 0039 | `tests/hardening/test_review_reproduction.py::test_f3_the_original_self_assignment_is_refused_in_sql` |
| F4 Revisions loaded sibling revisions by path | Medium | Frozen text in each revision (0027, 0030, 0035, 0036). See "Historical migration exception". | 0027, 0030, 0035, 0036 | Static check `tests/hardening/test_security_closure.py::test_no_migration_loads_another_revision_by_path`, plus equivalence evidence below |

### Ceremony activation decision (WDS direction 1, conditionally approved)

`webdesk_guard.fn_issue_ceremony_activation(user, token_hash, destination, ttl)` issues a bootstrap activation token. It is
conditionally approved, subject to the following, each of which is tested.

- **Eligibility.** The function requires a live approval with `administrator_appointment` set, `ceremony_id` not null, status
  `approved`, and `expires_at > now()`. An account without such an appointment is refused (`ceremony activation needs a live
  ceremony-backed appointment`). Test: `tests/integration/test_security_closure.py::test_a_ceremony_token_is_refused_without_a_ceremony_backed_appointment`.
- **Expiry.** Once the appointment window has passed, issuance is refused. Test: `tests/committed/test_deadlines.py::test_a_bootstrap_token_is_refused_once_the_appointment_has_expired`
  (real clock, installation window of six seconds).
- **Single use and supersession.** Each issuance supersedes the previous live token. The superseded token cannot be consumed; the
  newest can be consumed once. Test: `tests/integration/test_security_closure.py::test_a_bootstrap_token_is_single_use_superseded_and_audited`.
- **Role isolation.** Only `webdesk_ceremony` may execute the function. The application login is refused by privilege
  (`tests/hardening/test_security_closure.py::test_the_application_role_cannot_call_the_ceremony_activation_function`). The
  ceremony role's function list is pinned (`tests/hardening/test_privilege_audit.py`, `CEREMONY_EXECUTE`).
- **Audit.** Each issuance writes a `token.issued` audit row for the account. The single-use test asserts two rows for two issuances.
- **Savepoint.** A refusal rolls back inside the ceremony role before the caller's role is restored, so no aborted transaction state
  is left behind (`src/webdesk/tokens/service.py`, `issue`).

Scope: the ceremony role gains one function, so it now executes four guard functions, not three. This extends decision 6. WDS
approval is recorded here as conditional on the reviewer verifying the list above.

### R-F2 residual and its exact scope

Before this fix, a worker or outbox identity could write `system` audit rows naming any account, so an audit row could appear to
be an account's own action. The fix is narrow.

- Refused: any event whose actor type is not `system`, and any `system` event whose actor identifier equals an existing account's
  identifier (`worker audit may not name an account`).
- Allowed: deployment-defined worker labels (for example `worker-1`, `outbox-worker`, `parser`, `run:<run_id>`).

**Residual that remains:** a worker can still write a `system` event under any label that is not an account identifier, and that
label is not checked against the deployment's worker list. The label cannot make a row look human or belong to an account, but it
can make a system event look as if another worker wrote it. WDS direction 2 accepts this residual. The worker identity is a
deployment dependency: it must be provisioned with its own login (see `docs/PRODUCTION_BOUNDARY.md`), and its labels should be
enforced by deployment configuration.

### Historical migration exception (narrow, WDS-approved on stated conditions)

Revisions 0027, 0030, 0035 and 0036 were committed earlier on this branch. Commit 4340350 changes their source text: sibling
revisions are no longer loaded by path, and the same text is kept as literal snapshots. WDS granted a narrow exception on the
following conditions. Each is verified in the evidence document.

1. Executed `UPGRADE_SQL` and `DOWNGRADE_SQL` are byte-identical to the committed originals (`git show 4340350^:...`).
2. Revision identifiers and dependencies are unchanged.
3. Fresh installation and forward migration are verified.
4. The exception is documented here.
5. The independent reviewer verifies the equivalence. This is open until the reviewer does so.

No general permission to rewrite committed migrations is granted. Evidence and the resolution are in
`docs/INCREMENT_3_EVIDENCE.md`, section "Phase 1 review-fix closure".

**Remote history.** The remote-tracking reference in the local clone (`origin/feature/increment-1-foundation`, last fetched
2026-10-20) does not contain the commits that introduced 0027 to 0036. Whether any shared environment applied those revisions is
therefore unknown from this repository. WDS must confirm that no environment other than local test databases has applied them. If
any has, the exception does not cover it, and the migration must not be edited there.

### Follow-up changes after 4340350 (uncommitted at the time of writing)

- R-F2 rule in migration 0039 and its tests (integration suite).
- Savepoint inside the ceremony role switch (`tokens/service.py`), so a refusal does not leave aborted state.
- Ceremony tests: eligibility, expiry, single use, audit (integration and committed suites).
- Reproduction module `tests/hardening/test_review_reproduction.py`, replacing scratch probes.

### Verification (single pass, 2026-10-26, fresh databases)

| Step | Result |
| --- | --- |
| Full regression suite (`tests`) | 617 passed, 0 failed, exit 0 |
| Restricted-login hardening (`tests/hardening`, includes privilege audit and reproduction) | 210 passed, exit 0 |
| EVAL-F11j (`test_eval_f11j.py`, `test_eval_f11j_extended.py`) | 37 passed, exit 0 |
| Ruff lint (`src`, `tests`, `migrations`) | clean after one docstring fix; exit 0 |
| Ruff format | 5 files not formatted, all predating this work and untouched (0017, 0019, 0020, `test_privilege_hardening.py`, `test_reassessment.py`) |
| Mypy strict (`src/webdesk`) | clean, 56 source files |
| Migration fresh head, downgrade to 0029, upgrade to head | pass; catalog identical to a fresh head build |
| One-step downgrade of 0039 | restores the 0038 catalog exactly |

The full suite ran before one docstring-only edit in `tests/integration/test_security_closure.py`. No test logic changed after it.

### Production-only versus non-production blockers

- Non-production acceptance blockers: the reviewer's verification of the historical migration exception (item 5 above); the unresolved
  remote-history question; ruff formatting on five files that predate this work. None of these affects database behaviour.
- Production-only blockers (unchanged; see `docs/PRODUCTION_BOUNDARY.md`): trusted authority deployment and signing-key custody;
  authenticated transport in place of loopback with a bearer secret; separate database identities; worker deployment and isolation;
  an approved email transport; operational monitoring and recovery; authenticated ceremony operator and verifier identities.

## P-INC3-AI-SCAN-07 — AI read v1 scan-status ruling (post-baseline clarification, 2026-10-26)

WDS ruling on the scan-status question raised against `ai-read/v1`. This is a clarification recorded after the S0 baseline. It
rewrites no approved specification.

- Gate 1 source eligibility is unchanged. `not_scanned` remains eligible for authorized Foundation processing where scanning is
  unavailable (`REQUIREMENT_SCHEMA.md` `RunInputSnapshot` and R1; `ARCHITECTURE.md` quarantine "when scanning is available").
- The AI v1 read path may return `not_scanned` content to a verified principal that is in scope, unexpired, unrevoked and
  authorized under the existing rules. Quarantined and restricted content are denied for every principal.
- External transmission of real client content to an AI provider is not authorized by a `not_scanned` status. It needs a
  separately accepted content-safety, disclosure and deployment policy.
- Non-production content-read tests may use synthetic fixtures, including `not_scanned` sources.
- Production integration remains blocked.

Contract text reflecting this: `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` section 13A.
