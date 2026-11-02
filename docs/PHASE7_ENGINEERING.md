# Phase 7 engineering record: H-60 to H-77

Authoritative scope: `docs/INCREMENT_3_HARDENING_PLAN.md`, Phase 7 (lines 152–171), the decisions in §9 and the
boundaries in §10. Authorization: the WDS "Foundation Phase 7 complete end-to-end execution" message in chat.
No approver identity, timestamp, signature or artifact digest is recorded here beyond that message.

Branch: `feature/foundation-phase-7`. Phase 7 starts at bdf6f15; implementation commits 123f08d..ae032a2.
Engineering frozen SHA: **ae032a2**.

## Requirement matrix

| Req | Requirement (plan, short) | Status | Implementation | Tests |
| --- | --- | --- | --- | --- |
| H-60 | Upload size checked before parse, authorization and revision | Implemented (123f08d) | `intake/ingest.py`: `validate_upload` runs before `_authorize` and the revision check | `tests/integration/test_phase7_intake.py` (413 and 415 with a stale revision) |
| H-61 | Multipart field allowlist | Implemented before Phase 7; unchanged | — | existing |
| H-62 | Idempotency keys on run.start and reparse | Implemented (473ed22) | `idempotency.service.run_keyed` (mutation and key in one savepoint); `api/routes.py`, `runs/service.py`, `intake/reparse.py` | `tests/committed/test_phase7_idempotency.py` (replay, different payload 409, other actor, refusal keeps denial audit, lost race commits no run) |
| H-63 | Orphan files | Implemented before Phase 7; unchanged | — | existing |
| H-64 | EML HTML and `name=` parts per H-DEC-6 | **Not implemented: dependency** | H-DEC-6 is ruled only on the Phase 4 branch, and the parser being changed is the Phase 4 `parse_eml` rewrite | — |
| H-65 | `.md` MIME alternatives | **Blocked** | No documented list of accepted Markdown MIME alternatives (architecture lists only `text/markdown`). WDS must name them | — |
| H-66 | `source_trust` server-derived: the uploader cannot set `approved_reference` | Implemented (f4c633f) | The ingest service refuses `approved_reference` itself, with an audited denial, so no caller can set it. No wider derivation rule is specified in the plan | `test_h66_the_service_refuses_approved_reference_trust_with_an_audited_denial` |
| H-67 | Late reclassification to restricted | **Blocked by H-DEC-2** | The plan requires a policy ruling before any change | — |
| H-68 | Lock order per H-25; cancel rule H-DEC-1 | **Not implemented: Phase 3 dependency** | H-25 lock order is Phase 3 (migration 0050 there); importing it is outside Phase 7 authority. The plan says the parked-run cancel rule (H-DEC-1) "is not changed here" | — |
| H-69 | Checkpoint guard checks value types | Implemented (0ae3222) | Migration `0047_p7_checkpoint_value_types` | `tests/integration/test_intake_schema.py` (accepted types; six wrong-type cases, SQLSTATE 23514) |
| H-70 | Run audits carry `project_id`; claim, requeue, transitions audited | Implemented (ae032a2) | Migration `0049_p7_run_audit_project_id` (8-argument `fn_worker_record_audit`, stale-mark audit); `runs/service.py`, `runs/jobs.py`, `audit/service.py` | `tests/integration/test_runs_db.py`, `test_gap_closure.py`, `test_security_closure.py` |
| H-71 | Error mapping: only the active-run index is `active_run_exists` | Implemented (c172a5b) | `runs/service.py` maps by constraint name; other integrity errors are audited 409 refusals | `tests/committed/test_phase7_runs.py` (start/retry races), `test_runs_db.py` |
| H-72 | Atomic rate limits | Implemented before Phase 7; unchanged | — | existing |
| H-73 | Withdrawal audit non-null; reason redacted | Implemented (a0a8a72) | Migration `0048_p7_withdrawal_audit_notnull` (refuses if NULL rows exist); `identity/contacts.py` audit details hold `reason_given` and `reason_length` only | `test_contact_lifecycle.py`, `test_gate1_schema.py` |
| H-74 | Signed artifacts: replay, operator and verifier binding, PEM load | Implemented (4153083) | Migration `0046_p7_ceremony_digest_unique`; `ceremony/install.py`, `recovery.py`, `cli/install.py`, `cli/recover.py` | unit, committed and integration tests named `test_h74_*` |
| H-75 | Restricted grants validated; source grant bound to its project | Implemented (7dc8f84) | `projects/service.py grant_restricted`; `rbac/sql_store.py has_restricted_grant` | `test_projects.py`, `test_intake_db.py` (`test_h75_*`) |
| H-76 | One time source (H-21) | **Not implemented: Phase 3 dependency** | H-21 is Phase 3 work; not imported | — |
| H-77 | Denial audits carry resource references | Implemented (85d44dd) | `intake/ingest.py`, `reparse.py`, `reassess.py` `_deny` | `test_intake_db.py`, `test_gap_closure.py`, `test_reassessment.py` |

