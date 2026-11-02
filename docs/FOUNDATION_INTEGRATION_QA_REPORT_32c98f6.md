# Independent QA report: Foundation Phases 2–7 integration candidate `32c98f6`

Reviewer: independent QA, acting alone. Date: 2 November 2026 (finished about 09:50 UTC). This is a technical assessment only. It is not a phase acceptance and not a production approval. No commits, pushes or merges were made.

## 1. Environment

| Item | Value |
| --- | --- |
| Checkout | `D:/WDS/qa-int-32c98f6`, a detached worktree at `32c98f6206c6e7a42785b888dabbfd176f3c7997`. Latest code commit `db7d6f1`; `32c98f6` changes only `docs/FOUNDATION_INTEGRATION_P2_P7.md` |
| Branch under review | `feature/foundation-integration-p2-p7` (points at `32c98f6`) |
| Cluster | container `webdesk-int-qa-postgres`, `127.0.0.1:5487`, PostgreSQL 16.4 (Debian 16.4-1.pgdg120+2), system identifier `7703463818934988838` |
| Bootstrap | `bootstrap_int_qa.sh`, read first (it refuses any target other than `webdesk-int-qa-postgres`/5487). Ran with exit 0: base and hardening databases migrated to `0059_int_mark_inputs_fence (head)` |
| Tooling | Python 3.12.10, pytest 8.3.3, SQLAlchemy 2.0.36, Alembic 1.13.3, psycopg 3.2.3, ruff 0.6.9, mypy 1.11.2 |
| Secrets | Not printed. Every mutation log that held a URL or password was deleted. The kept logs (`full_suite.log`, `migcheck.log`, `mutations.log`) were scanned and contain neither |
| Cluster state at the end | Databases: `postgres`, `template0/1`, `webdesk_int_base`, `webdesk_hardening`. No scratch database or per-run test login was left. Container and volume untouched |

## 2. Checks table

