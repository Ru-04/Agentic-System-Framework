# QA-07 merge authorization request (29 October 2026)

**Decision:** QA-07-MERGE-01. **Status: HOLD. No merge has been executed.**
A merge requires the Authorized Approver's explicit approval of the exact candidate SHA below.

## Exact commits

| Item | Value |
|---|---|
| Candidate (QA-07 branch head) | `bb06554dd3365df8d9f8b6b3fc13a463a34b1715` (`claude/qa07-validation`) |
| Target | `740b1695555303b29323a58df3e2345663d9821d` (`feature/increment-1-foundation`) |
| Ancestry | Target is an ancestor of candidate (verified). Candidate is 91 commits ahead |
| Changed files vs target | 184 |

## CI

- **Run #60 on `bb06554` passed.** Reported to WDS by the Authorized Approver on 29 October 2026, and not re-queried in this session.
- Earlier runs on this branch: #53–#55 success, #56 failure on `3930a69` (log not accessible), #57 `8304d2c` success, #58 `d60e794` success, #59 `f4e0f96` success.
- The #56 failure is not proven to be caused by the pilot audit assertion. The failing test name is unknown. The #57 run on the corrected assertion passed.
- Local pytest is blocked by Windows Application Control (error 4551). It is not bypassed. Local ruff and mypy were run earlier. CI is the test record.

## PG (independent QA) evidence

- **Management-reported:** PG reported PASS with zero defects. WDS recorded this as management-reported only.
- **Missing from repository:** PG's personal independence declaration, review scope, reviewed SHA, findings, decision and attestation. The file `docs/governance/PG_INDEPENDENCE_DECLARATION_TEMPLATE_2026-10-26.md` is still a blank template.
- **Coverage gap:** Nothing in the repository shows that PG reviewed any commit. Every commit from `8304d2c` onward, including `bb06554`, is unreviewed by PG on the record.
- No PG content has been written by this session.

## QA-07 disposition

Engineering controls verified in this session (see `QA07_CONTROL_MATRIX_2026-10-28.md`, Class A):

1. **No protected specialist execution without trusted operator authorization.**
   - `specialists/harness.py` runs `verify_operator_decision` before `provider.run`. A refusal raises before the provider is called.
   - Every provider `run` in `specialists/mock.py`, `platforms/generic.py`, `platforms/shopify.py`, `synthetic_slice.py` and `investigation/specialists.py` calls `require_harness_scope()` first. Retrieval (`investigation/retrieval.py`) does the same.
   - The only callers of `run_specialist`, `call_adapter` and `retrieve_approved_pages` in `src/` are the harness, the adapter and the pilot. The pilot runs only through `execute_verified`.
   - No production code constructs an `AuthorityContext` or a `permission_check`. A protected operation therefore cannot run from production code today. The reason is that no trusted issuer exists, not that one has been verified (B1).
2. **Run-start and RBAC.**
   - `runs/service.py` `start_run` calls `authorize(SqlAuthorizationStore(conn), actor, RUN_START, ...)` and audits denials. This is the existing platform check.
   - Nothing under `src/webdesk/runs` or `src/webdesk/api` imports `specialists` or `investigation`.
   - `rbac_permission_check` calls the same `rbac.engine.authorize` with the existing `run.start` permission. It is unit-tested with a fake store only. The SQL-backed check is not integration-tested (C1).
3. **Disabled by default and fail closed.**
   - No live LLM SDK import exists in `src/` (checked: no `anthropic` or `openai` imports).
   - No runtime enable flag exists. The protected path has no caller in production. A missing verifier raises `VERIFIER_MISSING`. A missing decision raises `MISSING`.
   - Note that "disabled by default" here means "unreachable in production", not a configuration switch.
4. **Production-only controls (conditional disposition, not implemented):** Class B (B1–B7) and Class C (C1–C6) in the control matrix. These stay blocking for production integration and live operation. They are not claimed as implemented, and they are not required for the development merge, which is limited to the Class A controls.
5. **Migration head, R4 exclusion, branch rules.**
   - `alembic heads` returns a single head: `0019_least_privilege_intake_and_workflow`.
   - Migrations 0020–0027 are absent. No R4-named path is in the diff.
   - No `pyproject.toml`, `uv.lock` or migration file differs from the target.
   - Target branch protection: API reports `protected: false`. Rule details returned 401 with the available credentials. Required checks are **unverified**.

## Known limits (not closed by this merge)

1. Decision store is in-memory. Revocation is an in-memory flag (B2).
2. No trusted issuer of operator decisions exists. The test fixtures `pilot_authority` and `_authority` are the only issuers (B1, B7).
3. The SQL-backed RBAC check is not integration-tested (C1).
4. `harness_scope` is public, so in-process code can enter it. The control refuses direct and accidental calls only (B6).
5. The permission check passes data class `internal`. Production must pass the real classification (B5).
6. The workspace must be a project UUID. Synthetic `ws-*` identifiers are refused, so the pilot cannot run against production data (B5).
7. Six deleted lines in `intake/reassess.py`, `tests/hardening/conftest.py` and `tests/integration/test_gate1_schema.py` come from commit `79c90bc`. They were checked as syntax-tree identical to the target in this session. PG should re-verify independently.

## Remaining blockers before a merge

1. **PG's personal review record** must be in the repository, bound to an exact SHA that covers `bb06554`. Without it, the QA gate is open.
2. **Branch protection and required checks** must be confirmed with authorized access.
3. **WDS formal disposition** of known limits 1–6 (accepted as development-only risk, or remediated).

## Recommendation

**HOLD.** Do not merge `bb06554` into `feature/increment-1-foundation` until blockers 1–3 are closed and the Authorized Approver approves the exact SHA `bb06554dd3365df8d9f8b6b3fc13a463a34b1715`.

## Approval record

- Approved candidate SHA: [Authorized Approver to state]
- Approver: [Authorized Approver to sign]
- Date: [Authorized Approver to record]
