# M2 Sprint 5: source activation matrix (2 November 2026)

Authority: WDS management decision, Sprint 5, section 2 ("Additional Documentation Sources"). Scope: previously approved boundaries whose ownership, exact-path, edition, version and security conditions are satisfied. No domain-wide access. No unknown source. Every activation below is read-only and exact-path.

## 1. Activated (2 November 2026)

| Field | Adobe Commerce exact pages | Magento Open Source release notes |
|---|---|---|
| Source ID | `adobe_commerce_exact_pages` | `magento_open_source_release_notes` |
| Permitted host and paths | `developer.adobe.com`: exact `/commerce/webapi/rest/`, `/commerce/webapi/graphql/`, `/commerce/extensibility/events/` | `experienceleague.adobe.com`: exact `/en/docs/commerce-operations/release/notes/magento-open-source/overview` |
| Publisher and verification | Adobe (partially verified, Adobe operator). Browser check of all three pages on 2 Nov 2026: Adobe Commerce developer content, Adobe navigation. Owner statement not found | Adobe (owner confirmation not recorded). Browser check on record (MAGENTO-01). Owner statement not found |
| Platform and edition | `adobe_commerce` / Adobe Commerce only | `magento_open_source` / Magento Open Source. **Release and version claims only**; feature claims are UNSUPPORTED_SOURCE |
| Activation authorization | WDS management decision, Sprint 5 section 2, 2 Nov 2026 | Same |
| Retrieval restrictions | HTTPS, exact path only, no children, no query, redirects not followed, read-only | Same |
| Version applicability | Neither page states a version, so no claim can cite a version. Every capability is UNKNOWN | Page states no version. Release history is UNKNOWN for any version |
| Timestamp and provenance | Retrieved 2026-11-02 (see `SPRINT5_REAL_EVIDENCE_2026-11-02.json`) | Same |
| Security test results | `tests/unit/test_sprint5_activation.py` (6 passed): sibling page never requested; a title cannot supply a passage; Magento feature claims refused; activated body passage supports its capability. Full unit suite passes | Same |

Not in the activation: the Adobe **shared PHP** page (`adobe_shared_php`). Its ownership check was NOT CHECKED under the authorization. It stays APPROVED BUT INACTIVE.

## 2. Previously active (28 October 2026, unchanged)

| Source | Status | Notes |
|---|---|---|
| `woocommerce_docs` (`developer.woocommerce.com` `/docs`, `/guides`) | APPROVED AND ACTIVE | Ownership partially verified. Only `/docs/*` and `/guides/*`. Unchanged |
| `bigcommerce_docs_product_page` (exact product page) | APPROVED AND ACTIVE | Owner not confirmed. Single-product scope. Unchanged |

## 3. Not activated, with reasons

| Source | Status | Reason | What is needed |
|---|---|---|---|
| Shopify (`shopify_docs`) | APPROVED BUT INACTIVE | **Not eligible.** See section 4 | Reconcile the decision records and correct the boundary definition (section 4) |
| Shift4Shop (`shift4shop_3dcart_discovery`) | DISCOVERY ONLY | Ownership NOT VERIFIED. B4 deferred. No retrieval path approved | Ownership verification, then exact pages, then separate WDS authorization |
| WordPress core (`wordpress_core_docs`) | NO APPROVED SOURCE | B6 deferred. No domain approved | WDS authorization of a named domain, then ownership verification and exact paths |
| Standalone Applications (`NO_APPROVED_SOURCE`) | NO APPROVED SOURCE | No technology named. The registry says WDS must name one first | WDS names a technology; then a source proposal and separate authorization |
| Middleware Applications (`NO_APPROVED_SOURCE`) | NO APPROVED SOURCE | No product named. The registry says WDS must name one first | WDS names a product; then a source proposal and separate authorization |
| Adobe Commerce Marketplace (proposal) | DEFERRED | Not in ADOBE-01 | Separate authorization |
| Adobe Commerce frontend-core | REJECTED | Edition not established | Not applicable now |
| devdocs.magento.com | REJECTED | Contributor guide refused (C4) | Not applicable now |

No exact boundary is proposed for Shift4Shop, WordPress core, Standalone or Middleware in this record. Each needs an ownership check first, and writing exact paths before that check would be inventing them.

## 4. Shopify: reconciliation of the S2 approval record

The management decision asked for the missing S2 record to be reconciled. The record is **present**: `docs/governance/DECISION_REGISTER_SPRINT2.md`, decisions S2-D07 to S2-D12. The statement in `sources.json` and the Sprint 5 plan that the record was "not located" is **wrong** and is corrected here.

| Decision | What it approves | Status in the record | Effect on the code |
|---|---|---|---|
| S2-D07 | `help.shopify.com`: permitted access methods only. **Do not bypass HTTP 403 or anti-bot protection** | One page read through an authorized browser on 22 Oct 2026. The fetch client still gets HTTP 403. Browser text was not ingested | The code's `SHOPIFY_INACTIVE` lists `help.shopify.com` as a whole host. D07 does not approve a whole host, and does not define paths |
| S2-D08 | `shopify.com` `/pricing` and `/plus` (and `www`) only | **Flagged for decision-maker confirmation.** Both pages returned HTTP 403, so no plan document was retrieved | Code matches D08 (`SHOPIFY_PLAN_SCOPES`) |
| S2-D09 | Canadian government (CRA) pages | This decision is about **canada.ca, not Shopify**. `engine.py` cites "S2-D07 to S2-D09" for Shopify, which includes an unrelated decision | Citation error in `engine.py` comment |
| (none) | `shopify.dev` | **No decision record approves `shopify.dev`** | The code's `SHOPIFY_INACTIVE` lists it as a whole host |
| Ownership | — | `NOT RECORDED` in `sources.json` | Mandatory verification unresolved |

**Conclusion: Shopify is not eligible for activation.** Its mandatory conditions are unresolved: ownership is not recorded, S2-D08 is not confirmed, the plan pages are blocked (403) and the boundary is not bypassable, and the coded boundary is broader than the approved decisions (`help.shopify.com` whole host, `shopify.dev`). I made no change to Shopify configuration, because the boundary is inactive and changing it needs a WDS decision on the scope. **OPEN for WDS:** confirm S2-D08, restrict `help.shopify.com` and remove `shopify.dev` (or record its approval), and correct the S2-D09 citation.

## 5. Scope statement

Nothing in this matrix authorizes unrestricted domain access, crawling, or any source not listed above. Retrieval uses the approved pilot opener, which identifies itself, follows no redirects, and makes no proxied call.
