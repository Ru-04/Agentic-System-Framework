# S8-01 threat model and trust-boundary register

**Requirement:** S8-01 (GREEN, `SPRINT7_8_DEPENDENCY_MATRIX_2026-11-03.md`): threat register and trust-boundary review for Foundation ↔ AI ↔ specialists, review/reporting and worker persistence.
**Baseline:** Foundation candidate `5974d59` (`feature/sprint8-hardening-resilience`, cut from it).
**Status:** Document only. It records what the repository shows, cites where, and marks anything not verified as **UNKNOWN**. It does not approve any control, threshold or acceptance decision. Mitigation owners are workstreams, not individuals.
**Not independent review.** Independent QA of this register is a separate gate (`SPRINT8_REQUIREMENTS_v1.0.md`, Definition of Done).

## 1. Sources and method

| Source | Path (in repo at `5974d59` unless stated) | Last changed |
|---|---|---|
| Architecture | `WebDesk_Agentic_Requirement_Platform_Specs/ARCHITECTURE.md` §3, §13, Authentication boundary (Amendment A2) | `af37f7b` |
| AI read contract | `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` §3–§10 | `5ee372e` |
| Production boundary | `docs/PRODUCTION_BOUNDARY.md` (decision 7) | `640287e` |
| Worker privilege matrix | `docs/PHASE3_WORKER_PRIVILEGE_MATRIX.md` | `3065361` |
| Integration state | `docs/FOUNDATION_INTEGRATION_P2_P7.md` | `5974d59` |
| G0 evidence (scratch run, not independent QA) | `docs/governance/SPRINT6_G0_EVIDENCE_2026-11-03.md` on `claude/sprint5-specialist-evaluations` | not on this branch |
| Source and migrations | `src/webdesk/**`, `migrations/versions/**` | see per-row citations |

Method: each trust boundary was identified from the components that exist in the repository, then threats were listed per boundary. A control is marked **VERIFIED-REPO** only when a file or migration implements it and a named test exercises it. **PARTIAL** means implemented but a named part is untested or depends on a production item. **UNKNOWN** means the repository does not show it. **NOT IN REPO** means the component is absent at `5974d59`.

Test references are to files that exist at `5974d59`. The G0 record (`5974d59`, 1031 passed, 0 skipped, a developer run) is cited as evidence of the suite's last full run. It was not re-executed for this register.

## 2. Components present and absent at `5974d59`

| Component | Present? | Evidence |
|---|---|---|
| FastAPI application, human and AI routes | Present | `src/webdesk/api/app.py`, `routes.py`, `ai.py` |
| Authentication authority (separate process, loopback) | Present | `src/webdesk/authority/server.py`, `client.py`, `service.py` |
| Operation proofs | Present | migrations `0021`, `0024`, `0025`–`0027`; `src/webdesk/authority/proofs.py` |
| Deny-by-default authorization engine | Present | `src/webdesk/rbac/engine.py`, `matrix.py`, `sql_store.py` |
| Durable worker (claim, lease, fence, reap) | Present | migrations `0050`–`0059`; `src/webdesk/runs/jobs.py`, `committed.py`, `heartbeat.py`; `src/webdesk/worker/loop.py` |
| Outbox worker (prior-contact notices) | Present | `src/webdesk/outbox/worker.py`; migrations `0005`, `0033`, `0055`, `0059` |
| Intake parser child process | Present | `src/webdesk/intake/isolation.py`, `parser_child.py`, `parse_service.py` |
| AI principal (`ai-read/v1`) | Present (read-only) | migration `0041_ai_read_v1.py`; `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` |
| Workspace entity (OPEN-11) | **NOT IN REPO.** No workspace table, module or column in `src/` or `migrations/`. OPEN-11 is blocked. | `SPRINT7_8_DEPENDENCY_MATRIX_2026-11-03.md` |
| Specialists (seven, Sprint 6) | **NOT IN REPO.** No specialist code in `src/`. Sprint 6 integration (S6-INT) is not complete. | `FOUNDATION_INTEGRATION_P2_P7.md`; `src/` search |
| Review and reporting (S7) | **NOT IN REPO** at `5974d59`. Sprint 7 runs in its own worktree. | dependency matrix |
| Real email transport | **NOT IN REPO** as enabled. SMTP adapter exists, disabled by default and refused without `WEBDESK_SMTP_VERIFIED=true`. | `src/webdesk/delivery/smtp.py`; `docs/PRODUCTION_BOUNDARY.md` §6 |

