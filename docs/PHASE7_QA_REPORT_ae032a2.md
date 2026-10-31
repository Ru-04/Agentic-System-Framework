# Foundation Phase 7: independent QA report (candidate `ae032a2`)

Reviewer: independent QA agent. I did not write this code. Date of run: 2026-10-31. No approvals, approver identities or sign-offs are recorded here. The verdict below is QA's own.

## 1. Environment

| Item | Value |
|---|---|
| Checkout | `D:/WDS/qa-p7-ae032a2`, detached worktree, own `.venv` from `uv.lock` |
| HEAD | `ae032a28b1d34d68795022c61ebe1f9334038e44` (branch `feature/foundation-phase-7`) |
| Phase 7 range | `bdf6f15..ae032a2`, 10 commits |
| Cluster | Docker `webdesk-p7-qa-postgres`, `127.0.0.1:5485` (no other port or container was used) |
| System identifier | `7702525271513341990` |
| PostgreSQL | `PostgreSQL 16.4 (Debian 16.4-1.pgdg120+2) on x86_64-pc-linux-gnu, compiled by gcc (Debian 12.2.0-14) 12.2.0, 64-bit` |
| Bootstrap | `bootstrap_p7_qa.sh webdesk-p7-qa-postgres 5485 C:/Users/baps/.webdesk-p7-qa D:/WDS/qa-p7-ae032a2`. I read it before running it. Exit 0. Both `webdesk_p6_base` and `webdesk_hardening` migrated to `0049_p7_run_audit_project_id (head)`. One benign NOTICE: `webdesk_authority_login` already held `webdesk_authority`. |
| Tools | ruff 0.6.9; mypy (from the venv); pytest (from the venv) |

Secrets stayed in `C:/Users/baps/.webdesk-p7-qa/`. No password was printed or written to git or to this report.

## 2. Checks run

