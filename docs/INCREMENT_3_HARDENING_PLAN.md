# Increment 3 Hardening Plan (for approval; no code written)

**Status:** Proposed. Awaiting approval. No code, migration, test or specification change has been made.

**Baseline:** branch `feature/increment-1-foundation`, commit `acd5c51`.

**Inputs read:**
- The independent review *"WebDesk Foundation Increments 1–2 — Implementation Review"* (verdict: NOT READY), findings X1–X8, the EVAL-F classification table, the ten verification questions, and the non-blocking list.
- The approved v0.3.10 baseline: GOVERNANCE §8 and §11, REQUIREMENT_SCHEMA §3.1, §4, ARCHITECTURE §7 and §13, EVALUATION_PLAN Gate 1 suite, and DECISION_REGISTER.
- `docs/INCREMENT_1_EVIDENCE.md` and `docs/INCREMENT_2_EVIDENCE.md`.
- The repository at `acd5c51`. Each reviewer claim below was checked against the code.

**Spot checks at `acd5c51` (confirmed by inspection):**
- `migrations/versions/0001_gate1_foundation_schema.py:557` grants `webdesk_app` table-level `INSERT, UPDATE` on `users`, `projects`, `user_contact_approvals`, `contact_reservations` and `role_assignments`.
- `0001:528` `role_assignments_guard` is `BEFORE INSERT` only. `0001:337` and `0001:503` trust the session variable `webdesk.consume_appointment`.
- `src/webdesk/runs/jobs.py:53` excludes `attempts >= 3` from `claim`. `renew` at `:79` sets `now() + 120 s`.
- `src/webdesk/intake/parse_service.py:118` catches `Exception` only around the parser call. The segment write at `:152` catches only `SQLAlchemyError`.
- `src/webdesk/intake/reparse.py:98` is the only caller of `mark_downstream_stale`. Supersession does not propagate staleness.
- No caller exists in `src/` for `apply_recovery`, `sweep_expired` or `OutboxWorker`.

**Reviewer's EVAL-F baseline (used as the starting point):** 1 PASS, 12 PARTIAL, 10 FAIL. F-CFG-01 passes. EVAL-DEPLOYMENT-GATE-001 applies to production only (see H-DEC-7).

---

## 1. Summary

Increment 3 is hardening only. It adds no features and changes no approved business rule. It closes the eight findings X1–X8, corrects the evidence record, and makes the existing services safe under real attack and real failure.

Order of work:
1. X1, database authorization and separation of duties. This comes first, and every step is proven with negative tests run as `webdesk_app`.
2. Identity correctness (X2, X3, X8 status codes).
3. Durable execution (X4).
4. Parse robustness (X5, X6).
5. Staleness and archive integrity (X7).
6. Recovery CLI and entry points (X8).
7. Evidence re-run and independent re-review.

Existing migrations `0001`–`0009` are **not rewritten**. Every fix is a new migration, `0010` onwards.

---

## 2. Findings-to-work map