## 3. Trust boundaries

| ID | Boundary | Crossing mechanism | Trust placed on the far side |
|---|---|---|---|
| TB-1 | Browser or API client → FastAPI application | HTTP. Human session bearer; AI principal bearer on `/v1/ai/*` (`Authorization: AI-Principal <token>`) | None. Every request is authorized server side. |
| TB-2 | Application → authentication authority | Loopback HTTP with a bearer shared secret (`client.py` accepts only `127.0.0.1` / `localhost`, `http`) | The authority is trusted to verify credentials and issue proofs. Transport is **not** authenticated beyond the shared secret (`PRODUCTION_BOUNDARY.md` §3). |
| TB-3 | Application login role → PostgreSQL guard functions | `webdesk_app` membership; `SECURITY DEFINER` guards owned by `webdesk_guard_owner` | The guard decides. The application role cannot write credentials, sessions, proofs or `ai_principals` directly (migrations `0023`, `0041`). |
| TB-4 | Foundation → AI principal read path | `/v1/ai/*`, read-only, per-request checks (`ai.py`, contract §3.2 and §7) | The AI caller is untrusted and bound to one run, one project and one human. Its reads re-check the bound human's rights in the same transaction. |
| TB-5 | Foundation → specialists | Not built (see §2) | **UNKNOWN.** No contract is implemented in the repository beyond the read contract. |
| TB-6 | Specialists / review / reporting → persisted state (S7) | Not built | **UNKNOWN.** |
| TB-7 | Worker process → persistence (`webdesk_worker`, `webdesk_outbox`) | Login roles that are members of one group role each; table reads only; every write through a fenced guard | The lease holder for its own job or notice, for its unexpired lease only. |
| TB-8 | Uploaded source file → parser | Child process per parse, resource bounded (`isolation.py`) | The file is hostile. The parser output is untrusted text until validated. |
| TB-9 | Outbox → email transport | `EmailTransport.send(..., idempotency_key=notice_id)` | The transport is an external system. Its delivery is at-least-once with a key. |
| TB-10 | Operator CLI and ceremony → database | Owner-signing ceremony, `webdesk_ceremony`, `cli/*` | Owner authorization artifact, verified by the database. Production custody is open (`PRODUCTION_BOUNDARY.md` §2). |
| TB-11 | Application → audit and logs | `webdesk_guard.record_*` functions; structured events | Logs and audit must not carry secrets, addresses or content. Redaction is checked, not assumed. |
| TB-12 | Contact address → outbox row | AES-256-GCM sealed value, associated data = purpose and user (`crypto/contact_box.py`) | The key is an environment value (`WEBDESK_OUTBOX_ENCRYPTION_KEY`). Custody is open. |

## 4. Privileged actions and their proofs

| Action class | Proof operation(s) | Enforcing function or rule | Source |
|---|---|---|---|
| Project create | `project.create` | `actor_for` then `ROLE` rule | `projects/service.py`; `rbac/matrix.py` |
| Membership add or revoke | `project.membership.add`, `project.membership.revoke` | proof resource must equal the project | `projects/service.py`; `tests/integration/test_projects.py` |
| Role assign and revoke | `role.assign`, `role.revoke` | proof resource equals the assignment | `rbac/assign.py`, `rbac/revoke.py` |
| Account disable | `user.disable` | proof-guarded write | `identity/disable.py`; migration `0018` |
| Run start, cancel, retry | `run.*` permissions | `RUN_START` for Analyst (assigned); cancel, retry and resume Administrator only | `rbac/matrix.py`; `runs/service.py` |
| AI principal issue and revoke | `ai.principal.issue`, `ai.principal.revoke` | membership of the run's project; one live principal per run | contract §3.1, §4; migration `0041` |
| Owner-initiated reset | `account.reset.issue` | `reset_not_self` refusal | `tests/support/proofs.py`; `authority/service.py` |

## 5. Threat register

Status key: **VERIFIED-REPO** (control and named test exist); **PARTIAL**; **UNKNOWN**; **NOT IN REPO**. "Owner" is the workstream accountable for the mitigation.

