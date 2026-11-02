# M2 Sprint 5: requirement-to-test matrix and engineering status (2 November 2026)

**Status: engineering status only. Sprint 5 is NOT accepted.** No threshold is approved. PG independent QA has not been received. This matrix maps the directive S5-COMPLETE-AUTH-01 and the Sprint 5 plan (`SPRINT5_PLAN_2026-10-30.md`) to evidence. It adds no acceptance criteria.

Branch `claude/sprint5-specialist-evaluations`. Base commit when this work started: `46e3418`. Remote head at start: `46e3418`. `f175812` is an ancestor of it.

## 1. Engineering verification (this change set)

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check src tests` | All checks passed |
| Format | `ruff format` on changed files | Applied; clean |
| Strict types | `mypy --strict src/webdesk/evaluation src/webdesk/investigation` | No issues in 9 files |
| Unit and integration suite | `pytest tests` | 915 passed, 128 skipped |
| Skips | PostgreSQL and hardening tests | Skipped: `WEBDESK_TEST_DATABASE_URL` and `.env.hardening.local` are not configured in this worktree. **Not run here.** CI must run them |
| Sprint 5 unit tests | `tests/unit/test_sprint5_harness.py`, `test_sprint5_scorecard.py` | 37 passed |

Results are against the local worktree. The final CI result for the pushed SHA is recorded in the acceptance package, not here.

## 2. Requirement-to-test matrix

| # | Requirement (directive or plan) | Evidence | Status |
|---|---|---|---|
| A | Baseline read; SHAs verified; requirement matrix | This file; `git rev-parse` at start: local and remote `46e3418` | Done |
| B1 | Seven specialists covered | Dataset v4 (`sprint5_scenarios_v4.json`, 30 scenarios, 3 to 6 per specialist). Test `test_the_v4_dataset_matches_its_manifest_and_covers_all_seven_specialists` | Done for requirement-level routing. **Coverage is partial**, see section 3 |
| B2 | Positive, negative and ambiguous cases | Scenario notes S5-012 to S5-030 tag each case | Done for the requirement-level dimensions only |
| B3 | Dimensions the runner cannot measure | Scorecard status column: citation correctness, evidence relevance, feasibility, practical suitability | Reported as not evaluable or not evaluated. Not hidden |
| C1 | S5-005 resolved (redirect) | Cause: **incorrect implementation**. The rule did not refuse a request to follow a redirect. Policy: `retrieval.py` ("Redirects are not followed"). Fix: `PROHIBITED_OPERATIONS` in `investigation/specialists.py`. Test `test_the_redirect_request_is_refused_before_any_capability_match` | Resolved |
| C2 | S5-007 resolved (out-of-catalog) | Cause: **incorrect implementation**. Order data is a named BigCommerce capability with no approved page (`bigcommerce.md` section 13). The rule returned CLARIFY, which is for requests naming no capability. Fix: `UNAPPROVED_CAPABILITIES` and `Decision.UNSUPPORTED_SOURCE`. Test `test_order_data_is_unsupported_source_not_clarification`. The no-capability case still CLARIFY: `test_a_request_naming_no_capability_still_clarifies` | Resolved |
| C3 | Regression tests for both | Listed above, plus page-level redirect regression `test_a_redirect_leaving_the_boundary_is_refused_at_page_level` | Done |
| C4 | Distinctions preserved | Unknown capability: CLARIFY. Missing requirement information: CLARIFY. Unsupported evidence source: UNSUPPORTED_SOURCE. Unauthorized operation: REFUSE. Verified unsupported platform capability: UNSUPPORTED_SOURCE (per spec). Tests in `test_sprint5_harness.py` | Done |
| D1 | Scorecards: per specialist, counts, matched and mismatched, failure categories | `src/webdesk/evaluation/scorecard.py`; committed output `docs/governance/SPRINT5_SCORECARD_2026-11-02.json`; reproducibility test | Done |
| D2 | Citation correctness, source applicability, version and edition, authorization failures | Scorecard fields `uncited_support`, `authorization_failures`, `dimensions_covered`. Citation correctness is **not evaluable** at requirement level | Partial by design |
| D3 | Requirement-level and real correctness kept apart | Scorecard `scope` field; real record `SPRINT5_REAL_EVIDENCE_RECORD_2026-11-02.md` | Done |
| D4 | Historical 9 of 11 preserved | Section 4 below | Done |
| D5 | Threshold proposal, not approved | `SPRINT5_THRESHOLD_PROPOSAL_2026-11-02.md` | Proposed; **not approved** |
| E1 | Real evidence for active pilot sources | Live approved pilot run, 2 November 2026: `SPRINT5_REAL_EVIDENCE_RECORD_2026-11-02.md` | Done for two pages. Findings narrow |
| E2 | Inactive sources: unsupported and unknown behaviour | v4 scenarios S5-001, 003, 008, 009, 010, 011, 012, 016, 024, 025, 027, 029 | Done at requirement level. No real evidence claimed |
| E3 | Source-activation proposal | Real record, section 4: none proposed here | Deferred to WDS per source |
| F1 | Shopify 55-pair engineering preparation | `SHOPIFY_55_LABELLING_HANDOFF_2026-11-02.md`; `human_status()` in scorecard; sheet digest recorded | Engineering prepared. **0 of 55 labelled. No rater named** |
| F2 | No fabricated labels | Scorecard reports `labelled: 0, total: 55` from the sheet itself | Done |
| G | Full applicable suite | Section 1 | Local: done. CI on the final SHA: see acceptance package |
| Stage 2 | Independent QA by PG | `SPRINT5_PG_QA_PACKAGE_2026-11-02.md` | **READY — DELIVERY PENDING.** No PG review exists |
| Stage 3 | Remediation | Not applicable until independent findings exist | Not started (no findings) |
| Stage 4 | Acceptance package | In the chat response; recommendation HOLD | Prepared, not approved |

## 3. Seven-specialist coverage, as measured

Counts are by expected class in dataset v4. Expected classes are not outcomes. They are what the contracts say should happen.

| Specialist | Scenarios | Supported routing (INVESTIGATE) | Version unknowns | Refusal | Unsupported source | Clarify | Source status |
|---|---|---|---|---|---|---|---|
| Shopify | 5 | 0 | 0 | 0 | 2 (S5-001, S5-012) | 3 (S5-002, S5-013, S5-014) | Inactive |
| Shift4Shop | 3 | 0 | 0 | 0 | 2 (S5-003, S5-016) | 1 (S5-015) | No approved source |
| WordPress / WooCommerce | 6 | 1 (S5-018) | 2 (S5-004, S5-017) | 2 (S5-005, S5-019) | 0 | 1 (S5-020) | **Active** (docs) |
| BigCommerce | 5 | 1 (S5-021) | 2 (S5-006, S5-022) | 0 | 1 (S5-007) | 1 (S5-023) | **Active** (product page, single product) |
| Magento / Adobe Commerce | 5 | 0 | 0 | 0 | 4 (S5-008, 009, 024, 025) | 1 (S5-026) | Inactive |
| Standalone Applications | 3 | 0 | 0 | 0 | 2 (S5-010, S5-027) | 1 (S5-028) | No technology source |
| Middleware Applications | 3 | 0 | 0 | 0 | 2 (S5-011, S5-029) | 1 (S5-030) | No product source |

Honest limits of this coverage:
- The runner never retrieves. Every "supported" result here is routing, not evidence.
- Only three specialists exercise the version rule with real text, and "positive" cases for inactive sources are expected UNSUPPORTED_SOURCE, which measures the boundary, not vendor capability.
- Workspace authorization, the adapter contract and operator refusal are covered by existing unit tests (for example `test_adapter_v02.py`, `test_seven_specialist_conformance.py`, `test_source_refusal_precedence.py`), not by the scenario set. They are not re-scored here.

## 4. Historical baseline (kept, not overwritten)

- Under the runner before this change, v3 scored **9 of 11**. Mismatches: S5-005 (observed CLARIFY, expected REFUSE) and S5-007 (observed CLARIFY, expected UNSUPPORTED_SOURCE). The 9 of 11 result is the record of that runner.
- Under the same pre-change runner, the new v4 scenarios scored **25 of 30**. Five mismatches: S5-005 and S5-019 (redirect, CLARIFY), S5-007 (order data, CLARIFY), and **S5-018 and S5-021** (INVESTIGATE_WITH_UNKNOWNS observed where INVESTIGATE expected). The S5-018 and S5-021 cause was a runner defect: `observe` passed `requested_version=None` for every scenario, so a version named in the requirement was ignored. The fix reads the stated version from the requirement text (`stated_version`).
- The v4 expectations were written from the specialist documents before the runner changed. Three of the five pre-change mismatches were implementation gaps. Two were the version defect above.
- After the change, v3 scores 11 of 11 and v4 scores 30 of 30. These are requirement-level results and do not show that the specialists are accurate.

## 5. Open contract conflict (WDS decision)

- **S5-011**: `middleware_applications.md` section 19 gives CLARIFY for "webhook delivery and retry requirement with no product named". The frozen scenario expects UNSUPPORTED_SOURCE. The runner follows the scenario. Either outcome is defensible: the specification's section 14 says CLARIFY when essential context is missing, and section 13 says vendor-specific behaviour is UNSUPPORTED_SOURCE. **Decision needed. The expectation has not been changed.**

## 6. Limitations and owners

| Item | Owner | Status |
|---|---|---|
| Thresholds for each dimension | WDS | Proposal only |
| Shopify 55-pair rater and adjudicator | WDS (name required) | Not named |
| PG independent QA | PG | Delivery channel not confirmed |
| Activation beyond two pilot sources | WDS, per source | Not requested |
| BigCommerce publisher ownership unconfirmed | WDS | Open (`sources.json`) |
| WooCommerce publisher partially verified | WDS | Open (`sources.json`) |
| BigCommerce page content changed since 28 Oct pilot | Engineering | Re-pinned 2 Nov; history not reconstructable |
| BigCommerce citation passage is an endpoint path, not a sentence | Engineering and WDS | Narrow claim kept; flagged |
| "18 evaluation dimensions" in plan section 4 | WDS | Source documents list 11. Plan count not reconciled |
| PostgreSQL and hardening tests | Engineering | Not run locally; CI |
| Sprint 6 | WDS | Not started. Requires separate authorization |
