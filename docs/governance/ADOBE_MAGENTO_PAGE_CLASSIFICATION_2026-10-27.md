# Adobe Commerce and Magento Open Source page classification (27 October 2026)

**Method:** read-only page reads in the built-in browser, specific public pages only, no login, no crawling. Each page's own edition statement is quoted. Read on 27 October 2026. **Discovery and verification only. Nothing is activated.**

## 1. Candidate pages from the approval request

| Candidate URL | Final URL | What the page says about editions | Classification |
|---|---|---|---|
| `https://developer.adobe.com/commerce/php/` | Same (no redirect) | "PHP-based extensions for Adobe Commerce and Magento Open Source" | **Shared with Adobe Commerce** |
| `https://developer.adobe.com/commerce/contributor/guides/install/` | Same | "anyone who contributes to the Magento Open Source codebase"; "you cannot use the Magento software in a production environment" | **Magento Open Source only** (contributor audience. Not evidence of platform capability) |
| `https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview` | Same (last updated 8 Oct 2026) | "Learn about the latest improvements in the Magento Open Source codebase". Notes that code is bundled with Adobe Commerce, and that some projects are released separately | **Magento Open Source only** (release notes for the Open Source codebase). Note the separate host `experienceleague.adobe.com` |

## 2. Adobe Commerce pages checked (for the exact-page proposal)

| URL | Final URL | Edition statement | Classification |
|---|---|---|---|
| `https://developer.adobe.com/commerce/webapi/rest/` | Same | "REST APIs that are available in Adobe Commerce (PaaS) and Adobe Commerce as a Cloud Service (SaaS)" | **Adobe Commerce only** |
| `https://developer.adobe.com/commerce/webapi/graphql/` | Same | "Adobe Commerce provides two GraphQL implementations… Adobe Commerce on Cloud and on-premises (PaaS)" | **Adobe Commerce only** |
| `https://developer.adobe.com/commerce/extensibility/events/` | Same | "These capabilities are now available in Adobe Commerce" (Adobe I/O Events) | **Adobe Commerce only** |
| `https://developer.adobe.com/commerce/frontend-core/` | Same | Page loaded; edition statement not captured in the read | **Unclear**. Do not use until the edition statement is confirmed |

## 3. Exact-page proposal for the Adobe Commerce boundary (B3)

Only pages verified above are proposed. Each is an exact URL, and no child pages are included.

| Exact URL | Label | Use in the initial investigations |
|---|---|---|
| `https://developer.adobe.com/commerce/php/` | Shared (Adobe Commerce and Magento Open Source) | Landing statement and edition scope |
| `https://developer.adobe.com/commerce/webapi/rest/` | **Adobe Commerce only** | REST API scope for the Adobe Commerce investigation |
| `https://developer.adobe.com/commerce/webapi/graphql/` | **Adobe Commerce only** | GraphQL scope for the Adobe Commerce investigation |
| `https://developer.adobe.com/commerce/extensibility/events/` | **Adobe Commerce only** | Event-driven integration scope for the Adobe Commerce investigation |

Pages below the landing page (for example `/commerce/php/architecture/`) are **not verified** and are not proposed. Their edition is not inferred from the landing page.

## 4. Magento Open Source proposal (B5)

Verified Open Source-only pages:
- `https://developer.adobe.com/commerce/contributor/guides/install/`: contributor audience only. Not proposed for capability investigation.
- `https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview`: release notes. Proposed only for release-version applicability, not for feature claims.

Open Source feature documentation (for example `devdocs.magento.com`) redirects to Adobe Commerce and is not verified as Open Source-only. **No Open Source feature page list is proposed.**

## 5. Ownership and redirects (this round)
- `developer.adobe.com`: Adobe developer domain, serving the Commerce documentation.
- `experienceleague.adobe.com`: Adobe documentation domain. A third host, not yet on the boundary list.
- `devdocs.magento.com`: redirects to `developer.adobe.com/commerce/docs/`. Refused under the rules.

## 6. Restrictions that apply
- https only, exact host, the exact URLs listed. No prefixes. No crawling. No redirects followed.
- Edition-exclusive pages are labelled. Their features are not attributed to Magento Open Source.
