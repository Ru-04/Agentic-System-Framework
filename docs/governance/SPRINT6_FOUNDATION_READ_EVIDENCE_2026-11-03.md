# Sprint 6 Foundation engineering evidence (3 November 2026)

**Branch:** `sprint6-foundation-read`, cut from `feature/foundation-integration-p2-p7` at `5974d59`.
**Commits:** `ffce468` (OPEN-02 route move and contract-shape 405), then the commit that carries this record (SHA reported in the handoff).
**Scope:** the five `ai-read/v1` GET endpoints (checked, not reimplemented), OPEN-02, the Foundation-issued operator confirmation (OPEN-03/04/05/06), the minimum R-1 to R-3 migrations (OPEN-18), restricted worker-owned persistence (OPEN-17), and their PostgreSQL tests.
**Not in scope (not implemented):** workspace isolation and any workspace table (OPEN-11, D-DEP-1); R-4; specialist adapter 0.3 and its verifier wiring (Specialist team); AI Engine code; any public HTTP write route; production activation.

## 1. Migrations (single Alembic head)

| Revision | Purpose | Contract |
|---|---|---|
| `0060_s6_r1_operation` | Adds proof operation `specialist.execution.confirm` to the `operation_proofs` CHECK; rule row Approver with membership required; authority allowlist accepts the operation | 6.2, 8.1, 11.3 R-1 |
| `0061_s6_r2_confirmation` | `operator_confirmation` table (binding, digests, 15-minute maximum lifetime, states `confirmed`/`consumed`/`revoked`); `fn_confirm_specialist_execution_with_proof`; `fn_revoke_specialist_confirmation_with_proof`; `fn_record_specialist_audit` | 8.2 to 8.4, 11.3 R-2 |
| `0062_s6_r3_results` | `specialist_execution`, `ai_result`, `ai_finding`, `citation` tables; `fn_begin_specialist_execution` (atomic consumption plus execution record); `fn_persist_specialist_result` (provenance-checked persistence) | 9.2, 9.3, 10.1 to 10.4, 11.3 R-3 |

