# Increment 1 Evidence Report: Gate 1 Foundation (T1–T14 + T15 verification)

Status: **Increment 1 verification run complete. Gate 1 is NOT complete.** Several release-blocking
EVAL-F tests are only partly covered, not started, or deferred to Increment 2 (see §3).

## 1. Verification run

| Check | Command | Result |
|---|---|---|
| Full test suite | `pytest -v` (integration tests against PostgreSQL 16.4, `webdesk_test`) | **205 passed, 0 failed, 0 errors** |
| Lint | `ruff check .` | All checks passed |
| Format | `ruff format --check .` | 51 files already formatted |
| Types | `mypy` (strict, `src/webdesk`) | Success: no issues in 26 source files |
| Migrations | `alembic upgrade head` → `downgrade 0004` → `upgrade head` | Clean both ways |

Test counts by file: `test_gate1_schema` 22, `test_contact_lifecycle` 11, `test_auth_lifecycle` 8,
`test_role_assignment` 10, `test_tokens` 10, `test_projects` 9, `test_outbox_worker` 9,
`test_idempotency` 6, `test_install_ceremony` 5, `test_rbac_sql` 3, `test_audit_service` 2;
unit tests 102 (`test_rbac_engine` 55, `test_email_policy` 15, `test_config` 12,
`test_install_authorization` 10, `test_contact_box` 8, `test_delivery_and_tokens` 6,
`test_audit_redaction` 3, `test_scaffold` 1).

The integration tests need a migrated database (`alembic upgrade head` on
`WEBDESK_TEST_DATABASE_URL`). Most roll back. The outbox tests commit rows and delete them in
teardown.

## 2. Task-to-spec traceability

| Task | Governing spec | Implementation | Tests |
|---|---|---|---|
| T1 scaffold | ARCH §2, §14 | `pyproject.toml`, `docker-compose.yml`, `.env.example` | scaffold |
| T2 settings, fail-closed | ARCH §14; GOV §8, §11 | `src/webdesk/config.py` | `test_config` (12) |
| T3 schema, triggers, roles | SCHEMA §3.1, §4.1; GOV §8, §11 | `migrations/versions/0001`, `0002` | `test_gate1_schema` (22) |
| T4 audit, redaction | GOV §11; SCHEMA §4.10 | `audit/service.py` | `test_audit_redaction`, `test_audit_service` |
| T5 email normalization | SCHEMA §3.1; P-GATE1-CONTACT-01 | `identity/email.py` | `test_email_policy` (15) |
| T6 RBAC | GOV §11 matrix, C-1, C-2, C-3 | `rbac/matrix.py`, `engine.py`, `sql_store.py` | `test_rbac_engine` (55), `test_rbac_sql` (3) |
| T7 installation ceremony | P-GATE1-BOOTSTRAP-02 | `ceremony/install.py`, `cli/install.py` | `test_install_authorization`, `test_install_ceremony` |
| T8 contact approval, change, withdrawal | P-GATE1-CONTACT-01; B3/B4 | `identity/contacts.py` | `test_contact_lifecycle` (11) |
| T9 tokens, transport, rate limit | ARCH §13; EVAL-F11c, F11e | `tokens/service.py`, `delivery/transport.py`, `ratelimit/limiter.py` | `test_tokens` (10), `test_delivery_and_tokens` (6) |
| T10 credentials, login, sessions | GOV §11; SCHEMA Session | `auth/service.py`; migration `0004` | `test_auth_lifecycle` (8) |
| T11 role assignment, appointments | R2; B1/B2; F11b, F11f, F11h, F11i | `rbac/assign.py`, `ceremony/recovery.py` | `test_role_assignment` (10) |
| T12 projects, membership, grants | GOV §11; SCHEMA §4.1; F09 (project part), F11-SELFGRANT | `projects/service.py` | `test_projects` (9) |
| T13 idempotency, revision | SCHEMA §3 DTOs; F05 | `idempotency/service.py` | `test_idempotency` (6) |
| T14 outbox worker, sealed address | F11g; ARCH §7 | `outbox/worker.py`, `crypto/contact_box.py`; migration `0005` | `test_outbox_worker` (9), `test_contact_box` (8) |

## 3. EVAL-F coverage (release-blocking for limited Foundation)

Coverage key: **Covered** = all listed pass conditions have a test; **Partial** = some pass
conditions are untested or not implemented; **Deferred** = Increment 2 scope, not started.