| # | Check | Command | Result | Exit |
|---|---|---|---|---|
| 1a | HEAD | `git rev-parse HEAD` | `ae032a28b1d34d68795022c61ebe1f9334038e44` | 0 |
| 1b | Commits | `git log --oneline bdf6f15..ae032a2` | 10 commits: 123f08d H-60, f4c633f H-66, 85d44dd H-77, 473ed22 H-62, c172a5b H-71, 7dc8f84 H-75, 4153083 H-74, 0ae3222 H-69, a0a8a72 H-73, ae032a2 H-70 | 0 |
| 1c | Diff | `git diff bdf6f15..ae032a2` (read in full) | 37 files, +2340 / -92 | 0 |
| 2 | Full suite | `source env.sh; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | **733 passed, 0 failed, 0 errors, 0 skipped**, 1 warning (starlette/anyio DeprecationWarning), 679.34 s | 0 |
| 3a | Lint | `ruff check src tests migrations` | All checks passed | 0 |
| 3b | Format | `ruff format --check src tests migrations` | 5 files would be reformatted: 0017, 0019, 0020, 0040, `tests/hardening/test_privilege_hardening.py`. All 5 are listed as exceptions in `docs/RUFF_FORMAT_EXCEPTIONS.md`. `test_reassessment.py` is now formatted, matching its updated row. | 1 (expected; documented exceptions only) |
| 3c | Types | `mypy --strict src/webdesk` | Success: no issues found in 61 source files | 0 |
| 4a | Migration round trip | Scratch DB `qa_p7_mig_scratch` (owner `webdesk_integration_owner`): `upgrade 0045`, catalog dump, `upgrade head`, dump, `downgrade -1` (to 0048), dump, `downgrade 0045_alert_requires_dead_letter`, dump, `upgrade head`, dump | Every step exit 0. Catalog at 0045 before and after the downgrade: **identical** (`diff` exit 0). Head before and after the round trip: **identical** (`diff` exit 0). The scratch DB was dropped afterwards. | 0 |
| 4b | Single head | `alembic heads` | `0049_p7_run_audit_project_id (head)` | 0 |
| 4c | Revision ID length | script over `migrations/versions/*.py` | Maximum 32 (`0048_p7_withdrawal_audit_notnull`). 0046=30, 0047=30, 0049=28. | 0 |
| 4d | Chain | Read `down_revision` | 0045 → 0046 → 0047 → 0048 → 0049, linear | n/a |
| 4e | Downgrade fidelity | Catalog dump: md5 of `pg_get_functiondef`, owner, `prosecdef`, `proconfig` and ACL for every function in `public`, `webdesk_guard` and `webdesk_authority`; all constraints; column NOT NULL; indexes; triggers; table and column grants | 0045 → head differs **only** in: new body of `webdesk_checkpoint_guard()`, `fn_mark_downstream_stale` and `fn_worker_mark_inputs_changed` (owner and ACL unchanged); new `fn_worker_record_audit(...,uuid)`; `user_withdrawals.audit_event_id` NOT NULL; new index `setup_trust_ceremonies_digest_unique`. The downgrade restores the 0045 state exactly, including the 0007, 0032 and 0043 function bodies. | 0 |
| 7 | Accepted migrations untouched | `git diff bdf6f15..ae032a2 -- migrations/versions/00[0-3]*.py migrations/versions/004[0-5]*.py` | empty | 0 |
| 7 | Credentials | grep of the diff for password, secret, private key and token patterns, plus `.env`, `.pem` and `.key` filenames | none. The only PEM in the diff is a public test key on an unsupported curve. | 0 |
| end | Clean checkout | `git status --short` | empty | 0 |

## 3. Privileges (checked on `webdesk_hardening` and `webdesk_p6_base`)

- `webdesk_app`, `webdesk_app_login`, `webdesk_worker`, `webdesk_outbox`, `webdesk_ceremony`, `webdesk_authority`, `webdesk_authority_login` and `webdesk_guard_owner` all have `rolsuper=f`, `rolcreaterole=f`, `rolcreatedb=f`, `rolbypassrls=f`.
- No application role owns any table, view or sequence. **Exception, pre-existing and not touched by Phase 7:** `webdesk_authority` owns schema `webdesk_authority` and `webdesk_authority.fn_issue_operation_proof` (from 0021, `CREATE SCHEMA webdesk_authority AUTHORIZATION webdesk_authority`). See finding F-6.
- New or replaced SECURITY DEFINER functions:
  - `webdesk_guard.fn_worker_record_audit(text,text,text,text,text,jsonb,jsonb,uuid)`: owner `webdesk_guard_owner`, `search_path=pg_catalog, public`, ACL `{guard_owner=X, webdesk_worker=X, webdesk_outbox=X}`. That is exactly the grantee set of the 7-argument original, with no PUBLIC. The 7-argument function is unchanged.
  - `fn_mark_downstream_stale` and `fn_worker_mark_inputs_changed`: owner, `search_path` and ACL (`guard_owner`, `webdesk_worker`) are unchanged from 0045, verified by catalog diff.
  - `webdesk_checkpoint_guard()` is a trigger function, not SECURITY DEFINER. Its owner and ACL are unchanged. The trigger is `BEFORE INSERT`, and the table is append-only by trigger, so UPDATE cannot bypass it.
- SQL guards were not weakened. The catalog diff shows the only changes are added checks (H-69 types, H-73 NOT NULL, H-74 unique index) and added audit inserts (H-70).
- Proof requirements were not bypassed. A keyed `run.start` or reparse replay returns the stored response without consuming a new proof, and no mutation happens. This is the same semantics as the existing upload idempotency. Every mutating path still goes through `consume_with`.

## 4. Per-requirement table

| Item | Plan requirement (§3 Phase 7) | Verdict | Evidence | Mutation check I ran (result) |
|---|---|---|---|---|
| H-60 | Body limit before `request.form()`. Size and type checks before authorization, locks and revision checks. | Satisfied (code). Test gap: F-1. | `routes.py:134-156` `_bounded_form` (pre-existing from 43e0ff1). `ingest.py:182` `validate_upload` now runs before the idempotency lookup, `_authorize` (`:220`) and `_precheck_project` (`:231`). The `source.upload` proof issuance checks session liveness only, not permission. Tests: `test_h60_a_file_just_over_the_limit_is_413...stale_revision`, `test_h60_a_wrong_type_file_is_415...stale_revision`, `test_h60_an_oversized_body_is_refused_with_413_before_parsing`. | (a) Validation moved after the revision precheck: **caught** (`test_h60_a_file_just_over_the_limit...` failed). (b) Validation moved after authorization but before the precheck: **survived** all of `test_phase7_intake.py`, `test_intake_db.py` and `test_http_intake.py` (34 passed). A temporary QA probe (since deleted) showed HEAD returns 415/413 to an actor refused with 403 for a valid file, and the probe fails under mutation (b). See F-1. |
| H-61 | Multipart allowlist | Satisfied, pre-existing, unchanged | `ACCEPTED_UPLOAD_FIELDS` in `routes.py` from 43e0ff1, an ancestor of `bdf6f15`. `test_h61_a_field_outside_the_allowlist...` passes. | None (pre-existing; not in scope of this candidate) |
| H-62 | Idempotency keys on `run.start` and reparse | Satisfied | `idempotency/service.py` `run_keyed`: the mutation and the key share a savepoint. A lost race rolls back and returns 409 `concurrent_request`. A domain refusal releases the savepoint, so the denial audit survives. `runs/service.py start_run` and `intake/reparse.py`. Keys are scoped by (actor, endpoint, key). Tests (HTTP and committed): replay, different payload → 409 `idempotency_key_reused`, per-actor independence, refusal keeps its audit and stores no key, reparse replay and different payload, lost race commits no run. | (a) Lost race commits the savepoint instead of rolling it back: **caught** (`test_h62_a_lost_race_on_the_key_commits_no_run`). (b) Replay lookup removed from `start_run`: **caught** (`test_h62_a_run_start_replay...`). |
| H-63 | Bytes only after admission | Satisfied, pre-existing, unchanged | `ingest.py` H-63 comments at `_admit`. `test_h63_*` pass. | None (pre-existing) |
| H-64 | EML HTML bodies, `name=` parts | Not implemented (correct) | No change to `intake/parsers.py`. Depends on H-DEC-6 and the Phase 4 EML parser. | n/a |
| H-65 | `.md` MIME alternatives | Not implemented (correct) | No change to `validation.py`. No documented alternative MIME list exists to implement against. | n/a |
| H-66 | `source_trust` server-derived | Satisfied | Route refusal (pre-existing) plus a new service refusal at `ingest.py` (after `actor_for`), audited `source.upload.denied` / `trust_not_permitted` 422 with refs. Test `test_h66_the_service_refuses_approved_reference_trust...`. | Service check disabled: **caught**. |
| H-67 | Late reclassification to restricted | Not implemented (correct) | Blocked by H-DEC-2. Refusal unchanged. | n/a |
| H-68 | Lock order, cancel rules | Not implemented (correct) | No lock-order change in `runs/jobs.py` or `runs/service.py`. `_run_project` is a plain read with no new lock. The parked-run cancel rule is unchanged (H-DEC-1). | n/a |
| H-69 | Checkpoint guard validates value types | Satisfied | 0047: `refs` values must be arrays of UUID strings, `flags` values must be booleans, SQLSTATE 23514, and the messages name the key only. Tests: 1 accept case and 6 parametrized refuse cases. | Base DB downgraded to 0046 (0047 removed), H-69 tests run: **6 failed, 1 passed** (caught). Upgraded back to head. |
| H-70 | `project_id` on every run audit; audit claim, requeue, transitions and stale-marking | Satisfied | `jobs.py`: `job.claimed`, `run.transitioned` (every `_transition`), `run.parked`, `run.failed` and `job.requeued` all carry `project_id`. `service.py`: `_audit` takes a keyword-only `project`, so every start, cancel, retry and resume success or denial names it. 0049: the stale-mark audits now carry the run's project, and `inputs_changed_during_run` is now audited. No other SQL function writes a run or job audit (catalog query). Tests: 4 `test_h70_*` in `test_runs_db.py` and 3 in `test_security_closure.py`. | (a) Claim audit without project: **caught**. (b) Requeue audit renamed: **caught**. (c) 0049 `fn_mark_downstream_stale` audit with project set to NULL (migration edited, base DB `downgrade -1` and `upgrade head`): **caught** (`test_h70_a_superseded_input...`). Restored, base DB re-migrated, function md5 matches unmodified head. |
| H-71 | Only the active-run unique violation maps to `active_run_exists`; others are an audited refusal, not a 500 | Satisfied | `service.py _integrity_refusal` matches SQLSTATE 23505 and constraint `workflow_runs_one_active`. Anything else is `database_refused`, audited 409. Used in `_start` and in `_control` (retry racing start). Tests: `test_h71_another_unique_violation...` (unrelated unique index → `database_refused`), plus 2 committed two-connection race tests. | (a) Constraint-name check removed: **caught**. (b) `_control` integrity mapping removed: **caught** (HTTP `{'error': 'IntegrityError'}` instead of an audited 409). |
| H-72 | Atomic rate limits | Satisfied, pre-existing, unchanged | `ratelimit/limiter.py` unchanged in range. `pg_advisory_xact_lock` per key. `test_phase7_ratelimit.py` passes. | None (pre-existing) |
| H-73 | `audit_event_id` NOT NULL; reason redacted in the audit | Satisfied | 0048 refuses to apply if NULL rows exist and never rewrites rows. Then SET NOT NULL. `contacts.withdraw` audit details are now `{"reason_given": true, "reason_length": n}`. `fn_withdraw_with_proof` writes the reason only to `user_withdrawals`. Tests: `test_h73_a_withdrawal_without_an_audit_event_is_refused`, `test_h73_the_not_null_migration_refuses_existing_null_rows`, extended withdrawal lifecycle test. | (a) Reason put back in the audit: **caught**. (b) Base DB downgraded to 0047 (NOT NULL removed): **caught**. Upgraded back to head. |
| H-74 | Nonce or unique digest; operator and verifier bound into the signed payload; malformed or unsupported key produces the audited denial | Satisfied | 0046 unique index on `signed_authorization_digest` (the digest is SHA-256 of the canonical signed payload). `apply_recovery` refuses reuse under the advisory lock: `authorization_already_used` 409, audited, no ceremony row. `prepare_install` requires signed `deployment_operator_id` and `independent_verifier_id` equal to the CLI values. `prepare_recovery` requires the signed operator, and the verifier comes from the payload (H-50). `UnsupportedAlgorithm` maps to `owner_key_invalid`, which the CLI audits. Tests: unit (missing identifier ×2, operator mismatch, verifier mismatch, unsupported curve, recovery missing operator, recovery mismatch), committed CLI (operator mismatch audited), integration (replay refused, DB refuses a duplicate digest). | (a) `UnsupportedAlgorithm` not caught: **caught**. (b) Verifier binding removed: **caught**. (c) Recovery operator binding removed: **caught**. (d) Service digest check removed: **caught**. (e) Base DB downgraded to 0045 (index removed): **caught** (`test_h74_two_ceremonies_cannot_share...`). Upgraded back to head. |
| H-75 | `grant_restricted` validates resource exists, project active, grantee active; `has_restricted_grant` binds source to project | Satisfied (service level, as the plan names). See F-3. | `projects/service.py:224-245`: `resource_not_found` 404, `project_archived` 409, `grantee_not_active` 409, all audited `grant.denied`. `rbac/sql_store.py`: a source grant counts only if `sources.project_id = :p`. The SQL read path (`fn_can_read_source_version`) derives the source from the version, so it is already bound. Tests: missing resource (project and source params), archived project, inactive grantee, source grant under another project. | (a) Source/project binding removed: **caught**. (b) Grantee check removed: **caught**. (c) Resource checks removed: **caught**. |
| H-76 | One time source | Not implemented (correct) | No `clock_timestamp()` lease change, no ceremony clock change. Needs H-21 (Phase 3). | n/a |
| H-77 | Denial audits in ingest, reparse and reassess carry resource references | Satisfied | ingest `_deny`: `project_id` plus refs `[project, superseded source?]`. reparse: `[version, project]`. reassess: `[source, project]`. Tests in `test_intake_db.py`, `test_gap_closure.py`, `test_reassessment.py`. | Refs emptied in each of the three: **caught** in all three. |

Every source mutation was restored with `git checkout -- <file>`. Every SQL mutation was undone by `alembic upgrade head` on `webdesk_p6_base`. Afterwards the md5 of each replaced function on `webdesk_p6_base` equals `webdesk_hardening` and the scratch head: `checkpoint_guard 8dc7c816…`, `fn_mark_downstream_stale e420951e…`, `fn_worker_mark_inputs_changed 1863304b…`, `fn_worker_record_audit(…uuid) 7659f730…`. The index and the NOT NULL are present.

## 5. Boundaries (§10 and the review brief)

- No Phase 3 fencing, claim-commit, renewal or lock-order change. No `clock_timestamp()` / H-21 time source. The `jobs.py` diff adds audit calls only, and `install.py` / `recovery.py` keep the injected clock.
- No other phase's implementation changed beyond what the items need. Edits to pre-existing tests are signature adaptations (`_transition` owner/project, `prepare_*` operator) and added assertions. No assertion was removed and no test was deleted. The suite went from the Phase 6 count to 733, all passing.
- No credentials in git. No accepted migration (0001–0045) edited.
- §10 exclusions (agents, LLM, deployment, login endpoints): not touched.

## 6. Findings

**F-1 (Medium). The H-60 "before authorization" ordering has no regression test.**
- File: `tests/integration/test_phase7_intake.py:187-224`. Code: `src/webdesk/intake/ingest.py:182` (validation) vs `:220` (`_authorize`).
- The code is correct. But both H-60 tests use an authorized analyst with a stale revision, so they prove "before revision" only. Plan §5 (F03) asks for "size before authorization".
- Reproduction:
  1. Move the `validate_upload` try/except block from before the idempotency lookup to just after the `_authorize(...)` call in `ingest_source`.
  2. Run `pytest tests/integration/test_phase7_intake.py tests/integration/test_intake_db.py tests/committed/test_http_intake.py`. Result: 34 passed.
  3. Add a test where the admin session (no content grant; a valid file gets 403) uploads `tool.exe` / `application/octet-stream`. It expects 415 and fails under the mutation, getting 403. At HEAD it passes, and 413 for a 20 MiB + 1 byte file also passes.
- Non-blocking: the behaviour is right today, and the gap is regression protection. Add that test before Phase 8 evidence.

**F-2 (Low, pre-existing, now reused by H-71). Control denial events carry a doubled prefix.**
- File: `src/webdesk/runs/service.py:363` and `:369`. `_control` is called with `operation="run.cancel"` / `"run.retry"`, and the event is `f"run.{operation}.denied"`, so the audit event types are `run.run.cancel.denied` and `run.run.retry.denied`. The H-71 path at `:363` inherits this.
- Reproduction: `SELECT DISTINCT event_type FROM audit_events WHERE event_type LIKE '%retry.denied'` after `test_h70_a_denied_control_names_the_run_project`. That test itself matches with `LIKE '%retry.denied'`.
- Present at `bdf6f15:src/webdesk/runs/service.py:282`, so not introduced by Phase 7. Non-blocking. Recommend a fix and an evidence note.

**F-3 (Low). The H-75 checks are service-level plain reads; the SQL guard does not re-check them.**
- File: `src/webdesk/projects/service.py:224-245`; `webdesk_guard.fn_grant_restricted_with_proof` (it only consumes the proof and inserts). `webdesk_app` has EXECUTE on it.
- A grant racing an archive, or a direct guard call with a valid `restricted.grant` proof, can still insert a grant on an archived project, a missing resource or an inactive grantee.
- Impact is limited: `fn_can_read_source_version` refuses inactive users and binds source to version, so such a grant authorizes nothing extra.
- The plan scopes H-75 to `projects/service.py` and `rbac/sql_store.py`, so the requirement is met as written. Non-blocking. Consider moving the checks into the guard in a later phase.

**F-4 (Low). The `source.parse.*` worker audits still have no `project_id`.**
- File: `src/webdesk/intake/parse_service.py:161`. The project is in `record_refs` but not passed as `project_id`.
- These are version-level parse audits emitted inside a run, not run audits. H-70 says "every run audit", so I judge this outside the letter of H-70. Recorded so the evidence report does not over-claim. Non-blocking.

**F-5 (Informational). `docs/RUFF_FORMAT_EXCEPTIONS.md` header text is stale.**
- Line 3 says "five files" (still true) and line 9 says "Two files are committed tests" (now one). The table is correct.

**F-6 (Informational, pre-existing). `webdesk_authority` owns schema `webdesk_authority` and `fn_issue_operation_proof`.**
- From 0021. Not changed by Phase 7. Listed because the brief's privilege check asks that no application role own objects. This is the established authority-role design, not a Phase 7 regression.

**F-7 (Informational). Operator-visible artifact format change.**
- Install and recovery artifacts must now carry a signed `deployment_operator_id`, and install artifacts also `independent_verifier_id`. Older artifacts are refused (`authorization_malformed`).
- This is stated in commit 4153083. No `docs/` engineering note exists for Phase 7 the way `PHASE6_X8_ENGINEERING.md` recorded the H-50 change. It should be carried into the Phase 8 evidence and the owner signing procedure.

**F-8 (Informational). Two minor H-62 coverage gaps.**
- No reparse-specific lost-race test, and no reparse refusal-under-key test. Both paths share `run_keyed`, which is covered through `run.start`.
- A keyed replay returns the stored response before authorization, by design (the same as upload).

No Blocker or High findings.

## 7. Scope position assessment

- **Implemented in this candidate: H-60, H-62, H-66, H-69, H-70, H-71, H-73, H-74, H-75, H-77.** Confirmed. Each has code matching the plan text and tests, and at least one mutation per item was caught. Two qualifications:
  - H-60's body limit and route-level H-66 refusal pre-date Phase 7 (43e0ff1). This candidate adds the service ordering and the service refusal.
  - H-60 has the test gap in F-1.
- **Already implemented before Phase 7, unchanged: H-61, H-63, H-72.** Confirmed. Code from 43e0ff1 / `limiter.py` (ancestors of `bdf6f15`), no change in range, tests pass.
- **Not implemented: H-64, H-65, H-67, H-68, H-76.** Confirmed. No changes to `parsers.py`, `validation.py`, reclassification, lock order, cancel rule or time source. The stated blockers (H-DEC-6 and the Phase 4 EML parser; no documented MIME alternatives; H-DEC-2; H-25 / H-DEC-1; H-21) match plan §3 and §9.
- Plan §3 names migration `0013` for H-69 and H-73. The candidate uses new revisions 0047 and 0048 instead, because 0013 is an accepted, frozen migration. I agree with that choice.

## 8. Final state

- `webdesk_p6_base` at `0049_p7_run_audit_project_id (head)`. `webdesk_hardening` at head.
- Databases on 5485: `postgres`, `template0`, `template1`, `webdesk_hardening`, `webdesk_p6_base`. The scratch DB and the per-test databases were dropped.
- `git status --short` in `D:/WDS/qa-p7-ae032a2`: empty. HEAD `ae032a28b1d34d68795022c61ebe1f9334038e44`. Nothing committed, pushed or merged.

## 9. Verdict

The Medium finding (F-1) is non-blocking: the code behaves correctly, and only a regression test is missing. Low and Informational findings are either pre-existing or outside the letter of the Phase 7 items.

QA PASSED — ELIGIBLE FOR WDS PHASE 7 ACCEPTANCE
