# M2 Sprint 4: engineering acceptance with conditions (28 October 2026)

**Status: ENGINEERING ACCEPTED WITH CONDITIONS. FORMAL GATE CLOSURE PENDING.**
Recorded in `MANAGEMENT_DECISION_REGISTER_2026-10-26.md` as S4-ACCEPT-01.

## 1. Binding

| Item | Value |
|---|---|
| Accepted engineering commit | `58d1a39c0e85aedaf95d91d13c2211095859485d` |
| CI evidence | `specialist-ci` run #36 (`40669580089`): SUCCESS on `58d1a39` |
| Later commits | Documentation only: `24693f2`, `5d5c491`, `a7e9011` |
| Independent QA | S4-QA-01: PG reported PASS, no defects, confirmed by WDS management. PG personal evidence **PENDING VERIFICATION** |

This acceptance does not extend to any commit after `58d1a39` that changes engineering code.

## 2. Accepted scope

- Shared investigation engine (`src/webdesk/investigation/engine.py`).
- Adapter v0.2 integration (`src/webdesk/specialists/adapter_v02.py`).
- Seven-specialist synthetic investigation paths (`src/webdesk/investigation/specialists.py`).
- Deterministic requirement decisions: INVESTIGATE, INVESTIGATE_WITH_UNKNOWNS, CLARIFY, REFUSE.
- Source-refusal classification (SOURCE-REFUSAL-01): authorization refusal is separate from evidence unavailability.
- Source-boundary and edition controls, including approved-but-inactive boundaries.
- Workspace and authorization security tests.
- Verified automated engineering baseline (CI run #36, plus local unit results).

## 3. What this acceptance does not establish

- No specialist has performed a real evidence-backed investigation. Every supported result is `[SYNTHETIC]`.
- No documentation source is active. Retrieval is not implemented (Mode 2 is absent).
- Shift4Shop, Standalone Applications and Middleware Applications have no approved source. Their results are unsupported-source outcomes, not capability findings.

## 4. Conditions remaining

| # | Condition | Owner | Current state |
|---|---|---|---|
| 1 | PG personal independence declaration, review record and attestation | PG | Pending. Not in repository. |
| 2 | Frozen Sprint 4 acceptance criteria located and reconciled with delivered scope | WDS | Not located (see section 5) |
| 3 | Real documentation-backed investigations | Engineering, after activation approvals | Not started (see section 6) |
| 4 | Evidence source activation through the applicable authorization process | WDS | No source active. No activation requested. |
| 5 | Shopify 55-pair human evaluation | Independent reviewer named by WDS | 0 of 55 |
| 6 | Independent remediation clearance | PG | Pending. Management reports no defects. |

## 5. Frozen Sprint 4 acceptance criteria: search result

I searched the repository and the project folder (`D:\WDS\Agentic System FrameWork`) for the frozen baseline and its per-sprint criteria.

- Searched: `docs/`, `WebDesk_Agentic_Requirement_Platform_Specs/`, all governance records, and text references to "Frozen Implementation Baseline", "9 sprints", "4 milestones" and "Sprint 4".
- Found: sprint references in governance records, and the Sprint 4 scenarios and proposals. None is the frozen per-sprint criteria document.
- Not found: a document listing the frozen Sprint 4 acceptance criteria.

**Action required:** WDS to identify the authoritative frozen criteria document and supply its location. Until then, this record cannot confirm that the delivered scope matches the frozen criteria.

## 6. Real-investigation and source-activation requirements

These are prepared, not started. Nothing here activates a source or retrieves a page.

| Item | Current state | Needed before work starts |
|---|---|---|
| Retrieval layer (Mode 2) | Not implemented. The engine's `ACTIVE_BOUNDARIES` is empty. | A retrieval design approved by WDS. Engineering must not add network code without that approval. |
| WooCommerce (`developer.woocommerce.com` `/docs/*`, `/guides/*`) | Approved for controlled retrieval after activation gates. Ownership PARTIAL (Automattic via WordPress.org). | Source activation approval. |
| BigCommerce (`docs.bigcommerce.com/developer/docs/*` plus the product-catalog page) | Approved boundary, inactive. | Source activation approval. |
| Adobe Commerce (four exact pages, including one shared page) | Approved boundary, inactive. | Source activation approval. |
| Magento Open Source (one release-notes page) | Approved boundary, inactive. Release claims only. | Source activation approval. |
| Shopify (`shopify.dev`, `help.shopify.com` and plan scopes) | Approved boundary, inactive. | Source activation approval. Shopify 55-pair labels. |
| Shift4Shop | No approved source. | Source proposal, verification and approval. |
| Standalone Applications | No technology selected. | WDS decision on one named technology, then source approval. |
| Middleware Applications | No product selected. | WDS decision on one named product, then source approval. |

## 7. Sprint 5 transition

WDS authorized preparation for M2 Sprint 5 — Specialist Evaluations. Formal Sprint 5 commencement is not claimed. Draft scenarios are in `SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md`, which is not a frozen criteria document.
