# Source verification matrix (26 October 2026)

**Method used:** web search only (discovery). **No page was fetched from any domain.** Search results are not ownership proof. Each row below says what the search showed and what is still unverified.

**Configuration state:** code allowlists and platform profiles are unchanged. Every profile keeps `approved_source = None`. No source is activated.

| Source | Approved entry (cdfea8a) | Exact URLs seen in search | Ownership evidence (search only) | Edition / section evidence | Redirects | Status | Conditions to activate |
|---|---|---|---|---|---|---|---|
| WooCommerce | `developer.woocommerce.com` `/docs/*`, `/guides/*` | `https://developer.woocommerce.com/guides/`; `https://developer.woocommerce.com/docs/llms.txt` | WordPress.org listing says WooCommerce is developed and supported by Automattic. Developer-site statement not seen | REST API, Core API, Store API, WooCommerce Admin, Blocks, hook index listed on the guides page | None observed in search | Partially verified | Verify Automattic ownership on the developer site, by a fetch that has been approved |
| BigCommerce | `developer.bigcommerce.com` `/docs/*` | `https://developer.bigcommerce.com/docs/` (home) | Domain matches product. Owner statement not seen | Storefront, store operations, apps. Third-party sources point to `/api-reference/catalog/...` and to v2/v3 | Not observed | Partially verified | Verify owner; add the API reference paths (see change request C1) |
| Adobe Commerce | `developer.adobe.com` `/commerce/php`, `/commerce/frontend-core`, `/commerce/marketplace` | `https://developer.adobe.com/commerce/php`; `.../frontend-core`; `.../marketplace/`; `experienceleague.adobe.com/en/docs/commerce` | Adobe developer domain. Operator is Adobe on the search evidence | PHP extensions, frontend, Marketplace. Also cross-referenced to Magento Open Source | Not observed | Partially verified | Decide prefix vs exact page list (see change request C2) |
| WordPress (`developer.wordpress.org`) | Not approved | `https://developer.wordpress.org/apis`; `https://developer.wordpress.org/advanced-administration/` | Run by the WordPress Documentation Team, with handbook maintainers. Foundation ownership **not confirmed** by search | API clearinghouse and developer handbooks | Not observed | **Not verified; not approved** | Confirm ownership; approve paths separately |
| Magento Open Source (`devdocs.magento.com`) | Deferred (not approved) | `https://devdocs.magento.com/guides/v2.2/rest/catalog-notes.html`; `.../v2.4/graphql` | Search shows the domain now presents Adobe Commerce content | Mixed Open Source and Adobe Commerce pages; edition boundary unclear | Not observed | **Deferred** | Edition boundary and owner confirmed |
| Shift4Shop (`developer.3dcart.com`) | Deferred | `https://developer.3dcart.com/` ("Developer Portal") | No owner named in results. Third-party sites cite other hosts that conflict | REST API reference, Build an App, themes, front-end API | Not observed | **Deferred; ownership not verified** | Owner confirmed on the vendor's own site |

## Notes
- The search result for BigCommerce orders is a third-party reference. Official order pages still need a check.
- Search evidence does not satisfy "verified official ownership". Activation needs a fetch, and a fetch needs a separate approval.
