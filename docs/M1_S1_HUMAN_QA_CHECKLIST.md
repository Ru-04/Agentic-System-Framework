# M1 Sprint 1 — Human QA Acceptance Checklist

**Purpose:** for a human QA signatory to check the evidence and record a decision. Nothing in this file is a sign-off. Every decision field is blank until the signatory fills it in.

**Commit under review:** `84bc7db` or later. Reviewed set: `cce425f`, `a9482d2`, `84bc7db`, plus the uncommitted CI and report changes listed in `docs/M1_S1_FINAL_GATE_REPORT.md`.

## A. Evidence to read

| Ref | Document | What it shows |
|---|---|---|
| E1 | `docs/M1_S1_SPRINT_COMPLETION_REPORT.md` | Original implementation report. Sections 4 and 6 are superseded by a correction banner. |
| E2 | `docs/M1_S1_QA_CLOSURE_REPORT.md` | Independent QA findings QA-01 to QA-13, fixes, test matrix, residual risks. |
| E3 | `docs/M1_S1_FINAL_GATE_REPORT.md` | Specification reconciliation (BLOCKED), CI readiness, outstanding blockers. |
| E4 | `src/webdesk/specialists/` | Contract, errors, authority, workspace, harness, mock. |
| E5 | `tests/unit/test_specialist_*.py` | Specialist unit and contract tests (42 original tests). |
| E6 | `tests/unit/test_specialist_qa_regressions.py` | 29 regression tests for QA-01 to QA-11. |
| E7 | `.github/workflows/specialist-ci.yml` | CI definition (uncommitted changes listed in E3). |

## B. Test evidence (recorded runs)

| Check | Result | Source |
|---|---|---|
| Unit suite (`tests/unit`) | 237 passed | E2 section 3 |
| Integration and committed (`tests/integration`, `tests/committed`) | 223 passed | E2 section 3 |
| Hardening (`tests/hardening`) | 75 passed | E2 section 3 |
| Full suite (`uv run pytest -q`, all env vars set) | 535 passed | E2 section 3 |
| CI PostgreSQL job steps (replayed locally against `postgres:16.4`) | 298 passed | E3 section 4 |
| `ruff format --check`, `ruff check src tests migrations`, `mypy` (strict, `src/webdesk`) | clean | E2 section 3 |
| CI workflow on a GitHub runner | **not run** | E3 section 4 |

Reviewer: confirm the runs above, or re-run them. Record the run you used.

## C. Independent QA findings and their state

| ID | Severity | State | Reviewer decision |
|---|---|---|---|
| QA-01 | High | Fixed, regression test added | [ ] accept  [ ] reject |
| QA-02 | Medium | Fixed | [ ] accept  [ ] reject |
| QA-03 | Low | Fixed | [ ] accept  [ ] reject |
| QA-04 | Medium | Fixed | [ ] accept  [ ] reject |
| QA-05 | Low | Fixed. Residual: `__context__` still holds the original exception object in memory. | [ ] accept  [ ] reject |
| QA-06 | Medium | Fixed | [ ] accept  [ ] reject |
| QA-07 | Medium (design) | **Deferred to M3 S6 by user decision.** Authority is declared, not enforced at run time. | [ ] accept residual risk  [ ] reject |
| QA-08 | Low | Fixed | [ ] accept  [ ] reject |
| QA-09 | Low | Fixed | [ ] accept  [ ] reject |
| QA-10 | Low | Fixed | [ ] accept  [ ] reject |
| QA-11 | Low | Fixed | [ ] accept  [ ] reject |
| QA-12 | Low (informational) | Out of Sprint 1 scope. Evidence existence not checked. Sprint 2. | [ ] accept  [ ] reject |
| QA-13 | Low (documentation) | Corrected by E2 and the banner on E1 | [ ] accept  [ ] reject |

## D. Security and governance boundaries

| Boundary | Evidence | Reviewer decision |
|---|---|---|
| No Phase 1 control bypassed. The change adds files under `src/webdesk/specialists/` and tests, and does not modify existing modules, migrations, role grants or gates. | `git show --stat cce425f` and `git show --stat a9482d2`: no existing source files changed. Hardening suite passes (75). | [ ] confirm  [ ] reject |
| No production AI activation or restricted production integration | Specialist package has no import of authority, session or privilege code. No model or provider call. | [ ] confirm  [ ] reject |
| Specialists cannot approve, grant, route or accept requirements | Forbidden actions list and tests in `authority.py` and `test_specialist_qa_regressions.py` (QA-06). Declaration only, see QA-07. | [ ] confirm  [ ] reject |
| Workspace isolation on request, evidence, output and findings | Tests in `test_specialist_harness.py` and `test_specialist_qa_regressions.py` (QA-01). | [ ] confirm  [ ] reject |
| Shift4Shop treated as an independent platform (D-01) | Catalog keeps `SHIFT4SHOP` separate from `SHOPIFY`. Legacy ID `CAP-3D-CART-SHIFT-SHOPIFY` kept as provisional by your decision. | [ ] confirm  [ ] reject |

## E. Specification and approval status

| Item | Status | Reviewer decision |
|---|---|---|
| Approved v2.0 specialist package (16 Oct 2026) available | **Not available** (E3 section 1) | [ ] received  [ ] not received |
| Gate 1 authorization (16 Oct 2026) excludes specialist work | Stated in `GATE1_IMPLEMENTATION_AUTHORIZATION.md` | [ ] acknowledge |
| Conflict: Gate 1 says "implementation-ready"; seven documents say "NOT implementation-approved" | Unresolved (E3 section 1) | [ ] resolved  [ ] open |

## F. Unresolved risks

1. QA-07: specialist authority is not enforced at run time until M3 S6.
2. Approved specification not available. The implementation is not checked against an approved contract.
3. CI not run on a GitHub runner. Runner-specific behaviour unverified.
4. Milestone M1 independent testing (separate from implementation) not performed.
5. The sign-off record for human QA is not in the repository.

## G. Sign-off (to be completed only by the human QA signatory)

- Signatory name: ______________________________
- Role: ______________________________
- Commit reviewed (SHA): ______________________________
- Decision: [ ] PASS   [ ] FAIL   [ ] PASS WITH CONDITIONS (list below)
- Conditions: ______________________________
- Date: ______________________________
- Signature or approval reference: ______________________________

*This checklist does not record sign-off. The signatory's decision is recorded only in section G, once completed by them.*