| ID | Boundary | Threat (STRIDE) | Mitigation in repository | Evidence in repository | Status | Gap or unknown | Owner |
|---|---|---|---|---|---|---|---|
| T-01 | TB-1 | Spoofed session or forged bearer token (S) | Session token stored as hash only (`auth/service.py` `session_token_hash`; `ratelimit/limiter.py` `subject_hash`); AI token stored as SHA-256 hash (`api/ai.py` `_hash`); human and AI schemes separate; human route refuses AI credential | `tests/committed/test_ai_read_v1.py`; `tests/hardening/test_eval_f11j.py` | VERIFIED-REPO | Token lifetime on the human path is not re-measured here | Foundation |
| T-02 | TB-1 | Forged operation proof (S) | Proof must exist, be unspent and bound; unknown proof refused `proof_missing` | `tests/sprint8/test_s8_02_fail_closed_db.py::test_a_forged_proof_is_refused_and_creates_no_project` (**BLOCKED**, see §6); `tests/hardening/test_eval_f11j.py` | VERIFIED-REPO (existing); S8-02 copy BLOCKED | DB execution needs scratch credentials | Foundation |
| T-03 | TB-1 | Replay of a spent proof (R) | `consumed_at` one-time consumption; `proof_spent` refusal | `tests/integration/test_phase2_guards.py`, `tests/hardening/test_proof_rollback.py` | VERIFIED-REPO | — | Foundation |
| T-04 | TB-1 | Expired proof used later (S, R) | 30-second TTL checked against `now()` in the guard (`0024`) | `tests/hardening/test_eval_f11j.py` (`proof_expired`) | VERIFIED-REPO (existing) | The S8-02 expiry test uses a real 31 s wait on committed rows; not executed | Foundation |
| T-05 | TB-2 | Stolen or leaked authority shared secret (S, E) | Secret of at least 32 characters; authority refuses `WEBDESK_ENV=production` | `authority/server.py`; `tests/hardening/conftest.py` | PARTIAL | No key custody, rotation or revocation procedure (`PRODUCTION_BOUNDARY.md` §2) | WDS decision; Foundation |
| T-06 | TB-2 | Interception of authority traffic (I) | Loopback only; `client.py` rejects non-loopback and non-HTTP addresses | `tests/sprint8/test_s8_02_fail_closed_unit.py::test_the_authority_client_refuses_non_loopback_or_non_http_addresses` (3 cases, passed) | PARTIAL | No TLS and no mutual authentication. Accepted only for non-production (`PRODUCTION_BOUNDARY.md` §3) | WDS decision; Foundation |
| T-07 | TB-2 | Authority unreachable, client trusts stale session (S) | `AuthorityUnavailable`; no session trusted | `tests/sprint8/test_s8_02_fail_closed_unit.py::test_an_unreachable_authority_fails_closed_and_trusts_no_session` (passed) | VERIFIED-REPO | — | Foundation |
| T-08 | TB-3 | Application role writes protected tables directly (T, E) | `REVOKE` on protected tables; guard functions only; privilege audit pins the function set | `tests/hardening/test_privilege_audit.py` (12 tests), `tests/hardening/test_app_role_negative.py`, migrations `0017`, `0023`, `0032` | VERIFIED-REPO | Verified on scratch clusters; production identity provisioning is open (`PRODUCTION_BOUNDARY.md` §4) | Foundation |
| T-09 | TB-3 | Guard executed with mutable actor argument (E) | Guard derives actor from proof, not from arguments (Amendment A2) | `tests/hardening/test_sql_authorization.py`, `tests/hardening/test_privilege_hardening.py` | VERIFIED-REPO | — | Foundation |
| T-10 | TB-3 | Cross-project read by a member of another project (I) | Membership is per project; `membership_missing` for other project | `tests/sprint8/test_s8_02_fail_closed_unit.py::test_membership_in_one_project_does_not_open_another_project` (passed); DB copy BLOCKED | VERIFIED-REPO (pure); DB PARTIAL | DB copy needs scratch credentials | Foundation |
| T-11 | TB-3 | Grant or restricted grant for one project used on another (I, E) | `grant_missing` and `restricted_content_grant_missing` per resource | `tests/sprint8/test_s8_02_fail_closed_unit.py` (4 cases, passed) | VERIFIED-REPO (pure) | — | Foundation |
| T-12 | TB-3 | Cross-workspace read or write (I, E) | None. No workspace entity exists. | none | **UNKNOWN** | OPEN-11. Cannot be tested until the entity exists | WDS decision (OPEN-11) |
| T-13 | TB-4 | AI principal reads beyond the bound human (I) | Per-request re-check of human rights in one transaction; restricted and quarantined content denied | `tests/committed/test_ai_read_v1.py` (28 tests, includes revocation and expiry) | VERIFIED-REPO | — | Foundation |
| T-14 | TB-4 | Replayed or expired AI token (S, R) | 15-minute TTL checked in the database; revocation and rotation | contract §4; `tests/committed/test_ai_read_v1.py` | VERIFIED-REPO | — | Foundation |
| T-15 | TB-4 | Enumeration of run or document identifiers (I) | Out-of-scope identifiers return `404` with no disclosure; denial recorded in audit only | contract §7, §9; `tests/committed/test_ai_read_v1.py` | VERIFIED-REPO | Full contract matrix on fresh database not re-run | Foundation |
| T-16 | TB-5 | Specialist bypasses Foundation authorization (E) | None: no specialist code | none | **UNKNOWN** | S6-INT; specialist contracts not implemented | Sprint 6 integration |
| T-17 | TB-6 | Unapproved review, approval or report export (E, I) | Not built at `5974d59` | none | **NOT IN REPO** | Sprint 7; S7-07 and S7-10 are RED | Sprint 7 |
| T-18 | TB-7 | Two workers process the same job (D) | `FOR UPDATE SKIP LOCKED`; claim is a guard; one live lease per job | `tests/committed/test_durable_execution.py::test_two_workers_racing_for_one_queued_job_get_exactly_one_claim`; `tests/committed/test_committed_runs.py` | VERIFIED-REPO | — | Foundation |
| T-19 | TB-7 | Stale worker writes after its lease was reclaimed (T, R) | Every state change fenced by `lease_owner` and unexpired lease (`0050`, `0051`, `0055`, `0059`) | `tests/committed/test_durable_execution.py` (fencing cases); `tests/sprint8/test_s8_07_08_replay_and_fencing.py::test_a_stale_claim_replayed_after_another_worker_sent_is_fenced` (BLOCKED in this run) | VERIFIED-REPO (existing) | S8 copy not executed | Foundation |
| T-20 | TB-7 | Worker role gains write or other-role access (E) | `webdesk_worker` holds SELECT on three tables only; pins in privilege audit | `docs/PHASE3_WORKER_PRIVILEGE_MATRIX.md`; `tests/committed/test_worker_login.py` | VERIFIED-REPO | Production worker login provisioning is open | Foundation |
| T-21 | TB-7 | Duplicate outbox send after lost lease (D) | Idempotency key = notice ID on every attempt; lease fence before and after the send | `src/webdesk/outbox/worker.py`; `tests/integration/test_outbox_worker.py`; `tests/sprint8/test_s8_07_08_replay_and_fencing.py` (BLOCKED in this run) | PARTIAL | The transport must honour the key. Delivery is at-least-once, not exactly-once; no webhook guarantee is claimed | Foundation; transport owner |
| T-22 | TB-7 | Retry storm or unbounded retry (D) | Exponential backoff capped at 300 seconds; dead letter at threshold; alert written | `outbox/worker.py` (`backoff_seconds`); `tests/integration/test_outbox_worker.py` | VERIFIED-REPO | Threshold and lease values are configuration, not approved SLOs | Foundation; WDS decision |
| T-23 | TB-8 | Malformed or hostile file crashes or exhausts the host (D, E) | Parser child process with memory and time bounds; `ParserFailure` classes; 20 MiB and 50-file limits per ARCHITECTURE §13 | `src/webdesk/intake/isolation.py`; `tests/unit/test_parse_isolation.py`, `tests/unit/test_parse_defects.py`, `tests/committed/test_parse_concurrency.py` | VERIFIED-REPO (repository tests) | Parser bounds are not a load test (S8-10 is out of this scope) | Foundation |
| T-24 | TB-8 | Quarantined or restricted source reaches an LLM (I) | Quarantined never parsed, retrieved or supplied; restricted never returned to AI | `ARCHITECTURE.md` §13; contract §5; `tests/committed/test_ai_read_v1.py` | VERIFIED-REPO | Malware scanner absent: `not_scanned` is the state for every file | WDS decision (scanner) |
| T-25 | TB-9 | Notice address leaks to logs or audit (I) | Address never in audit or error text; reason codes only | `outbox/worker.py` docstring and `_audit_failure`; `tests/unit/test_audit_redaction.py`; `tests/integration/test_outbox_worker.py` (`OLD_EMAIL not in body`) | VERIFIED-REPO | Logs of the running process are not inspected here | Foundation |
| T-26 | TB-9 | Real reset or activation mail sent unverified (R) | Reset delivery disabled by default; SMTP refused without verified flag | `src/webdesk/delivery/smtp.py`; `PRODUCTION_BOUNDARY.md` §6 | VERIFIED-REPO (gate); production transport **UNKNOWN** | No approved transport exists | WDS decision |
| T-27 | TB-10 | Ceremony run without owner authorization (E) | Installation and recovery need an owner-signed artifact verified in the database | `tests/unit/test_install_authorization.py`; `tests/integration/test_install_ceremony.py` | PARTIAL | Owner signing key custody is open (`PRODUCTION_BOUNDARY.md` §2) | WDS decision |
| T-28 | TB-11 | Audit events modified or deleted (T) | Audit append-only to application roles; corrections are audited maintenance | `ARCHITECTURE.md` §13; `tests/hardening/test_privilege_audit.py`; `tests/integration/test_audit_service.py` | PARTIAL | Tamper-evident storage is future work (ARCHITECTURE §13) | Foundation |
| T-29 | TB-12 | Contact ciphertext opened under the wrong purpose or user (I, T) | AES-GCM with associated data (purpose, user) | `src/webdesk/crypto/contact_box.py`; `tests/unit/test_contact_box.py`; outbox tests (unreadable row dead-lettered) | VERIFIED-REPO | Key custody open | WDS decision |
| T-30 | All | Unbounded request, body or payload size (D) | Upload body bound; AI response limit 10 MiB; per-subject rate limits | `tests/unit/test_upload_body_bound.py`; contract §9; `src/webdesk/ratelimit/limiter.py` | PARTIAL | Load and capacity behaviour is S8-10, out of this scope | Foundation |

