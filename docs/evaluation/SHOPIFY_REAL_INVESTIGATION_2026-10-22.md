# Shopify real investigation and relevance evaluation (22 October 2026)

**Status:** executed run record. **Not acceptance evidence.** Human review and AS's QA sign-off are not given.

## 1. Method

- Corpus: the allowlisted `shopify.dev` pages below, fetched live under the approved live-retrieval scope (decision 1 of the 22 October 2026 Sprint 2 decisions, recorded run only).
- Retrieval: keyword passages with at least two distinct meaningful terms shared with the requirement, top five per requirement.
- Relevance grade (`webdesk.evidence.relevance`): DIRECT if at least three requirement terms and at least half of the requirement's terms are in the passage; PARTIAL if at least two terms; IRRELEVANT otherwise. Lexical only. No model call (D09).
- The specialist emits findings for DIRECT and PARTIAL passages, and labels each finding with its grade. Only DIRECT evidence counts toward option-class coverage.

## 2. Corpus

| Source | URL | Result | Characters | SHA-256 (prefix) |
|---|---|---|---|---|
| shopify-doc-01 | https://shopify.dev/docs/api/storefront/latest | retrieved | 32212 | `34a565281e9fc1dd` |
| shopify-doc-02 | https://shopify.dev/docs/api/admin-graphql/latest | retrieved | 18016 | `b101a4e02edca93a` |
| shopify-doc-03 | https://shopify.dev/docs/api/admin-graphql/latest/objects/Metafield | retrieved | 7888 | `9141383d93e89b80` |
| shopify-doc-04 | https://shopify.dev/docs/api/storefront/latest/queries/product | retrieved | 31523 | `32fcdb98a936feff` |
| shopify-doc-05 | https://shopify.dev/docs/apps/build/checkout | retrieved | 17607 | `fa1760df1f7fb1d9` |
| shopify-doc-06 | https://shopify.dev/docs/apps/build/online-store/theme-app-extensions | retrieved | 4119 | `0a4a6df101b41f33` |
| shopify-doc-07 | https://shopify.dev/docs/apps/build/functions | retrieved | 9185 | `e010c3b645df9c59` |
| shopify-doc-08 | https://shopify.dev/docs/apps/build/metafields | retrieved | 15578 | `ee7e2380e45d7e98` |
| shopify-doc-09 | https://shopify.dev/docs/apps/build/app-extensions | retrieved | 6598 | `0173e1d00eef60a5` |
| shopify-doc-10 | https://shopify.dev/docs/apps/build/app-extensions/list-of-app-extensions | retrieved | 4708 | `5dcc05778e10e757` |
| shopify-doc-11 | https://shopify.dev/docs/apps/build/discounts | retrieved | 13655 | `8c7d020dccb1c942` |
| shopify-doc-12 | https://shopify.dev/docs/apps/build/online-store | retrieved | 10820 | `d49b727183931763` |
| shopify-doc-13 | https://shopify.dev/docs/apps/build/customer-accounts | retrieved | 9457 | `db64041581a61ce1` |
| shopify-doc-14 | https://shopify.dev/docs/apps/build/markets | retrieved | 19198 | `388346c1712fdd10` |
| shopify-doc-15 | https://shopify.dev/docs/apps/build/admin | retrieved | 9595 | `27cfce4bffa5d361` |
| shopify-doc-16 | https://shopify.dev/docs/apps/build/authentication-authorization | retrieved | 10404 | `a0f7c15ad8595913` |

`help.shopify.com` was on the allowlist but returned HTTP 403 to the fetch client. No bypass was attempted, and no help-centre evidence was used.

## 3. Results for all 17 evaluated requirements

