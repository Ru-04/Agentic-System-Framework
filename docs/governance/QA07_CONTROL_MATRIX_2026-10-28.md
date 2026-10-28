# QA-07 control matrix (28 October 2026)

**Decision:** QA-07-MERGE-01. **Branch:** `claude/qa07-validation`. **Rule source:** GOVERNANCE section 11, C-1.
**Purpose:** separate what the development integration merge needs, what Sprint 6 production integration needs, and what live production needs. A merge control is never deferred because a production implementation is planned later.

Status values: **Implemented** (code and test on this branch), **Partial** (code exists, a named gap remains), **Not built** (no code).

## Class A: mandatory for the first development integration merge

| # | Control | Status | Implementation | Test evidence |
|---|---|---|---|---|
| A1 | A protected specialist operation runs only after a verified operator decision | Implemented | `specialists/harness.py` verifies before `provider.run`; `execute_verified` for non-specialist operations | `test_qa07_runtime_authority.py`; `test_qa07_rbac_wiring.py` |
| A2 | Decision binds actor, workspace, specialist, capability, request and granted actions | Implemented | `verify_operator_decision` mismatch checks; capability bound by adapter | `[wrong actor]`, `[wrong workspace]`, `[wrong specialist]`, `[wrong request]`, `test_adapter_refuses_a_capability_the_decision_does_not_name` |
| A3 | Expired and revoked decisions are refused | Implemented | `EXPIRED`, `REVOKED` checks at execution time | `[expired]`, `[revoked]`; pilot `expired` case |
| A4 | Missing or unknown decision is refused | Implemented | `MISSING` | `[missing]`; pilot `unknown decision` case |
| A5 | `run.start` is checked against the existing RBAC engine at execution time | Implemented (adapter) | `specialists/authorization.py` `rbac_permission_check` calls `rbac.engine.authorize` | `test_qa07_rbac_wiring.py` (Analyst + active membership permitted; Approver, Administrator-only, reviewer, inactive membership, inactive user, no roles refused) |
| A6 | Only Analyst with active project membership may start a run (C-1) | Implemented (via RBAC matrix) | `rbac/matrix.py` `RUN_START: {Analyst: ASSIGNED}` | As A5 |
| A7 | Missing trusted verifier fails closed | Implemented | `VERIFIER_MISSING` when `permission_check` is None | `test_a_missing_trusted_verifier_fails_closed`; pilot `no verifier` case |
| A8 | Workspace and actor must be identifiers the RBAC engine can evaluate | Implemented | `rbac_permission_check` refuses non-UUID values | `test_a_workspace_that_is_not_a_project_identifier_is_refused`; `test_the_rbac_check_refuses_an_actor_that_is_not_a_user_identifier` |
| A9 | Direct provider invocation is refused | Implemented | `require_harness_scope()` in every provider `run` | `test_direct_provider_call_outside_the_harness_is_refused[...]` |
| A10 | Direct evidence retrieval is refused | Implemented | `retrieve_approved_pages` requires scope before any transport call | `test_direct_evidence_retrieval_outside_the_harness_is_refused_before_any_request` |
| A11 | The pilot cannot create its own authority | Implemented | `run_pilot` takes caller `AuthorityContext`; retrieval runs only via `execute_verified`; no scope entry in `pilot.py` | `test_pilot.py` self-authorization cases: expired, wrong actor, no verifier, missing grant, unknown decision, other request. Each makes zero requests |
| A12 | Scope does not leak to other threads, to asyncio tasks, or after errors | Implemented | Scope is a `_Scope` object deactivated in `finally`; a copied context cannot reuse a closed scope | `test_a_provider_run_on_another_thread_cannot_inherit_the_harness_scope`; `test_an_asyncio_task_created_outside_the_scope_is_refused`; `test_a_task_created_in_the_scope_cannot_use_it_after_the_scope_closes` |
| A13 | Denials execute no protected action | Implemented | Refusal raised before provider or retrieval; call counts asserted | Call-count assertions in negative tests |
| A14 | Denial errors are sanitized | Implemented | Fixed text; code only in audit | `test_error_text_is_sanitized_and_names_no_identifiers` |
| A15 | Audit holds identifiers and outcome only | Implemented | `audit_entry` | `test_audit_holds_identifiers_and_outcome_but_no_task_text` |
| A16 | Existing platform run-start checks still apply | Implemented (unchanged) | `runs/service.py` `start_run` calls `authorize(RUN_START)` and audits denials | Existing RBAC and run tests (unchanged) |
| A17 | No new role or permission created | Implemented | `RUN_PERMISSION` equals `Permission.RUN_START`; asserted | `test_run_permission_matches_the_existing_rbac_permission` |
| A18 | R4 chain excluded; no migration or dependency change | Implemented | No files from the excluded range; no migrations changed | Diff check in traceability report R12, R13 |
| A19 | Source restrictions and synthetic labelling preserved | Implemented (unchanged) | Two active pilot boundaries; `[SYNTHETIC]` labels | `test_capability_overstatement.py`; `test_pilot.py` |

## Class B: required for Sprint 6 production integration (not built)

| # | Control | Status | Required before |
|---|---|---|---|
| B1 | Operator-decision issuance through the trusted application workflow (approval UI or API, with actor identity from the session) | Not built. Test fixtures only | Any protected run executing in production |
| B2 | Persistent decision store with revocation visible across processes, backed by platform authorization tables | Not built. In-memory only | Any run in production |
| B3 | Specialist execution wired into the run workflow, through the verified harness only | Not built. Specialist execution is not reachable from `runs/service.py` today | Connecting specialists to runs |
| B4 | Audit entries written to the platform audit table, not an in-memory list | Not built | Production audit obligations |
| B5 | Workspace identifier for specialist requests equal to the project identifier, with classification passed to RBAC | Not built. The investigation tests use `ws-*` synthetic identifiers, which the production verifier refuses (fail closed) | Connecting specialists to real projects |
| B6 | Process-boundary protection against hostile in-process code (the context variable is not a security boundary) | Not built. Reviewer decision required | Production deployment |
| B7 | Pilot execution entry point (operator workflow) | Not built. The pilot can run only with a verified caller authority | Any pilot run outside tests |

## Class C: required before any live production operation

| # | Control | Status |
|---|---|---|
| C1 | Integration test of the RBAC check against the PostgreSQL store (`rbac/sql_store.py`) | Not built for this check |
| C2 | Live LLM execution stays disabled until its own approval | Unchanged, disabled |
| C3 | Source activation beyond the two pilot boundaries requires its own approval | Unchanged |
| C4 | Independent security review and penetration testing of the authorization boundary | Not performed |
| C5 | Independent QA sign-off by PG for production (not the development merge) | Not requested |
| C6 | Operational monitoring and alerting on authorization denials | Not built |

## Notes for the reviewer

- Class A is what the development merge requires. Every A-row has code and a test on this branch, subject to CI on the final SHA.
- Class B rows are the reason production integration stays blocked. They are not reasons to waive a Class A control.
- Specialist execution is not reachable from the run-start workflow today (checked by import search over `src/webdesk/runs` and `src/webdesk/api`). The merge therefore adds the gate for the specialist path without changing any live route.
