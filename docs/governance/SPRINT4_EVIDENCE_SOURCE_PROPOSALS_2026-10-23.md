# Sprint 4 inputs: proposed evidence-source allowlists and scenarios (23 October 2026)

**Status: PROPOSALS ONLY. Nothing here is approved (D08). No source was fetched.** The hosts and paths below are candidates to be checked by WDS against the vendor's own publications before any is approved. Each approval needs an allowlist entry reviewed under the Sprint 4 rules. Sprint 4 has not been authorized.

Rules that apply to every entry: exact host and path scope; https only; no crawling; no redirects followed; vendor pages only (secondary material is excluded, D08); an entry is added only when a WDS decision approves it.

## Proposed allowlists (unverified candidates)

| Platform | Candidate source (to verify) | Scope proposed | Status |
|---|---|---|---|
| Shift4Shop (formerly 3dcart) | Vendor help-centre / developer documentation host (**not identified**) | Must be named by WDS | Not identified |
| WordPress & WooCommerce | WooCommerce developer documentation; WordPress developer documentation | Exact documentation paths, identified by WDS | Candidate only |
| BigCommerce | BigCommerce developer documentation | Exact documentation paths, identified by WDS | Candidate only |
| Magento / Adobe Commerce | Adobe Commerce developer documentation | Exact documentation paths, identified by WDS | Candidate only |
| Standalone Applications | None fixed. Depends on the named product | WDS must name each product and its vendor | Not identified |
| Middleware Applications | None fixed. Depends on the named product | WDS must name each product and its vendor | Not identified |

The two "Not identified" rows cannot be proposed without the product names. The assistant has not guessed them.

## Representative investigation scenarios (for test design, not evidence)

Each scenario is a requirement the specialist must handle. The expected behaviour is stated. No scenario is a verified investigation.

1. **Shift4Shop:** "Storefront theme change without custom code." Expect: clarification if the requirement is short; otherwise findings only from approved passages, feasibility not determined.
2. **WordPress & WooCommerce:** "Product variations with a separate price per variation." Expect: native and extension options listed separately, each with its evidence grade.
3. **BigCommerce:** "Checkout customization on the standard plan." Expect: a plan-applicability unknown, no feasibility claim.
4. **Magento / Adobe Commerce:** "Bulk product import from CSV." Expect: no finding without a permitted source; no native claim without DIRECT evidence.
5. **Standalone Applications:** "Offline use of a desktop tool." Expect: requirement clarification (product not named).
6. **Middleware Applications:** "Retry failed webhook deliveries without duplicate processing." Expect: topics for retries and webhooks only where whole-word evidence exists; no language or runtime recommendation.

Each scenario also needs: a passage that should be rejected (instruction-like text, another workspace, an unapproved origin), and a stale-evidence case.

## Required before Sprint 4 starts
- WDS decision on each allowlist entry (D08).
- Authorization of Sprint 4 under the applicable development and acceptance rules.
- Milestone 1 closure or a dated exception that covers Sprint 4 (see the tracker).
