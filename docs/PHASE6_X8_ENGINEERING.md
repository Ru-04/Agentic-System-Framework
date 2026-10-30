# Phase 6 (X8) engineering record: H-50, H-51, H-52 and H-DEC-8

Authoritative scope: `docs/INCREMENT_3_HARDENING_PLAN.md`, Phase 6 (lines 146–151) and the H-DEC-8 row.
WDS confirmed in chat that Phase 6 means exactly H-50, H-51 and H-52. The earlier broader description of
Phase 6 as general notification work is withdrawn.

Implementation commit: **e644669** (on `feature/foundation-phase-6`, from `feature/foundation-phase-5` at ddbb983).

## Requirement matrix

| Req | Requirement (plan text) | Implementation | Tests | Status |
| --- | --- | --- | --- | --- |
| H-50 | Recovery CLI `python -m webdesk.cli.recover`, install pattern | `src/webdesk/cli/recover.py` | `tests/unit/test_phase6_cli.py`, `tests/integration/test_phase6_x8.py` | Complete |
| H-50 | Every refusal validated before any insert; no `initiated` row left | `ceremony/recovery.py` (`apply_recovery`: target and reservation checks before the ceremony insert) | `test_h50_a_refused_appointment_leaves_no_initiated_ceremony_row` | Complete |
| H-50 | Refusals audited through the commit-on-domain-error runner | `cli/recover.py` `run_recovery_audited` via `run_in_transaction` | same | Complete |
| H-50 | Verifier ID comes from the signed artifact, not a constant | `prepare_recovery` requires `independent_verifier_id`; `apply_recovery` uses it | `test_recovery_artifact_without_a_verifier_is_refused`, `test_recovery_artifact_supplies_the_verifier_it_names` | Complete |
| H-51 | Sweep and outbox entry points | `cli/sweep.py` (one audited pass), `cli/outbox.py` (one batch, fail closed) | `test_sweep_cli_...`, `test_outbox_cli_...` | Complete as one-shot entry points; scheduling is H-26 |
| H-51 | Sweep `SET LOCAL ROLE` does not leak into the caller's transaction | `identity/sweep.py` restores the caller's role after success | `test_h51_the_sweep_restores_the_callers_role` | Complete |
| H-52 | Catch every transport exception; each failure audited | `outbox/worker.py` `deliver` (catch-all, `outbox.delivery.failed`) | `test_h52_a_non_transport_exception_is_audited_and_retried` | Complete |
| H-52 | Renewal invoked by the heartbeat | Lease renewed immediately before every send. The periodic heartbeat is H-22 (Phase 3) | existing `test_only_the_lease_holder_can_renew` | Partial: periodic heartbeat is a Phase 3 dependency |
| H-52 | Dead-lettering and in-app alert real, not only an audit row (H-DEC-8) | `in_app_alerts` table (migration 0044) written by `fn_outbox_record_alert` in the dead-letter transaction | `test_h52_a_dead_letter_writes_one_alert_and_a_duplicate_is_refused`, `test_h52_a_failed_alert_audit_rolls_back_the_dead_letter` | Complete |
| H-52 | Restricted-role access | Outbox role: EXECUTE on the function only. App and login roles: no privilege | `test_h52_application_and_outbox_roles_cannot_read_or_change_alerts`; `tests/hardening/test_privilege_audit.py` allow-list | Complete |

## H-DEC-8 decision record

- **Decision:** Option 1, a dedicated in-app alert table. Selected by WDS in the Phase 6 authorization message.
- **Design:** `in_app_alerts(alert_id, notice_id UNIQUE, user_id, alert_kind = 'delivery_failed', reason_code, created_at)`.
  Identifiers and a reason code only: no address, no message body, no secret.
- **Existing-table check:** `outbox_notices` already carries a `delivery_failure_alert` purpose. That is an outbox
  message for later sending, not an in-app record, so it does not satisfy H-DEC-8 option 1 and was not reused.
- **Audit remains separate:** the audit event `ops.alert.delivery_failed` is kept, and `outbox.delivery.failed`
  is added per failed attempt.
- **Approval provenance:** the WDS authorization message in this conversation (Phase 6 final authorized execution).
  No approver identity, timestamp, signature or artifact hash is recorded here beyond that message.
- **Administrative attestation required:** none beyond the WDS selection. The governance register entry should
  reference the authorization message, and any formal attestation must come from the governance process.

## Migration 0044

- Revision `0044_in_app_alerts`, down-revision `0043_x7_stale_reason_first_mark`.
- Creates `in_app_alerts`. Grants `SELECT, INSERT` to `webdesk_guard_owner` only.
- Creates `webdesk_guard.fn_outbox_record_alert(uuid, uuid, text)` (SECURITY DEFINER, owner guard owner,
  `search_path` pinned). EXECUTE to `webdesk_outbox` only.