| # | Check | Command | Result | Exit |
| --- | --- | --- | --- | --- |
| 1a | Tip ancestry | `git merge-base --is-ancestor <tip> HEAD` for 518ab67, 6e8f574, c6c5325, 50f3e40, 178a419, ee4d3b9, d91513c, f189b41, 09d1bdb (plus Phase 5 ddbb983 and Phase 6 7943d03) | All 11 are ancestors. Branch heads: P2 518ab67, P3 50f3e40, P4 d91513c, P7 f189b41 (they match the round-3 SHAs) | 0 each |
| 1b | Migration provenance | `git rev-parse <ref>:migrations/versions/<f>` at HEAD vs `feature/foundation-phase-{2..7}` | All 61 files from 0001 to `0055_approval_worker_fence` are blob-identical to every phase branch that has them. `env.py`, `script.py.mako`, `alembic.ini`, `pyproject.toml` and `uv.lock` are identical across P2/P3/P4/P7. `git diff --stat 09d1bdb HEAD -- migrations/` shows insertions only | 0 |
| 1c | Integration diffs | `git show --remerge-diff` for the 8 merges; `git show` for the 15 "Integration:" commits | Read; see §3.1 | – |
| 2 | Test deletion and weakening | AST inventory of every `test*` function on each phase branch vs HEAD (scratch `testinv.py`) | HEAD has 893 test functions and 0 skip/xfail marks or in-body skips. No test has fewer assertions than on its branch. Two branch tests are absent at HEAD (see §3.2). 19 test bodies differ from every branch version; all are API adaptations (clock removal, H-74 operator/verifier, `FAR_FUTURE` expiry) with assertion counts unchanged | – |
| 3 | Full suite | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -rsxX` | **1026 passed**, 0 failed, 0 skipped, 0 xfailed, 1 warning (Starlette/anyio deprecation), 700.38 s | 0 |
| 4a | Lint | `ruff check src tests migrations` | All checks passed | 0 |
| 4b | Format | `ruff format --check src tests migrations` | 4 files would be reformatted: 0017, 0019, 0020, 0040. This is exactly the list in `docs/RUFF_FORMAT_EXCEPTIONS.md`; 245 files already formatted | 1 (documented exceptions only) |
| 4c | Types | `mypy --strict src/webdesk` | No issues in 71 source files | 0 |
| 5a | Heads | `alembic heads` | `0059_int_mark_inputs_fence (head)`: one head | 0 |
| 5b | Migration gate on fresh scratch databases | scratch `migcheck.py` (16 scratch databases, all dropped). Catalog = the cycle test's queries plus policies, enums, sequences, views, every function by md5, schemas, default ACLs, database ACL and column types | 26 of 29 PASS; the 3 FAILs are the informational reverse-order references (see 5c). Details in §3.4 | 1 (informational rows only) |
| 5c | Out-of-order upgrade (informational) | same script | Fence first, then 0049: a transient one-argument `fn_worker_mark_inputs_changed(uuid)` exists with PUBLIC EXECUTE. `upgrade head` removes it and the final catalog equals head | – |
| 6 | Mutations | `runmut.sh` (apply → targeted pytest → `git checkout -- <file>`) | 22 mutation and baseline runs; every product mutation was caught except where noted (§4) | per run |
| 7 | Privilege audit | `pytest tests/hardening/test_privilege_audit.py` | 17 passed | 0 |
| 7b | Catalog privilege queries | psql on `webdesk_int_base` and `webdesk_hardening` | See §3.5 | 0 |
| 8 | H-68 probe | temporary `tests/committed/test_qa_probe_tmp.py` (deleted) | Passes at head; deadlocks when the cancel lock order is inverted (§4, M13) | 0 / 1 |
| – | Final tree | `git status --short` | empty | 0 |

## 3. Per-area verdicts with evidence

### 3.1 Conflict resolutions: PASS

- **`runs/jobs.py`**: kept from Phase 3: the lease hold (`fn_worker_hold_lease`, KEY SHARE), the committed per-step intake, `LeaseLost`, correlation UUIDs, and the fenced `fn_worker_mark_inputs_changed(job, owner)` with `LeaseLost` on refusal. Kept from Phase 7: `project_id` on `job.claimed`, `run.transitioned` (every `_transition` now takes `owner` and `project_id`), the `run.parked` intake audit, `run.failed` and `job.requeued`. `job.requeued` is written once, with correlation, attempts, `delay_seconds` and project. The Phase 7 supersession filter in `finish_intake` is kept. Diff against P3: additions only, apart from the reused `delay` variable.
- **`audit/service.py`**: `record_worker_event` takes both `project_id` and `correlation_id`. The correlated path calls the 0056 nine-argument function with the project. The `params.pop("project")` from the first merge was removed in `d055337`.
- **`ceremony/*`, `cli/install.py`, `cli/recover.py`**: Phase 7 H-74 is kept: `signed_identifier` checks the operator and verifier and refuses with `operator_mismatch`/`verifier_mismatch`; `owner_key_invalid`; recovery refuses a replayed digest with `authorization_already_used` (409). Phase 6 H-50 is kept: refusals come before the ceremony insert, and the verifier is taken from the artifact. Phase 3 is kept: no `Clock` remains in `src`; `require_unexpired` and recovery decide expiry with `database_now()` (`clock_timestamp()`); `_coverage` uses `clock_timestamp()`. The diff of ceremony/cli against P7 is clock removal and nothing else.
- **`api/routes.py`**: Phase 4 streaming `_bounded_form(request, limit)` (counts at `receive`, refuses on the declared length or the running total) is kept. `MAX_UPLOAD_REQUEST_BYTES = 20 MiB + 1 MiB` (the same value as Phase 4 `MAX_BYTES + 1 MiB`). The H-61 allowlist `ACCEPTED_UPLOAD_FIELDS` replaces Phase 4's deny-list `SERVER_OWNED_FIELDS`; the allowlist is the stricter of the two. The H-66 `approved_reference` refusal is kept, and so is `upload.read(MAX_BYTES + 1)`.
- `projects/service.py` keeps both imports. `tests/support/db_cleanup.py` takes Phase 6's client-backend-only filter. `reap_expired` reads the run's project for both reaper audits.

### 3.2 Tests deleted, weakened, skipped or xfailed: PASS, with one documentation inaccuracy

- No skip, xfail or in-body skip exists at HEAD. No test lost assertions.
- `tests/committed/test_migration_cycle.py::test_the_0050_downgrade_to_0043_and_reupgrade_reproduce_the_head_catalog` (Phase 3) was replaced in `db7d6f1` by `test_supported_rollback_to_the_integration_merge_revisions_reproduces_each_catalog`. **Justified by ruling 4.** Its negative control and head re-upgrade are kept, and it compares 4 states instead of 1.
- `tests/unit/test_install_authorization.py::test_expired_authorization_is_refused` (base, P2/P4–P7) is absent. Phase 3 itself replaced it with `test_preparation_reads_the_signed_expiry_but_does_not_decide_it` (D-3); the integration kept Phase 3's version. The database-clock refusal is tested in `tests/committed/test_authorization_expiry.py`, and mutation M12 shows that it bites. **Justified by the Phase 3 design (D-3), not by a ruling.**
- The integration record says "No test was removed from either side" (Merge commits section). As literal text this is inaccurate for the two replacements above (finding F-8).

### 3.3 Full suite and static checks: PASS

The suite gave 1026 passed, 0 skipped, exit 0, matching the engineer's count. ruff check is clean. The format exceptions equal the documented four frozen migrations. mypy strict is clean.

### 3.4 Migrations: PASS within the supported range (ruling 4)

- On a fresh database Alembic applies 65 steps. The Phase 5–7 line (0049) and 0057 both come before `0055_approval_worker_fence`, as the record claims. A second fresh head is catalog-identical to the first.
- Downgrades from head to `-1`, `0058`, `0057`, `0056` and `0055_int` give version rows `{0058}`, `{0058}`, `{0057, 0055_approval_worker_fence}`, `{0056, 0055_approval_worker_fence}` and `{0055_int, 0055_approval_worker_fence}`. Each downgraded catalog equals a fresh database migrated to the same revisions in Alembic order. Each re-upgrade equals head. No state has a `webdesk_guard` function with PUBLIC EXECUTE.
- A reference migrated to the same revisions in the reverse order (fence first) differs by one extra unfenced one-argument mark function. This is the out-of-order transient the record already documents (F-5).
- Cluster role memberships were the same before and after the supported cycles; `webdesk_test_clock` was not touched.
- Head has 88 `webdesk_guard` functions, none with PUBLIC EXECUTE. Only `fn_worker_mark_inputs_changed(uuid,text)` exists.
- Migration review:
  - 0055_int and 0058 are SQL-free merge points.
  - 0056 drops the 8-argument correlated function and creates the 9-argument one with `p_project_id uuid DEFAULT NULL`. Its checks (NULL correlation, system-only, no account actor) are verbatim from 0052. Grants: REVOKE PUBLIC, EXECUTE to `webdesk_worker` only. The downgrade restores the 0052 text and grants.
  - 0057 is CREATE OR REPLACE, with `now()` changed to `clock_timestamp()` and nothing else; the downgrade restores the 0045 text.
  - 0059: `DROP FUNCTION IF EXISTS (uuid)`, then the Phase 3 lease/owner/`leased`/unexpired fence with job KEY SHARE first, then the first-mark UPDATE (`is_stale = false`), then the `run.stale_marked` audit with the project, returning true. Grants: REVOKE PUBLIC, EXECUTE to `webdesk_worker`. The downgrade restores the verbatim `0055_approval_worker_fence` text and grants.
- Three lines redefine database objects (P2 0044–0046, P3 0050–0055, P5–7 0042_x7–0049). The only object two of them both redefine is `fn_worker_mark_inputs_changed`; `fn_reject_change_with_proof` is shared only through the common ancestor 0042_phase2. The two-line function is reconciled by 0059.

### 3.5 Privileges: PASS (one Low pre-existing deviation)

- No `webdesk_*` application role or login is a superuser, and none has CREATEROLE or CREATEDB. Only the cluster superuser `webdesk_owner` and the test-only `webdesk_integration_owner`/`webdesk_test_owner` have those attributes.
- Object owners:
  - Relations are owned by the migrator (`webdesk_integration_owner`), or by `webdesk_test_owner` in `webdesk_hardening`.
  - `webdesk_guard_owner` (NOLOGIN definer) owns the `webdesk_guard` schema and its 88 functions.
  - **Pre-existing exception:** `webdesk_authority` owns the `webdesk_authority` schema and `fn_issue_operation_proof` (since 0021).
- SECURITY DEFINER functions:
  - There are 89 SECURITY DEFINER functions in total. 88 are owned by `webdesk_guard_owner`; the other is the authority exception above.
  - 89 of 89 have a pinned `search_path`, and none has PUBLIC EXECUTE.
  - Three functions carry `search_path=public` instead of `pg_catalog, public` (finding F-2, pre-existing in Phase 3 0053).
  - Database ACL: PUBLIC has CONNECT only, with no TEMP.
- Guards and proofs:
  - Integration SQL touches only three functions: the 0056 correlated audit, the 0057 expiry and the 0059 mark. Each keeps or strengthens its checks.
  - No `fn_consume_operation_proof` call was removed from any path.
  - Only one application-code change touches a guard path: the contacts `ProofRefused` mapping (`baa0b49`). It runs after the guard refused.
- The privilege audit gave 17 passed. Mutation M9 (an extra grant to `webdesk_app`) is caught by the privilege audit and by the integration test.

### 3.6 Reconciliation correctness and rulings: PASS, with one Medium on ruling 2

- **0056**: correlated worker audits carry `project_id` (M4 and M17: 5 tests fail each).
- **0057**: on-demand change expiry uses `clock_timestamp()` (M5 fails the test).
- **0059**:
  - The Phase 3 fence (owner: M6; expiry: M6b) and the Phase 7 audit with project (M7a, M7b) are present, and so is the Phase 5 first mark (M8). Each mutation is caught by at least one test.
  - Grants match the replaced function. Only the `(uuid,text)` signature exists, and the one-argument version is gone (catalog and migcheck).
- **Ruling 1 ("Ignore comments in test")**: implemented exactly.
  - `strip_sql_comments` is applied only to the definition column of `functions` in the Phase 2 catalog test.
  - The bite holds: a code change in a restored body fails (M1), a comment-only addition (`--` and `/* */`) passes (M2), and a whitespace-only change still fails (M2b).
  - No migration was edited (commit `478606a` touches only the test; blob checks pass).
- **Ruling 2 ("Treat as attachment", H-64)**: implemented for text and other leaf parts (M10 and M10b each fail 4 of 6 tests). Exception: a *multipart* part that carries `name=` is neither the body nor reported, and its text is silently dropped (finding F-1, Medium).
- **Ruling 3 ("Keep approval_refused")**: holds.
  - A losing `approve_create` remains an audited 409 `approval_refused`. Removing the mapping fails both the integration test and the Phase 3 `test_competing_concurrent_approvals_produce_exactly_one_approval` (M11).
  - `fc53073` adds tests only. Nothing goes further than the ruling.
- **Ruling 4 ("Rollback stops at merge")**: holds.
  - The cycle test steps only through 0058 → 0057 → 0056 → 0055_int, comparing each state with a fresh database, then re-upgrades to head and checks that `webdesk_test_clock` is unchanged.
  - Bite: changing the 0057 downgrade text fails the test at 0056 (M3).
  - My own migcheck confirms the same range independently.

### 3.7 Cross-phase behaviour: PASS (with honest gaps)

- **H-68**:
  - Lock order: claim (job UPDATE, then run), cancel (`fn_cancel_run_with_proof`: jobs FOR UPDATE, then run), the worker step (hold KEY SHARE, then `_lock_run`) and 0059 (job KEY SHARE, then run) all lock job then run.
  - QA probe P1: a worker holds the job lock, cancel waits, the worker locks the run, marks it and commits, then cancel completes. No deadlock.
  - With the cancel order inverted (M13), the probe deadlocks (`DeadlockDetected`), while the existing `test_a_cancellation_waits_for_a_claim_without_a_deadlock` still passes (finding F-3).
- **H-76**:
  - Leases, claim, hold, the 0059 fence, the ceremony expiry (`database_now`) and the 0053/0054/0055/0057 approval predicates use `clock_timestamp()`. The only `datetime.now` left in `src` is a log timestamp (`worker/loop.py:135`).
  - M12 and M12b show that the database-clock expiry decision is tested.
  - Remaining `now()` uses: the outbox lease functions (`fn_outbox_claim`, `fn_outbox_renew`, `fn_outbox_retry`, `fn_outbox_mark_sent`), which are the **known gap**, still open. Session, proof, token and read-grant expiry are out of the PH3-FC-01 scope. One Python status classifier is covered by finding F-4.
- **H-64**: as ruled for leaf parts. HTML-only bodies are flagged per H-DEC-6, and a named HTML part is not flagged as an HTML-only body. Gap: F-1.
- Also confirmed by mutation:
  - H-61 allowlist (M14), F-2 streaming bound (M15) and H-66.
  - The H-66 route check is defence in depth. Removing it alone is not detected because the service refuses as well (M16); removing the service check is detected (M16b).

## 4. Mutations run (all restored with `git checkout -- <file>`; tree clean after each)

| ID | File (temporary change) | Tests run | Result |
| --- | --- | --- | --- |
| M0 | none (baseline) | `test_migration_catalog.py` | 1 passed |
| M1 | `0042_x7` downgrade body line 324: adds `'failed'` to the parse list | catalog test | **1 failed** (functions differ) |
| M2 | `0042_x7` downgrade body line 300: adds a `--` line and a `/* */` comment | catalog test | 1 passed (comments ignored, as ruled) |
| M2b | `0042_x7` line 324: one extra leading space | catalog test | **1 failed** |
| M3 base / M3 | `0057` downgrade `now()` → `clock_timestamp()` | `test_migration_cycle.py` | 1 passed / **1 failed** at `0056_int_corr_audit_project` |
| M4 base / M4 | `0056` line 60 `VALUES (p_project_id,` → `VALUES (NULL,` | `test_integration_p2_p7.py` | 13 passed / **5 failed** |
| M5 | `0057` line 40 `clock_timestamp()` → `now()` | `-k expiry` | **1 failed** |
| M6 base / M6 | `0059` line 50: owner predicate removed | P2–P7, durable, runs_db, x7, privilege audit (112) | 112 passed / **1 failed** |
| M6b | `0059` line 51: lease-expiry predicate → `true` | 28 selected | **1 failed** (`test_the_claim_holder_marks_its_run_and_a_stale_holder_cannot`) |
| M7a | `0059` line 65: project → NULL | 28 selected | **1 failed** (Phase 7 `test_h70_..._marks_with_its_project`) |
| M7b | `0059` line 65: event type renamed | 28 selected | **1 failed** |
| M8 | `0059` line 59: `AND is_stale = false` removed | 28 selected | **1 failed** (Phase 5 `test_h40_the_superseded_reason_survives_worker_intake`) |
| M9 | `0059` line 100: EXECUTE also to `webdesk_app` | 28 selected | **2 failed** (integration test and privilege audit) |
| M10 base / M10 | `parsers.py` `_eml_named` → `return False` | EML unit tests (14) | 14 passed / **4 failed** |
| M10b | `parsers.py`: named leaves not added to attachments | `test_eml_named_parts.py` | **4 failed** |
| M11 | `contacts.py`: `ProofRefused` always re-raised | P2–P7 `-k "loses or approval"` and Phase 3 race test | **2 failed** |
| M12 | `ceremony/install.py`: `require_unexpired` disabled | `test_authorization_expiry.py` | **2 failed** |
| M12b | `ceremony/recovery.py`: database expiry check disabled | same | **1 failed** |
| M13 | `0050` line 122: cancel locks the run before the jobs | QA probe and H-68 test | probe **failed with DeadlockDetected**; the existing H-68 test **passed** (F-3) |
| M14 base / M14 | `routes.py`: allowlist → deny-list `{"storage_key"}` | upload tests (20) | 20 passed / **1 failed** (H-61) |
| M15 | `routes.py`: streaming bound `received > limit` disabled | upload tests | **1 failed** (F-2) |
| M16 | `routes.py`: H-66 route check disabled | upload tests | 20 passed (the service also refuses) |
| M16b | `intake/ingest.py:167`: H-66 service check disabled | `-k h66` | **1 failed** |
| M17 | `audit/service.py`: correlated call without the project | P2–P7 `-k project` | **5 failed** |
| P1 | QA probe (temporary file, deleted) at head | probe | 1 passed |

## 5. Findings

No Blocker. No High.

**F-1 (Medium): a multipart part with `name=` is not reported as an attachment, and its text is dropped silently.**
- Where: `src/webdesk/intake/parsers.py:780` (`_eml_body` skips a named part of any type, including multipart) together with `parsers.py:800-810` (`_eml_named_leaves` recurses into a named, non-attachment multipart and reports only named *leaves*).
- Effect: for `multipart/mixed` → `multipart/alternative; name="alt.bin"` → `text/plain`, the integrated parser returns status `succeeded` with only the subject segment, no flagged region and no attachment. The Phase 4 parser at `d91513c` extracted the inner text as the body.
- Why it matters: this does not meet ruling 2's "reported as an attachment" for that part, and it leaves a silent extraction gap, contrary to the H-34 intent.
- Scope: an unusual input; leaf parts behave as ruled.
- Reproduce: run `.venv/Scripts/python.exe` on `parse_eml` with the message above; the scratch probe is `h64_probe.py`, case `named-multipart`. Compare with `git show d91513c:src/webdesk/intake/parsers.py`.
- WDS needs to rule whether a named multipart is reported as one attachment or its children are parsed.

**F-2 (Low, pre-existing in Phase 3, not introduced by the integration): three SECURITY DEFINER functions are pinned to `search_path=public` rather than `pg_catalog, public`.**
- Where: `migrations/versions/0053_contact_approval_clock.py:34`.
- Functions: `fn_advance_contact_revision`, `fn_issue_token` and `fn_revoke_expired_activation_tokens`. 0053's own downgrade restores `'pg_catalog', 'public'`, so 0053 regressed them. The file is frozen and byte-identical to Phase 3.
- Practical risk is low: pg_catalog is still searched implicitly first, and PUBLIC has no TEMP on the database. No test asserts the standard `search_path` for all definers.
- Reproduce: `select oid::regprocedure, proconfig from pg_proc where prosecdef and not proconfig @> array['search_path=pg_catalog, public']`.

**F-3 (Low, test strength): the H-68 test does not detect a lock-order inversion.**
- Where: `tests/committed/test_durable_execution.py:227` (`test_a_cancellation_waits_for_a_claim_without_a_deadlock`).
- The holder already owns both the job and the run when cancel starts, so a run-before-jobs cancel still only waits. With the 0050 cancel order inverted (M13) that test passes, while an interleaved probe deadlocks.
- The product lock order is correct today.
- Reproduce: apply M13 and run the test.

**F-4 (Low, pre-existing Phase 2 code, also on Phase 3): an appointment-refusal classifier uses `now()`.**
- Where: `src/webdesk/rbac/assign.py:61` (`expires_at <= now() AS lapsed`).
- The database (`webdesk_role_guard`, 0055) decides with `clock_timestamp()`. If an appointment lapses mid-transaction, the API reason can be 409 `refused` instead of 409 `appointment_consumed_or_expired`.
- Only the reason string is affected; the authorization decision is not.

**F-5 (Informational): an out-of-order upgrade briefly exposes an unfenced, PUBLIC-executable mark function.**
- Where: `migrations/versions/0049_p7_run_audit_project_id.py:97`, removed by `0059_int_mark_inputs_fence.py:97`.
- Upgrading `0055_approval_worker_fence` first, then 0049, creates `fn_worker_mark_inputs_changed(uuid)` with PUBLIC EXECUTE until 0059 drops it.
- `upgrade head` reaches the head catalog either way. The record documents this.

**F-6 (Informational, test hygiene): the Phase 2 catalog test changes a cluster-wide role.**
- Where: `tests/committed/test_migration_catalog.py:230`.
- The test still downgrades to 0041, below the ruling-4 range. The 0046 downgrade drops and recreates `webdesk_test_clock`.
- After the suite, the bootstrap's INHERIT/SET membership for `webdesk_integration_owner` was replaced by an ADMIN-only membership (observed: `admin=t, inherit=f, set=f`). The suite passes either way, as the record states.

**F-7 (Informational, H-76 gap): outbox leases still use `now()`.**
- Functions: `fn_outbox_claim`, `fn_outbox_renew`, `fn_outbox_retry` and `fn_outbox_mark_sent`.
- Session, proof, token and read-grant expiry also use `now()`; they are outside PH3-FC-01 as Phase 3 scoped it.
- Open, as the record says.

**F-8 (Informational, record accuracy): "No test was removed from either side" is not literally true.**
- Where: `docs/FOUNDATION_INTEGRATION_P2_P7.md`, "Merge commits and conflict resolutions".
- Phase 3's cycle test was replaced (justified by ruling 4; the record notes the rename in the `db7d6f1` row).
- The base `test_expired_authorization_is_refused` exists only in Phase 3's D-3 form.

**F-9 (Informational): H-66 is enforced twice, and the HTTP test cannot tell which layer refused.**
- The route check (`routes.py:167`) and the service check (`ingest.py:167`) both refuse. The HTTP test therefore passes when only the route check is removed (M16).

## 6. Verdict

The candidate preserves both sides' safeguards in every conflict area. Migrations 0001–0055 are byte-identical to their phase branches. Within the supported range the history is catalog-exact. 0056, 0057 and 0059 are correct, and their bite is shown by mutation. Rulings 1, 3 and 4 are implemented exactly. Ruling 2 is implemented for leaf parts, with one Medium edge case (F-1) for WDS to rule on. Neither F-1 nor any other finding is Blocker or High.

QA PASSED — INTEGRATION CANDIDATE TECHNICALLY VERIFIED

Final state: `git status --short` in `D:/WDS/qa-int-32c98f6` is empty. No commits, pushes or merges. No other worktree, branch, port or container was touched.