| ID | Finding | Affected source | Migrations | Corrective tasks | EVAL-F tests (must pass) |
|---|---|---|---|---|---|
| **X1** | DB protections cover INSERT only. `webdesk_app` can UPDATE protected state. Session-variable trust (`set_config`) gates appointment consumption and classification. | `migrations/0001` (grants 557; guards 384–528; set_config 337, 503), `0002:22–23`, `0009` (set_config guard), `intake/reassess.py`, `ceremony/recovery.py`, `rbac/assign.py`, `identity/contacts.py`, `intake/ingest.py`, `runs/service.py` | New `0010`–`0013` (see §3) | H-01 to H-09 | F01, F02, F03, F04, F08, F11, F11b, F11c, F11d, F11f, F11h, F11i, F12, F13 |
| **X2** | Activation and reset denial audits are lost: the audit is written inside the savepoint that is then rolled back. | `auth/service.py` (`activate`, `reset_password`), `tokens/service.py` (`consume`) | — | H-10 | F11c, F12 |
| **X3** | Late activation: `tokens.issue` and `consume` do not check that the governing approval is unexpired. Expiry relies on the sweep, which nothing calls. | `tokens/service.py`, `auth/service.py`, `identity/sweep.py`, DB trigger on `users` status | `0011` | H-11, H-22 | F11c, F11d, F11f |
| **X4** | Durable jobs: expired leases at 3 attempts are never reaped (wedge). Renewal is a no-op. Attempts roll back with the transaction. No worker process exists. | `runs/jobs.py` (`claim` 42–57, `renew` 79–88, `process_one` 252), `runs/service.py` (lock order), new `src/webdesk/worker/` | `0012` | H-20 to H-27 | F06, F07, F09, F11g |
| **X5** | One bad file fails the run and poisons later runs. A `UnicodeEncodeError` in the segment write escapes. Decompression and segment counts are unbounded. | `intake/parse_service.py` (118, 143, 152), `intake/parsers.py`, `intake/validation.py`, `runs/jobs.py` | — | H-30, H-31, H-32 | F13, F14, F14b, F03 |
| **X6** | Locators incomplete: EML has no Message-ID or offsets; TXT has no offsets and splits on U+2028/U+0085; DOCX tables dropped; partial reason not persisted; PDF image-only page reports `succeeded`. | `intake/parsers.py`, `intake/parse_service.py`, `migrations/0007` (locator CHECK) | `0013` (locator and reason columns) | H-33, H-34, H-35 | F04, F14b, F03 |
| **X7** | Supersession does not mark dependent runs stale. The in-flight check counts superseded pending versions (false stale). Archive races run start. | `intake/ingest.py` (supersede), `runs/jobs.py` (138–151), `projects/service.py` (`archive_project`), `runs/service.py` (`start_run`) | — | H-40 to H-42 | F09, F10, F13 |
| **X8** | No recovery CLI. Sweep and outbox worker have no entry point. Recovery inserts a ceremony row before refusals, leaving an orphan `initiated` row. Wrong status codes (F11f 403, F11h 403/409). Hard-coded verifier ID. | `ceremony/recovery.py`, `rbac/assign.py`, `cli/`, `identity/sweep.py`, `outbox/worker.py` | — | H-50 to H-52 | F11f, F11h, F11i, F11g, F12 |

**Non-blocking items:** folded into §4 under H-60 onwards. Each is assigned a task and a test. Nothing is deferred silently.

---

## 3. Ordered implementation tasks

Each task closes only when its negative tests pass as `webdesk_app` on committed rows (§6).

### Phase 0: Environment for hardening (prerequisite)

- **H-00 Negative-test environment.**
  - Create a **non-superuser** owner role for the test database, and a separate `webdesk_app_login` login role that is a member of `webdesk_app`.
  - Test database bootstrap runs migrations as the owner. Protected-action tests connect **only** as `webdesk_app_login`, never through `SET ROLE` from a superuser session.
  - Files: `tests/conftest.py` (new), `tests/db/bootstrap.sql` (new, test-only, no secrets committed), `docker-compose.yml` (test profile).
  - Tag `inc2-acd5c51` at the baseline, for rollback (§7).
  - EVAL: all, as infrastructure.

### Phase 1: X1, database authorization and separation of duties (priority)

- **H-01 Inventory and revoke table-level UPDATE.** List every `UPDATE` privilege held by `webdesk_app` and `webdesk_ceremony`. Revoke table-level UPDATE. Grant column-level UPDATE only where a documented flow needs it. Migration `0010`.
- **H-02 State-machine triggers (UPDATE side).** Migration `0010`:
  - `users.status`: only the transitions in REQUIREMENT_SCHEMA §3.1 (`pending_contact_approval → pending_activation` with approval; `pending_activation → active` with a live token consumed; `active → disabled`; `pending_contact_approval → disabled` by withdrawal only). Any other transition is refused.
  - `role_assignments`: only `revoked_at` may change, and only once. Every other column is immutable.
  - `user_contact_approvals`: after `status` leaves `pending`, nothing changes (`expires_at`, `approved_by_user_id`, `proof_ref`, `requested_email_normalized` all immutable).
  - `project_access_grants` and `restricted_content_grants`: only `revoked_at` may change, once. `user_id`, `resource_id`, `granted_by` are immutable.
  - `contact_revision` and `session_epoch`: changed only by the owning functions in H-03.