## Decisions made in engineering

- **H-62:** `run_idempotent` was not used, because its savepoint rolls back on any exception and would drop denial audits (C-2). The new `run_keyed` releases the savepoint on a domain refusal, rolls it back on a database error, and rolls the mutation back if the key insert loses a race. The key is looked up right after the actor is known, before any other check. Response shapes are unchanged.
- **H-74:** a unique index on `signed_authorization_digest`, not a nonce column: the digest is the SHA-256 of the whole signed payload. `apply_recovery` refuses a reused digest before any write, as an audited `authorization_already_used` 409. The payload now carries `deployment_operator_id` (install and recovery) and `independent_verifier_id` (install). A missing field is `authorization_malformed`; a CLI value that differs is `operator_mismatch` or `verifier_mismatch`. `UnsupportedAlgorithm` from key loading is `owner_key_invalid`.
- **H-75:** a non-active project is `project_archived` (409); a missing resource is `resource_not_found` (404); a missing or inactive grantee is `grantee_not_active` (409).
- **H-70:** new audited events `job.claimed`, `job.requeued`, `run.transitioned`, and `run.stale_marked` (reason `inputs_changed_during_run`). The 7-argument `fn_worker_record_audit` is kept with unchanged grants but is no longer called from `src`.
- **H-73:** revision ID shortened to fit `alembic_version.version_num varchar(32)`.

## Migrations

All four are new; no accepted migration (0001–0045) was edited.

| Revision | Down revision | Change | Downgrade |
| --- | --- | --- | --- |
| `0046_p7_ceremony_digest_unique` | `0045_alert_requires_dead_letter` | Unique index on the authorization digest; refuses if duplicates exist | Drops the index |
| `0047_p7_checkpoint_value_types` | 0046 | Checkpoint guard checks value types | Restores the 0007 guard text |
| `0048_p7_withdrawal_audit_notnull` | 0047 | `user_withdrawals.audit_event_id` NOT NULL; refuses if NULL rows exist | Drops NOT NULL |
| `0049_p7_run_audit_project_id` | 0048 | 8-argument worker audit function; stale-mark audit with project | Restores the 0032 and 0043 function text |

## Verification (engineering, commit ae032a2)

- Full suite: **733 passed**, 0 failed, 0 errors, 0 skipped, exit 0 (13 min 38 s). One third-party deprecation warning (Starlette/anyio). Cluster `webdesk-p7-postgres`, port 5484, system identifier 7702521200730619942, PostgreSQL 16.4.
- Baseline before Phase 7 code (bdf6f15): 688 passed, exit 0.
- `ruff check src tests migrations`: pass, exit 0. `ruff format --check`: only the five documented exceptions (`0017`, `0019`, `0020`, `0040`, `tests/hardening/test_privilege_hardening.py`). `mypy --strict src/webdesk`: no issues in 61 files, exit 0.
- Migrations on a fresh scratch database: upgrade head, downgrade -1, downgrade to 0045, upgrade head, all exit 0. Single head `0049_p7_run_audit_project_id`. Afterwards: the digest index exists; `audit_event_id` is NOT NULL; both `fn_worker_record_audit` versions are SECURITY DEFINER, owned by `webdesk_guard_owner`, with `search_path` pinned and EXECUTE granted only to `webdesk_worker` and `webdesk_outbox` (no PUBLIC). The scratch database was dropped.
- Mutation checks: one or more per implemented item, run by the engineer. Each removed safeguard made at least one test fail, and the source was restored.

