# Source verification results (C0, C3, C5; discovery for C1, C2, C4), 26 October 2026

**Authority:** WDS Authorized Approver, chat, 26 October 2026 (C0, C1 preparation, C2 proposal, C3, C4 discovery, C5). Read-only, specific public pages, no authentication, no crawling, no bulk download. **Discovery only. No source activated. No runtime retrieval enabled.**

**Retrieval times:** pages were read on 26 October 2026 in the built-in browser. Times are the session times, not server timestamps.

## 1. Results by source

| Source | Pages read (exact URL) | Final URL after redirects | Ownership or maintainer evidence | Edition / section evidence | Status |
|---|---|---|---|---|---|
| WooCommerce | `https://developer.woocommerce.com/docs/` | Same | Page states the docs are for developers; merchant docs point to `woocommerce.com`. No explicit owner line on the page | Extension, theme, Store API and REST guidance | **PARTIALLY VERIFIED** (same product family as WordPress.org listing, which states Automattic develops it, from the earlier search) |
| WooCommerce | `https://developer.woocommerce.com/guides/` | Same | Blog page. Says the REST API docs moved into the main developer docs (8 May 2026) | Blog posts, not reference pages | Context only |
| BigCommerce | `https://developer.bigcommerce.com/docs/` | **`https://docs.bigcommerce.com/developer/docs/overview/quick-start`** (redirect to a different host) | Page title "BigCommerce Developers"; no explicit owner line read | Storefront, store operations, apps; REST and GraphQL | **PARTIALLY VERIFIED** (product name; host moved) |
| BigCommerce | `https://developer.bigcommerce.com/api-reference/catalog/catalog-api/products/getproducts` | **`https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product`** (redirect to a different host and a different page) | Same site as above | Admin REST, catalog, products, get product, v3 path `/stores/:store_hash/v3/catalog/products/:product_id` | **Boundary change required** |
| Adobe Commerce | `https://developer.adobe.com/commerce/php/` | Same | Adobe developer domain. Page states it covers Adobe Commerce **and** Magento Open Source | Shared technical content, not edition-exclusive | **PARTIALLY VERIFIED** (operator Adobe; shared-edition content) |
| Adobe Commerce | `https://developer.adobe.com/commerce/frontend-core/` | Same | Same | Shared frontend content | **PARTIALLY VERIFIED** |
| Magento Open Source (discovery) | `https://developer.adobe.com/open/magento` | Same | Lists community projects on GitHub: Magento Open Source, DevDocs, Merchant Documentation | Open Source community entry; DevDocs is the Open Source developer docs repository | **Discovery only** (see section 3) |
| Shift4Shop | `https://developer.3dcart.com/` | Same | Titled "Developer Portal" for Shift4Shop REST API. No owner line read | Build an App, Build a Theme, API Reference, Front-end API | **UNVERIFIED** owner |
| Shift4Shop (vendor support) | `https://support.3dcart.com/Knowledgebase/Article/View/370/6/how-can-i-create-an-app-for-shift4shop` | Same | Vendor support knowledgebase. States developers register on **the REST API portal**, and the link target is **`https://apirest.3dcart.com/`** | REST API reference | **PARTIALLY VERIFIED** (vendor support page names `apirest.3dcart.com` as the REST API portal; `developer.3dcart.com` is not named by that page) |
| WordPress | `https://developer.wordpress.org/` | Same | Footer: "The WordPress trademark is the intellectual property of the WordPress Foundation". Site content is run by the WordPress documentation team (earlier search) | Developer resources: Block Editor, Themes, Plugins, Common APIs, API Reference | **PARTIALLY VERIFIED**: trademark owner is the Foundation; **operational stewardship** is the documentation team. These are not the same, and domain ownership is not stated on the page |

## 2. Findings that change the boundaries
1. **BigCommerce host change.** The approved host `developer.bigcommerce.com` redirects to `docs.bigcommerce.com`. Under the allowlist rules, a redirect to a host that is not approved is refused. Either the approved host becomes `docs.bigcommerce.com`, or the redirect is refused. This is a boundary change for WDS to decide (C1 and this item).
2. **BigCommerce API reference location.** The product catalog reference is under `docs.bigcommerce.com/developer/api-reference/rest/admin/...`, not under `/docs/*` on the approved host.
3. **Shift4Shop REST API portal host.** The vendor support page names `apirest.3dcart.com`, not `developer.3dcart.com`. Both are under the `3dcart.com` domain. Owner of the domain is still not stated on any page read.
4. **Adobe Commerce and Magento Open Source share content.** The Adobe Commerce PHP and frontend pages say they cover both editions. A prefix on these paths permits shared content for both editions, which conflicts with MAG-01's separation.

## 3. Discovery for C4 (Magento Open Source)
- Open Source developer documentation: `devdocs.magento.com` (DevDocs repository on GitHub, linked from `developer.adobe.com/open/magento`).
- Merchant docs: separate, not in scope.
- Shared with Adobe Commerce: the PHP and frontend pages above. These need an edition label on each page before use.
- Proposed Open Source page list is in `SOURCE_CHANGE_REQUEST_2026-10-26.md` (to be approved in chat).

## 4. Not verified in this round
- The owner of `developer.woocommerce.com`, `developer.bigcommerce.com` / `docs.bigcommerce.com`, `developer.adobe.com`, `developer.3dcart.com`, `apirest.3dcart.com`, and `developer.wordpress.org` as the registered domain holder. No WHOIS or legal page was read.
- Redirect chains beyond the first hop observed.
- Any page not listed above.

## C4 Magento Open Source fetch (26 October 2026, limited, read-only)
- Requested: `https://devdocs.magento.com/guides/v2.4/`. **Redirected** to `https://developer.adobe.com/commerce/docs/` (Adobe Commerce Developer Documentation). The devdocs host is therefore not an independent Open Source documentation host today.
- `https://developer.adobe.com/open/magento` (community entry, read earlier): lists Magento Open Source on GitHub, DevDocs on GitHub, and Merchant Documentation. These are repositories, not runtime documentation pages.
- Result: **no Open Source-only runtime page list can be proposed yet.** The devdocs redirect and the shared Adobe pages mean edition-specific pages must be identified individually and approved one by one.
- Redirect rule applied: devdocs.magento.com to developer.adobe.com is a cross-host redirect to an unapproved host, so it is refused under the allowlist rules.
