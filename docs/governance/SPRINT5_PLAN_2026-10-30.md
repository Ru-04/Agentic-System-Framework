# M2 Sprint 5 — Specialist Evaluations: plan and status (30 October 2026)

**Status: planning baseline and frozen inputs only. Engineering not complete. No Sprint 5 acceptance requested.**
**Branch:** `claude/sprint5-specialist-evaluations`, created from `e907861` (Sprint 4 baseline, CI run #52 success).

## 1. Frozen inputs (git blob hashes, first 12 characters)

| Input | Blob | Use |
|---|---|---|
| `docs/governance/SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md` | 4947d5648b18 | Scenario draft (not yet approved as a dataset) |
| `docs/governance/SPRINT4_5_ACCEPTANCE_RECONCILIATION_PROPOSED_2026-10-28.md` | 242f65cc2b45 | Proposed amended baseline; requires amendments before approval |
| `docs/evaluation/HUMAN_REVIEW_SHEET_SPRINT2.md` | 7133ea3de4f6 | 55-pair review sheet; no labels recorded |
| `docs/evaluation/HUMAN_REVIEW_PROTOCOL.md` | 5d8c73496020 | Rater definitions (DIRECT, PARTIAL, IRRELEVANT) |
| `docs/specialists/knowledge/sources.json` | c29455ea79b8 | Source registry |
| `docs/specialists/REAL_EVIDENCE_COVERAGE_2026-10-28.md` | cd28e96c7fb6 | Per-specialist evidence status |
| `docs/governance/SOURCE_PILOT_RESULTS_2026-10-28.json` | b174c69bd708 | Real pilot run results |

Blob hashes identify content. They are not evaluation-result hashes. Evaluation-result hashes will be recorded when results are produced.

## 2. Carried-forward obligations and where they are tracked

Tracked in `SPRINT4_CLOSURE_RECORD_2026-10-30.md` (O1–O7). Sprint 5 work maps to them:

- O1 (Shopify 55 pairs): engineering side (rater instructions, blinded sheet, agreement calculation) is in scope. The labels are **blocked** until WDS names an independent rater. No labels will be generated.
- O2 (source expansion): blocked on WDS approval per source. No source will be activated by this plan.
- O3, O4, O5: scenarios and harness in scope; real retrieval only for sources already active.
- O6, O7: PG-owned. Not performed here.

## 3. Work breakdown

| WP | Work | Status |
|---|---|---|
| WP1 | Frozen baseline and this plan | Done (this commit) |
| WP2 | Evaluation harness: runner, scoring, false-positive and false-negative reporting, citation validation, export, deterministic output | Not started |
| WP3 | Scenario datasets for all seven specialists, separated into synthetic, real-documentation, human-labelled and awaiting-source categories, with hashes and a leakage check | Not started |
| WP4 | Shopify 55-pair engineering side (instructions, sheet, agreement and error analysis) | Not started |
| WP5 | Real investigations for active sources only (WooCommerce docs, BigCommerce product page), with the verification list in section 5 | Not started |
| WP6 | Seven-specialist conformance and regression tests | Not started |
| WP7 | Full verification: ruff, strict mypy, unit, integration, PostgreSQL where relevant, CI | Not started |
| WP8 | PG QA package | Not started; PG delivery channel not confirmed |

## 4. Thresholds requiring WDS approval (not set here)

These are not historical decisions, and nothing is invented:

- Pass thresholds for each of the 18 evaluation dimensions.
- Repeatability: number of runs and the match rule.
- Scorecard definition per dimension.
- Agreement threshold for the 55-pair human evaluation.

Until approved, every result is reported as **threshold pending**, not PASS.

## 5. Verification list for each permitted real investigation

Exact requirement; specialist and capability ID; platform and edition; actual source URL; version applicability; retrieved passage; citation integrity; feasibility conclusion; unknowns; dependencies; technical risks; source authorization.

## 6. Specialist-specific scope (from the Sprint 5 mandate)

- **Shopify:** capability matching, relevance, citation quality, platform restrictions, the 55 pairs (O1). Pilot metadata alone is not a verified finding.
- **Shift4Shop:** canonical ID, legacy alias, source-unavailable behaviour. No vendor support may be claimed (source ownership unresolved).
- **WordPress / WooCommerce:** core versus WooCommerce; variants; API capability; unknown-version handling. Variation pricing stays UNKNOWN.
- **BigCommerce:** the single-product citation must not prove catalog operations.
- **Magento / Adobe Commerce:** Adobe-only features must not be attributed to Magento Open Source.
- **Standalone Applications:** neutral architectural scenarios only, until a technology context is approved.
- **Middleware Applications:** neutral integration scenarios (patterns, event flows, retries, idempotency), until a product context is approved.

## 7. Definition of Done (Sprint 5 engineering)

- Harness and datasets exist, with frozen hashes recorded before any score is reported.
- Every specialist has scenarios in each required category, and the categories are kept apart.
- No score is reported against a threshold that WDS has not approved.
- Shopify 55 results are reported as pending unless genuine human labels exist.
- Full CI is green on the exact engineering SHA.

Independent QA, remediation and formal acceptance are separate stages and are not part of this Definition of Done.

## 8. Current gate status

| Gate | Status |
|---|---|
| Sprint 4 management closure | Granted (S4-CLOSE-01) |
| Frozen scenario dataset approval | Pending WDS |
| Threshold approval | Pending WDS |
| Shopify 55-pair rater | Pending WDS (name required) |
| Source activation beyond the two pilot sources | Pending WDS |
| PG independent QA for Sprint 5 | Pending PG (delivery channel and independence confirmation not established) |
| Sprint 6 | Not started; requires separate authorization |

## 9. Standing restrictions

No fabricated PG review or attestation. No fabricated Shopify labels. No invented platform facts or citations. No unapproved retrieval. No live LLM. No production integration without QA-07. No R4 change. No protected-branch merge. The frozen four-milestone, nine-sprint structure is unchanged.
