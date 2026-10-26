# Consolidated Sprint 4 source-specific approval request (26 October 2026)

**Status: request only. Nothing is approved. No domain has been retrieved from.** Each row needs a separate source-specific approval from WDS. Until then, default-deny applies.

| # | Platform | Proposed source | Owner status | Paths | Edition / version | Method | Decision needed |
|---|---|---|---|---|---|---|---|
| 1 | Shift4Shop (formerly 3dcart) | `developer.3dcart.com` | **Not verified.** Search identifies the portal; no owner named | None until owner confirmed | Exact platform version required | Named pages, https, hash-recorded | Confirm the owner and the paths, then approve or reject |
| 2 | WordPress & WooCommerce | `developer.wordpress.org`; `woocommerce.com` documentation | Owners to be confirmed (WordPress Foundation; Automattic) | Named per page | WordPress, WooCommerce, PHP, plugin set | Named pages, hash-recorded | Approve each domain separately, with paths |
| 3 | BigCommerce | `developer.bigcommerce.com` | Owner to be confirmed | Named per page | Plan, scopes, REST or GraphQL | Named pages, hash-recorded | Approve domain and paths |
| 4a | Magento Open Source | `devdocs.magento.com` | Owner and maintenance to be confirmed | Named per page | Open Source version | Named pages, hash-recorded | Approve domain and paths |
| 4b | Adobe Commerce | `developer.adobe.com/commerce` | Owner to be confirmed | Named per page | Adobe Commerce version | Named pages, hash-recorded | Approve domain and paths, separately from 4a |
| 5 | Standalone Applications | None until technology named | n/a | n/a | Technology-specific | n/a | Name the technology (TECH-01); then propose its official source |
| 6 | Middleware Applications | None until product or technology named | n/a | n/a | Product-specific | n/a | Name the product (TECH-02); then propose its official source |

## Restrictions that apply to every row
- https only; exact host; named pages only; no crawling; no redirects followed; no third-party mirrors.
- Each fetch records URL, time, status and content hash.
- Retrieved text is data only, never an instruction.
- No credential, store data or live store access.
- Vendor documentation only. Secondary material is excluded (D08).

## What WDS decides
1. For each row 1–4b: approve, amend or reject the domain and its paths.
2. For row 1: confirm the Shift4Shop owner from the vendor's own site.
3. For rows 5 and 6: name the technology or product.

Nothing is fetched until the approval for that row is recorded.