| Brief | # | Requirement | Passages retrieved | DIRECT | PARTIAL | Status | Findings (partial or direct) | Sources cited | Direct-evidence option classes | Gaps (of 3) |
|---|---|---|---|---|---|---|---|---|---|---|
| SH-CASE-01 | 1 | Validate Canadian postal addresses at checkout, with particular attention to rural and remote addresses. | 3 | 0 | 3 | incomplete | 2 | shopify-doc-05 | none | 3 |
| SH-CASE-01 | 2 | Do not rely on IP-based province detection. Province must be captured explicitly. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-01 | 3 | Let a customer renew a rate plan from the order status page without creating an account. | 5 | 0 | 5 | incomplete | 3 | shopify-doc-09, shopify-doc-13 | none | 3 |
| SH-CASE-01 | 4 | Create the customer account after purchase, reusing details already entered at checkout. | 5 | 0 | 5 | incomplete | 4 | shopify-doc-01, shopify-doc-13 | none | 3 |
| SH-CASE-01 | 5 | Calculate regional tax and fixed levies correctly for a digital subscription, and avoid shipping fields that do not apply. | 2 | 0 | 2 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 1 | Provide a dedicated page per artist, with featured works, while keeping SEO and live inventory intact. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 2 | Provide faceted filters with AND/OR logic, updating results without a page reload, with merchandising control of the filter set. | 3 | 0 | 3 | incomplete | 1 | shopify-doc-11 | none | 3 |
| SH-CASE-02 | 3 | Provide search that handles natural-language phrasing, typos and autocomplete at catalogue scale. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 4 | Keep checkout behaviour unchanged. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 1 | Campaign-specific pages with real-time sales tracking and commission calculation per fundraiser. | 2 | 0 | 2 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 2 | Coexistence of permanent partner stores and campaign-driven stores. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 3 | Role-based administration for partners and staff. | 1 | 0 | 1 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 4 | Synchronization of orders and product data with several external systems, some with custom endpoints. | 5 | 0 | 5 | incomplete | 3 | shopify-doc-03, shopify-doc-08 | none | 3 |
| SH-CASE-04 | 1 | Pickup time slots with capacity limits, cut-off times and same-day rules, enforced at checkout. | 5 | 0 | 5 | incomplete | 2 | shopify-doc-05 | none | 3 |
| SH-CASE-04 | 2 | Blackout dates and holidays. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-04 | 3 | Staff dashboard with daily volume, forecasting and reporting. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-04 | 4 | Automated order preparation timelines. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |

**Summary:** 17 requirements evaluated and retained. Requirements with a DIRECT passage: **0**. Requirements with at least one cited finding (partial or direct): **6**. Requirements with no finding: **11**. Passage grades across all runs: {'direct': 0, 'partial': 31, 'irrelevant': 0}.

## 4. What this shows

- No requirement has DIRECT lexical evidence in the approved corpus. Under the stated rule, option coverage is therefore zero for every requirement.
- The strict DIRECT rule is conservative. Long requirements need many shared terms, so a correct but differently worded answer can be graded PARTIAL. The rule was not loosened, because loosening it to change the result would be tuning to the outcome.
- The grades are lexical. They cannot confirm that a passage answers a requirement. Human review, or a semantic validator approved under D09, is needed to grade direct evidence.
- Feasibility remains NOT DETERMINED for all 17 requirements.

## 5. Gap register

| Requirements | Gap | Needed to close |
|---|---|---|
| SH-CASE-01 #2; SH-CASE-02 #1, #3, #4; SH-CASE-03 #2; SH-CASE-04 #2, #3, #4 (8 requirements) | No passage from the corpus passes the two-term retrieval rule | Additional official sources; see `docs/governance/PROPOSED_ALLOWLIST_EXPANSION_2026-10-22.md` |
| SH-CASE-01 #1, #3, #4, #5; SH-CASE-02 #2; SH-CASE-03 #1, #3, #4; SH-CASE-04 #1 (9 requirements) | Only PARTIAL passages; for several, no finding is emitted because no Shopify topic or option term is in the passage | Human review of partial passages, or direct documentation from an approved source |
| All 17 | Plan tier and version applicability are not verified | Plan-tier and version sources from an approved domain, and a client clarification |

## 6. Limits

- The requirement texts are sanitized brief text, used verbatim from the brief document.
- The corpus is 16 pages. It is not a full documentation set.
- No page text is stored in the repository. The evidence is held outside it, under its SHA-256.