## Known limitations

- H-64, H-65, H-67, H-68 and H-76 are not implemented (see the matrix).
- Route-level 413 (body larger than the server limit, before the service runs) is not audited. Open WDS question: whether the architecture requires an audit there.
- H-66: the plan text (uploader cannot set `approved_reference`) is met; any wider server-side trust derivation would need a WDS rule.
- Install and recovery artifacts signed before H-74 lack `deployment_operator_id` / `independent_verifier_id` and will be refused. The owner must re-sign them.
- Existing event-name quirk kept: guard-refusal denials in `_control` are written as `run.run.retry.denied` / `run.run.cancel.denied`.
- Out of scope, unchanged: `source.parse.*` worker audits have no `project_id`; `authority.proof.refused` audits carry no record references.

## Cross-phase dependencies

| Dependency | Owner | Note |
| --- | --- | --- |
| Migration ancestry: 0046_p7..0049_p7 on 0045 | Integration | Phases 2, 3 and 4 fork from `0041_ai_read_v1`. Phase 2 has `0046_fixed_contact_change_window` (same numeric prefix, different ID); Phase 3 has 0050–0054. Reconcile into one linear chain before any merge |
| H-68 lock order (H-25) and cancel rule (H-DEC-1) | Phase 3 / WDS | Phase 7 cancel and claim lock orders are unchanged |
| H-76 single time source (H-21) | Phase 3 | Not imported |
| H-70 overlap with Phase 3 `runs/jobs.py` | Integration | Both branches edit `jobs.py` and worker audit calls; merge must keep `project_id` on every audit |
| H-64 EML handling (H-DEC-6) | Phase 4 | Parser rewrite and ruling are on the Phase 4 branch |
| Signed artifact format | Owner signing process | New required fields for install and recovery |

## Independent QA and acceptance status

- Engineering frozen SHA: **ae032a2** (`feature/foundation-phase-7`). The reviewer's report is
  `docs/PHASE7_QA_REPORT_ae032a2.md`, copied unchanged from the reviewer's output.
- Reviewer: a separate agent that did not write the code, working in a detached checkout
  `D:/WDS/qa-p7-ae032a2` at ae032a2, on QA cluster `webdesk-p7-qa-postgres`, port 5485,
  system identifier 7702525271513341990, PostgreSQL 16.4.
- Reviewer results: full suite 733 passed, 0 failed, 0 errors, 0 skipped, exit 0; ruff check clean; format check
  shows only the five documented exceptions; `mypy --strict` clean; migrations 0045 → head → -1 → 0045 → head
  all succeeded, with the downgrade catalog matching 0045 exactly; accepted migrations 0001–0045 unchanged;
  privileges as intended; 20 code and 4 database mutations, all caught except one H-60 variant (F-1).
- Verdict on ae032a2: **QA PASSED — ELIGIBLE FOR WDS PHASE 7 ACCEPTANCE** (reviewer assessment, not WDS acceptance).
- No remediation round was needed.
- WDS formal acceptance: **GRANTED** (see Formal acceptance record).

### Open findings (none blocking)

