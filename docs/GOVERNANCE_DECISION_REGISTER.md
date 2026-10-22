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
