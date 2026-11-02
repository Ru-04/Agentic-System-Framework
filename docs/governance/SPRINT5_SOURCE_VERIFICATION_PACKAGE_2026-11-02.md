# M2 Sprint 5: consolidated source verification package (2 November 2026)

**Purpose:** one decision package for WDS. Every candidate in the Sprint 5 candidate register was checked (read-only, redirects refused, no bypass). **Nothing is activated by this document.** The checks establish ownership, relevance and applicability. They do not establish authorization. Authorization stays with the decision register and with WDS.

**Method of the checks:** the approved pilot opener (identifies itself, follows no redirects, refuses any 3xx response). Each page's title and `og:site_name` were read, and its substantive text was extracted under the Decision 3 policy. Search-result URLs were verified this way; no page content was used as evidence except where a row says so.

## 1. Consolidated decision table

| Ref | Specialist | Official publisher | Exact URL | Ownership verification | Relevant capability | Technical applicability (checked) | Proposed activation scope | Current authorization | Remaining blocker | Recommendation |
|---|---|---|---|---|---|---|---|---|---|---|
| A5 | Magento / Adobe Commerce | Adobe | `https://developer.adobe.com/commerce/php/` | Domain and Adobe title. No `og:site_name`. No owner statement | None registered (shared PHP) | Reachable (200). 48 substantive words, describing PHP extensions for Adobe Commerce and Magento Open Source | Exact `/commerce/php/` only | ADOBE-01 approves the page. Not activated | No registered capability uses it. Shared-edition decision | **HOLD** (no claim needs it) |
| A6 | Shopify | Shopify | `https://www.shopify.com/pricing` | `og:site_name` = Shopify; title matches | Plan feature availability | Reachable (200, no bypass). 969 substantive words; "Compare features across Shopify plans" | Exact `/pricing` only | S2-D08: approved, **flagged for confirmation** | WDS confirms S2-D08 | **APPROVE after S2-D08 confirmation** |
| A6′ | Shopify | Shopify | `https://www.shopify.com/plus` | Not reached | Plan feature availability | **301 redirect. Refused** (redirects are not followed) | None until a final URL is approved | S2-D08 lists `/plus` | The approved path redirects | **REJECT** as written; amend to the final URL if WDS wants it |
| B1a | Shopify | Shopify Help Center | `https://help.shopify.com/en/manual/intro-to-shopify/pricing-plans/plans-features/basic-shopify-plan` | Title and `og:site_name` = Shopify Help Center | Plan feature availability | Reachable (200). 431 words; "Available features on the Basic plan" | Exact page | S2-D07 covers help.shopify.com access by permitted methods. No exact path approved | Exact-path approval; WDS confirms that a standard request is a permitted method under S2-D07 | **APPROVE** (exact page), with that confirmation |
| B1b | Shopify | Shopify Help Center | `https://help.shopify.com/en/manual/b2b/getting-started/plan-features` | As B1a | Plan feature availability (B2B) | Reachable (200). 320 words; "The features available to you depend on your plan." | Exact page | As B1a | As B1a | **APPROVE** (exact page), with that confirmation |
| B2 | Shopify | Shopify Help Center | `https://help.shopify.com/en/manual/products` | As B1a | None for plan features | Reachable. 474 words, but no plan or API passage | None | Browser read (22 Oct) only | Low relevance to the plan capability | **REJECT** for plan features |
| B3a | Shopify | Shopify | `https://shopify.dev/docs/api/storefront/latest` | `og:site_name` = Shopify | None registered (Storefront API) | Reachable. 2,825 words of API reference | Would need exact paths | None. No `shopify.dev` path approved (Decision 2) | A capability must be registered before any path is relevant | **HOLD** |
| B3c | Shopify | Shopify | `https://shopify.dev/docs/api/storefront/latest/queries/product` | As B3a | None registered | Reachable. 2,456 words. No sentence states product and API together | As B3a | None | Capability registration | **HOLD** |
| B3d | Shopify | Shopify | `https://shopify.dev/docs/api/admin-graphql/latest/objects/Metafield` | As B3a | None registered | Reachable. 785 words. No passage for the terms | None | None | No evidence for any registered capability | **REJECT** |
| B3e | Shopify | Shopify | `https://shopify.dev/docs/apps/build/checkout` | As B3a | None registered (checkout extensions) | Reachable. Passage: "build an app with extensions" | As B3a | None | Capability registration | **HOLD** |
| B4 | Shopify | Shopify | `https://shopify.dev/docs/api` | As B3a | None | Index page only | None | None | Not evidence | **REJECT** |
| B5 | Shift4Shop | Shift4Shop (3dcart). **Ownership not verified** | `https://developer.3dcart.com/` | Domain only. No title, no site name | Product read API (CAP-3D-CART-SHIFT-SHOPIFY) | Reachable (200). 369 words, portal text. The product reference page is not identified | None until the product page is found | SRC-02 discovery only; B4 deferred | Ownership verification; the product reference page; base-URL conflict | **HOLD** |
| B6 | WordPress core | WordPress.org. `og:site_name` = WordPress Developer Resources | `https://developer.wordpress.org/rest-api/reference/posts/` | Site name and title match | None registered for core | Reachable (200). 1,427 words of endpoint definition (posts) | Exact `/rest-api/reference/posts/` | None. B6 deferred | Domain authorization; a registry capability for core | **HOLD** |
| B6′ | WordPress core | WordPress.org | `https://developer.wordpress.org/rest-api/reference/` | As B6 | None | 5 substantive words (index) | None | None | Not evidence | **REJECT** (use the posts page as the example) |
| B7 | Magento / Adobe Commerce | Adobe | `https://developer.adobe.com/commerce/webapi/rest/reference` | Requested URL **301 redirects**; final `/reference/` returns 200 | REST product read (Adobe) | Final page: 51 substantive words. The content is rendered by script (generated reference) | None | ADOBE-01 does not cover it | Redirect; script-rendered content; exact endpoint pages not identified | **REJECT** as an evidence source for now |
| B8a | BigCommerce | BigCommerce. `og:site_name` = BigCommerce Docs | `https://docs.bigcommerce.com/developer/docs/admin/checkout-and-cart/orders/overview` | Title and site name match | Order data (UNAPPROVED: bigcommerce.md section 13) | Reachable (200). 2,089 words; "introduces … Orders V2 and Orders V3 REST API resources" | Exact page | **Not authorized.** The `/developer/docs` subtree was narrowed out in this cycle (see section 2) | Subtree decision; capability registration for order data | **HOLD** |
| B8b | BigCommerce | BigCommerce | `https://developer.bigcommerce.com/docs/store-operations/orders` | Not reached | Order data | **301 redirect. Refused** | None | Host not approved | Host decision | **REJECT** |
| B9 | Standalone Applications | Representative only, not a source | `https://www.postgresql.org/docs/current/` (representative) | PostgreSQL Global Development Group (title and site name) | Not a registered Standalone capability. Representative of a project-named database | Reachable (200). 417 words | None | None. Not approved for any capability | No technology selected by WDS; no capability for database choice | **HOLD** (representative; not a permanent restriction) |
| B9′ | Standalone Applications | Representative only | `https://nodejs.org/en/docs` | Not reached | Representative of a project-named runtime | **307 redirect. Refused** | None | None | The canonical URL must be identified first | **HOLD** |
| B10 | Middleware Applications | None selected | None | Not applicable | Webhook retry, error recovery, idempotency, synchronisation (recognised, neutral) | No product named by the project. The ERP is not identified | None | No product source | ERP identity from the project; a product is not required | **HOLD** |

