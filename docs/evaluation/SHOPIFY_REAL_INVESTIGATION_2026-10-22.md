# Shopify investigation and relevance evaluation — 22 October 2026

**Status:** executed evaluation record. **Not acceptance evidence.** Human review and AS's QA sign-off are not given.

## 1. Method

- Retrieval: keyword passages sharing at least two distinct meaningful terms with the requirement; plurals and hyphenated compounds are folded; top 20 candidates per requirement, ranked by grade, then Shopify topic or option signal, then shared terms.
- Relevance (`webdesk.evidence.relevance`): DIRECT if at least three requirement terms and at least half of the requirement's terms appear; PARTIAL if at least three appear; IRRELEVANT otherwise. Lexical only; no model call (D09).
- Findings are emitted for DIRECT and PARTIAL passages, labelled with their grade. Only DIRECT evidence counts toward option-class coverage.
- Feasibility is NOT DETERMINED for every requirement.

## 2. Sources

| Source | URL | Scope | Result | Characters | SHA-256 (prefix) |
|---|---|---|---|---|---|
| shopify-doc-01 | https://shopify.dev/docs/api/storefront/latest | S2 run | retrieved | 32212 | `34a565281e9fc1dd` |
| shopify-doc-02 | https://shopify.dev/docs/api/admin-graphql/latest | S2 run | retrieved | 18016 | `b101a4e02edca93a` |
| shopify-doc-03 | https://shopify.dev/docs/api/admin-graphql/latest/objects/Metafield | S2 run | retrieved | 7888 | `9141383d93e89b80` |
| shopify-doc-04 | https://shopify.dev/docs/api/storefront/latest/queries/product | S2 run | retrieved | 31523 | `32fcdb98a936feff` |
| shopify-doc-05 | https://shopify.dev/docs/apps/build/checkout | S2 run | retrieved | 17607 | `fa1760df1f7fb1d9` |
| shopify-doc-06 | https://shopify.dev/docs/apps/build/online-store/theme-app-extensions | S2 run | retrieved | 4119 | `0a4a6df101b41f33` |
| shopify-doc-07 | https://shopify.dev/docs/apps/build/functions | S2 run | retrieved | 9185 | `e010c3b645df9c59` |
| shopify-doc-08 | https://shopify.dev/docs/apps/build/metafields | S2 run | retrieved | 15578 | `ee7e2380e45d7e98` |
| shopify-doc-09 | https://shopify.dev/docs/apps/build/app-extensions | S2 run | retrieved | 6598 | `0173e1d00eef60a5` |
| shopify-doc-10 | https://shopify.dev/docs/apps/build/app-extensions/list-of-app-extensions | S2 run | retrieved | 4708 | `5dcc05778e10e757` |
| shopify-doc-11 | https://shopify.dev/docs/apps/build/discounts | S2 run | retrieved | 13655 | `8c7d020dccb1c942` |
| shopify-doc-12 | https://shopify.dev/docs/apps/build/online-store | S2 run | retrieved | 10820 | `d49b727183931763` |
| shopify-doc-13 | https://shopify.dev/docs/apps/build/customer-accounts | S2 run | retrieved | 9457 | `db64041581a61ce1` |
| shopify-doc-14 | https://shopify.dev/docs/apps/build/markets | S2 run | retrieved | 19198 | `388346c1712fdd10` |
| shopify-doc-15 | https://shopify.dev/docs/apps/build/admin | S2 run | retrieved | 9595 | `27cfce4bffa5d361` |
| shopify-doc-16 | https://shopify.dev/docs/apps/build/authentication-authorization | S2 run | retrieved | 10404 | `a0f7c15ad8595913` |
| shopify-plan-01 | https://www.shopify.com/pricing | S2-D08 | **failed: vendor returned HTTP 403** | — | — |
| shopify-plan-02 | https://www.shopify.com/plus | S2-D08 | **failed: vendor returned HTTP 403** | — | — |
| cra-01 | https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-specific-situations/e-commerce.html | S2-D09 | retrieved | 19085 | `98deead7e90eb054` |
| cra-02 | https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/b-090.html | S2-D09 | retrieved | 1489 | `8289fd4384bed8e1` |

Not retrieved, and not used as evidence: the Shopify plan pages above (HTTP 403 to the fetch client; no bypass attempted), and `help.shopify.com` (HTTP 403 to the fetch client; a browser read of one page succeeded, but its text was not ingested into the corpus, see section 6).

## 3. Results for all 17 retained requirements

