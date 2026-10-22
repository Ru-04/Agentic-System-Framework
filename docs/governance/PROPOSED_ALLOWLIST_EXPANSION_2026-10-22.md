# Proposed allowlist expansion — for authorized review (22 October 2026)

**Status:** PROPOSAL ONLY. No new domain has been accessed. Nothing below is approved until the decision-maker approves it in writing (decision 3 of the 22 October 2026 Sprint 2 decisions).

**Current allowlist (working selection, not yet formally approved under D08):** `shopify.dev`, `help.shopify.com`.

## 1. What the current allowlist already covers

- `shopify.dev` supplied 16 fetched pages in the recorded run. Its coverage is limited to the developer documentation topics listed in the evaluation record.
- `help.shopify.com` is on the list, but its pages returned HTTP 403 to the fetch client. This is an access block, not a missing domain. Adding a second domain does not fix it. Any change to access method (for example, an approved user agent or an approved browser-based retrieval) needs its own decision.

## 2. Requirements the current corpus cannot answer, and the candidate source for each

These are candidates to check in review. They are not verified, and the existence of a page is not assumed.

| Requirement(s) | Gap | Candidate source (to verify in review) | Domain status | Notes |
|---|---|---|---|---|
| SH-CASE-01 #1, #5 (Canadian address and levy rules) | Partial evidence only | Shopify Help Centre tax and address pages (`help.shopify.com`, already listed but blocked) | Already listed | Blocked by 403. Needs an approved access method. |
| SH-CASE-01 #2 (province selection without IP detection) | No passage retrieved | Shopify developer docs on address and checkout fields (`shopify.dev`, already listed) | Already listed | Probe the approved host for the right page before any fetch. |
| SH-CASE-01 #3, #4 (renewal without account, account after purchase) | Partial evidence only | Customer account documentation (`shopify.dev`, already listed; the overview page was fetched) | Already listed | Needs a narrower page on the approved host. |
| Plan-tier clarification for all requirements | Plan applicability not verified | Shopify plan and feature comparison pages (`shopify.com`) | **New domain** | Needed to verify Shopify Plus and plan limits. Marketing content, so it needs review for official-status. |
| SH-CASE-02 #1, #3, #4 (artist pages, search, filters) | No passage retrieved | Search & Discovery and online store documentation (`shopify.dev` or `help.shopify.com`) | Already listed | Probe for the right page. |
| SH-CASE-03 #2 (partner stores and campaign stores) | No passage retrieved | Markets and multi-store documentation (`shopify.dev`, already listed; markets page fetched) | Already listed | Narrower page needed. |
| SH-CASE-03 #3 (staff permissions) | Partial evidence only | Staff account and permission documentation (`help.shopify.com`, already listed) | Already listed | Blocked by 403. |
| SH-CASE-04 #1 (pickup slots) | Partial evidence only | Local pickup and delivery documentation (`help.shopify.com`, or a `shopify.dev` page if one exists) | Already listed | Functions pages already show local pickup options. A narrower page is needed. |
| SH-CASE-04 #2–#4 (blackout dates, dashboards, workflow automation) | No passage retrieved | Shopify Flow and reports documentation (`help.shopify.com`, or `shopify.dev` if one exists) | Already listed | Blocked by 403 for help pages. |

Canadian address and tax rules may also need a government source (for example, the Canada Revenue Agency for sales-tax rules). Government sources are not official vendor documentation under D08, and they would need their own approval as a source category.

## 3. Summary of expansion requests

1. **Approve an access method for `help.shopify.com`** (not a new domain). Without this, 11 of the 17 requirements stay uncovered, and most of the candidate sources above are on this host.
2. **Approve `shopify.com`** for plan-tier and feature-availability pages only, with the rule that marketing pages are used only to clarify plan applicability, never as evidence of a platform capability.
3. **Decide whether government tax or address sources are in scope.** If yes, they need a separate source category and approval. The current policy covers only official vendor documentation and approved internal knowledge (D08).

## 4. What is not proposed

- No general web search or arbitrary retrieval.
- No third-party blogs, forums, app-store listings, or review sites.
- No retrieval from the case-study website that generated the briefs, because it is WDS's own marketing and is not a source of platform facts.

## 5. Re-run after approval

Once approved, the evaluation is re-run on the same 17 requirements. The record will report:
- coverage for each requirement, by grade (DIRECT, PARTIAL, IRRELEVANT);
- any requirement still uncovered;
- every new source by URL, retrieval time and SHA-256 prefix.

No requirement is removed to improve the reported figures.

## 6. Approval

- Decision on item 1 (access method for help.shopify.com): ____________
- Decision on item 2 (shopify.com for plan-tier pages): ____________
- Decision on item 3 (government sources): ____________
- Approver name, role and date: **not provided in this document**. Left blank.
