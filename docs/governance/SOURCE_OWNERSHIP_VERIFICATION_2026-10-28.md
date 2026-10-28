# Source ownership and publisher verification (S4-SOURCE-OWNERSHIP-01, 28 October 2026)

**Scope:** read-only, public, browser-based checks of the minimum publisher-controlled landing pages for the previously approved sources. Authorized by WDS Authorized Approver under S4-SOURCE-OWNERSHIP-01.
**Activation status:** UNCHANGED. No source is active. The investigation engine's active set is empty.
**What this establishes:** that each page is published under the vendor's brand and domain, and where redirects occurred. It does not establish legal ownership, and it does not verify any technical capability claim.

## Results

| Source | URL inspected | Final URL | Redirect | Observed publisher evidence | Result |
|---|---|---|---|---|---|
| WooCommerce | `https://developer.woocommerce.com/` | same | none | Title "The WooCommerce Developer Blog"; og:site_name matches; WooCommerce community and release links. Footer legal links point to automattic.com (privacy and agency pages) and wordpress.com terms. | PUBLISHER-CONTROLLED. Owner statement not found. |
| WooCommerce | `https://developer.woocommerce.com/docs/` | same | none | Title "Getting started \| WooCommerce developer docs" | Consistent with the approved `/docs/*` path. |
| BigCommerce | `https://docs.bigcommerce.com/` | `https://docs.bigcommerce.com/developer/docs/overview/quick-start` | Yes, inside approved `/developer/docs/*` | og:site_name "BigCommerce"; links to support.bigcommerce.com. "Built with Fern" is third-party tooling, not ownership evidence. | PUBLISHER-CONTROLLED. Owner statement not found. |
| Adobe Commerce | `https://developer.adobe.com/commerce/webapi/rest/` | same | none | Title "REST API Overview"; Adobe developer navigation; links to developer.adobe.com/apis. | PUBLISHER-CONTROLLED for this page only. GraphQL, events and PHP pages not checked. |
| Magento Open Source release notes | `https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview` | same | none | Title "Magento Open Source release notes \| Adobe Commerce"; Adobe Experience League navigation. | PUBLISHER-CONTROLLED. Owner statement not found. |
| Adobe shared PHP | not checked under this authorization | | | | NOT CHECKED |

Timestamp: browser batch run 2026-10-28, approximately 11:32 to 11:35 UTC. Per-page times were not captured separately.

## Discrepancies and limits

1. **Redirect:** BigCommerce's root redirected to a quick-start page. The destination is inside the approved path, so it is recorded but not treated as a boundary breach.
2. **No explicit owner statement** was found on any page. The WooCommerce footer shows Automattic legal links, which is consistent with the existing PARTIAL status. It is not a statement of ownership.
3. **Brand and domain evidence only.** This does not verify any technical capability claim, as the authorization requires.
4. **Coverage:** one Adobe page, not the three approved exact pages (GraphQL, events) and not the shared PHP page.
5. **Not checked:** Shopify and Shift4Shop were outside this authorization.

## Source manifest

`docs/specialists/knowledge/sources.json` now carries the ownership evidence for each checked source. Activation status is unchanged in every entry.

## Recommendation for the activation decision

Ownership is supported for WooCommerce, BigCommerce and Magento Open Source release notes, at publisher-control level. Ownership is partial for Adobe, because only one of its four pages was checked. Activation still needs a separate WDS decision, and this report does not recommend activation on its own.