- Downgrade drops the function and the table.
- Downgrade to 0043 and re-upgrade to head were run on the development cluster; exit codes are recorded in the QA report.

## Verification (developer, commit e644669)

- Full suite: 672 passed, 0 failed, 0 skipped, exit 0. Cluster `webdesk-p6-postgres`, system identifier 7702488924708163622, PostgreSQL 16.4.
- Clean baseline before changes (commit ddbb983): 660 passed, 0 failed, 0 skipped, exit 0.
- New Phase 6 tests: 12 (6 unit, 6 committed-database). Ruff check and format pass on changed files. `mypy --strict src/webdesk` passes.
- One regression found and fixed: the hardening allow-list of guard functions for `webdesk_outbox` gained
  `fn_outbox_record_alert`, the one intended grant. The test still fails for any unlisted grant.

## Known limitations

- H-52 periodic heartbeat is a Phase 3 dependency (H-22). Renewal happens at the start of delivery and immediately before the send.
- H-51 entry points are one-shot. Repeated passes need the Phase 3 worker (H-26), which is not in this branch.
- No read path or UI for `in_app_alerts` exists. That is intentional: the requirement is a durable record, and no
  alert UI or lifecycle was approved.
- Recovery artifacts issued before this change have no `independent_verifier_id` and will be refused. The owner must re-sign them.

## Cross-phase dependencies

| Dependency | Owner | Note |
| --- | --- | --- |
| Heartbeat renewal and worker supervision (H-22, H-26) | Phase 3 | Entry points here are one-shot |
| Outbox worker lease semantics and fencing | Phase 3 | `fn_outbox_*` functions unchanged |
| Recovery artifact format (new required field) | Owner signing process | Artifacts must be re-signed with `independent_verifier_id` |
| Migration ancestry: 0044 on 0043 on Phase 5 head | Integration | Reconcile before any merge |
| Phase 5 Finding 5 (`fn_worker_mark_inputs_changed`) | Phase 3 | Unchanged by Phase 6 |

## Independent QA and acceptance status

- Engineering frozen SHA: **9a9e8d3** (`feature/foundation-phase-6`). Full suite: 681 passed, 0 errors,
  0 failed, 0 skipped, exit 0 (two runs by the reviewer, both clean).
- Independent QA verdict on 9a9e8d3: **QA PASSED — eligible for WDS Phase 6 acceptance** (reviewer
  assessment, not WDS acceptance). Reviewer checkout detached at 9a9e8d3; QA cluster `webdesk-p6-qa-postgres`,
  port 5483, system identifier 7702493747633016870.
- Commit history of the review: e644669 (QA FAILED: five findings) → 207b780 (findings fixed; one
  intermittent teardown error, QA FAILED) → 538ac10 (guard counts client backends only) → 9a9e8d3
  (guard tests added; QA PASSED).
- WDS formal acceptance: **PENDING** (requires WDS decision).
- Open informational items, not blockers: `recover` exit 0 through the command line is covered only at
  the service level; the verifier is not checked for distinctness from the operator or owner; the
  periodic heartbeat (H-22) is a Phase 3 dependency; alert-function wrong-owner refusal has no
  permanent test (verified by the reviewer with a scratch test).
- Teardown root cause, evidence-based: pg_stat_activity background processes have NULL usename and NULL
  state; the guard now counts only client backends (538ac10), and tests/integration/test_session_leak_guard.py
  checks that a live client session still blocks the drop.

## Formal acceptance record (draft, not granted)

Recorded from the acceptance text supplied in chat. The content matches the reviewed evidence above.

- Scope: H-50, H-51, H-52; H-DEC-8 option 1 (dedicated `in_app_alerts` table).
- Engineering SHA: 9a9e8d3. Documentation SHA: eb1a4d1.
- Independent QA: PASSED, eligible for WDS acceptance (reviewer assessment).
- Technical recommendation: ACCEPT, standalone scope only.
- **WDS formal acceptance: PENDING.** Requires explicit authenticated WDS confirmation, recorded against the
  verified artifacts. The approver identity, timestamp, signature and channel are not in this repository and
  have not been filled in.
- Follow-up recommended before or with acceptance: promote the wrong-owner alert-refusal scratch test to a
  permanent regression test. This is a test-only change and would require a new frozen SHA and reviewer re-check.
- Accepted limitations and dependencies: as listed above. Standalone acceptance does not authorize deployment,
  waive Phase 3 security requirements, or establish cross-phase integration readiness.
