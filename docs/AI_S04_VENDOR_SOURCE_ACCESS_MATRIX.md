# AI-S04 Vendor Source and Access Approval Matrix

Status: **approval-ready request, nothing approved.** Default deny applies to every row. No domain below has been accessed,
and no vendor retrieval, sandbox access or credential has been used. Domains marked *candidate* are unverified: WDS must
confirm each one before it is added to the allowlist (C-06).

Exclusions for all rows: no client production environment, no real client data, no unapproved vendor credential, no live
retrieval during preparation (synthetic or sanitised examples only).

## 1. Matrix

| Platform | Candidate official documentation domains | Versions and editions to identify | Test-store or sandbox access | Intended API permissions (read-only first) | Permitted test data | Retrieval and evaluation method | Credential handling | Freshness and citation rule |
|---|---|---|---|---|---|---|---|---|
| **Shopify** | `shopify.dev` (candidate) | Plan; API version (for example a dated Admin API version); Storefront API version; app-development version | Development store on an approved partner or development account | Read-only Admin and Storefront queries; no write scopes in the first round | Synthetic catalogue, synthetic customers, synthetic orders | Retrieve named pages on the approved domain only; compare claims against cited paragraphs | Approved development-store token, held in the approved secret store; never in code, fixtures or documents | Record page URL, version label and check date; reject undated claims; mark superseded API versions |
| **WordPress / WooCommerce** | `woocommerce.com` documentation paths (candidate); `developer.wordpress.org` (candidate) | WordPress core version; WooCommerce version; PHP version; approved plugin set | Test site on an approved host, with an approved plugin list | WooCommerce REST API read-only keys on the test site | Synthetic products, orders and customers | Retrieve named pages only; check each plugin claim against its own documentation | Approved consumer key and secret on the test site only; rotated after evaluation | Record URL, version and date; reject claims not tied to the installed version |
| **BigCommerce** | `developer.bigcommerce.com` (candidate) | Store plan; API scopes granted; GraphQL and REST variant in use | Sandbox store on an approved account | Read-only API scopes first; no write scopes in the first round | Synthetic catalogue and orders | Named-page retrieval; compare plan- and scope-dependent claims | Approved API account token, held in the approved secret store | Record URL, plan and scope, and date; reject plan-dependent claims without the plan |
| **Shift4Shop (formerly 3dcart)** | *No domain identified in this repository.* WDS to supply the official documentation source | Exact platform version (the specialist requires it); themes and API version in use | Test store on an approved account | Read-only API key first | Synthetic catalogue and orders | Named-page retrieval once a domain is approved | Approved API key on the test store only | Record source, version and date; reject claims without an exact version |
| **Magento Open Source and Adobe Commerce** | `developer.adobe.com/commerce` (candidate); `devdocs.magento.com` (candidate) | **Edition (Open Source or Adobe Commerce), tested separately**; version; deployment model; installed modules | Staging instance per edition on approved hosting | Read-only REST or GraphQL token per edition | Synthetic catalogue and orders | Named-page retrieval per edition; never treat an edition as equivalent to the other | Approved integration token per instance; stored in the approved secret store | Record edition, version and date; reject cross-edition claims |

## 2. Access mechanism (all rows)

- Retrieval only from the approved domain list. No crawling, no search-engine lookup, no third-party mirror.
- Each fetch is recorded: URL, time, response status, and content hash. The evaluation cites the recorded hash.
- Retrieved text is stored as data for evaluation only and is never executed or treated as an instruction.
- Each platform's allowlist entry is added separately, after its approval, so an unapproved domain is refused.

## 3. Approval requests

1. Approve or amend each candidate domain in section 1 (WDS to verify ownership and current location).
2. Supply the official documentation source for Shift4Shop.
3. Approve test-store or sandbox access for each platform, and name the holder.
4. Approve the read-only API permission set for each platform.
5. Approve the secret-storage mechanism for test credentials.
6. Approve the retrieval mechanism (named-page retrieval only).
7. Choose the Magento edition to test first and confirm the second edition follows.

## 4. Verification order (WDS sequence)

1. Shopify
2. WooCommerce
3. BigCommerce
4. Shift4Shop
5. Magento Open Source, then Adobe Commerce

Parallel verification is permitted when reviewers, source access and environment capacity are available. A platform is
not marked verified without its official documentation or authorised test evidence.
