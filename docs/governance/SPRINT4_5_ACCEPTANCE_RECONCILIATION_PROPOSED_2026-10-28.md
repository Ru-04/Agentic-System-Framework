# Sprint 4 and Sprint 5 acceptance-criteria reconciliation

**PROPOSED — NOT ORIGINAL FROZEN CRITERIA.** The original frozen criteria were searched for (repository, git history, governance records, project folder) and were not found. This document is a reconstruction for WDS approval. It is not a historical record.

## 1. Search result

- Git history: no commit adds a frozen nine-sprint plan or a per-sprint criteria list. Matching files are documentation for Increments 2 and 3, the evaluation plan and the specification baseline approval record.
- `WebDesk_Agentic_Requirement_Platform_Specs/`: no per-sprint M2 criteria. The decision register and evaluation plan refer to the frozen baseline without reproducing it.
- `docs/governance/AI_S04_SCOPE_RECONCILIATION_2026-10-26.md` is the most specific frozen-scope reference found. It states: S4 is deep platform-specific investigation, integration and option feasibility, restrictions, evidence capture, technical risk and unknowns, and estimation inputs. S5 is scenario evaluation of all seven, repeatability and scorecards.

## 2. Starting point

The established scope in section 1 above, together with `MANAGEMENT_DECISION_REGISTER_2026-10-26.md` (A4 and S4-ACCEPT-01). Nothing is added beyond what these records state.

## 3. Proposed Sprint 4 criteria

| ID | Criterion | Evidence | Status |
|---|---|---|---|
| S4-C1 | Seven specialist investigation paths through adapter v0.2 | CI run #36 on `58d1a39`; conformance tests | Met (synthetic) |
| S4-C2 | Deterministic requirement decisions and refusal precedence | Tests on `9f2325a` and `58d1a39` | Met |
| S4-C3 | Source boundaries, edition separation, redirect and URL refusal | Engine and boundary tests | Met (synthetic) |
| S4-C4 | Workspace isolation and operator authorization | Adapter and conformance tests | Met |
| S4-C5 | Controlled retrieval infrastructure, inactive by default | `test_controlled_retrieval.py` | Met (no activated source) |
| S4-C6 | At least one real, documentation-backed, cited investigation per specialist where a source is approved | Not performed | **Not met. Blocked by source activation.** |
| S4-C7 | Independent QA of the engineering baseline | PG review | **Not met. PG personal evidence pending.** |
| S4-C8 | Source activation through the applicable authorization | `SOURCE_ACTIVATION_REQUEST_2026-10-28.md` | **Not met. No source activated.** |
| S4-C9 | Shopify 55-pair human evaluation | 0 of 55 | **Not met.** |

## 4. Proposed Sprint 5 criteria

Scope from `AI_S04_SCOPE_RECONCILIATION_2026-10-26.md`, with the evaluation dimensions in the Sprint 5 request: requirement interpretation, capability accuracy, evidence relevance, citation correctness, unknown and unsupported outcomes, security behaviour, feasibility assessment, reliability and regression.

| ID | Criterion | Threshold | Status |
|---|---|---|---|
| S5-C1 | Scenario evaluation of all seven specialists | Every scenario in `SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md` run | Not started. **Threshold to be set by WDS.** |
| S5-C2 | Repeatability | Same input, same outcome class and citations | Not started. **Number of runs to be set by WDS.** |
| S5-C3 | Scorecards | Defined per dimension | Not started. **Scorecard definition to be set by WDS.** |

## 5. Material differences from approved scope

1. Real investigation for all seven specialists is not achieved. Under this proposal it becomes a Sprint 4 criterion (S4-C6), which was not the approved scope wording.
2. Sprint 5 thresholds are not set. No threshold is proposed here without WDS input.
3. S4-C5 is met by infrastructure only. No retrieval has run against a real source.

WDS to approve, amend or reject this reconciliation. No criterion is treated as frozen until WDS says so.
