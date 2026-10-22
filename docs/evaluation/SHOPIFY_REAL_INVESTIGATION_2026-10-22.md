# Shopify real investigation — run record (22 October 2026)

**Status:** executed run record. **Not acceptance evidence.** Acceptance under D11 needs independent QA review of these outputs (AS sign-off, not yet given).

**Run:** the Shopify specialist (`ShopifySpecialist`, minimum two distinct matched terms) was run once per brief requirement, against the corpus below. Every output is `incomplete` by design. Feasibility is never determined.

## 1. Evidence corpus (live, allowlisted, metadata only)

| Source | URL | Result | Characters | SHA-256 |
|---|---|---|---|---|
| shopify-doc-01 | https://shopify.dev/docs/api/storefront/latest | retrieved | 32212 | `34a565281e9fc1dd…` |
| shopify-doc-02 | https://shopify.dev/docs/api/admin-graphql/latest | retrieved | 18016 | `b101a4e02edca93a…` |
| shopify-doc-03 | https://shopify.dev/docs/api/admin-graphql/latest/objects/Metafield | retrieved | 7888 | `9141383d93e89b80…` |
| shopify-doc-04 | https://shopify.dev/docs/api/storefront/latest/queries/product | retrieved | 31523 | `32fcdb98a936feff…` |
| shopify-doc-05 | https://shopify.dev/docs/apps/build/checkout | retrieved | 17607 | `fa1760df1f7fb1d9…` |
| shopify-doc-06 | https://shopify.dev/docs/apps/build/online-store/theme-app-extensions | retrieved | 4119 | `0a4a6df101b41f33…` |
| shopify-doc-07 | https://shopify.dev/docs/apps/build/functions | retrieved | 9185 | `e010c3b645df9c59…` |
| shopify-doc-08 | https://shopify.dev/docs/apps/build/metafields | retrieved | 15578 | `ee7e2380e45d7e98…` |
| shopify-doc-09 | https://shopify.dev/docs/apps/build/app-extensions | retrieved | 6598 | `0173e1d00eef60a5…` |
| shopify-doc-10 | https://shopify.dev/docs/apps/build/app-extensions/list-of-app-extensions | retrieved | 4708 | `5dcc05778e10e757…` |
| shopify-doc-11 | https://shopify.dev/docs/apps/build/discounts | retrieved | 13655 | `8c7d020dccb1c942…` |
| shopify-doc-12 | https://shopify.dev/docs/apps/build/online-store | retrieved | 10820 | `d49b727183931763…` |
| shopify-doc-13 | https://shopify.dev/docs/apps/build/customer-accounts | retrieved | 9457 | `db64041581a61ce1…` |
| shopify-doc-14 | https://shopify.dev/docs/apps/build/markets | retrieved | 19198 | `388346c1712fdd10…` |
| shopify-doc-15 | https://shopify.dev/docs/apps/build/admin | retrieved | 9595 | `27cfce4bffa5d361…` |
| shopify-doc-16 | https://shopify.dev/docs/apps/build/authentication-authorization | retrieved | 10404 | `a0f7c15ad8595913…` |

Help-centre pages on `help.shopify.com` were not included: they returned HTTP 403 to the fetch client.

## 2. Results per brief requirement

| Brief | Requirement | Status | Cited findings | Sources cited | Option classes evidenced | Gaps reported |
|---|---|---|---|---|---|---|
| SH-CASE-01 | Validate Canadian postal addresses at checkout, including rural and remote addresses | incomplete | 14 | shopify-doc-05 | custom code against a documented API, third-party app or extension | 1 of 3 |
| SH-CASE-01 | Capture province explicitly at checkout instead of IP-based detection | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-01 | Let a customer renew a subscription from the order status page without an account | incomplete | 3 | shopify-doc-09, shopify-doc-13 | none | 3 of 3 |
| SH-CASE-01 | Create a customer account after purchase reusing checkout details | incomplete | 4 | shopify-doc-01, shopify-doc-13 | custom code against a documented API, third-party app or extension | 1 of 3 |
| SH-CASE-01 | Calculate tax and fixed levies for a digital subscription and hide shipping fields | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-02 | Dedicated page per artist with featured works in the online store | incomplete | 2 | shopify-doc-01 | custom code against a documented API | 2 of 3 |
| SH-CASE-02 | Faceted product filters with AND OR logic that update without a page reload | incomplete | 1 | shopify-doc-10 | native Shopify configuration | 2 of 3 |
| SH-CASE-02 | Search with autocomplete and typo tolerance across a large catalogue | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-02 | Keep the checkout behaviour unchanged | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-03 | Campaign pages with real-time sales tracking per fundraiser | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-03 | Permanent partner stores coexisting with campaign stores | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-03 | Role-based staff permissions for partners and administrators | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-03 | Synchronize orders and product data with external systems through webhooks and the Admin API | incomplete | 15 | shopify-doc-08, shopify-doc-14 | custom code against a documented API, native Shopify configuration | 1 of 3 |
| SH-CASE-04 | Pickup time slots with capacity limits and cut-off times enforced at checkout | incomplete | 5 | shopify-doc-05 | third-party app or extension | 2 of 3 |
| SH-CASE-04 | Blackout dates and holidays for pickup | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-04 | Staff dashboard with daily volume reporting | incomplete | 0 | — | none | 3 of 3 |
| SH-CASE-04 | Automated order preparation timelines using workflow automation | incomplete | 0 | — | none | 3 of 3 |

## 3. Interpretation limits

- A cited finding means a retrieved passage shares at least two meaningful terms with the requirement and matches a Shopify topic or option class. It is not a judgement that the passage answers the requirement.
- Passages from the official docs were spot-checked. Several are relevant (for example, local pickup through Shopify Functions for SH-CASE-04). Others are tangential (for example, a checkout UI extension example for a postal-validation requirement). This record makes no relevance claim beyond the matched-term rule.
- Requirements with no cited finding (for example, Canadian postal and province rules, customer-account creation after purchase, campaign sales tracking, role-based staff permissions, search and autocomplete) are gaps. The corpus does not cover them. They need additional approved sources, which the current allowlist does not provide.
- Feasibility is not determined for any requirement. Every output carries the clarification question for the plan tier.
- The specialist does not apply a plan or version check. Plan-specific wording is reported as an unknown only when the matched passage contains it.

## 4. Gap register (for the human reviewer)

| Gap | Why it matters | Needed to close |
|---|---|---|
| Canadian address validation and province rules | Core to SH-CASE-01 | Approved Canadian tax, shipping or address documentation; an approved address-validation app's official docs |
| Customer account creation after purchase; guest renewal | Core to SH-CASE-01 | Approved customer-accounts documentation beyond the overview page |
| Campaign tracking, permanent partner stores, staff roles | Core to SH-CASE-03 | Approved multi-store, markets and staff-permission documentation |
| Search, autocomplete, faceted filters | Core to SH-CASE-02 | Approved Search & Discovery and filter documentation; a decision on the AI search component (D09) |
| Pickup blackout dates, staff dashboard, workflow automation | Core to SH-CASE-04 | Approved local pickup, Flow and reporting documentation |
