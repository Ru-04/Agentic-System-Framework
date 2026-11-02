# M2 Sprint 5: candidate source register, all seven specialist categories (2 November 2026)

**Status: for WDS decision. No source is activated by this register.** Part A lists sources already approved and, where marked, active. Part B lists proposed new sources. Each proposed row needs an explicit WDS decision. Search-result URLs in Part B were **not fetched**: they are candidates only, and their ownership and content are unverified.

Authorities: S2-D07 to S2-D12 (`DECISION_REGISTER_SPRINT2.md`), B1 to B6 and ADOBE-01, MAGENTO-01 (`approved_boundaries.py`), S4-PILOT-EVIDENCE-01 (28 October 2026), the management section 2 decision (2 November 2026), and Sprint 5 Decision 2 (restricted Shopify policy, 2 November 2026).

## Restricted-source policy applied to every row

1. No whole-host authorization. Each approved source names exact paths or a bounded subtree.
2. A path is never activated because a sibling page is approved.
3. A source needs ownership verification, an exact path, an edition and version applicability, and an approval reference before activation.
4. Access through a 403 response is not a route: no bypass.
5. Search-result URLs are discovery only, not evidence.

## Part A. Approved sources

| # | Specialist | Capability ID (registry) | Capabilities served | Publisher | Exact URL | Path scope | Purpose | Ownership verification | Version / edition | Approval reference | Activation status | Required approval | Recommended scope | Restriction or conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | WordPress / WooCommerce | CAP-WORDPRESS-WOOCOMMERCE | product variation pricing (UNKNOWN on evidence), REST API product read, Store API cart | Automattic (partially verified, WordPress.org listing) | `https://developer.woocommerce.com/docs/`, `/guides/` | Bounded subtrees `/docs/*`, `/guides/*` | Developer reference | Partially verified; owner statement not found | Not applicable; pages state no version, so no version claim | B2 (26 Oct), SOURCE-01 (27 Oct), pilot 28 Oct | **APPROVED AND ACTIVE** | None to keep. Any change needs a new decision | Keep as is | Subtrees are broad within one host. Pilot read the Store API products page: UNKNOWN |
| A2 | BigCommerce | CAP-BIGCOMMERCE | product catalog read, single product only | BigCommerce (domain and product match; owner not confirmed) | `https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product` | Exact page; `/developer/docs/*` is approved but not activated | Single-product API reference | Publisher-controlled; owner statement not found | API v3 read from the page path | B1 (26 Oct), SOURCE-01, pilot 28 Oct | **APPROVED AND ACTIVE** | None | Keep | The verified citation rested on a JSON payload inside a script. Under the Decision 3 policy it no longer holds (see the real evidence report). WDS decision needed |
| A3 | Adobe Commerce | CAP-MAGENTO-ADOBE-COMMERCE | REST product read; GraphQL query; event-driven integration (no capability registered for events) | Adobe (partially verified, Adobe operator) | `https://developer.adobe.com/commerce/webapi/rest/`, `/commerce/webapi/graphql/`, `/commerce/extensibility/events/` | Exact pages only | REST, GraphQL and events overview | Browser check of all three pages, 2 Nov 2026 | Adobe Commerce only; no version stated on pages | ADOBE-01 (27 Oct), management section 2 (2 Nov) | **APPROVED AND ACTIVE** (2 Nov) | None | Keep | No page states a version, so no version-specific claim is possible. The events page has no registered capability |
| A4 | Magento / Adobe Commerce | CAP-MAGENTO-ADOBE-COMMERCE | release history only (feature claims UNSUPPORTED) | Adobe (owner confirmation not recorded) | `https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview` | Exact page | Magento Open Source release notes | Publisher-controlled; owner statement not found | Magento Open Source; release and version claims only | MAGENTO-01 (27 Oct), management section 2 (2 Nov) | **APPROVED AND ACTIVE** (2 Nov) | None | Keep | Page states no version. The pilot page title and headings do not count as evidence (Decision 3) |
| A5 | Magento / Adobe Commerce | CAP-MAGENTO-ADOBE-COMMERCE | Adobe shared PHP (not a registered capability) | Adobe (partially verified) | `https://developer.adobe.com/commerce/php/` | Exact page `/commerce/php/` | Shared Adobe and Magento PHP | **Not checked** under any authorization | Shared | ADOBE-01 | APPROVED BUT INACTIVE | Ownership check, then activation decision | Keep inactive until a capability needs it | No capability uses it yet |
| A6 | Shopify | CAP-ECOMMERCE | plan feature availability | Shopify (plan pages on `shopify.com`) | `https://www.shopify.com/pricing`, `https://www.shopify.com/plus` (and `shopify.com` host) | Exact prefixes `/pricing` and `/plus` | Plan and feature availability | **Not recorded** (`sources.json`) | Plan must be named per claim | S2-D08, **flagged for decision-maker confirmation** | APPROVED BUT INACTIVE | **Confirm S2-D08.** A retrieval route that does not depend on bypassing 403 | Keep inactive. Confirm S2-D08 before any activation | Both plan pages returned HTTP 403 to the fetch client. No plan document has been retrieved |

