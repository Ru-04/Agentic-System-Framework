# QA-07 runtime authorization: requirement-to-test traceability (28 October 2026)

**Decision:** QA-07-MERGE-01 (`MANAGEMENT_DECISION_REGISTER_2026-10-26.md`). The QA-07 gate blocks the merge of the first development PR. Management has not waived it.
**Branch:** `claude/qa07-validation`, based on the held candidate `79c90bc`. The protected target was not touched.
**Rule source:** GOVERNANCE section 11, C-1. Only a user with the `Analyst` role and an active project membership may start a run. The existing RBAC permission `run.start` is the bound permission. No new role or permission was created. `RUN_PERMISSION` is asserted equal to `webdesk.rbac.matrix.Permission.RUN_START`.

## Implementation
- `src/webdesk/specialists/authorization.py`: decision record, verification, harness scope, audit entry.
- `src/webdesk/specialists/harness.py`: `run_specialist` requires an `AuthorityContext`. It verifies the decision before the provider runs, runs the provider inside the harness scope, and audits each outcome.
- `src/webdesk/specialists/adapter_v02.py`: `call_adapter` requires an `AuthorityContext`. It refuses an actor that does not match the request, and it binds the decision to the canonical capability.
- Every provider `run` calls `require_harness_scope()`: investigation, synthetic slice, mock, generic platform, Shopify.
- `src/webdesk/investigation/retrieval.py`: `retrieve_approved_pages` requires the harness scope before any boundary check or transport call.
- `src/webdesk/specialists/errors.py`: new code `authorization_denied`. The error text is fixed.

## Requirement-to-test traceability

| Req | Requirement (management list) | Enforcement | Tests (`tests/unit/test_qa07_runtime_authority.py` unless stated) |
|---|---|---|---|
| R1 | Authorized, workspace-bound operator decision verified before the protected operation executes | `verify_operator_decision` runs before `provider.run` in the harness | `test_valid_decision_lets_the_harness_run_the_provider_once_and_audits_the_allowance`; `test_valid_decision_lets_the_adapter_complete_through_the_harness` |
| R2a | Missing decision fails closed | `MISSING` when id is blank or unknown | `test_every_mismatch_or_invalid_decision_is_refused_before_execution[missing]` |
| R2b | Invalid decision fails closed | `INVALID` on wrong permission or naive timestamp | `[wrong permission]`; `test_naive_timestamp_fails_closed` |
| R2c | Expired decision fails closed | `EXPIRED` when now is at or after expiry | `[expired]` |
| R2d | Revoked decision fails closed | `REVOKED` | `[revoked]` |
| R2e | Mismatched decision fails closed | `MISMATCH` on actor, workspace, specialist or request | `[wrong actor]`, `[wrong workspace]`, `[wrong specialist]`, `[wrong request]` |
| R2f | Permission revoked at execution time | `NOT_PERMITTED` from the permission check, which is the RBAC engine (`rbac_permission_check`) | `[permission revoked]`; `test_run_start_is_refused_without_an_active_analyst_and_membership` |
| R2g | Missing trusted verifier fails closed | `VERIFIER_MISSING` when `permission_check` is None | `test_a_missing_trusted_verifier_fails_closed`; pilot `[no verifier]` case |
| R2h | Non-Analyst, inactive membership, inactive user, no roles | RBAC `run.start` = Analyst AND active membership, through `authorize()` | `test_run_start_is_refused...[non-Analyst (Approver)]`, `[Administrator alone]`, `[technical reviewer]`, `[inactive membership]`, `[inactive user]`, `[no roles]` (`tests/unit/test_qa07_rbac_wiring.py`) |
| R2i | Non-UUID workspace or actor cannot be verified | Refused by `rbac_permission_check` | `test_a_workspace_that_is_not_a_project_identifier_is_refused`; `test_the_rbac_check_refuses_an_actor_that_is_not_a_user_identifier` |
| R3a | Action cannot be substituted | Granted actions must cover every declared action; forbidden actions are never grantable | `test_granted_actions_must_cover_every_declared_action`; `test_forbidden_grant_is_refused_even_when_listed_in_the_decision` |
| R3b | Workspace cannot be substituted | Decision workspace must equal request workspace | `test_a_decision_for_one_workspace_cannot_authorize_a_request_in_another` |
| R3c | Specialist cannot be substituted | Decision specialist must equal request specialist | `[wrong specialist]` |
| R3d | Request cannot be substituted | Decision request id must equal request id | `[wrong request]` |
| R3e | Approval scope (capability) cannot be substituted | Adapter binds the decision to the canonical capability | `test_adapter_refuses_a_capability_the_decision_does_not_name` |
| R3f | Actor cannot be substituted | Decision actor must equal authority actor, which must equal the adapter request actor | `test_adapter_refuses_an_actor_substitution_before_the_provider_runs` |
| R4a | Unauthorized request cannot reach provider execution | Denial raises before `provider.run`; provider call count stays 0 | Call-count assertions in every `[...]` case; `test_adapter_refuses...` |
| R4b | Unauthorized request cannot reach evidence retrieval | `retrieve_approved_pages` requires the scope before any transport call | `test_direct_evidence_retrieval_outside_the_harness_is_refused_before_any_request` (`tests/unit/test_qa07_runtime_authority.py`) |
| R4c | Protected side effects are blocked | Specialist runs are the only gate added. No specialist is invoked from the API, run or intake code (grep: none). Ingest, contact and identity paths call the existing `rbac.engine.authorize`. The run-start path was not re-checked in this change | Existing RBAC and API tests. Run-start authorization is an open item for review |
| R5a | Direct provider call cannot bypass the check | `require_harness_scope()` refuses outside the harness | `test_direct_provider_call_outside_the_harness_is_refused[investigation|synthetic_slice|mock]`; `test_a_direct_provider_run_is_refused_outside_the_harness` |
| R5b | Alternative adapter cannot bypass | Adapter requires `authority`; the harness is the only route to providers | `test_the_harness_cannot_be_called_without_an_authority_context` |
| R5c | Asynchronous execution cannot bypass | Scope is a context variable, so a worker thread does not inherit it | `test_a_provider_run_on_another_thread_cannot_inherit_the_harness_scope`. No specialist asynchronous path exists in scope (grep of `src/webdesk`) |
| R5d | Scope cannot leak after denial or error | Scope resets in `finally` | `test_scope_does_not_leak_after_a_denied_harness_run`; `test_scope_does_not_leak_after_a_provider_error_inside_the_harness` |
| R6a | Audit records decisions accurately | Each allow and deny appends an entry with the request workspace and the reason code | `test_valid_decision...` (allowed); every `[...]` case asserts `denied` and the code |
| R6b | Audit exposes no secrets or task text | Audit holds identifiers and outcome only | `test_audit_holds_identifiers_and_outcome_but_no_task_text`; `test_the_audit_record_names_the_request_workspace_not_the_decision_workspace` |
| R7 | Error responses stay sanitized | Fixed text `operator authorization was not verified`; the code goes only to the audit | `test_error_text_is_sanitized_and_names_no_identifiers` |
| R8a | Source restrictions preserved | Only the two pilot boundaries are active | `test_only_the_pilot_boundaries_are_active` (`tests/unit/test_capability_overstatement.py`) and the existing suite |
| R8b | Synthetic labelling preserved | Unchanged; existing suite | Existing `[SYNTHETIC]` tests |
| R8c | Production restrictions preserved | No production wiring added; no network code added | This report (section "Known limits") |
| R9 | Regression: permission equals existing RBAC permission | Asserted | `test_run_permission_matches_the_existing_rbac_permission` |
| R10 | Regression: forbidden declared actions still refused, and in the same order | `check_actions` still runs before authorization | `test_forbidden_declared_actions_are_still_refused_before_authorization` |
| R11 | Regression: all existing behaviour kept | Existing call sites supply a matching decision through test-support wrappers (`tests/support/authority.py`). Negative tests use production functions | Full unit suite: 908 passed locally |
| R12 | Migrations and dependencies unchanged | None changed | `git diff --name-only 79c90bc..HEAD` has no migration, `pyproject.toml` or `uv.lock` |
| R13 | R4 chain excluded | No file from `af37f7b`..`89634a8` is present | Checked: no migration `0020` to `0027` in the diff |

