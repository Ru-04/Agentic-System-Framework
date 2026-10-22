# Shopify Evaluation Case Briefs — Sanitized (D11)

**Status:** Proposed evaluation cases. Derived from WDS's own public portfolio pages. Client names, brands and identifying details are removed.
**Use:** Sprint 2 Shopify evaluation input (decision D11). These briefs are not acceptance evidence on their own.
**Source reliability:** every claim below is WDS's own marketing description of past work. Outcomes and figures on those pages are NOT used here, and none has been verified.
**Traceability:** each brief maps to one public WDS case-study page. The page slug is kept in section 0 only, so the mapping can be checked against the public site.

## 0. Traceability (public pages)

| Brief | Public WDS page (slug) |
|---|---|
| SH-CASE-01 | `telus-high-stakes-shopify-plus-store-customization` |
| SH-CASE-02 | `shopify-plus-custom-filters-advanced-search` |
| SH-CASE-03 | `custom-shopify-platform-for-fundraising-and-multi-system-integration` |
| SH-CASE-04 | `shopify-custom-dashboard-automation` |

## SH-CASE-01 — Shopify Plus telecom rate-plan store

**Context:** A Canadian telecom subscription business sells rate plans on Shopify Plus, with account and renewal flows.

**Requirements (sanitized):**
1. Validate Canadian postal addresses at checkout, with particular attention to rural and remote addresses.
2. Do not rely on IP-based province detection. Province must be captured explicitly.
3. Let a customer renew a rate plan from the order status page without creating an account.
4. Create the customer account after purchase, reusing details already entered at checkout.
5. Calculate regional tax and fixed levies correctly for a digital subscription, and avoid shipping fields that do not apply.

**Evaluation questions for the Shopify specialist:**
- Which of requirements 1 to 5 are native Shopify capability, which need a third-party app, and which need custom code?
- For each: which Shopify plan is needed, and which API or extension surface applies (Checkout extensibility, customer accounts, order status page, Storefront or Admin API)?
- Which claims are version-sensitive or plan-specific, and what must be verified before a decision?
- Where the platform does not support a flow natively (for example, guest renewal from the order status page for digital subscriptions), what are the documented constraints?

**Known unknowns to report, not to resolve:** regulatory treatment of the levy; whether a telecom partner API is in scope.

## SH-CASE-02 — Shopify Plus art catalogue: artist pages, filters and search

**Context:** An online art-print retailer with thousands of listings, multiple artists, and a merchandising team that edits filter sets.

**Requirements (sanitized):**
1. Provide a dedicated page per artist, with featured works, while keeping SEO and live inventory intact.
2. Provide faceted filters with AND/OR logic, updating results without a page reload, with merchandising control of the filter set.
3. Provide search that handles natural-language phrasing, typos and autocomplete at catalogue scale.
4. Keep checkout behaviour unchanged.

**Evaluation questions for the Shopify specialist:**
- Which of these are native Shopify capability on the relevant plan, and which need an app or custom development?
- What does the documented Storefront API or Search and Discovery capability cover, and what limits apply to filter logic and result volume?
- Requirement 3 is an AI-driven search component. Is it within the Shopify specialist's scope, or does it belong to a separate evidence and model decision (D09)? The specialist must report this as an unknown, not decide it.
- Which claims depend on plan, app version or API version?

**Known unknowns to report, not to resolve:** search provider choice; whether natural-language search needs a model call (not authorized, D09).

## SH-CASE-03 — Multi-system Shopify platform for campaign fundraising

**Context:** A pet-products retailer runs fundraising campaigns through Shopify, with permanent partner stores and campaign pages, and integrates several external product and printing services.

**Requirements (sanitized):**
1. Campaign-specific pages with real-time sales tracking and commission calculation per fundraiser.
2. Coexistence of permanent partner stores and campaign-driven stores.
3. Role-based administration for partners and staff.
4. Synchronization of orders and product data with several external systems, some with custom endpoints.

**Evaluation questions for the Shopify specialist:**
- Which parts can be modelled with native Shopify features (multiple stores or markets, metafields, customer accounts, staff permissions), and which exceed them?
- For requirement 4: which integration surfaces are available (webhooks, Admin API), what rate limits and data structures apply, and which systems are outside Shopify's documented scope?
- Which claims about staff permissions or plan limits depend on the plan tier?

**Known unknowns to report:** commission rules are business rules, not platform facts. They must be recorded as client-confirmed or unresolved, not inferred.

## SH-CASE-04 — Shopify pickup scheduling and dashboard automation

**Context:** A local retailer of collectible goods with time-sensitive in-store pickup orders.

**Requirements (sanitized):**
1. Pickup time slots with capacity limits, cut-off times and same-day rules, enforced at checkout.
2. Blackout dates and holidays.
3. Staff dashboard with daily volume, forecasting and reporting.
4. Automated order preparation timelines.

**Evaluation questions for the Shopify specialist:**
- Which of these are native (local pickup settings, delivery profiles, Flow automation) on the relevant plan, and which need a custom app or extension?
- Which checkout surface enforces the slot rules, and which surface would be overridden by custom code (checkout extensibility constraints)?
- Which claims about Flow, app limits or API versions must be verified against current official documentation before use?

**Known unknowns to report:** forecasting method; staffing rules; these are business inputs.

## 1. Use rules

- Each brief is a case for the Shopify specialist's investigation. It is not a statement of a requirement the client has confirmed.
- Scoring must follow D11: no acceptance on these briefs alone, and each claim needs a cited official-source passage or it is reported as unverified.
- Any change to a brief needs the decision-maker's approval.
- Sanitization status: names removed from the brief text. Client-confirmed approval for use of these scenarios is **not yet recorded**. Required before external use.