Other approved decisions outside the specialist scope, recorded for completeness: S2-D09 (two exact `canada.ca` CRA pages, regulatory background only, not a specialist source).

## Part B. Proposed new sources (not activated; need separate approval)

| # | Specialist | Capability ID (registry) | Capabilities served | Publisher | Candidate URL (not fetched) | Path scope proposed | Purpose | Ownership verification | Version / edition | Existing approval | Activation status | Required additional approval | Recommended activation scope | Restriction or conflict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | Shopify | CAP-ECOMMERCE | Plan features (Basic plan, B2B plan features) | Shopify Help Center | `https://help.shopify.com/en/manual/intro-to-shopify/pricing-plans/plans-features/basic-shopify-plan`; `https://help.shopify.com/en/manual/b2b/getting-started/plan-features` | Two exact pages | Plan feature availability | Not verified. Host not in any approval | Plan must be named | S2-D07 governs access: permitted methods only, no 403 bypass | Not approved | **Yes**: exact paths, ownership check, a permitted route | Two exact pages, after ownership check | Host-level access is refused by S2-D07 policy. Access by fetch has returned 403 |
| B2 | Shopify | CAP-ECOMMERCE | Plan features (product page for the Sprint 2 manual page) | Shopify Help Center | `https://help.shopify.com/en/manual/products` | One exact page | Products manual | Browser-verified on 22 Oct 2026 (S2-D07). Not ingested | Not applicable | S2-D07 (browser read only) | Not approved for ingestion | Yes: a permitted, auditable capture method (the Sprint 2 record says browser text is not ingested) | Not recommended until a capture method is approved | Browser read is not an auditable retrieval method |
| B3 | Shopify | No registered capability | Storefront API, Admin GraphQL, product object, checkout extensions (the 16-page Sprint 2 corpus) | Shopify | `https://shopify.dev/docs/api/storefront/latest`; `…/admin-graphql/latest`; `…/storefront/latest/queries/product`; `…/admin-graphql/latest/objects/Metafield`; `https://shopify.dev/docs/apps/build/checkout` | Five exact pages, from the Sprint 2 corpus | Developer reference for capabilities that need registry entries | Not verified. Sprint 2 corpus was fetched under a whole-host allowlist with no located decision | Not stated on pages | None located. S2-D07 covers `help.shopify.com` only | Not approved. The Sprint 2 corpus was a provenance exception | Yes: exact paths approved and capability registration | Exact paths only. No `shopify.dev` subtree | The corpus is **not** authorised for new evidence. Its text was fetched under the withdrawn whole-host allowlist |
| B4 | Shopify | No registered capability | Shopify API product read | Shopify | `https://shopify.dev/docs/api` (index only) | Not proposed beyond the index | None | Not verified | Not stated | None | Not approved | Yes | None | Whole-section approval is refused under Decision 2 |
| B5 | Shift4Shop | CAP-3D-CART-SHIFT-SHOPIFY | Product read API | Shift4Shop (3dcart), **ownership NOT VERIFIED** | `https://developer.3dcart.com/` (portal); `https://developer.3dcart.com/build-an-app` | Not proposed: the product reference page is not identified | Developer reference | **Not verified** (SRC-02 discovery only, B4 deferred) | Version not established. Third-party sources cite other base URLs (`apirest.3dcart.com`, `api.shift4shop.com/v3`, `developers.shift4shop.com`) that are unverified | SRC-02 (discovery only) | Discovery only | Yes: ownership verification, the exact product reference page, then authorization | None until the page is identified | Base URL conflict must be settled from the official portal before any path is proposed |
| B6 | WordPress core | No registered capability for core | REST API posts and endpoints (core, not WooCommerce) | WordPress.org | `https://developer.wordpress.org/rest-api/reference/` | One exact page, no children | Core REST API reference | Not verified (official-looking domain; ownership check needed) | WordPress version not stated; the page is version-agnostic | B6 deferred; WordPress core documentation not approved | NO APPROVED SOURCE | Yes: domain authorization, a registry capability for core, ownership check | Exact page only | Core is outside the WooCommerce capability set. Registering a core capability is a WDS decision |
| B7 | Magento / Adobe Commerce | CAP-MAGENTO-ADOBE-COMMERCE | REST product read on Adobe Commerce | Adobe | `https://developer.adobe.com/commerce/webapi/rest/reference` | One exact page | REST endpoint reference | Adobe browser check needed | Adobe Commerce only | ADOBE-01 does not cover it | Not approved | Yes | One exact page after ownership check | Large generated reference. Exact product endpoint paths are not yet identified |
| B8 | BigCommerce | No registered capability (order data is UNAPPROVED, bigcommerce.md section 13) | Order data | BigCommerce | `https://docs.bigcommerce.com/developer/docs/admin/checkout-and-cart/orders/overview`; `https://developer.bigcommerce.com/docs/store-operations/orders` | Two exact pages | Orders API reference | Not verified. `developer.bigcommerce.com` is not in any approval | Orders API v2 and v3 both appear; the page states no version | None | Not approved | Yes: capability registration, exact paths, and a decision on the `developer.bigcommerce.com` host | One host and one exact page, after registration | Two hosts. The approved host is `docs.bigcommerce.com`. The S5-007 expectation (UNSUPPORTED_SOURCE) holds until this is decided |
| B9 | Standalone Applications | CAP-STANDALONE-APPLICATIONS | Architecture selection | None | None | None | None | Not applicable | Not applicable | None | NO APPROVED SOURCE | WDS must name a technology first | None | Technology-neutral (Decision 1). No source is proposed |
| B10 | Middleware Applications | CAP-MIDDLEWARE-APPLICATIONS | Webhook retry, error recovery, idempotency, synchronisation | None | None | None | None | Not applicable | Not applicable | None | NO APPROVED SOURCE | Vendor sources only if WDS names a product (a project decision, not required) | None | Technology-neutral (Decision 1). Retry logic is a recognised requirement, not a vendor claim |