- **H-03 Replace session-variable trust with SECURITY DEFINER functions.**
  - Create a `NOLOGIN` owner role, `webdesk_guard_owner`. The application roles get `EXECUTE` on a fixed set of functions and no table privilege for the protected columns.
  - Functions: `fn_consume_appointment(approval, assignment)`, `fn_reassess_classification(source, new_class, justification, expected_revision)`, `fn_advance_contact_revision(user, approval)`, `fn_create_project(name, classification, actor)` (creates the project and the system-principal membership together), `fn_withdraw_user(user, reason, expected_revision)`.
  - Each trigger checks `current_user = 'webdesk_guard_owner'`, not a session variable. The `webdesk.consume_appointment` and `webdesk.reassess` settings are removed.
  - Migration `0011`.
- **H-04 Appointment single use.** Unique index on `role_assignments(appointment_approval_id)` where not null. Consumption only through `fn_consume_appointment`. Migration `0011`.
- **H-05 Prior-activation marker.** `users.activated_at` set once, when a token-backed activation completes, and immutable after. Withdrawal (`user.withdraw`) refused when it is set. This implements the marker REQUIREMENT_SCHEMA §3.1 requires. Migration `0011`.
- **H-06 Source and snapshot tables.**
  - `source_versions.scan_status`: `quarantined → clean` is refused by the database (no scanner is approved, so no path exists). Transitions are checked in a trigger.
  - `run_input_snapshots` and `source_segments` insert guard: the version must belong to the same project and must not be quarantined.
  - `sources.access_classification`: changed only by `fn_reassess_classification`.
  - Migration `0012`.
- **H-07 `system:project_create` context.** The principal is accepted only from `fn_create_project`, which also requires the actor to equal the project creator. Direct inserts with that principal are refused. Migration `0011`.
- **H-08 Ceremony row immutability.** `setup_trust_ceremonies.kind` and the install marker are immutable. Completion fields change only by the ceremony owner function. Migration `0011`.
- **H-09 Negative test suite as `webdesk_app_login`.** One test per bypass in X1 (listed in §5). Each test asserts the refusal's SQLSTATE and that no row changed. Files: `tests/integration/test_app_role_negative.py` (new).

### Phase 2: Identity correctness (X2, X3, X8 status codes)

- **H-10 Denial audits outside the savepoint (X2).** In `auth.activate`, `auth.reset_password` and `tokens.consume`, the savepoint covers only the mutations. The denial is recorded in the outer transaction, then the refusal is raised. Test through `run_in_transaction` on committed rows, so the audit row survives. Files: `auth/service.py`, `tokens/service.py`.
- **H-11 Approval-deadline check (X3).** `tokens.issue` and `tokens.consume` refuse when the governing approval is not approved or has expired. The database also refuses `pending_activation → active` unless a live approved, unexpired approval exists for the current contact. Migration `0011`. Test with an injected clock on a committed row, without back-dating through the owner.
- **H-12 Status codes (X8).**
  - F11f: an Administrator grant without an appointment below two returns **403**. Expired, consumed or deadline conflicts return **409**.
  - F11h: no approval or a different user returns **403**. Expired or consumed approval returns **409**.
  - Files: `rbac/assign.py`, `ceremony/recovery.py`. Tests updated, and each change logged in the evidence report with its reason.
- **H-13 Contact-change reject path.** `identity/contacts.reject_change`, Administrator-only, audited, releases the target reservation and leaves the current contact unchanged.
- **H-14 Revocation and disable services.** `revoke_role`, `revoke_project_grant`, `revoke_restricted_grant`, `disable_user`. Each is Administrator-only, audited, and refuses self-action where GOV §11 requires separation. These are the revocation paths GOV §11 and REQUIREMENT_SCHEMA §3.1 require ("every issue, revoke and expiry is logged").

### Phase 3: Durable execution (X4)

