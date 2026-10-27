# Sprint 4 investigation scenarios (preparation, 27 October 2026)

**Status: preparation only. No source is active. No retrieval has run. These scenarios define what a future, gated investigation would test. They are not investigation results and must not be reported as platform capability.**

Gate for every scenario: source inactive until WDS activation approval; Sprint 4 entry gate open; security gate met; production blocked by QA-07.

Outcome labels used below:
- **VERIFIED SUPPORT**: a retrieved, hash-recorded page within an approved boundary states the capability for the stated version or edition.
- **UNKNOWN SUPPORT**: the approved pages do not settle it, or the edition/version is missing.
- **UNSUPPORTED SOURCE**: the claim needs a page outside the approved boundary, or a refused redirect.

## WooCommerce (approved boundary: `developer.woocommerce.com` `/docs/*`, `/guides/*`)
1. **Product-variation pricing.** Requirement: different price per variation of one product. Pages to check: WooCommerce product documentation within `/docs/`. Needs: WooCommerce version. Expect VERIFIED SUPPORT only if a page states it for that version.
2. **Checkout customisation via hooks.** Requirement: change the checkout form. Pages: extension development guidance within `/docs/`. Needs: WooCommerce and WordPress version. Expect UNKNOWN SUPPORT if only the Store API is documented.
3. **REST API product read.** Requirement: read product data through the API. Pages: REST documentation reached through `/docs/`. Needs: version and the authentication method. Expect VERIFIED SUPPORT only with the version stated.

## BigCommerce (approved boundary: `docs.bigcommerce.com/developer/docs/*` and the product-catalog page)
1. **Product-catalog read.** Requirement: list or read products through the catalog API. Page: the approved `get-product` page. Needs: API version (v3 path shown on the page) and the store plan. Expect VERIFIED SUPPORT for a single-product read. The list endpoint is UNKNOWN until its page is approved.
2. **Plan-dependent feature.** Requirement: a feature only available on a higher plan. Pages: within `/developer/docs/`. Needs: the plan. Expect UNKNOWN SUPPORT without the plan.
3. **Order data.** Requirement: read orders. Page: not in the approved boundary. Expect UNSUPPORTED SOURCE until a page is approved.

## Adobe Commerce (approved exact pages: REST, GraphQL, events; shared PHP landing page)
1. **REST product read.** Page: `https://developer.adobe.com/commerce/webapi/rest/`. Edition: Adobe Commerce only (PaaS or SaaS). Expect VERIFIED SUPPORT for the overview statement only. Endpoint-level claims need their own approved pages.
2. **GraphQL storefront query.** Page: `https://developer.adobe.com/commerce/webapi/graphql/`. Edition: Adobe Commerce only. Expect VERIFIED SUPPORT for the overview only.
3. **Event-driven integration.** Page: `https://developer.adobe.com/commerce/extensibility/events/`. Edition: Adobe Commerce only. Must not be attributed to Magento Open Source without a separate verified page.
4. **PHP extension development.** Page: `https://developer.adobe.com/commerce/php/` (shared). Expect a shared statement only. Any claim about edition-exclusive behaviour is UNKNOWN until an edition-labelled page is approved.

## Magento Open Source (approved: one release-notes page only)
1. **Version identification.** Page: `https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview`. Use: release history and version applicability only. Expect VERIFIED for release-note statements; not for general feature support.
2. **Feature support (any).** No approved Open Source feature page. Expect UNSUPPORTED SOURCE. The contributor guide and the devdocs redirect are refused.

## Standalone Applications and Middleware Applications (technology-neutral)
- No technology or product is selected. No source is proposed. Each scenario needs a named technology (for Standalone) or product (for Middleware), then its own official source, approved separately.
- Bounded starting scenarios, to be chosen by WDS, not by the assistant: one named desktop or mobile framework; one named middleware product covering webhooks and retries.
- Until then, outcome for every requirement is UNKNOWN SUPPORT with a clarification request.

## Negative and security cases (for every platform)
- A redirect to an unlisted host is refused and reported.
- A path with a query string, encoding or dot segments is refused.
- A requirement with fewer than three specific terms gets a clarification, not a finding.
- Retrieved text containing instructions is excluded and counted, and never executed.
- Workspace A evidence never appears in workspace B output.
