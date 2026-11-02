# M2 Sprint 5: real evidence report (2 November 2026)

**Status: engineering record. Not an acceptance decision.** This supersedes the earlier record `SPRINT5_REAL_EVIDENCE_RECORD_2026-11-02.md` for the current extraction. The machine record is `SPRINT5_REAL_EVIDENCE_2026-11-02.json`.

## 1. What was retrieved, and how

- Five exact approved pages: the two pilot pages (28 October boundaries) and three Adobe Commerce exact pages plus the Magento Open Source release-notes page (activated 2 November 2026).
- Retrieval: the approved read-only opener, redirects not followed, exact paths only. Run timestamp `2026-11-02T07:44:37Z` (see the JSON).
- Text extraction changed during this run (section 4). Digests in the earlier record (07:06 run) are not comparable to the digests here.

## 2. Results

| Case | Source | Capability | Requested version | Outcome | Passage | Verified claim |
|---|---|---|---|---|---|---|
| WooCommerce products reference | `woocommerce_docs` | product variation pricing | none | UNKNOWN | none | None. Variation and price occur in the page but not in one sentence |
| BigCommerce get-product | `bigcommerce_docs_product_page` | product catalog read | v3 | **VERIFIED** (single product) | endpoint line `…/v3/catalog/products/1` | Single-product retrieval through the v3 product endpoint, narrow |
| Adobe REST overview | `adobe_commerce_exact_pages` | REST product read | none | UNKNOWN | none | None. No version stated, and no sentence states the capability |
| Adobe GraphQL overview | `adobe_commerce_exact_pages` | GraphQL query | none | UNKNOWN | heading "GraphQL overview" | None. Version not stated; the passage is a heading |
| Magento Open Source release notes | `magento_open_source_release_notes` | release history | none | UNKNOWN | heading "Release information" | None. No version stated |

Summary: **one verified claim, narrow.** Four UNKNOWN. No unsupported claim was made. No citation was made without a passage.

## 3. Per-claim fields

### 3.1 BigCommerce single-product retrieval (VERIFIED, narrow)
- Requirement: read a single product through the BigCommerce product page.
- Specialist and capability: `bigcommerce`, `product catalog read`.
- Evidence URL: `https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product`.
- Publisher: BigCommerce. Owner not confirmed (`sources.json`).
- Edition: not applicable.
- Version applicability: `v3`, read from the page's API path. Not stated in the requirement.
- Retrieval timestamp: recorded in the JSON.
- Content digest and passage digest: in the JSON.
- Feasibility: single-product retrieval through the v3 endpoint is supported by this page. Nothing broader.
- Limitations: the passage is an endpoint path, not a descriptive sentence. Listing, searching and other catalog operations are unknown (`COVERAGE` in `specialists.py`). Owner unconfirmed.

### 3.2 Unknowns (WooCommerce, Adobe, Magento)
For each: requirement, specialist and capability, URL, publisher and verification status, version applicability (none stated), feasibility UNKNOWN, limitations as above. These are recorded so that a future reader does not mistake a missing claim for a checked negative.

## 4. Change to the text extraction, and why it matters

- **Defect found:** the document title was included in the page text. For the Adobe GraphQL page, the title "GraphQL overview" was a passage containing the required term. A title can name a capability without describing it, so it cannot support a claim.
- **Fix:** the title element is removed from the body before text extraction (`retrieval.py`). The title stays in `Page.title` for provenance. Regression test: `test_the_document_title_cannot_supply_a_passage`.
- **Remaining defect (OPEN, for PG review):** headings still supply passages. The Adobe GraphQL and Magento results above are headings. A rule that requires a minimum body length or a sentence of prose is a design choice I did not make without approval. Until it is decided, a heading-only passage can produce a claim **only** when the version is also stated and matches, which none of these pages does.
- **Effect:** the digests of both pilot pages changed. The 28 October pilot digests are historical.

## 5. Source-applicability and version limits

- No activated page states a version, so no version-specific claim can be made from any of them today.
- The Adobe pages are Adobe Commerce pages. ADOBE-01 forbids attributing their features to Magento Open Source. The runner enforces this at requirement level (`S5-025`). This is not tested against page content.

## 6. What this record does not establish

- No real evidence exists for Shopify, Shift4Shop, WordPress core, Standalone or Middleware.
- No real evidence establishes any Adobe or Magento capability for any version.
- The scenario scores are requirement-level routing on synthetic fixtures and are not evidence about any vendor.