## 6. Verification status of this session's tests (S8-02, S8-07, S8-08)

| Test module | Result in this session | Reason |
|---|---|---|
| `tests/sprint8/test_s8_02_fail_closed_unit.py` | **18 passed** | No database needed. Run with `pytest tests/sprint8/test_s8_02_fail_closed_unit.py`. |
| `tests/sprint8/test_s8_02_fail_closed_db.py` | **Not executed. BLOCKED** | No PostgreSQL credential for the scratch cluster at `127.0.0.1:56544` is provisioned in this worktree. The module is skipped with a `BLOCKED:` reason. |
| `tests/sprint8/test_s8_07_08_replay_and_fencing.py` | **Not executed. BLOCKED** | Same reason. |

The DB-backed tests have not been run. They are written against the existing `committed_engine` and `committed_admins` fixtures and were checked only for lint, format and undefined names. Their results must not be read as PASS.

## 7. Items recorded as UNKNOWN or not verified

1. **OPEN-11 workspace identity.** No entity exists. Every cross-workspace threat (T-12) is unverifiable.
2. **Specialists and S6-INT.** No specialist code exists at `5974d59`. Threats T-16 and any end-to-end misuse path are unverifiable.
3. **Review, reporting and S7 persistence.** Not built in this worktree (T-17).
4. **Production identities and secrets.** Login provisioning, key custody, rotation and revocation are open (`PRODUCTION_BOUNDARY.md` §2, §4).
5. **Transport security.** No TLS or mutual authentication between application and authority (T-06).
6. **Malware scanning.** No scanner is configured; every source is `not_scanned` (T-24).
7. **Scratch database isolation for this session.** Scratch-cluster DB tests not run (§6).
8. **Restore and recovery.** Not verified here (S8-12 is RED).

## 8. Owners and next actions

| Action | Owner | Gate |
|---|---|---|
| Resolve OPEN-11 | WDS decision | Blocks T-12 and S8-02 workspace test |
| Provide scratch PostgreSQL credential for `127.0.0.1:56544` to run `tests/sprint8/*_db.py` and `*_replay_and_fencing.py` | Engineering (environment) | Blocks execution of 14 DB-backed checks |
| Close production blockers 1–7 in `PRODUCTION_BOUNDARY.md` | WDS decision and deployment | Not part of Sprint 8 acceptance here |
| Independent review of this register | Independent reviewer (not this session) | Required for S8-01 completion |
