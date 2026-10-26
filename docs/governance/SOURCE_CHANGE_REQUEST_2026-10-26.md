# Source change request (26 October 2026): for WDS chat decision

**Status: request only. No change is applied.** Each item needs an explicit chat decision before any boundary changes or any retrieval happens.

## C0. One-time verification fetches (new authority needed)
- **Why:** ownership cannot be verified from search results. The verification needs the owner's own pages.
- **Proposed fetch set (pages only, read once, hash recorded):**
  - `https://developer.woocommerce.com/guides/` (WooCommerce ownership context)
  - `https://developer.bigcommerce.com/docs/` (BigCommerce ownership context)
  - `https://developer.adobe.com/commerce/php` (Adobe operator context)
  - `https://developer.3dcart.com/` (Shift4Shop ownership) **only if you approve it separately below**
  - `https://developer.wordpress.org/apis` (WordPress context) **only if you approve it separately below**
- **Security implications:** read-only, no credentials, no store access, no crawling, no redirects followed. The content is data only.
- **Recommendation:** approve the first three. Shift4Shop and WordPress as separate items.

## C1. BigCommerce API reference paths
- **Current approved:** `developer.bigcommerce.com/docs/*`.
- **Proposed addition (exact pages, not prefixes):**
  - `/api-reference/catalog/catalog-api/products/getproducts` and `/api-reference/catalog/catalog-api/variants/getvariants`
  - v3 catalog pages, and the v2 order pages, which the third-party sources say are still on v2.
- **Reason:** the `/docs/*` prefix covers the guides, but the API reference sits under `/api-reference/`, which is outside it.
- **Recommendation:** approve only the exact pages, after the owner check. Do not add the whole `/api-reference/` tree.

## C2. Adobe Commerce: prefixes or exact endpoints?
- **Current approved:** `/commerce/php`, `/commerce/frontend-core`, `/commerce/marketplace`. These are prefixes. Anything under them would be allowed.
- **Proposed boundary:** exact page lists, one per topic the requirement names, with the edition and version stated.
- **Reason:** prefixes broaden access silently. Exact pages keep the boundary auditable.
- **Recommendation:** convert to exact pages. Keep the prefixes only if you explicitly decide to keep them.

## C3. Shift4Shop ownership check
- **Current:** `developer.3dcart.com` is deferred, owner unverified.
- **Proposed:** one fetch of the vendor's own official site, to confirm the owner, and then decide the portal.
- **Recommendation:** approve the owner check only. No documentation path is approved by this item.

## C4. Magento Open Source edition boundary
- **Current:** `devdocs.magento.com` is deferred. Search shows Adobe Commerce content on it.
- **Proposed:** WDS confirms which pages are Open Source only, and approves those pages by exact URL.
- **Recommendation:** approve only after the page list is supplied.

## C5. WordPress
- **Current:** `developer.wordpress.org` not approved. Search showed the WordPress Documentation Team runs it. Foundation ownership not confirmed.
- **Proposed:** one owner check, then approve exact handbook pages if needed for WooCommerce work.
- **Recommendation:** approve the owner check only.

## Security implications (all items)
- A fetch is retrieval. Retrieval happens only after approval. Each fetch records URL, time, status and content hash.
- No redirects followed. Any redirect to another host is refused and reported.

## Decision requested
Reply with decision IDs: C0 (first three fetches), C1, C2, C3, C4, C5. For each, approve, amend or reject.
