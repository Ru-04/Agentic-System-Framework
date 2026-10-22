# M1 Sprint 1 — QA Closure Report

**Implementation commit reviewed:** `cce425f` (M1 Sprint 1: shared specialist foundation)
**Status:** **BLOCKED** — approved specification reconciliation cannot be completed (section 1). Sprint 1 is not closed. QA-07 and the Shift4Shop ID are now decided (section 5).
**Baseline:** Specialist Delivery Implementation Baseline v1.0 (frozen)

## 1. Approved specification reconciliation — BLOCKED

Searched: this repository (all branches and worktrees under `D:\WDS\Agentic System FrameWork`), `C:\Users\baps\Downloads`, and the Downloads zip packages.

Result:
- No approved v2.0 seven-specialist specification exists in any searched location.
- The only 16 October 2026 artifact is the v0.3.10 package (`WebDesk_Agentic_Requirement_Platform_Specs_v0.3.10_FINAL_INDEPENDENT_REVIEW.zip`). Its README states: "FOR INDEPENDENT RE-REVIEW ONLY — NOT APPROVED FOR IMPLEMENTATION." Its registry is `status: working_draft_unapproved`.
- Governing decisions that are confirmed: D-01 (Shift4Shop/3dcart is an independent eCommerce platform, not a Shopify migration or 3D visualiser). The contract matches this: `SpecialistId.SHIFT4SHOP` is independent of `SHOPIFY`.

Documents required to unblock:
1. The approved v2.0 specialist requirements (dated 16 October 2026), with an approval record.
2. Confirmation that the v0.3.10 draft is superseded by that approved set, or the list of approved decisions that apply.
3. Decision on the canonical name and ID for the Shift4Shop specialist (D-01, D-15, C-01). `CAP-3D-CART-SHIFT-SHOPIFY` is kept as a legacy alias. It still carries "SHOPIFY" in its name, and this ID is provisional.

Not decided here: no approved decision was assumed, and no frozen requirement was changed.

## 2. Independent QA — code review and adversarial testing

Performed by a separate QA agent with no implementation context. It read the code, ran the tests itself, and wrote a temporary adversarial file, which it deleted afterwards. No source was edited by that agent.

Findings and resolution:

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| QA-01 | High | Provider could rewrite the request and move the workspace check onto the rewritten value | **Fixed.** Identity is captured before the provider runs. Provider gets a deep copy. Regression tests added. |
| QA-02 | Medium | Incomplete output accepted blank unknowns (`""`, `"  "`) | **Fixed.** Unknowns are non-blank. |
| QA-03 | Low | Whitespace-only identifiers and text accepted | **Fixed.** Shared `NonBlank` type on all identifiers and text. |
| QA-04 | Medium | Provider chose the error code and its message, including another workspace ID, reached the caller | **Fixed.** Any provider exception becomes `PROVIDER_FAILURE` with a fixed message. |
| QA-05 | Low | Raw exception text reachable through `__cause__` | **Fixed.** `from None`. `__suppress_context__` is set. Residual: `__context__` still holds the original exception object in memory. |
| QA-06 | Medium | Forbidden actions enforced only through the allowlist | **Fixed.** Forbidden list is checked first and is independent of the allowlist. |
| QA-07 | Medium (design) | Authority is a self-declaration. The harness does not mediate what the provider's code does at run time. | **Deferred by decision (user, Sprint 1).** Declaration check stays in Sprint 1, documented in `authority.py`. Run-time enforcement moves to the orchestrator and database layer in M3 S6 (core-owned). Residual risk: a provider can perform an action it did not declare until M3 S6. |
| QA-08 | Low | Malformed declared actions raised raw `TypeError` | **Fixed.** Fail closed with `CAPABILITY_DENIED`. |
| QA-09 | Low | Non-mapping request raised `AttributeError` | **Fixed.** `INPUT_INVALID`. |
| QA-10 | Low | `SpecialistError` did not survive pickling | **Fixed.** `__reduce__` added. |
| QA-11 | Low | Caller received the provider's own output object | **Fixed.** Output is re-validated from a copy. |
| QA-12 | Low (informational) | Evidence existence and free-text workspace leakage are not checked | **Out of Sprint 1 scope.** Belongs to the Sprint 2 evidence services. |
| QA-13 | Low (documentation) | Completion report claimed no defects and passing security negatives | **Corrected** by this report. See section 6 of `M1_S1_SPRINT_COMPLETION_REPORT.md`, which now carries a correction banner. |

