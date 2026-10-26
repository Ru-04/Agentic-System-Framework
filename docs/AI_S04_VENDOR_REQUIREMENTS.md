# AI-S04 Vendor Documentation and Platform-Access Requirements

Status: **requirements only.** None of these is in place. No vendor documentation was consulted and no platform was
accessed for AI-S04. Each item needs a WDS decision before it is used.

## 1. Requirements common to all five specialists

- An approved evidence source for each platform: the official vendor documentation, identified by product, version and
  date checked. Default deny applies; the live-research domain allowlist is empty (C-06).
- The exact platform and version in use for each client project (the specialists ask for it; none is assumed).
- An authorised test instance per platform, under an approved access policy. No real client project or client data.
- Credentials handled only by an approved mechanism. No credentials are stored in code, fixtures or documents.
- A data-classification and retention decision for any vendor material retrieved (source retention policy is open).
- Approval for each vendor source before it becomes a collection (collection-level approval).

## 2. Per specialist

| Specialist | Official documentation needed | Version and edition to confirm | Authorised test access needed | Specific notes |
|---|---|---|---|---|
| Shopify | Admin API, Storefront API, app and theme documentation, rate limits, webhook behaviour | Plan, API version, staff permissions | Development store under an approved access policy | AI-1 specialist; its claims need the same verification |
| WordPress / WooCommerce | WooCommerce REST API and extension documentation; WordPress core and plugin documentation | WordPress, WooCommerce, PHP, plugin set | Test site with an approved plugin set | CMS and commerce concerns verified separately |
| BigCommerce | Storefront and Management APIs, GraphQL, app and extension documentation, plan limits | Store plan, API scopes, app permissions | Sandbox store with approved API scopes | Plan and permission dependencies |
| Shift4Shop (formerly 3dcart) | Current vendor API, themes and integration documentation | Exact version of the 3dcart / Shift4Shop platform | Test store with an approved API key | Version must be identified before any claim; registry ID migration pending |
| Magento Open Source / Adobe Commerce | Magento and Adobe Commerce module, API, deployment and architecture documentation | Edition (Open Source or Adobe Commerce), version, deployment model, installed modules | Staging instance on an approved edition | Capabilities can differ by edition; each edition is verified separately |

## 3. Verification each platform needs before acceptance

- R1: each platform-specific claim traced to a checked official source, with the version it applies to.
- R2: each platform's integration path exercised against the authorised test instance, with results recorded as evidence.

## 4. Decisions WDS must make

1. Approve the official documentation sources for each platform.
2. Approve authorised test access for each platform, and who holds it.
3. Approve the edition or version to be tested first for Magento and Shift4Shop.
4. Approve the sequence in which real-platform verification proceeds.
