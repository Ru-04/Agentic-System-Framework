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

- `tests/committed/test_ai_read_v1.py`: 28 cases over the real HTTP stack, restricted application role and in-process authority.
  Positive: issuance (token stored as hash only), run, project and version reads, segments and content. Negative: wrong token,
  human session on AI routes, other run, other project, quarantined, restricted with a restricted grant, explicit revocation,
  rotation, 60-second expiry (real clock), cancelled run (state injection), removed membership, disabled human, administrator
  without membership, client-supplied bound-human header ignored, contract header, method, pagination, oversized content (413),
  audit redaction and correlation, direct table read and insert refused, direct resolver call refused.
- `tests/hardening/test_privilege_audit.py`: pins updated for the new application and authority functions (17 pass).
- `tests/hardening/test_review_reproduction.py` and the earlier F1–F4 modules: still pass.

## 5. Results (2026-10-26, one ordered pass on freshly rebuilt databases, after all corrections)

| Step | Result | Exit |
|---|---|---|
| Rebuild of integration and hardening databases | migrated to head 0041 | 0 |
| Full regression suite (`tests`) | 649 passed, 0 failed, 0 errors | 0 |
| AI v1 contract tests (`tests/committed/test_ai_read_v1.py`, 28 cases, part of the full-suite run) | passed, including non-empty parsed segments | 0 (full-suite run) |
| Restricted-login hardening (`tests/hardening`, privilege audit, reproductions, part of the full-suite run) | passed | 0 (full-suite run) |
| Ruff lint (`src`, `tests`, `migrations`) | all checks passed | 0 |
| Ruff format | 6 files not formatted, all documented in `docs/RUFF_FORMAT_EXCEPTIONS.md` (3 frozen migrations, committed revision 0040, 2 tests) | 1 (documented exceptions) |
| Mypy strict (`src/webdesk`) | no issues, 57 source files | 0 |
| Migration fresh head, downgrade and upgrade chain | upgrade head ok, downgrade to 0029 ok, upgrade to head ok, catalog equals fresh head | 0 |
| Migration 0041 one-step downgrade | catalog equals the 0040 catalog exactly | 0 |

## 6. Closure of issues raised in the previous review

1. **Teardown error (resolved).** The test database was dropped with `WITH (FORCE)`, which hid sessions left attached by
   earlier tests. Three observations: (a) idle owner-role connections were left by test engines that kept pooled connections;
   (b) the CLI installation engine in `src/webdesk/cli/install.py` was never disposed, which left a session attached to a test
   database after the in-process CLI tests; (c) the failing "permission denied to terminate" error came from a session of
   another role, and I did not capture its role in a run. Changes: test engines use `NullPool` (committed fixture, HTTP intake and
   AI tests); the drop no longer uses `FORCE` and fails naming any attached session; the CLI disposes its engine on every path.
   The ordered full run then reported 0 errors. That is one run, so the result is a single observation, not a proof of absence.
2. **Scan-status rule (ruled by WDS).** Recorded in `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` section 13A and
   `docs/GOVERNANCE_DECISION_REGISTER.md` P-INC3-AI-SCAN-07. No approved specification text is changed.
   - Gate 1 source eligibility: `not_scanned` remains eligible for authorized Foundation processing
     (`REQUIREMENT_SCHEMA.md` `RunInputSnapshot` and R1; `ARCHITECTURE.md` quarantines failed scans "when scanning is available").
   - AI v1 read authorization: a verified principal in scope may read non-quarantined, non-restricted content it is authorized
     for. Quarantined and restricted content is denied for every principal.
   - External model transmission: not authorized by `not_scanned`. Needs a separate content-safety, disclosure and deployment
     policy. Production integration remains blocked.
3. **Segment tests were vacuous (found and fixed).** The earlier segment assertions passed with no segments, because segments
   are produced only by the worker's parse step, which the test uploads never ran. The test upload now runs the parse step through
   the worker role, and the segment tests require non-empty results.
4. **Review gaps (added).** Bound-human Analyst role revocation refuses reads; a quarantined refusal is audited durably with its
   reason; text segments are cut to 4,000 characters with `text_truncated`; a request refused before database work writes no
   audit row (contract section 10 limitation).

## 7. Requirements for independent review

- Verify D-AI-1 to D-AI-5 against `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` section 2 and the implementation in section 1 above.
- Check that `fn_ai_resolve` and the public read functions cannot be reached except through `fn_ai_context` and the read functions.
- Check the classification rule (restricted, quarantined and human read right) and that `scan_status <> 'quarantined'` matches the
  human read path.
- Check the authority's issuance path and that the token is never logged or audited.
- Review the teardown issue (section 6.1) and the test isolation.

## 8. Readiness

- **READ CONTRACT READY (for independent contract review).** Internally consistent, WDS-approved, implemented, and tested.
  Not an acceptance.
- **NON-PRODUCTION INTEGRATION READY FOR INDEPENDENT REVIEW.** The full suite passes with 0 errors, and the migration and
  privilege checks pass. Independent acceptance is a separate gate.
- **PRODUCTION INTEGRATION BLOCKED.** The authority transport is loopback with a shared secret (decision 7), production
  deployment is not approved, and external model transmission is not authorized (contract section 13A). Evidence:
  `docs/PRODUCTION_BOUNDARY.md`.