Adversarial cases, from the QA agent's run of 101 cases: 81 passed, 20 failed. The 20 failures map to QA-01 to QA-11. After the fixes, the failing cases are covered by the 29 regression tests in `tests/unit/test_specialist_qa_regressions.py`.

No defects were found in: action-name casing and whitespace; nested extra keys; lookalike workspace IDs; empty identifiers; type coercion; `contract_version` variants; cross-category requests and outputs; enum casing; retry classification; and ordering (the provider is never called on any refusal).

## 3. Tests

| Check | Command | Before fixes (QA agent) | After fixes |
|---|---|---|---|
| Format | `uv run ruff format --check src tests` | pass | pass (118 files) |
| Lint | `uv run ruff check src tests` | pass | pass |
| Type (strict, `src/webdesk`) | `uv run mypy` | pass | pass (62 files) |
| Unit suite | `uv run pytest tests/unit -q` | 208 passed | **237 passed** |
| Regression file | `uv run pytest tests/unit/test_specialist_qa_regressions.py` | n/a | **29 passed** |
| Adversarial scratch | QA agent, deleted afterwards | 81 passed, 20 failed | not retained |
| Integration + committed (`tests/integration`, `tests/committed`) | PostgreSQL 16.4 | not executed | **223 passed** (local Docker Postgres, migrated to head) |
| Hardening (`tests/hardening`) | non-superuser owner and login roles | not executed | **75 passed** (local Docker Postgres, roles provisioned as in the handoff doc) |
| Full suite (`uv run pytest -q`, all env vars set) | all of the above | not executed | **535 passed** |
| CI workflow on ubuntu-latest | GitHub runner | not executed | **not executed** — no runner access; the workflow has never run remotely |

Environment: the test database ran in a throwaway container `webdesk-s1-qa-pg` on host port 5434. Port 5433 was already held by another project's container, which was not touched. Hardening was migrated as the superuser, because the migrations grant roles that the non-superuser owner cannot grant. `webdesk_test_owner` was then granted `webdesk_ceremony`, as the handoff doc describes. Environment-setup failures were fixed before the final run. No test code was changed to make a suite pass.

Note: the CI workflow runs `mypy`, which is configured for `src/webdesk` only. Tests are not type-checked. The CI step label now says so.

## 4. Phase 1 restrictions

The change is confined to new files under `src/webdesk/specialists/`, new tests, one CI workflow, and docs. No existing module, migration, role grant, authority service, or gate was modified (`git show --stat cce425f` shows 0 deletions and no existing files changed). The new package does not import from or call the authority, session, or privilege code. No production integration or AI activation is enabled.

## 5. Remaining blockers

1. Approved v2.0 specification (section 1). **Blocks Sprint 1 closure.**
2. QA-07: **resolved by user decision** (defer run-time enforcement to M3 S6). Residual risk recorded above.
3. Shift4Shop canonical name and ID (D-01 / D-15 / C-01): **user decision — keep legacy ID `CAP-3D-CART-SHIFT-SHOPIFY` as provisional.** Canonical alias still pending approval.
4. CI workflow not executed on a GitHub runner.
6. Independent human QA sign-off. The QA agent is independent of the implementation author, but it is not a human signatory, and the Definition of Done requires QA sign-off.

## 6. Commit and working-tree status

- Implementation commit: `cce425f`.
- Fixes and regression tests: **uncommitted** in the worktree.
  - Modified: `src/webdesk/specialists/authority.py`, `contract.py`, `errors.py`, `harness.py`, `.github/workflows/specialist-ci.yml`.
  - New: `tests/unit/test_specialist_qa_regressions.py`, `docs/M1_S1_QA_CLOSURE_REPORT.md`.
- No merge, push, stash, or protected-branch change has been made.

## 7. Final Sprint 1 status

**BLOCKED.**

- Specification reconciliation: BLOCKED (no approved v2.0 specification available).
- Code QA: completed. All in-scope defects fixed and retested. One design defect (QA-07) deferred to M3 S6 by user decision.
- Required testing: full suite passes (535), including integration and hardening. CI on a GitHub runner is not executed.
- Sprint 2 not started.