## Part C. Summary for WDS

- **Eligible for activation now:** none beyond what is already active. A2 and A3 are active and A4 was activated on 2 November.
- **Blocked:** A5 (ownership check), A6 (confirm S2-D08 and a permitted route), B3 and B4 (Shopify whole-host and provenance), B8 (host decision).
- **Needs registry or policy decision first:** B6 (core capability), B8 (order capability), B3 (capabilities for Shopify storefront and checkout).
- **Needs naming first:** B9, B10.
- **Needs ownership verification first:** B5, B7.

Decision requested (one consolidated answer): approve, amend or reject each Part B row. Rows B1, B2, B3 and B4 are governed by the Shopify policy and need confirmation of S2-D08 before any of them.

## Part D. Unresolved conflicts in the records

1. S2-D08 is flagged for decision-maker confirmation and has not been confirmed.
2. `sources.json` and the Sprint 5 plan say the S2 decision record was "not located". It is located (`DECISION_REGISTER_SPRINT2.md`). Those statements need correcting.
3. `engine.py` cites "S2-D07 to S2-D09" for Shopify. S2-D09 is the CRA decision. The citation needs correcting.
4. The Sprint 2 global allowlist (`SPRINT2_ALLOWLIST`) and `PROPOSED_SHOPIFY_ALLOWLIST` permitted whole hosts. They now permit only the scoped Shopify plan pages and the CRA pages (Decision 2 applied in this cycle).
5. The Sprint 2 corpus (16 `shopify.dev` pages, 22 October 2026) was fetched under the whole-host allowlist. No located decision approves those pages.

## Part E. WDS decision recorded (2 November 2026)

WDS decision: "Approve eligible rows."

Result: **no new activation.** Part C found no row eligible beyond the sources already active (A2, A3, A4). The Part B rows are not eligible because their conditions are open: ownership checks, exact-path approvals, the S2-D08 confirmation, capability registration, or naming of a technology or product. No code, source status or dataset was changed by this decision.

Rows still open, in the order they can be cleared:
1. A5 (Adobe shared PHP): ownership check, then an activation decision.
2. A6 (Shopify S2-D08 plan pages): WDS confirmation of S2-D08 and a permitted retrieval route.
3. B1, B2, B3, B4 (Shopify help and shopify.dev): exact-path approvals under the restricted policy.
4. B5 (Shift4Shop), B7 (Adobe REST reference): ownership checks and exact pages.
5. B6 (WordPress core), B8 (BigCommerce orders): capability registration and host decisions.
6. B9, B10: a named technology or product from WDS.