- **H-20 Commit the claim.** `claim` commits in its own transaction before any execution, so `attempts` is durable. Files: `runs/jobs.py`.
- **H-21 Clock source.** Lease times use `clock_timestamp()` in the database. The ceremony deadlines use the same source, not the injected clock. This removes the mix of clocks the review found. Files: `runs/jobs.py`, `ceremony/install.py`, `ceremony/recovery.py`, `identity/sweep.py`.
- **H-22 Renewal heartbeat.** The worker renews the lease on a time basis, every 30 seconds of database time, between committed steps. Renewal is never a no-op. Each step commits, so a crash loses at most one step. Files: `runs/jobs.py`, `worker/`.
- **H-23 Per-step transactions.** `process_one` commits after claim, after each version parse and after each state transition. A failure in one step records a failure in a fresh transaction.
- **H-24 Reaper.** An expired lease with `attempts >= 3` moves to `failed`, the run to `failed` with `failure_class = system_failure`, and the slot is released. Audited. Migration `0012` if a reaper index is needed.
- **H-25 Lock order.** `claim` and `cancel_run` both lock job then run. A test with two connections confirms no deadlock.
- **H-26 Worker entry point.** `python -m webdesk.worker` runs the job loop, the outbox worker and the expiry sweep. It handles SIGTERM by finishing the current step. Files: `src/webdesk/worker/__main__.py` (new), `worker/loop.py` (new). A process manager is required in production (checklist).
- **H-27 Crash and exhaustion tests (committed rows, real time).** A worker subprocess is killed during a step. Lease expiry is set through a configurable short lease for tests only (2 seconds). Tests cover: recovery after a crash, attempt counting across crashes, reaper after the third crash, slot release, and archive and start succeeding afterwards.

### Phase 4: Parse robustness (X5, X6)

- **H-30 Catch every per-version failure (X5).** `parse_version` catches `Exception` around the whole parse and the segment write. The version becomes `failed` with an error class. Other versions are unaffected. The run continues. Files: `intake/parse_service.py`.
- **H-31 Resource limits.** Enforced before and during parsing:
  - ZIP inflate ratio and total uncompressed size (DOCX, and any archive-shaped PDF input);
  - PDF page count and per-page stream size;
  - DOCX paragraph and table-cell count;
  - maximum segments per version;
  - maximum characters per segment.
  The numeric values are a proposal (H-DEC-3). Each limit produces a `failed` version with a stable error class.
- **H-32 Parse isolation and timeout.** Parsers run in a child process with a wall-clock timeout, shorter than the lease, and a memory cap. On Windows the memory cap uses a job object, which needs a decision (H-DEC-4). A timeout or child crash marks the version `failed`.
- **H-33 Complete locators.**
  - EML: Message-ID in provenance metadata (not content), and character offsets for subject and body.
  - TXT: character offsets, and line splitting on `\n` only.
  - DOCX: table cells as segments. The locator needs fields beyond SCHEMA §4.2 (`table_index`, `row`, `cell`), which is a decision (H-DEC-5).
  - PDF: an image-only page inside a text document is an unextractable region, so the result is `partial`.
  - HTML-only email body: handled per H-DEC-6.
  Migration `0013` widens the locator CHECK to the agreed fields.
- **H-34 Partial reason persisted (X6).** `parse_error` holds `{"class": "partial", "flagged_regions": [...]}` for `partial` results. Files: `intake/parse_service.py`.
- **H-35 Atomicity tests for each partial and failed path.** Each F14b pass condition gets a committed-row test with the real file, not a patched parser.

### Phase 5: Staleness and archive integrity (X7)

- **H-40 Supersession propagates staleness.** Ingest of a superseding version calls `mark_downstream_stale` on the superseded version, with reason `superseded`. Files: `intake/ingest.py`.
- **H-41 In-flight check excludes superseded versions.** The end-of-run check counts only versions that are the latest and not superseded. Files: `runs/jobs.py`.
- **H-42 Archive and start are serialised.** `archive_project` locks the project row first, then checks for active runs. `start_run` locks the project row and bumps `projects.revision` in the same transaction, so an archive with an expected revision detects a concurrent start. A two-connection test covers the race. Files: `projects/service.py`, `runs/service.py`.

### Phase 6: Recovery CLI and entry points (X8)

- **H-50 Recovery CLI.** `python -m webdesk.cli.recover`, following the installation CLI pattern. Every refusal is validated **before** any insert, so no `initiated` ceremony row is left behind. Refusals are audited through the commit-on-domain-error runner. The verifier ID comes from the signed artifact, not a constant. Files: `cli/recover.py` (new), `ceremony/recovery.py`.
- **H-51 Sweep and outbox entry points.** Both run from the worker (H-26). The sweep's `SET LOCAL ROLE` is scoped so it does not leak into the caller's transaction (non-blocking item).
- **H-52 Outbox errors (non-blocking, in scope here).** Catch every transport exception, not only `TransportUnavailable`. Each failure is audited. Renewal is invoked by the heartbeat. Dead-lettering and the in-app alert are real, not only an audit row, which needs an operational-alert record (decision H-DEC-8). Files: `outbox/worker.py`.

