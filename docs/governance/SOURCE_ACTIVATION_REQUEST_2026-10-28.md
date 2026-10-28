# Consolidated source activation request (28 October 2026)

**Status: REQUEST ONLY. No source is activated. No retrieval has run.** Each row needs a separate WDS decision. Activation is not implied by this request.

Activation controls in code: `src/webdesk/investigation/engine.py` (`ACTIVE_BOUNDARIES`, empty) and `src/webdesk/investigation/retrieval.py` (no transport is shipped; a transport must be supplied by an authorized caller).

| Source | 1. Exact domain and paths | 2. Approval reference | 3. Ownership | 4. Activation status | 5. Retrieval purpose | 6. Security restrictions | 7. Edition and version | 8. Recommended decision | 9. Remaining conditions |
|---|---|---|---|---|---|---|---|---|---|
| Shopify | `shopify.dev`, `help.shopify.com`; plan scopes in `SHOPIFY_PLAN_SCOPES` | Sprint 2 (S2-D07 to S2-D09), cited in `engine.py`. **Decision record not located in the repository.** | Not recorded in the repository | Inactive (`SHOPIFY_INACTIVE`) | Plan feature availability | Exact-host and path allowlist; no query, no encoding; no redirects followed | Not applicable (no edition). Version must be stated per page | **Defer** until the S2 decision record is located and ownership is verified | Locate S2-D07 to S2-D09; ownership check; 55-pair human labels (0 of 55) |
| WooCommerce | `developer.woocommerce.com` `/docs/*`, `/guides/*` | B2 (approved with conditions, 26 Oct 2026); SOURCE-01 (27 Oct 2026) | Partial: Automattic via WordPress.org listing. Not conclusively verified | Inactive (`WOOCOMMERCE_DOCS`) | Product variation pricing and related product documentation | Controlled read-only retrieval only; redirects refused | Not applicable. Version must be stated per page | **Defer.** Activate only after ownership is confirmed on the developer site | Confirm Automattic ownership of `developer.woocommerce.com`; activation approval |
| BigCommerce | `docs.bigcommerce.com/developer/docs/*` and the exact product-catalog page `.../developer/api-reference/rest/admin/catalog/products/get-product` only | B1 (26 Oct 2026); SOURCE-01 (27 Oct 2026) | Partial: domain and product match. Owner not confirmed; API reference needs separate check | Inactive (`BIGCOMMERCE_DOCS`) | Single product read; product catalog documentation | Exact page only for API reference; no `/api-reference/*` tree; redirects refused | Not applicable. API v3 path shown on the page | **Defer** until owner is confirmed and the API reference check is done | Owner confirmation; API reference check; activation approval |
| Adobe Commerce, exact pages | `developer.adobe.com/commerce/webapi/rest/`, `.../webapi/graphql/`, `.../extensibility/events/` | ADOBE-01 (27 Oct 2026) | Partial: Adobe operator | Inactive (`ADOBE_COMMERCE_EXACT`) | REST, GraphQL and events overview claims | Exact pages only; children, siblings, parents, query and encoding refused | Adobe Commerce only. Not applicable to Magento Open Source | **Defer** until the Adobe Commerce paths are confirmed as Adobe Commerce only | Confirm paths are Adobe Commerce only; activation approval |
| Shared Adobe and Magento documentation | `developer.adobe.com/commerce/php/` | ADOBE-01 (27 Oct 2026); labelled shared | Partial: Adobe operator | Inactive (`ADOBE_SHARED`) | Shared PHP extension statements. Shared statements only | Exact page; citations labelled shared; no edition-exclusive claim | Shared. Edition-exclusive claims need separate pages | **Defer** with the Adobe Commerce request | Same as Adobe Commerce; confirm shared labelling |
| Magento Open Source release notes | `experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview` only | MAGENTO-01 (27 Oct 2026, with restrictions) | Partial: Adobe. Owner confirmation not recorded | Inactive (`MAGENTO_OPEN_SOURCE_RELEASE_NOTES`) | Version identification and release history only | Release claims only; feature claims refused by the engine | Magento Open Source. Release claims only | **Approve for activation review** once the Adobe ownership check is complete. Feature support stays unsupported | Confirm ownership; confirm the release-notes page remains the only approved page |

## Not requested for activation

- **Shift4Shop** (`developer.3dcart.com`): B4 deferred. Owner not verified. Stays inactive.
- **WordPress** and any technology-specific documentation not listed above: stays inactive.
- **Standalone Applications and Middleware Applications**: technology-neutral. No technology or product is selected, and no permanent stack is chosen.

### Bounded example scenarios (for WDS to choose from; none is selected)

| Specialist | Example scenario | Needed from WDS before any source is proposed |
|---|---|---|
| Standalone Applications | One named desktop or mobile framework, e.g. a requirement about background sync | Name the framework. Then propose its official documentation source for separate approval |
| Middleware Applications | One named middleware product, e.g. a requirement about webhook delivery and retries | Name the product. Then propose its official documentation source for separate approval |

Until one is named, every requirement for these specialists returns UNSUPPORTED_SOURCE or CLARIFY.

## Note on a shared-contract conflict

The Sprint 2 global allowlist (`VENDOR_ALLOWLIST`, `SPRINT2_ALLOWLIST`) covers Shopify only. `SourceRecord` refuses any vendor origin outside it. The Sprint 4 retrieval path therefore does not use `SourceRecord`. It builds its own sanitized provenance (content hash, no URL in the record). Making the two consistent would change a shared Sprint 2 contract and needs a separate WDS decision.