| Test | Status | Notes |
|---|---|---|
| EVAL-F01-MATRIX | Partial | Matrix encoded and tested with a fake store and against SQL. Not every key is exercised for every role in assigned and unassigned states. `run.start` and Administrator-only controls are covered. |
| EVAL-F02-CLASS | Partial | Project `data_classification` is required and typed (tested). Source classification and tombstone content rules are untested (Sources are Increment 2). |
| EVAL-F03-UPLOAD | Deferred | Source intake is Increment 2. |
| EVAL-F04-LOCATOR | Deferred | Parsers and segments are Increment 2. |
| EVAL-F05-DTO | Partial | Idempotency replay, payload-hash 409 and revision 409 are tested at the service layer. No HTTP DTO layer exists yet, so the "client-set server-derived fields" rule is untested. |
| EVAL-F06-JOBS | Deferred | Durable job table and worker-run leases are Increment 2. |
| EVAL-F07-CONCURRENCY | Deferred | Run concurrency is Increment 2. |
| EVAL-F08-SOT | Partial | Audited service writes are in place. Checkpoints do not exist yet. |
| EVAL-F09-TRANSITIONS | Partial | Project creation creates no run (tested). Snapshots and run states are Increment 2. R3 archive-during-run is not reachable yet (see §4). |
| EVAL-F10-STALE | Deferred | Hash canonicalisation is Increment 2. |
| EVAL-F11-SELFGRANT | Covered | Self-grant refused in service and by CHECK constraints; second Administrator may grant. |
| EVAL-F11b-SELFASSIGN | Covered | Self-assignment refused; bootstrap-only-once; CHECK and trigger tests. |
| EVAL-F11c-ACTIVATION | Covered | Token-only activation; pending states cannot sign in; reset revokes sessions. |
| EVAL-F11d-CONTACT-APPROVAL | Partial | Normalization, reservations, approval rules, withdrawal and contact change are tested. Not tested: replacement create after expiry or rejection (not implemented), concurrent approval versus withdrawal, and 24-hour expiry sweeps for change requests (no sweep job). |
| EVAL-F11e-TOKEN-RATELIMIT | Covered | One live token, revision binding, 30-minute TTL, login and token limits, neutral errors, capture sink refused in production. |
| EVAL-F11f-CEREMONY-RECOVERY | Partial | Install and recovery coverage tested. Not tested: the 24-hour missed-activation cases that release reserved coverage (no sweep job). |
| EVAL-F11g-CONTACT-OUTBOX | Partial | Same-transaction write, SKIP LOCKED leases, lease fencing, backoff, dead-letter alert and sealed address are tested. Not tested: an SMTP outage leaving the contact change effective (the design does this, but no test forces the failure), and a lease-renewal loop. |
| EVAL-F11h-ADMIN-APPOINTMENT | Partial | Appointment consumption, reuse refusal and recovery appointments tested. Not tested: direct DB insertion of a role without an appointment (covered by trigger tests in `test_gate1_schema`, so effectively covered). |
| EVAL-F11i-ZERO-ADMIN-OFFLINE-POLICY | Partial | In-app refusal of zero-admin recovery tested. The offline path is a specification and cannot be tested here. |
| EVAL-F12-AUDIT | Partial | Append-only enforcement tested. Redaction tested. Not every denial path is audited with a test. |
| EVAL-F13, F14, F14b | Deferred | Source parsing and reparse are Increment 2. |
| F-CFG-01, EVAL-DEPLOYMENT-GATE-001 | Partial | Fail-closed configuration tested. Deployment gate has no hosting configuration yet. |

## 4. Open gaps and deliberate limitations

1. **R3 archive-during-run is not enforced.** `workflow_runs` does not exist yet. The check must be
   added with the run tables in Increment 2. The code records this.
2. **Replacement create requests** for an existing `pending_contact_approval` user are not built.
3. **Expiry sweeps** do not exist. Expiry is enforced at approval time with `expires_at > now()`.
   Missed-deadline effects on reserved coverage (F11f) therefore depend on a sweep that is not built.
4. **Session lifetime (8 hours) and password minimum (12 characters) are placeholders.** Neither is
   in the Gate 1 contracts. Both need WDS approval.
5. **Prior-contact address is sealed** (AES-256-GCM, migration `0005`). The key comes from
   `WEBDESK_OUTBOX_ENCRYPTION_KEY`. Key custody, rotation and production key storage are not
   decided. Production must not send change notices until they are.
6. **Audit denials survive only if the caller commits.** Services write denial events and then
   raise. A caller that rolls back on error discards them. The API layer must commit denial audits.
7. **No HTTP API layer exists.** Services are called directly. Neutral HTTP responses, status
   mapping and the API DTO rules are untested.
8. **Local Docker PostgreSQL runs as a superuser owner role.** Production must use a non-superuser
   owner and separate login roles for `webdesk_app` and `webdesk_ceremony`.
9. **Host port is 5433, not 5432.** A local PostgreSQL 17 service already owns 5432. I did not stop
   it.
10. **Migrations are raw SQL.** No ORM models exist. The plan's "SQLAlchemy metadata" step was
    replaced by DDL-as-source-of-truth.

## 5. Changes outside the original T1–T15 task list

- Migration `0002`: ceremony-role grants needed for installation.
- Migration `0003`: rate-limit event log.
- Migration `0004`: credentials (Argon2id hashes).
- Migration `0005`: sealed prior-contact ciphertext and its CHECK constraint.
- T4 and T5 were combined, as approved.

## 6. Not done

- Nothing is committed to git. The spec folder and all implementation files are untracked. The spec
  baseline should be committed before Increment 2 (GOVERNANCE §2).
- Increment 2 (intake, runs, jobs, checkpoints, staleness) has not started.
- No production deployment, live egress, LLM, RAG, estimation or SOW functionality was implemented.
