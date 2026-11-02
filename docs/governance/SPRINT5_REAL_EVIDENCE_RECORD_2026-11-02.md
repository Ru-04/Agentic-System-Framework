# M2 Sprint 5: real evidence record (2 November 2026)

**Status: engineering record. Not an acceptance decision.** The two pages were retrieved once on 2 November 2026 with the approved read-only pilot (S4-PILOT-EVIDENCE-01). No other URL was requested. Nothing was activated.

Retrieval used `webdesk.investigation.pilot` (`pilot_opener`, user agent `WebDesk-pilot/1.0`). Redirects are not followed. The pages were passed to the investigation engine, which made the outcome decisions below.

## 1. Results against the 28 October 2026 pilot record

| Case | 28 Oct pilot | 2 Nov live run | Change |
|---|---|---|---|
| `woocommerce_store_api_products` | `unknown_support`, content `d64e161a…` | `unknown_support`, content `d64e161a…` | None |
| `bigcommerce_get_product` | `verified_support`, content `f321bcd6…` | `verified_support`, content `09dee690…` | **Page content changed since 28 Oct** |

The BigCommerce citation from 28 October cannot be reproduced byte for byte. Its passage was not stored, so the change cannot be inspected. The 2 November digests are the current pins. Any future citation must be re-pinned to a fresh retrieval.

## 2. Verified and unverified findings

Each row below is one requirement against one retrieved page. Fields follow the Sprint 5 plan, section 5.

### 2.1 BigCommerce: single-product retrieval (verified, narrow scope)

| Field | Value |
|---|---|
| Requirement | Read a single product through the BigCommerce product page |
| Specialist and capability | `bigcommerce`; `product catalog read` |
| Evidence URL | `https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-product` |
| Page title | Get Product \| BigCommerce Docs |
| Publisher | BigCommerce (domain and product match; **owner not confirmed** in `sources.json`) |
| Edition | Not applicable |
| Version applicability | `v3`, read from the page's API path. Stated in the page, not in the requirement |
| Retrieval timestamp | 2026-11-02T07:06:51Z (page); run started 2026-11-02T07:06:37Z |
| Content digest (page) | `09dee690b174bd1a97aa9aacd7765e559fdd090ab47b2125178aac8df49abb61` |
| Passage | One sentence: an endpoint line, `https://api.bigcommerce.com/stores/store_hash/v3/catalog/products/1` |
| Passage digest | `0df66e955ccf76effb6e920a21c875fc4bae77d581aabb6395b044fc57d37348` |
| Feasibility conclusion | Single-product retrieval through the v3 product endpoint is supported by this page. Nothing broader is |
| Limitations | The passage is an endpoint path, not a descriptive sentence. It supports the endpoint's existence, not the wording of any behaviour. Listing, searching and other catalog operations are unknown (`COVERAGE` in `specialists.py`). Publisher ownership is unconfirmed |

### 2.2 WooCommerce: product variation pricing (not supported)

| Field | Value |
|---|---|
| Requirement | Price each product variation differently on WooCommerce |
| Specialist and capability | `wordpress_woocommerce`; `product variation pricing` |
| Evidence URL | `https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/` |
| Page title | Products API \| WooCommerce developer docs |
| Publisher | Automattic (**partially verified**, via WordPress.org listing) |
| Version applicability | **Not stated on the page.** No version can be cited |
| Retrieval timestamp | 2026-11-02T07:06:51Z |
| Content digest (page) | `d64e161a84a71edbeda10dda9901131262176e2fa3dcbdd4fea53fa29e13a65e` |
| Passage | None. The page contains both `variation` and `price`, but no single sentence contains both |
| Feasibility conclusion | **UNKNOWN.** Variation pricing is not established by any sentence on this page |
| Limitations | Terms are spread across the page. A capability claim needs one passage, so none is cited. Version not stated |

This matches the WDS rule that variation pricing stays UNKNOWN on real evidence (S5-004 note).

## 3. What this record does not establish

- No real evidence exists for Shopify, Shift4Shop, Adobe Commerce or Magento Open Source, Standalone Applications, or Middleware Applications. Their sources are inactive.
- No real evidence exists for WooCommerce capability beyond the unknown above, or for BigCommerce beyond single-product retrieval.
- The scenario scores in `SPRINT5_SCORECARD_2026-11-02.json` are requirement-level routing on synthetic fixtures. They are not evidence about either vendor.
- Passage digests are checks on content as retrieved today. They are not a claim that the page was correct at any other time.

## 4. Source-activation proposal

None proposed here. Activation of any further source needs a WDS decision per source, under `SOURCE_ACTIVATION_REQUEST_2026-10-28.md`. The 28 October pilot scope is unchanged.

## 5. Reproduction

Run the pilot once with the approved opener. Results will differ when vendor pages change, so compare content digests before comparing outcomes.