| Brief | # | Requirement | Retrieved | DIRECT | PARTIAL | Status | Findings | Sources cited | Direct-evidence option classes | Gaps (of 3) |
|---|---|---|---|---|---|---|---|---|---|---|
| SH-CASE-01 | 1 | Validate Canadian postal addresses at checkout, with particular attention to rural and remote addresses. | 3 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-01 | 2 | Do not rely on IP-based province detection. Province must be captured explicitly. | 1 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-01 | 3 | Let a customer renew a rate plan from the order status page without creating an account. | 20 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-01 | 4 | Create the customer account after purchase, reusing details already entered at checkout. | 20 | 0 | 3 | incomplete | 0 | — | none | 3 |
| SH-CASE-01 | 5 | Calculate regional tax and fixed levies correctly for a digital subscription, and avoid shipping fields that do not apply. | 4 | 0 | 1 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 1 | Provide a dedicated page per artist, with featured works, while keeping SEO and live inventory intact. | 3 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 2 | Provide faceted filters with AND/OR logic, updating results without a page reload, with merchandising control of the filter set. | 6 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 3 | Provide search that handles natural-language phrasing, typos and autocomplete at catalogue scale. | 2 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-02 | 4 | Keep checkout behaviour unchanged. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 1 | Campaign-specific pages with real-time sales tracking and commission calculation per fundraiser. | 10 | 0 | 1 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 2 | Coexistence of permanent partner stores and campaign-driven stores. | 2 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 3 | Role-based administration for partners and staff. | 1 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-03 | 4 | Synchronization of orders and product data with several external systems, some with custom endpoints. | 20 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-04 | 1 | Pickup time slots with capacity limits, cut-off times and same-day rules, enforced at checkout. | 20 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-04 | 2 | Blackout dates and holidays. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-04 | 3 | Staff dashboard with daily volume, forecasting and reporting. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |
| SH-CASE-04 | 4 | Automated order preparation timelines. | 0 | 0 | 0 | incomplete | 0 | — | none | 3 |

**Summary:** 17 requirements retained. With a DIRECT passage: **0**. With a cited finding: **0**. With no finding: **17**. Passage grades across the run: {'direct': 0, 'partial': 5, 'irrelevant': 107}.

## 4. Relevance diagnosis (S2-D10)

Measured on the earlier run (31 passages graded PARTIAL under the two-term floor, before plural folding and the tighter floor):

| Candidate cause | Measurement | Finding |
|---|---|---|
| Passage segmentation | Median passage 106 characters; a sentence-level pass found 0 DIRECT passages | Not the cause |
| Overly restrictive conditions | 0 of the PARTIAL passages met the 50% ratio alone | Not the cause |
| Poor ranking | Top passages already carried the maximum available overlap | Partly; fixed by candidate ranking |
| Lexical matching | Passages shared a median of 2 terms against a requirement median of 10 | A real limit of keyword matching |
| Insufficient or absent source coverage | 42 of 140 requirement terms (30%) appear nowhere in the corpus; several are plural or hyphenated forms | A real cause; plural and hyphen folding recovers some |
| Genuine absence of evidence | Most requirements have no sentence containing three or more of their terms in the corpus | The corpus does not address most requirements |

## 5. Independent label check (S2-D10)

A separate AI agent, not AS and not a human, labelled 55 blind requirement–passage pairs with plain definitions, without access to the rules or to the answer key. The check compares the rule's grade with those labels.

| PARTIAL floor | Agreement with the 55 agent labels | Rule PARTIAL but label IRRELEVANT |
|---|---|---|
| 2 terms, generic words excluded | 32 of 55 | 22 |
| 3 terms, generic words excluded (current) | 44 of 55 | 2 |

The earlier table (29, 46, 42) was computed before platform-generic words were excluded (QA4-04) and is superseded.

**Limits:** the floor was chosen after seeing these same 55 labels, so the 44 of 55 figure is tuned, not validated. A held-out set and human labels (AS or a reviewer) are needed before the rule can be called validated. The agent's labels are not human labels.

## 6. Gap register (computed from the run)

| Requirements | Gap | What would close it |
|---|---|---|
| SH-CASE-01 #1, SH-CASE-01 #2, SH-CASE-01 #3, SH-CASE-01 #4, SH-CASE-01 #5, SH-CASE-02 #1, SH-CASE-02 #2, SH-CASE-02 #3, SH-CASE-02 #4, SH-CASE-03 #1, SH-CASE-03 #2, SH-CASE-03 #3, SH-CASE-03 #4, SH-CASE-04 #1, SH-CASE-04 #2, SH-CASE-04 #3, SH-CASE-04 #4 (17 requirements) | No passage passes the relevance rule, or none was retrieved | Additional official sources from approved domains (see the allowlist expansion record); a `help.shopify.com` ingestion method |
|  (0 requirements) | Partial evidence only | Direct documentation; human review of partial passages |
| All 17 | Plan tier and version applicability not verified | Plan documentation from `shopify.com` (blocked, HTTP 403); client clarification |
| CRA-related requirements (SH-CASE-01 #1, #5) | Tax and address rules need professional review; the CRA pages are regulatory background, not legal or tax advice | Review by a qualified professional |

## 7. Limits

- Requirement texts are the sanitized brief text, used verbatim.
- The corpus is small and is not a full documentation set.
- No page text is stored in the repository. Evidence is identified by URL and SHA-256 prefix.
- Citations are checked against the stored text. None failed in this run.

