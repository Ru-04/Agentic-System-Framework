# M1 Sprint 1 — Shared Specialist Foundation: Sprint Completion Report

> **Correction (QA closure):** Sections 4 and 6 below are superseded. Independent QA on `cce425f` found 11 in-scope defects, and one design defect (QA-07) remains open. Sprint 1 status is **BLOCKED**. See [M1_S1_QA_CLOSURE_REPORT.md](M1_S1_QA_CLOSURE_REPORT.md) for the current status, findings and fixes.

**Baseline:** Specialist Delivery Implementation Baseline v1.0 (frozen)
**Branch/worktree:** `claude/webdesk-specialist-baseline-v1-3b21b1`
**Status:** Implementation complete and tested by the implementer. **Not signed off.** QA sign-off is required before the sprint can be marked Completed (Definition of Done).

## 1. Tasks completed (S1 deliverables)

| Deliverable | Where |
|---|---|
| Versioned common input/output contract (`1.0.0`) | `src/webdesk/specialists/contract.py` |
| Interface and error model (7 error codes, retryable flag) | `src/webdesk/specialists/errors.py` |
| Seven specialist category IDs mapped to registry IDs | `src/webdesk/specialists/catalog.py` |
| Workspace isolation (request, evidence, output, finding scope) | `src/webdesk/specialists/workspace.py` |
| Authority boundaries (deny by default; forbidden actions listed) | `src/webdesk/specialists/authority.py` |
| Shared mock harness and single execution path | `src/webdesk/specialists/harness.py`, `src/webdesk/specialists/mock.py` |
| CI checks (format, lint, mypy strict, unit tests) | `.github/workflows/specialist-ci.yml` |

No existing module was modified. Core orchestrator, schema, auth and migrations are untouched.

## 2. Files created or modified

Created:
- `src/webdesk/specialists/__init__.py`, `catalog.py`, `contract.py`, `errors.py`, `authority.py`, `workspace.py`, `harness.py`, `mock.py`
- `tests/unit/test_specialist_contract.py`, `tests/unit/test_specialist_harness.py`
- `.github/workflows/specialist-ci.yml`
- `docs/M1_S1_SPRINT_COMPLETION_REPORT.md` (this file)

Modified: none.

## 3. Tests executed and results

| Check | Command | Result |
|---|---|---|
| Baseline before changes | `uv run pytest tests/unit -q` | 166 passed |
| Format | `uv run ruff format --check src tests` | 117 files already formatted |
| Lint | `uv run ruff check src tests` | All checks passed |
| Type (strict) | `uv run mypy` | Success: no issues in 62 source files |
| Unit + specialist contract | `uv run pytest tests/unit -q` | **208 passed** (166 existing + 42 new) |

Not run: integration tests (`tests/integration`, `tests/committed`, `tests/hardening`). They need PostgreSQL (`WEBDESK_TEST_DATABASE_URL`) and do not touch the new package, so the new code does not change their results. They were not executed in this session.

New test coverage:
- Contract: seven categories match governance; each registry ID exists in `AGENT_REGISTRY.yaml`; extra or authority fields rejected on request and output; invalid fields rejected; cited findings require evidence; incomplete output must declare unknowns.
- Harness: honest default output; determinism; all seven categories conform; unsupported version, invalid input, and specialist mismatch are refused before the provider runs.
- Authority: forbidden actions (`approve_artifact`, `grant_permission`, `modify_routing`, `accept_inferred_requirement`, `write_requirement`, `resolve_blocker`) and unlisted actions are denied before any provider call.
- Workspace: cross-workspace evidence in the request, output, or findings is refused; the refusal does not name the other workspace.
- Error model: provider exceptions become retryable `PROVIDER_FAILURE` without leaking the exception text; only that code is retryable; malformed output and output that does not echo the request identity are refused.

## 4. Defects found and fixed

- Formatting drift in the new test file (fixed by `ruff format`).
- One lint error (E501, 104 > 100 chars) in `specialists/__init__.py` docstring (fixed).

No functional defects were found by the test run. The test run was not a substitute for independent QA.

## 5. Remaining blockers

1. **Approved v2.0 seven specifications are not in this repository.** The baseline requires contract verification against them. The repo holds `AGENT_REGISTRY.yaml` version `0.3.10-foundation-gate1-review`, marked `working_draft_unapproved`. Contract verification was done against that draft only. Needs: the v2.0 documents committed or supplied.
2. **3dcart / Shift4Shop canonical name and ID are pending** (DECISION_REGISTER D-01, D-15, C-01). The category uses the legacy ID `CAP-3D-CART-SHIFT-SHOPIFY`. Needs your decision before the ID is treated as final.
3. **Governance blocker on specialist routing:** the registry states structured routing (`structured_rules_status: pending_controlled_vocab_and_predicates_C05`, `machine_routing_enabled: false`). S1 does not implement routing, so this does not block S1, but it blocks S6 routing work.
4. **Outstanding Phase 1 gates are unchanged.** Restricted production integration and AI activation remain blocked (e.g. `P-INC3-PHASE1-CLOSE-07` proof rollback/reset-policy conformance gap). S1 does not touch them.
5. **Independent QA sign-off is missing.** Milestone M1 gate also requires an independent engineer's review of contract conformance and segregation of duties. Not performed.
6. **Changes are uncommitted** in the worktree. Commit and push have not been done.

## 6. Sprint acceptance status

| Acceptance item | Status |
|---|---|
| Contract tests | Pass (in unit suite) |
| Mock-provider tests | Pass |
| Security boundary negative cases | Pass (authority, workspace, output injection) |
| Lint/type/build checks | Pass locally; CI workflow added, not yet run on a runner |
| Contract verified against approved v2.0 specs | **Not met** (specs not in repo; blocker 1) |
| QA sign-off (Definition of Done) | **Not met** (pending independent QA) |

**Sprint 1 status: Implementation complete; acceptance pending QA sign-off and blocker 1.** I have not marked it Completed.

## 7. Next approved sprint

**M1 Sprint 2 — Shared evidence/RAG retrieval/citation and freshness services; real Shopify API/doc investigation with stated limitations.** Not started, per the instruction to wait until Sprint 1 acceptance passes. Sprint 2 also needs the approved evidence-access rules, which the baseline does not define in this repo.