### Phase 7: Non-blocking improvements (folded in)

- **H-60 Upload size before parse.** Enforce a request body limit before `request.form()`. Run size and type checks before authorization, locks and revision checks, so an oversized file returns 413 regardless of revision. Files: `api/routes.py`.
- **H-61 Multipart allowlist.** Replace the server-owned deny-list with an allowlist of accepted form fields. Files: `api/routes.py`.
- **H-62 Idempotency keys.** Add to `run.start` and `reparse`. Files: `api/routes.py`, `runs/service.py`, `intake/reparse.py`.
- **H-63 Orphan files.** Write bytes only after the database admission succeeds, or remove the file on refusal. Files: `intake/ingest.py`.
- **H-64 EML HTML bodies and `name=` parts.** Per H-DEC-6. Files: `intake/parsers.py`.
- **H-65 `.md` MIME.** Accept the documented alternatives for Markdown, with the canonical type stored. Files: `intake/validation.py`.
- **H-66 `source_trust` server-derived.** The uploader cannot set `approved_reference`. Files: `api/routes.py`, `intake/ingest.py`.
- **H-67 Late reclassification to restricted.** Blocked by the current rule (no reclassification after parsing). Needs a policy ruling before any change (H-DEC-2).
- **H-68 Lock order and cancel rules.** Lock order per H-25. The parked-run cancellation question is a governance decision (H-DEC-1). It is not changed here.
- **H-69 Checkpoint guard.** Validate value types (UUID arrays, boolean flags), not only keys. Migration `0013`.
- **H-70 Run audit rows.** Fill `project_id` on every run audit. Audit claim, requeue, transitions and stale-marking. Files: `runs/*`.
- **H-71 Error mapping.** `start_run` distinguishes the active-run unique violation from other `IntegrityError`s, so a race with `retry_run` cannot produce an unaudited 500.
- **H-72 Atomic rate limits.** Check and record in one step, under an advisory lock per key. Files: `ratelimit/limiter.py`.
- **H-73 Withdrawal audit.** `user_withdrawals.audit_event_id` non-null, and the free-text reason redacted in the audit details. Migration `0013`.
- **H-74 Signed artifacts.** Add a nonce or unique digest, bind the operator and verifier IDs into the signed payload, and wrap the PEM load so a malformed key still produces the audited denial. Files: `ceremony/install.py`, `ceremony/recovery.py`.
- **H-75 Restricted grants.** `grant_restricted` validates that the resource exists, the project is active and the grantee is active. `has_restricted_grant` binds the source to its project. Files: `projects/service.py`, `rbac/sql_store.py`.
- **H-76 One time source (see H-21).**
- **H-77 Denial references.** Denial audits in ingest, reparse and reassess carry resource references.

### Phase 8: Evidence and re-review

- **H-80 Correct the Increment 2 evidence report.** See §8.
- **H-81 Per-EVAL evidence format.** See §8.
- **H-82 Independent re-review.** Request it against this plan's acceptance criteria once Phases 1–6 pass.

---

## 4. Exact files and migrations expected to change

**Migrations (new; existing `0001`–`0009` unchanged):**

| Migration | Purpose | Tasks |
|---|---|---|
| `0010_app_role_column_grants` | Revoke table-level UPDATE; column-level grants; state-machine UPDATE triggers | H-01, H-02 |
| `0011_security_definer_functions` | Guard owner role; SECURITY DEFINER functions; removal of `set_config` trust; appointment unique index; prior-activation marker; project-create context; ceremony immutability; approval deadline on activation | H-03, H-04, H-05, H-07, H-08, H-11 |
| `0012_source_snapshot_guards` | Scan-status transitions; snapshot and segment eligibility; classification only through the function; lease reaper index | H-06, H-24 |
| `0013_locators_and_reasons` | Locator fields; partial reason storage; checkpoint value validation; withdrawal audit reference | H-33, H-34, H-69, H-73 |

Each migration has a tested downgrade.