The column `requirement_refs_digest` (renamed from `requirement_ids_digest` at the contract session's request, contract 1955eb0) is in 0061 and 0062. A scratch database that applied the earlier SHA must re-run the chain.

Verified on the scratch cluster (section 3):
- `alembic heads` -> `0062_s6_r3_results (head)`: one head.
- `alembic upgrade head` from `0059_int_mark_inputs_fence`: passed.
- `alembic downgrade 0059_int_mark_inputs_fence` then `alembic upgrade head`: passed.
- The five new tables exist at head (`information_schema` count = 5).

Frozen revisions `0001` to `0059` are unchanged. Migration `0060` embeds the deployed `fn_issue_operation_proof` text at 0059, so its downgrade restores that text exactly.

## 2. Tests and counts

| Suite | Result |
|---|---|
| Full suite, final state (`uv run pytest -ra -p no:warnings`, all DB variables set, 1059 collected) | **1058 passed, 1 failed** (5484 s). The failure is `tests/committed/test_phase2_identity.py::test_an_activation_refused_after_its_approval_lapses_is_audited_through_activate`, a timing-sensitive test with a 6-second approval window that asserts one audit row. The module then passed 7 of 7 on two consecutive reruns (30.5 s and 30.2 s). A clean full run on the final SHA is not yet recorded |
| `tests/committed/test_ai_read_v1.py` (the 33 `ai-read/v1` PostgreSQL tests) | 33 passed |
| `tests/committed/test_specialist_confirmation.py` (new, PostgreSQL) | 22 passed (21 at the earlier run, plus the audit-attribution test added later) |
| `tests/hardening/test_privilege_audit.py`, `tests/integration/test_phase_a.py`, `tests/unit/test_rbac_engine.py` (re-run after pin and matrix update) | 78 passed |
| `tests/unit` (no database) | 312 passed |

The first full-suite run on the same branch before the final fixes gave `4 failed, 1054 passed`. The four failures were consequences of this change and were corrected, not skipped:
- `test_privilege_audit.py` (two cases): the pinned sets of functions executable by `webdesk_worker` and `webdesk_authority` now include the new guard functions. The pins were updated to the new sets.
- `test_rbac_engine.py` and `test_phase_a.py`: the new `Permission.SPECIALIST_EXECUTION_CONFIRM` needs a matrix row. Row added: Approver `GRANTED`.

No assertion was weakened and no test was removed.

### Confirmation and persistence tests (21)

- Canonical operation: Approver with membership only (1).
- Confirmation: authenticated Approver with grant confirms once and spends the proof; proof for another project refused and spends nothing; caller without the Approver role refused; Approver without the project access grant refused; proof single-use; lifetime limited to 1 to 900 seconds (DB check); revoked confirmation cannot be consumed.
- Consumption: one execution per confirmation; concurrent consumption has exactly one winner (two threads, row lock held by the first); mismatched binding does not spend the confirmation; expired confirmation refused at consumption; run leaving an active status refuses consumption.
- Persistence: provenanced family A result persisted, execution completed, audit redacted of content; invented citation digest rolls back the whole result; citation into another project refused; `SUPPORTED` finding without citation refused; worker cannot write `verified`; family B requires https and timezone-aware `checked_at`.
- Restricted boundary: `webdesk_app` cannot call confirm, begin or persist and cannot read or insert into the results tables (SQLSTATE 42501); `PUBLIC` has no EXECUTE on the persistence function.

## 3. PostgreSQL environment and isolation

- Fresh container `sprint6-fpr-pg`, image `postgres:16.4`, published only on `127.0.0.1:56580`. Created for this run; no other container or database was used. Port `55432` was not used. Port `5433` (the repository's default compose cluster) was not used. The G0 cluster on `56544` was not used.
- Roles created on this cluster only: `webdesk_owner` (superuser, provisioning), `webdesk_integration_owner` (LOGIN, CREATEDB, CREATEROLE), `webdesk_test_owner` (LOGIN, NOSUPERUSER), `webdesk_app_login` (LOGIN, NOSUPERUSER). Passwords were generated locally with `secrets.token_hex(24)` and stored in a file outside the repository (scratchpad, not committed). No password appears in this record, in Git, or in logs.
- Databases: `webdesk_integration` (owner `webdesk_integration_owner`) and `webdesk_hardening` (owner `webdesk_test_owner`).
- Documented test-only grants applied as `webdesk_owner` (per `docs/PHASE2_DEDICATED_TEST_CLUSTER.md`): group memberships of the integration owner with INHERIT and SET; membership of `webdesk_ceremony` for the test owner; `webdesk_test_clock` membership for the integration owner. These grants exist only on this scratch cluster and are not production configuration. No test assertion or grant check was relaxed to obtain a pass.
- Each committed-database test runs in its own namespace database, and the run removes them after teardown (test harness behaviour).

## 4. Static checks

| Command | Result |
|---|---|
| `uv run ruff check .` | All checks passed! |
| `uv run ruff format --check` on changed files (9 files) | 9 files already formatted |
| `uv run ruff format --check .` (whole repository) | 4 files would be reformatted: `0017`, `0019`, `0020`, `0040`. These are the four documented frozen-migration exceptions in `docs/RUFF_FORMAT_EXCEPTIONS.md`; unchanged by this work |
| `uv run mypy --strict src/webdesk` | Success: no issues found in 71 source files |

## 5. CI status

The repository contains no CI configuration (no `.github/` directory, no workflow files). **CI was not run and no CI PASS is claimed.** The equivalent local gates are the full suite (section 2), ruff and mypy (section 4).

## 6. Security and design notes

- The confirmation is produced only by a Foundation proof for `specialist.execution.confirm`. The actor comes from the proof, never from the caller. Role and membership are checked by the existing validator against `operation_authorization_rules`. The project access grant whose `permitted_actions` holds the key is checked in `fn_confirm_specialist_execution_with_proof` (OPEN-04).
- Expiry uses `now()` on the database. The lifetime is a check constraint of at most 15 minutes. The test clock is not used.
- Consumption is one `UPDATE ... WHERE state = 'confirmed' AND expires_at > now() AND <every binding> AND <run and project active>` in the same transaction as the execution record.
- Persistence is by `webdesk_worker` through a guard function only. No table grant to `webdesk_app` or `PUBLIC`. No HTTP write route was added.
- Refusals in the confirmation and consumption functions write one audit row and return NULL. Refusals in persistence raise, rolling back the whole result, and the caller records the failure.

## 7. Known gaps (not closed here)

- **Specialist identifiers:** `specialist_id` is checked for shape only. The seven canonical identifiers belong to the specialist registry, which is not in this repository.
- **Source allowlist:** `source_url` is checked for `https://` only. The approved allowlist (contract section 13) is not in this repository.
- **Per-citation outcome:** `check_outcome` is stored per finding. Contract 10.3 also lists it per citation; that is not implemented.
- **Expiry state:** an expired confirmation keeps state `confirmed` and is treated as expired by its `expires_at`. The contract's terminal `expired` state is not stored.
- **Public Python routes:** no HTTP route was added for confirmation or consumption. The contract defines none (section 6). The authority and worker call the guard functions.
- **Independent QA and production:** not performed. This is a development-team record. Production is not authorized.
- **Workspace (OPEN-11):** no workspace entity or check. Authorization is project-level only.
