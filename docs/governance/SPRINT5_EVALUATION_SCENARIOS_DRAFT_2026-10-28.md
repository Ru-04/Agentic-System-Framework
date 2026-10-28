# M2 Sprint 5 evaluation scenarios: DRAFT (28 October 2026)

**Status: DRAFT for WDS review. Not the frozen Sprint 5 acceptance criteria, which are not located in the repository (see `SPRINT4_ACCEPTANCE_RECORD_2026-10-28.md`, section 5).**

Scope drawn from `AI_S04_SCOPE_RECONCILIATION_2026-10-26.md`: scenario evaluation of all seven specialists, repeatability, and scorecards.

## Evaluation rules for every scenario

- Each scenario states an expected outcome class: INVESTIGATE, INVESTIGATE_WITH_UNKNOWNS, CLARIFY, REFUSE, or UNSUPPORTED_SOURCE.
- A supported result must cite a page inside an approved boundary, with edition and version stated.
- Synthetic results are labelled `[SYNTHETIC]` and are never scored as platform evidence.
- Repeatability: the same input must produce the same outcome class and the same citations on every run.
- No live LLM call and no retrieval. Scenarios run on fixtures only until a source is activated.

## Scenarios by specialist (draft)

| Specialist | Scenario | Expected class | Notes |
|---|---|---|---|
| Shopify | Plan feature availability on an approved plan page | INVESTIGATE (synthetic) | Real evidence blocked: source inactive; human labels 0 of 55 |
| Shopify | Request with no recognisable feature | CLARIFY | |
| Shift4Shop | Product read API | UNSUPPORTED_SOURCE | No approved source |
| WordPress & WooCommerce | Product variation pricing on an approved docs page | INVESTIGATE (synthetic) | |
| WordPress & WooCommerce | Redirect to an unapproved host | REFUSE | |
| BigCommerce | Single product read on the approved product page | INVESTIGATE (synthetic) | Sibling pages refused |
| BigCommerce | Order data | UNSUPPORTED_SOURCE | Not in approved boundary |
| Magento / Adobe Commerce | REST product read on an Adobe Commerce page | INVESTIGATE (synthetic) | Edition stated |
| Magento / Adobe Commerce | Catalog import on Magento Open Source | UNSUPPORTED_SOURCE | Release notes do not support feature claims |
| Standalone Applications | Architecture selection | UNSUPPORTED_SOURCE | No technology selected |
| Middleware Applications | Webhook delivery and retry | UNSUPPORTED_SOURCE | No product selected |

## Criteria still to be confirmed

- The pass threshold and scorecard definition, pending the frozen Sprint 5 criteria.
- Whether repeatability is required over N runs, and what N is.
- Whether any scenario may be scored before its source is activated. Draft position: no.