**Source files expected to change:**
- `src/webdesk/auth/service.py`, `src/webdesk/tokens/service.py`: H-10, H-11
- `src/webdesk/ceremony/install.py`, `src/webdesk/ceremony/recovery.py`: H-12, H-21, H-50, H-74
- `src/webdesk/rbac/assign.py`, `src/webdesk/rbac/sql_store.py`: H-12, H-75
- `src/webdesk/identity/contacts.py`, `src/webdesk/identity/sweep.py`: H-13, H-14, H-21, H-51
- `src/webdesk/intake/ingest.py`, `intake/reparse.py`, `intake/reassess.py`, `intake/parse_service.py`, `intake/parsers.py`, `intake/validation.py`: H-30 to H-34, H-40, H-62 to H-66
- `src/webdesk/runs/jobs.py`, `runs/service.py`, `runs/staleness.py`, `runs/hashing.py`, `runs/errors.py`: H-20 to H-25, H-41, H-62, H-68, H-70, H-71
- `src/webdesk/projects/service.py`: H-42, H-75
- `src/webdesk/outbox/worker.py`: H-52
- `src/webdesk/ratelimit/limiter.py`: H-72
- `src/webdesk/api/routes.py`, `api/app.py`, `api/transactions.py`: H-60, H-61, H-62, H-66
- `src/webdesk/cli/install.py`, `src/webdesk/cli/recover.py` (new): H-50, H-74
- `src/webdesk/worker/` (new): H-26, H-22, H-27
- `src/webdesk/config.py`: lease and timeout settings (test values only; production values are a decision)

**Tests expected to change:**
- Existing tests that encode a defect are corrected and logged in the evidence report with the reason. Examples: F11f and F11h status-code assertions (H-12); owner back-dating of `expires_at` and activation (H-09 replaces with real-time and injected-clock tests); `tests/committed/test_committed_runs.py:113–119` (accepts almost any outcome); the F13 test that cancels by raw `UPDATE`.

---

## 5. EVAL-F mapping and new negative tests

**Negative tests as `webdesk_app_login` (H-09). Each must refuse, and the assertion includes SQLSTATE and no row change:**

| # | Attempt | Expected |
|---|---|---|
| N1 | `UPDATE users SET status='active'` on a `pending_contact_approval` user | refused |
| N2 | `pending_activation → active` without a live token and approval | refused |
| N3 | `disabled → active` | refused |
| N4 | `UPDATE role_assignments SET role='Administrator'` | refused |
| N5 | `UPDATE role_assignments SET revoked_at=NULL` after revocation | refused |
| N6 | Second use of a consumed appointment via `fn` or direct `set_config` | refused |
| N7 | `UPDATE user_contact_approvals SET expires_at=…` after decision | refused |
| N8 | `UPDATE user_contact_approvals SET approved_by_user_id=…` after decision | refused |
| N9 | `UPDATE users SET contact_revision=…` or `session_epoch=…` directly | refused |
| N10 | `UPDATE project_access_grants` or `restricted_content_grants` changing `user_id` | refused |
| N11 | `UPDATE sources SET access_classification=…` directly, or `set_config` to bypass | refused |
| N12 | `UPDATE source_versions SET scan_status='clean'` from `quarantined` | refused |
| N13 | Insert a segment or snapshot for a quarantined version | refused |
| N14 | Insert a snapshot row from another project | refused |
| N15 | `UPDATE setup_trust_ceremonies SET kind='recover'` | refused |
| N16 | Insert `system:project_create` membership for an unrelated user | refused |
| N17 | Withdraw an approved or previously activated user (after an approval-history rewrite) | refused |
| N18 | Insert an audit row and then update it | refused (append-only) |
| N19 | Non-Administrator `classification.reassess` through any path | refused |

**EVAL-F pass conditions to be proved (per the EVALUATION_PLAN Gate 1 suite):**

