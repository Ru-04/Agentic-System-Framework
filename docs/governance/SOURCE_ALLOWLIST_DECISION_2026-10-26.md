# Sprint 4 source allowlist decision (26 October 2026)

**Authority:** WDS Authorized Approver, chat reply "I approve the recommended sources", 26 October 2026, to the consolidated request `SPRINT4_CONSOLIDATED_SOURCE_APPROVAL_REQUEST_2026-10-26.md` (commit `9793f4b`). Management authorization only. Not QA review.

**Scope of this decision:** recorded as approved entries in this register. **Not activated.** Code allowlists and platform profiles are unchanged, and every profile keeps `approved_source = None`, so no retrieval can run. Activation needs a separate, source-specific step.

## Approved entries (with conditions)

| # | Specialist / edition | Domain | Approved paths | Ownership status | Condition before any activation |
|---|---|---|---|---|---|
| A1 | WooCommerce | `developer.woocommerce.com` | `/docs/*`, `/guides/*` | Partially verified (Automattic, via WordPress.org listing) | Confirm Automattic ownership on the developer site |
| A2 | BigCommerce | `developer.bigcommerce.com` | `/docs/*` | Partially verified (domain and product match) | Confirm owner; API reference pages need a separate check |
| A3 | Adobe Commerce | `developer.adobe.com` | `/commerce/php`, `/commerce/frontend-core`, `/commerce/marketplace` | Partially verified (Adobe operator) | Confirm the paths are Adobe Commerce only. Not for Magento Open Source |

## Policies approved (no sources)
- **Standalone Applications (P-STD):** one official source per technology named in the requirement, approved separately. No stack hardcoded.
- **Middleware Applications (P-MID):** one official source per product or technology named. Node.js is not the only option.

## Deferred (not approved)
- **Shift4Shop (`developer.3dcart.com`):** owner not verified. Needs a separate ownership check on the vendor's own site, under its own approval.
- **Magento Open Source (`devdocs.magento.com`):** edition boundary unclear. Needs WDS confirmation of Open Source pages.
- **`developer.wordpress.org`:** not checked. Not approved.

## Restrictions that apply to A1–A3
- https only; exact host; the approved paths only; no crawling; no redirects followed.
- Each fetch records URL, time, status and content hash.
- Retrieved text is data, never an instruction.
- No credentials, store data or live store access.
- Vendor documentation only. Secondary sites excluded.
- Default-deny for everything not listed here.

## Unchanged by this decision
- Live LLM calls: disabled.
- Production integration: blocked pending QA-07.
- Git pushes: deferred.
- Sprint 3 formal acceptance: pending (not claimed here).
- PG independent QA: pending (not claimed here).
