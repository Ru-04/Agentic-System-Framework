# Specialist Implementation Authorization Amendment (Limited) — 22 October 2026

- **Amends:** nothing. This is a separate, dated, limited authorization. The original `GATE1_IMPLEMENTATION_AUTHORIZATION.md` is preserved unchanged (decision D03).
- **Effective date:** 22 October 2026.
- **Authorizing role:** WDS project decision-maker, as stated in the authorization request dated 22 October 2026. Name, signature and approval reference **not provided**.
- **Companion record:** `docs/governance/DECISION_RECORD_2026-10-22.md`.

## 1. What is authorized

Isolated, non-production development of the seven specialist agents:

1. Shopify
2. Shift4Shop (formerly 3dcart)
3. WordPress & WooCommerce
4. BigCommerce
5. Magento / Adobe Commerce
6. Standalone Applications
7. Middleware Applications

Scope, in the frozen plan:
- M1 S1 Shared Specialist Foundation (implemented; formal closure pending human QA, see section 4).
- M1 S2 Shared Evidence Services and Real Shopify Investigation (in progress under this authorization).
- Preparation of isolated worktrees and implementation interfaces for the other six specialists. No M2 Sprint 3 implementation is authorized by this amendment.

Environment: isolated local worktrees, local test PostgreSQL (D10), GitHub feature-branch push and CI (D05).

## 2. Restrictions and prohibited activity

- No production activation of any specialist or AI function.
- No protected integrations and no deployment.
- No merge into protected branches.
- No live model or provider calls until provider, exact model ID, credentials and usage budget are approved (D09).
- No retrieval outside the approved allowlists (D08). Any allowlist in code is a proposed configuration until approved.
- No specialist execution before operator confirmation (D07).
- No privileged database action outside approved authorization controls.
- No simulated, synthetic or mock output presented as verified investigation or as accepted specialist output.
- No independent human QA acceptance recorded without a human signatory (D04).
- No change to the frozen sprint allocation, milestone scope, or acceptance criteria.

## 3. Dependencies and unresolved approvals

| Dependency | Status | Blocks |
|---|---|---|
| Reconciled specification package approval (D02) | Proposed; awaiting authorized human approval | Any claim that the specification is approved |
| Shared evidence allowlist: approved vendor documentation domains | Not provided. Sprint 2 uses a proposed allowlist | Live retrieval beyond the proposed list |
| Live model provider, exact model ID, credentials, budget (D09) | Not provided | Any live model call |
| Human QA sign-off, Sprint 1 (D04) | Not provided | Formal closure of Sprint 1 |
| Shift4Shop migration of legacy identifier | Not approved; legacy alias retained (D06) | Removing `CAP-3D-CART-SHIFT-SHOPIFY` |
| Runtime enforcement of specialist authority (QA-07) | Deferred to M3 S6 by prior decision | Any protected integration or activation |
| Production hosting, retention, production credentials (D10) | Not provided | Any production use |
| Independent milestone testers (M1, M2, M3, M4) | Not assigned | Milestone acceptance |

## 4. Status categories (kept separate)

1. **Development authorization:** granted for isolated non-production work (this amendment).
2. **Specification approval:** not approved. Reconciled package proposed.
3. **Sprint implementation:** Sprint 1 implemented; Sprint 2 in progress.
4. **Sprint QA and acceptance:** Sprint 1 limited progression authorized; not formally accepted. Human QA sign-off not recorded.
5. **Independent milestone acceptance:** M1 not started.
6. **Production release authorization:** not granted.

## 5. Applicable controls

- Phase 1 security controls: unchanged. The specialist package has no import of authority, session or privilege code.
- Workspace isolation, reviewer-controlled acceptance, human authorization and evidence traceability are preserved from the drafts.
- Audit: decisions and changes recorded in committed reports under `docs/`.

## 6. How approval evidence is retained

- Decision text: committed in `docs/governance/`.
- Each approval or sign-off: a separate file under `docs/governance/approvals/`, containing approver, role, date, commit SHA and decision. No such file is created by this amendment.
- CI evidence: GitHub Actions run identifiers and head SHAs recorded in the sprint reports.