| EVAL-F | Work items | Required new evidence |
|---|---|---|
| F01 | H-02, H-14 | Enforce `project.view/edit`, `requirement.view` and `audit.view` (currently unenforced, per the review); test all keys as `webdesk_app_login` |
| F02 | H-03, H-06, H-14 | Negative tests N11; tombstone rules |
| F03 | H-31, H-65 | HTTP 413 and 415 tests, size before authorization; quarantine enforced by DB (N12, N13) |
| F04 | H-33 | Message-ID and offsets; TXT offsets and `\n`-only splitting; DOCX table cells; EML locator enum enforced by CHECK |
| F05 | H-60 to H-62, H-66 | Allowlist, idempotency over HTTP, replay over HTTP |
| F06 | H-20 to H-27 | Crash tests; exhausted-lease reaper; renewal in real time; backoff asserted |
| F07 | H-25, H-42 | Two-connection race for archive versus start; no deadlock |
| F08 | H-69 | Checkpoint value validation; worker transitions audited |
| F09 | H-42, H-68 | Archive race; `created` state used or the state removed by a documented decision |
| F10 | H-41 | Altered-order negative digest; superseded versions excluded from in-flight |
| F11 | H-03, H-14 | Revocation services; N10 |
| F11b | H-07, H-03 | N4, N16 |
| F11c | H-02, H-10, H-11 | N1, N2, N3; late-activation refusal with an injected clock |
| F11d | H-02, H-13, H-14, H-05 | Withdrawal refused after activation (H-05); contact-change reject; N7, N8 |
| F11e | H-72, H-09 | Concurrent issuance and rate-limit race |
| F11f | H-11, H-12, H-50 | 403 vs 409; recovery CLI with no orphan rows; zero-admin refusal in DB |
| F11g | H-52, H-22, H-26 | Dead-letter for every transport error; renewal invoked; worker entry point |
| F11h | H-04, H-12 | Same-user reuse test (not a different user); N6 |
| F11i | H-02 | Zero-admin state cannot be undone by UPDATE |
| F12 | H-10, H-70, H-77, H-50 | Activation and reset denials survive; run audits carry `project_id`; denial references |
| F13 | H-30, H-41 | Poison file does not fail the run; itemisation asserted; immutability of past snapshots asserted |
| F14 | H-30, H-40 | Reparse after a parser-library error; the bad version can be reparsed |
| F14b | H-30 to H-35 | Real-file partial, failed and unsupported cases with persisted reasons |

---

## 6. Security acceptance criteria

1. Every negative test N1–N19 passes **as `webdesk_app_login`**, a non-superuser login role. No protected action is simulated through a superuser session or a `SET ROLE` from one.
2. No protected column can be changed by the application role without going through a SECURITY DEFINER function owned by `webdesk_guard_owner`. The application roles have no `EXECUTE` on any function that bypasses a state machine.
3. No trigger trusts a session variable for authorization.
4. A consumed appointment cannot be consumed again, by any path, including a second connection.
5. Denial audits survive every refusal path, tested through the production transaction runner on committed rows.
6. A stale or expired lease cannot be used to write job state. A crash cannot leave a run permanently blocked.
7. A malicious or malformed file cannot exhaust memory, CPU or time beyond the limits in H-31 and H-32, and cannot fail any other version or run.
8. Quarantined content cannot be parsed, snapshotted or read through any path, tested against the database.
9. No recovery or installation refusal leaves an orphan ceremony row.
10. The audit table remains append-only under `webdesk_app_login`.
11. A client cannot set `source_trust`, the uploader, the project creator, or any server-owned field.

---

## 7. Testing and rollback plan

**Test layers:**
- **Unit** (no database): parsers with generated fixtures, limit arithmetic, locator canonicalisation, hashing.
- **Negative, as `webdesk_app_login`** (rolled back): N1–N19, plus each F-test that touches a protected column.
- **Committed-row, two connections:** races (archive versus start, approve versus withdraw, token issuance, claim versus cancel).
- **Process-level:** the worker subprocess killed mid-step, the reaper, and the recovery CLI, all against a committed database with real time and a short test lease.
- **HTTP:** 413, 415, 422, allowlist and idempotency over real requests.
- **Regression:** the full existing suite must pass. Any test that encodes a defect is corrected and logged, with the reason, in the evidence report. No test is deleted to pass.

**Acceptance gate for each phase:** lint, format, mypy strict, full suite, and migration `upgrade head`, `downgrade -1`, `upgrade head` on a fresh database.