| ID | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| F-1 | Medium | No test proved the H-60 checks run before authorization (only before the revision check) | Closed by test-only commit 89d6ef2: `test_h60_size_and_type_are_checked_before_authorization` fails when validation is moved after `_authorize` |
| F-2 | Low | Pre-existing event names `run.run.cancel.denied` / `run.run.retry.denied`; the H-71 path inherits them | WDS call whether to rename |
| F-3 | Low | H-75 checks are service reads; `fn_grant_restricted_with_proof` does not re-check them, so a race with an archive or a direct function call can still insert a grant. The read path still refuses inactive users and ties sources to their project | Follow-up candidate: re-check inside the SQL function |
| F-4 | Low | `source.parse.*` worker audits have no `project_id` (version audits, outside H-70's letter) | Known limitation |
| F-5 | Informational | `docs/RUFF_FORMAT_EXCEPTIONS.md` header still says two test files are exceptions; now one | Documentation tidy-up |
| F-6 | Informational | `webdesk_authority` owns its schema and `fn_issue_operation_proof` (since 0021) | Pre-existing |
| F-7 | Informational | Signed artifact format changed (H-74); recorded here under Known limitations | Covered by this record |
| F-8 | Informational | Reparse has no lost-race test of its own; shares the `run.start` code path | Optional test |

## Acceptance-readiness package

- **Scope:** Phase 7, H-60 to H-77. Implemented: H-60, H-62, H-66, H-69, H-70, H-71, H-73, H-74, H-75, H-77.
  Already implemented and unchanged: H-61, H-63, H-72. Not implemented with stated reason: H-64, H-65, H-67,
  H-68, H-76. The reviewer confirmed this position.
- **SHAs:** start bdf6f15; engineering frozen ae032a2; documentation: the commit adding this record.
- **Evidence:** this record; `docs/PHASE7_QA_REPORT_ae032a2.md`.
- **Residual limitations:** see Known limitations and Open findings.
- **Non-production statement:** nothing was deployed, pushed or merged. All tests ran on isolated development and
  QA clusters. Standalone acceptance would not authorize deployment, waive Phase 3 requirements, or establish
  cross-phase integration readiness.
- **Technical recommendation:** ACCEPT, standalone scope only, with F-1 recommended as a test-only follow-up.

## Formal acceptance record

- Scope, SHAs and QA verdict: as above. Accepted engineering SHA ae032a2; documentation SHA 79fa636.
- **WDS formal acceptance: GRANTED**, stated by WDS in the Claude Code chat session on 2 November 2026
  ("I have given my formal phase 7 acceptance"). The approver identity, signature, approval-channel reference and
  artifact digests are not in this repository and have not been filled in.
- Post-acceptance, test-only commit 89d6ef2 closes QA finding F-1 (a test that H-60 size and type checks run
  before authorization; mutation-checked). It changes no source code.
- **Post-QA delta review of 89d6ef2: DELTA VERIFIED** (independent reviewer, a separate agent that did not write
  the test; detached checkout `D:/WDS/qa-p7-delta-89d6ef2`, removed after the run). Findings:
  - `89d6ef2` changes one file, `tests/integration/test_phase7_intake.py` (+38, no deletions). No existing assertion
    was altered and no skip, xfail or new noqa was added.
  - Focused run at 89d6ef2: `pytest tests/integration/test_phase7_intake.py`, 8 passed, 1 warning, exit 0. The file
    holds 7 existing tests plus the new one.
  - Mutation check: `validate_upload` moved after `_authorize` in a temporary copy. The new test fails
    (`403 == 415`, `content_grant_missing`), exit 1. Restored copy passes again, exit 0.
  - F-1 is resolved. The reviewer did not run the full suite, ruff or mypy, which were out of scope for this delta.
  - Hygiene (LOW): the reviewer's tool output printed a restricted QA test database URL, including its password. The
    password was not written to any file. Rotation is recommended and has not been done.
  - Cosmetic (not blocking): the valid-file control expects 403 because the admin account is not a project member.
    The docstring says "a user refused upload", and the variable name `admin_token` is misleading.
- **Post-QA test delta verdict: VERIFIED.** The earlier QA pass on `ae032a2` did not cover `89d6ef2`. This delta
  review covers only that commit.

## Cross-phase integration handoff

Integration is **not verified**. Before Phases 2–7 are combined:

1. Reconcile migrations into one linear chain. Phases 2, 3 and 4 fork from `0041_ai_read_v1`; Phases 5–7 continue
   0042–0049 on this line. Phase 2's `0046_fixed_contact_change_window` shares the 0046 prefix with
   `0046_p7_ceremony_digest_unique` (distinct IDs, but both would claim the next slot). Phase 3 uses 0050–0054.
2. Merge Phase 3 `runs/jobs.py` and worker audit changes with H-70 so every run audit keeps `project_id`.
3. Apply H-25 lock order and H-21 time source from Phase 3, then close H-68 and H-76.
4. Apply H-64 with the Phase 4 parser and the H-DEC-6 ruling.
5. Re-run the full suite and the privilege audit on the combined branch.