## Known limits (reviewer must assess)
1. **In-process bypass is not a security boundary.** The harness scope is a context variable, and `harness_scope` is importable. Code that deliberately imports it can enter the scope. The control refuses direct and accidental calls and calls from other threads. It does not stop malicious code in the same process. An independent reviewer must decide whether that is acceptable.
2. **The decision store is in memory.** `InMemoryDecisionStore` is the only implementation. There is no persistent store and no revocation across processes. Production needs a store backed by the platform's authorization data. That is not built, and production stays blocked (QA-07 production gate).
3. **Permission re-check uses the RBAC engine, through an adapter.** `rbac_permission_check(store)` calls `webdesk.rbac.engine.authorize` for `run.start`, with the workspace read as the project id. Tests use an in-memory store that implements the same protocol as the SQL store. The SQL store has not been exercised with this check in an integration test. Production must also pass the project's data classification (the adapter uses `internal`; the `run.start` rule ignores it, but this must be reviewed).
4. **Pilot self-authorization removed.** `run_pilot` no longer enters the harness scope. It takes an `AuthorityContext` from the caller and runs each retrieval through `execute_verified`, which verifies the decision first and then enters the scope. Missing, expired, revoked, mismatched or unverified decisions make no request. No production issuer of pilot decisions exists, so the pilot cannot run in production until the operator workflow exists. `pilot_authority()` in `tests/support` is a test fixture only.
5. **Test wrappers.** `tests/support/authority.py` issues matching decisions for existing tests. A test wrapper cannot mask a production refusal, because the negative tests call the production functions directly.
6. **Provider output tests.** Four provider-output tests call `run_in_harness`, which enters the scope explicitly. This is a test convenience, and the bypass tests cover the production route.

## Verification
- Previous local run, on `b5ea384`: 908 unit tests passed; ruff clean; strict mypy clean.
- Stage 1 revision (this commit): ruff check, ruff format and strict mypy clean locally. **Local pytest could not run in this session:** Windows Application Control (error 4551) blocked the pytest executable. Pytest was not rerun by another route. The CI run on the pushed SHA is the test record for this revision.
- Run-start path (`src/webdesk/runs/service.py` `start_run`): calls `authorize(RUN_START)` with the project, and audits denials. Nothing under `src/webdesk/runs` or `src/webdesk/api` imports `webdesk.specialists`, so **specialist execution is not reachable from the run-start workflow today.** That is why the specialist gate is not on a live path yet.
- CI: see the QA-07 merge package for the run bound to the final SHA.