**Rollback:**
- Tag `inc2-acd5c51` at the baseline. Revert by checking out the tag on a new branch. Migrations `0010`–`0013` each have a tested `downgrade` to the previous revision.
- Each phase is its own commit, so a single phase can be reverted without the others.
- The new worker is additive. Stopping the worker process returns the system to the Increment 2 behaviour, which has no worker, so nothing else depends on it.
- Data: the new migrations add columns and triggers and do not delete rows. A downgrade restores the Increment 2 schema without losing data, except that the new columns are dropped.

---

## 8. Evidence correction and format

**Correction of `docs/INCREMENT_2_EVIDENCE.md` (H-80), preserving history:**
- Keep the original text. Do not overwrite it.
- Add a section **"Reviewer correction (2026-10-19)"** that states:
  - the reviewer's classification: 1 PASS, 12 PARTIAL, 10 FAIL, with F-CFG-01 passing;
  - that "24 COMPLETE, 0 PARTIAL" was **overstated**, and why (the tests create state as the owner, several tests are weaker than their pass conditions, and some pass conditions were not checked);
  - that the work is described as "uncommitted" in the original text, which is out of date: the work is committed through `acd5c51`;
  - that EVAL-DEPLOYMENT-GATE-001 and D-16 block **production deployment only**, not Foundation acceptance. The original text was wrong to list D-16 as the item stopping Gate 1.
- Mark each original status row with a pointer to the correction.
- Add the stale phrase in `DEPLOYMENT_CHECKLIST.md` (references to a recovery CLI and sweep that did not exist) as a correction, not a silent edit.

**Per-EVAL evidence format (H-81).** Every test in the evidence report records:
- test ID and file;
- the role used (`webdesk_app_login`, owner, or other), and whether the database was committed or rolled back;
- inputs (fixture state, injected time, files);
- expected result (status, SQLSTATE, row state, audit row);
- actual result;
- spec section and EVAL pass condition, verbatim;
- commit SHA and run date.

---

## 9. Remaining decisions

Each decision blocks the task named. None is decided by this plan.

| ID | Decision | Blocks | Default proposed |
|---|---|---|---|
| **H-DEC-1** | **Governance ruling: may a parked run be cancelled?** ARCH §7 has no parked→cancelled transition. The current code allows it. **Flagged as a separate governance decision and not changed here.** | H-68 | Keep current behaviour until ruled |
| H-DEC-2 | Late reclassification to `restricted` after parsing: policy for quarantining already-parsed content | H-67 | Keep refusal; no change |
| H-DEC-3 | Numeric parse limits (ZIP ratio, uncompressed bytes, pages, segments, characters per segment) | H-31 | Proposed values to be chosen by WDS; tests use small values |
| H-DEC-4 | Parse isolation on Windows: job object for memory caps, or a process-only timeout | H-32 | Process timeout plus file-size pre-check |
| H-DEC-5 | DOCX table locator fields beyond SCHEMA §4.2 (`table_index`, `row`, `cell`) | H-33 | Add as an extension of `docx_paragraph` |
| H-DEC-6 | HTML-only email body: convert to text, or report as an unextractable region | H-64 | Report as unextractable (`partial`) |
| H-DEC-7 | EVAL-DEPLOYMENT-GATE-001: confirm it applies to production only, as the review states | Evidence wording | Production only |
| H-DEC-8 | Operational alert: a real in-app alert record, or an audit row with a notification queue | H-52 | Alert table, separate from the audit log |
| H-DEC-9 | Test database owner: confirm a non-superuser owner for negative tests | H-00 | Non-superuser owner, superuser only for migration bootstrap |
| H-DEC-10 | Session and password placeholders (C-8: 12 characters, 8 hours), outbox key custody (C-9) | Production only | Unchanged; recorded in checklist |
| H-DEC-11 | HTTP login and administration endpoints: defer to Increment 4, or include now | Scope | Defer (review's recommendation) |
| H-DEC-12 | `created` run state: use it, or remove it by a documented decision | F09 | Remove from the active vocabulary, documented |

**Spec change needed?** None, according to the review. The only exception is H-DEC-1, which needs a WDS ruling before any change, and no spec text is changed by this plan.

---

## 10. Scope boundaries

Not in Increment 3:
- specialist agents, routing, LLM calls, RAG, estimation, SOW generation;
- production deployment, hosting, egress, production email;
- any approved business policy change;
- login and administration HTTP endpoints (H-DEC-11).

Approval requested: this plan, the decisions in §9, and the ordering in §3.
