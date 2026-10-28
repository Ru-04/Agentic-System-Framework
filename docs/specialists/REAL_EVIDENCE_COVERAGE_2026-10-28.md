# Real-evidence coverage report, all seven specialists (28 October 2026)

Decision S4-PILOT-EVIDENCE-01. Pilot run recorded in `docs/governance/SOURCE_PILOT_RESULTS_2026-10-28.json`. Engineering commit: see the final CI record below.

**Only two sources are active**: WooCommerce docs (`/docs/*`) and the BigCommerce exact product page. Every other source is inactive.

Status labels: VERIFIED BY APPROVED PILOT EVIDENCE, PARTIALLY VERIFIED, UNKNOWN, UNKNOWN (NO VERSION), INACTIVE SOURCE, NO APPROVED SOURCE. Synthetic fixtures are not counted here.

| Specialist | Canonical ID | Active source | Verified finding | Partial | Unknown | Inactive or none |
|---|---|---|---|---|---|---|
| Shopify | CAP-ECOMMERCE | None (boundary inactive) | None | None | Plan feature availability: UNKNOWN | Shopify boundary inactive. Human relevance labels 0 of 55 |
| Shift4Shop | CAP-3D-CART-SHIFT-SHOPIFY (legacy) | None | None | None | Product read API: UNKNOWN | Discovery only. No approved source |
| WordPress & WooCommerce | CAP-WORDPRESS-WOOCOMMERCE | WooCommerce docs (pilot) | None | None | Product variation pricing: UNKNOWN (NO VERSION). Store API products page retrieved; no version stated; no single sentence containing both variation and price | WordPress core: no approved source. Store API cart and REST product read: no pilot evidence |
| BigCommerce | CAP-BIGCOMMERCE | BigCommerce product page (pilot) | Single-product retrieval through the v3 product endpoint: VERIFIED BY APPROVED PILOT EVIDENCE (version v3, from the page path) | Broader product catalog reading: PARTIALLY VERIFIED | Product listing and searching: UNKNOWN. Other catalog operations: UNKNOWN | Order data: no approved page |
| Magento / Adobe Commerce | CAP-MAGENTO-ADOBE-COMMERCE | None | None | None | REST product read, GraphQL query, release history, catalog import: UNKNOWN | Adobe exact pages and shared PHP page inactive. Magento release notes inactive. Adobe ownership checked for one page only |
| Standalone Applications | CAP-STANDALONE-APPLICATIONS | None | None | None | Architecture selection: no technology selected | NO APPROVED SOURCE |
| Middleware Applications | CAP-MIDDLEWARE-APPLICATIONS | None | None | None | Webhook delivery retry: no product selected | NO APPROVED SOURCE |

## Notes

1. **BigCommerce overstatement control.** The engine verifies the narrow page, and the provider reports only the single-product claim. Broader reading and listing are reported as partial or unknown. This is enforced by `COVERAGE` in `src/webdesk/investigation/specialists.py` and by tests in `tests/unit/test_capability_overstatement.py`.
2. **WooCommerce page relevance.** The Store API products page documents variations and retrieval of variations, but no single sentence contains both "variation" and "price". Variation pricing is therefore not reported as verified, even with a stated version.
3. **Excluded response.** The earlier WooCommerce variations URL returned a Page Not Found body with HTTP 200. Retrieval now excludes any not-found body, and that URL is not evidence.
4. **Version applicability.** No version applicability is inferred from another page. The WooCommerce page states no version. The BigCommerce version (v3) is taken from the endpoint path on its own page.
5. **Citations.** Citations carry the page digest and a passage digest. The evidence locator is the passage digest.
6. **Synthetic results.** Synthetic test outcomes are not counted as real investigations.

## Citation metadata (added 28 Oct 2026)

Each pilot citation now carries the source identifier (`woocommerce_docs`, `bigcommerce_docs_product_page`), the retrieval time, the document title from the page's title element, the version the engine checked, and the digest of the matched passage. The provider's evidence reference contract (`source_id`, `locator`) holds the source URL and the passage digest. It has no field for title or version, so those are held in the engine citation and the pilot results file, not in the adapter response.
