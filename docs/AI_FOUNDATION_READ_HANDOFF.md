# AI–Foundation read integration: handoff for independent security and contract review

Contract: `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` (`ai-read/v1`, WDS-approved). Baseline: S0 `82585db`
(`docs/AI_FOUNDATION_S0_MANIFEST.md`). Migration: `0041_ai_read_v1` (additive).

## 1. D-AI rulings implemented

| Ruling | Implementation |
|---|---|
| D-AI-1 identity | `POST /runs/{run_id}/ai-principal` (human session plus proof `ai.principal.issue`, resource = the run's project). The authority generates the token and calls `webdesk_guard.fn_issue_ai_principal_with_proof`. The database consumes the proof, sets `bound_user_id` from the proof actor, and stores only the SHA-256 hash. Scope is one project and one run. The AI principal never inherits membership; every read also requires the bound human's current membership or project access grant (`fn_ai_resolve`). |
| D-AI-2 restricted | Restricted content is refused for every principal (`fn_ai_version_gate`, `fn_ai_list_versions`). Quarantined content is never listed, read or acknowledged. The contract's exception path does not exist in v1. |
| D-AI-3 lifecycle | TTL at most 900 seconds, enforced by a table `CHECK` and the issuance function. Rotation revokes the previous live principal of the run (unique partial index). Explicit revocation via `POST /runs/{run_id}/ai-principal/revoke` (proof `ai.principal.revoke`). Run status, project status, bound-human status and membership are re-checked on every request. |
| D-AI-4 persistence | No AI write route exists. Every AI route is `GET`; any other method returns 405. Results and requirement records are not implemented. |
| D-AI-5 logging | One `audit_events` row per AI request, with principal identity (`ai-principal:<id>` or `ai-principal:unresolved`), project, run and resource references, correlation id, decision, status and bound-human id. Token values, hashes, content and segment text are never recorded. The database writes issuance and revocation rows, with no secret values. |

## 2. Endpoint and function inventory

Human routes (existing session plus proof):

| Route | Function | Notes |
|---|---|---|
| `POST /runs/{run_id}/ai-principal` | `issue_ai_principal` → authority `/v1/ai-principal/issue` → `fn_issue_ai_principal_with_proof` | Returns the token once |
| `POST /runs/{run_id}/ai-principal/revoke` | `revoke_ai_principal` → `fn_revoke_ai_principal_with_proof` | Returns the count revoked |

AI read routes (`AI-Principal` credential and `X-AI-Contract-Version: ai-read/v1`; `GET` only):

| Route | Database function | Limits |
|---|---|---|
| `GET /v1/ai/runs/{run_id}` | `fn_ai_get_run` | none |
| `GET /v1/ai/runs/{run_id}/project` | `fn_ai_get_project` | none |
| `GET /v1/ai/runs/{run_id}/source-versions` | `fn_ai_list_versions` | `limit` 1–100, keyset cursor |
| `GET /v1/ai/runs/{run_id}/source-versions/{id}/segments` | `fn_ai_version_gate`, `fn_ai_list_segments` | `limit` 1–200; text cut to 4,000 characters with `text_truncated` |
| `GET /v1/ai/runs/{run_id}/source-versions/{id}/content` | `fn_ai_version_gate`, content store | at most 10 MiB, otherwise 413 |

Database credential resolver: `fn_ai_context` (granted to the application role) returns only the decision and identifiers for the
presented token. `fn_ai_resolve` is executable by no login role (the direct-call negative test passes).

## 3. Migration and interfaces (0041)

- New table `ai_principals`: no application-role privilege; the guard owner alone reads and writes it.
- Operations `ai.principal.issue` and `ai.principal.revoke` added to `operation_proofs` (constraint) and to the authority's
  allowlist (not to the Administrator list); rules: role Analyst, membership required.
- Functions: `fn_issue_ai_principal_with_proof` (authority only), `fn_revoke_ai_principal_with_proof`, `fn_ai_resolve`,
  `fn_ai_context`, `fn_ai_get_run`, `fn_ai_get_project`, `fn_ai_list_versions`, `fn_ai_version_gate`, `fn_ai_list_segments`.
- Round trip verified: fresh database to head; downgrade to 0029 and upgrade to head reproduce the head catalog exactly; the
  one-step downgrade of 0041 reproduces the 0040 catalog exactly.

Rollback note: the downgrade deletes the `ai.principal.*` proof rows and rule rows (it cannot re-add the constraint otherwise), then
drops the table and functions. Audit rows are kept.

## 4. Tests

- `tests/committed/test_ai_read_v1.py`: 24 cases over the real HTTP stack, restricted application role and in-process authority.
  Positive: issuance (token stored as hash only), run, project and version reads, segments and content. Negative: wrong token,
  human session on AI routes, other run, other project, quarantined, restricted with a restricted grant, explicit revocation,
  rotation, 60-second expiry (real clock), cancelled run (state injection), removed membership, disabled human, administrator
  without membership, client-supplied bound-human header ignored, contract header, method, pagination, oversized content (413),
  audit redaction and correlation, direct table read and insert refused, direct resolver call refused.
- `tests/hardening/test_privilege_audit.py`: pins updated for the new application and authority functions (17 pass).
- `tests/hardening/test_review_reproduction.py` and the earlier F1–F4 modules: still pass.

## 5. Results (2026-10-26, one ordered pass on fresh databases)

- Full suite: 645 passed, 1 error. The error is a teardown error (see section 6).
- Ruff lint: clean (`src`, `tests`, `migrations`).
- Ruff format: five files not formatted, all pre-existing (`docs/RUFF_FORMAT_EXCEPTIONS.md`).
- Mypy strict: clean, 57 source files.
- Migration fresh head, downgrade and upgrade: catalog-identical; 0041 one-step downgrade equals the 0040 catalog.

## 6. Open issues and limitations

1. **Teardown error in the full run.** One committed-suite test (`test_a_quarantined_version_is_never_listed_or_read`) reported an
   ERROR at fixture teardown: PostgreSQL refused `DROP DATABASE … WITH (FORCE)` because a session of another role was still open.
   The test passes alone (re-run). The likely cause is a connection that an earlier committed test left open. The same class of
   shared-cluster isolation issue was seen in the previous increment. It is not fixed here. It needs a harness fix before a
   final acceptance run.
2. Malformed requests refused before database work (missing contract header or scheme, bad identifier or limit) produce no audit
   row, because they have no principal or project (contract section 10).
3. No requirement, evidence, citation or analysis-result tables exist in Foundation. Under D-AI-4 they are required for the later
   write contract. They are a gap, not a v1 need.
4. The authority transport is loopback with a shared bearer secret (decision 7). The issuance route inherits that transport.
5. The 60-second expiry test takes about 66 seconds.
6. The run-state tests inject state (`cancelled`, `completed`) directly through the owner, to test the read gate in isolation.

## 7. Requirements for independent review

- Verify D-AI-1 to D-AI-5 against `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` section 2 and the implementation in section 1 above.
- Check that `fn_ai_resolve` and the public read functions cannot be reached except through `fn_ai_context` and the read functions.
- Check the classification rule (restricted, quarantined and human read right) and that `scan_status <> 'quarantined'` matches the
  human read path.
- Check the authority's issuance path and that the token is never logged or audited.
- Review the teardown issue (section 6.1) and the test isolation.

## 8. Readiness

- **READ CONTRACT READY (for independent contract review).** It is internally consistent, WDS-approved, and implemented.
  This is not an acceptance.
- **NON-PRODUCTION INTEGRATION READY FOR REVIEW.** Implemented and tested in an isolated non-production environment, with one open
  harness issue (section 6.1). Not accepted.
- **PRODUCTION INTEGRATION BLOCKED.** The authority transport is loopback with a shared secret (decision 7), production
  deployment is not approved, and email and secrets handling are out of scope. Evidence: `docs/PRODUCTION_BOUNDARY.md`.
