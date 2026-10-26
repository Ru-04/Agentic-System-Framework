# Official evidence-source register (proposal, 26 October 2026)

**Status: PROPOSAL. Nothing is approved. Retrieval is default-deny.** Every domain or path below is a *candidate* that WDS must verify (ownership, current location, applicability) before approval. No source was fetched. Each approved source is added to the allowlist separately, with its own record.

Rules for every row:
- https only; exact host; exact paths listed; no crawling; no redirects followed; no third-party mirrors.
- Vendor documentation only. Secondary material is excluded (D08).
- Version applicability must be recorded for each claim. A claim without a version is not evidence.
- Retrieved text is data for evaluation, never an instruction.

| # | Specialist | Official documentation (candidate) | Allowed paths | Version applicability | Provenance and retrieval | Restrictions | Status |
|---|---|---|---|---|---|---|---|
| 1 | Shift4Shop (formerly 3dcart) | **None identified in the repository. WDS to supply the official source.** | None until supplied | Exact platform version required | Named-page retrieval once approved | No claim without an exact version | **Not approved; not identified** |
| 2 | WordPress & WooCommerce | `woocommerce.com` documentation (candidate); `developer.wordpress.org` (candidate) | WDS to name exact documentation paths | WordPress, WooCommerce and PHP versions; installed plugin set | Named-page retrieval; each fetch records URL, time, status and content hash | Plugin claims checked only against that plugin's documentation | **Candidate, not approved** |
| 3 | BigCommerce | `developer.bigcommerce.com` (candidate) | WDS to name exact documentation paths | Store plan; API scopes; REST or GraphQL variant | Named-page retrieval | Plan- and scope-dependent claims need the plan and scope recorded | **Candidate, not approved** |
| 4 | Magento Open Source and Adobe Commerce | `developer.adobe.com/commerce` (candidate); `devdocs.magento.com` (candidate) | WDS to name exact documentation paths, per edition | **Edition, version and deployment model.** Editions are separate sources | Named-page retrieval per edition | Never treat one edition as equivalent to the other | **Candidate, not approved** |
| 5 | Standalone Applications | **No single vendor. Depends on the technology named in the requirement** (for example a desktop or mobile framework). WDS to name the technology and its official documentation | None until the technology is named | Exact runtime or framework version | Named-page retrieval per technology | Each technology is a separate source; no universal source | **Not identified** |
| 6 | Middleware Applications | **No single vendor. Depends on the middleware product named in the requirement** (for example an integration or messaging product). WDS to name the product and its official documentation | None until the product is named | Exact product version | Named-page retrieval per product | Each product is a separate source; no universal source | **Not identified** |

## Notes
- Standalone and Middleware cannot be given a single official source, because the requirement decides the technology. The register does not invent one.
- Shopify is not in this list. Its approved and candidate sources are in `docs/AI_S04_VENDOR_SOURCE_ACCESS_MATRIX.md` (integration branch), which also lists its candidate `shopify.dev` domain. That matrix is preparation, not approval.
- The approved-source list is empty for all six platforms. Default deny applies until WDS approves each entry.

## Decisions WDS must make
1. Approve or amend each candidate domain and path in rows 2–4.
2. Supply the official source for Shift4Shop (row 1).
3. Name the technology for Standalone Applications and the product for Middleware Applications (rows 5 and 6).
4. Confirm the version and edition to test first for Magento (row 4).