## 2. Authorization conflict found in this cycle (requires WDS decision)

The BigCommerce boundary as implemented allowed the whole `/developer/docs` subtree. The pilot approval (S4-PILOT-EVIDENCE-01) and the B1 docstring in `approved_boundaries.py` name only the exact single-product page. `sources.json` records the subtree as approved. The implemented boundary was **narrowed to the exact page** in this cycle, so only the pilot's page is active. The records conflict, and the narrowing is the conservative reading. **WDS must confirm which scope is intended.** If the subtree is intended, B8a becomes a candidate, subject to a capability decision.

## 3. Recommendations summary (for one decision)

- **Approve, subject to confirmation of S2-D07 and S2-D08:** A6 (`/pricing`), B1a, B1b. Exact paths only, no subtree, no `/plus`.
- **Hold for registry work:** B3a, B3c, B3e (Shopify capabilities), B6 (core capability), B8a (order capability and subtree decision), B9 (a database or runtime capability, if WDS wants one), B10.
- **Hold for verification:** A5 (shared edition), B5 (ownership and product page), B7 (final URL and endpoint page).
- **Reject:** A6′, B2, B3d, B4, B6′, B8b, and B7 as an evidence source for now.

No row is approved by this document. Each activation needs WDS's explicit decision.

## 4. Required tests for any row approved later

For each approved exact page, before activation:
1. Permitted: the exact URL. Refused: sibling, parent, query-string and fragment variants.
2. Redirect: any 3xx is refused and no content is used.
3. Evidence: only substantive text (prose of at least four words, code or specification blocks, rendered examples inside the page's own markup). Headings, titles, navigation and script payloads cannot support a claim.
4. Version: a claim cites only a version the page states.
5. Edition: an Adobe-only page is not attributed to Magento Open Source.
6. Requirement-level routing: the expected outcome in the frozen dataset agrees with the activation.
7. The activation is recorded in `sources.json`, `ACTIVE_BOUNDARIES` and the activation matrix, and the consistency tests pass.
