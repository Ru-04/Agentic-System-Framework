# Capability coverage gap analysis and expansion proposal (28 October 2026)

**PROPOSED. This does not change `AGENT_REGISTRY.yaml` or `src/webdesk/specialists/catalog.py`.** Any new registry entry needs separate WDS authorization. Each row compares the registry responsibilities and purposes (AGENT_REGISTRY.yaml) with the 12 registered capabilities in the code catalog.

## 1. Current coverage (12 capabilities)

| Specialist | Registered capabilities | Source status |
|---|---|---|
| Shopify | plan feature availability | Approved, inactive |
| Shift4Shop | product read API | Discovery only |
| WordPress & WooCommerce | product variation pricing; REST API product read; Store API cart | WooCommerce approved, inactive. WordPress core: none |
| BigCommerce | product catalog read | Approved product page, inactive |
| Magento / Adobe Commerce | REST product read; GraphQL query (Adobe Commerce); release history and catalog import (Magento Open Source) | Adobe exact pages inactive; release notes inactive |
| Standalone Applications | application architecture selection | No source (technology not selected) |
| Middleware Applications | webhook delivery retry | No source (product not selected) |

## 2. Gaps against the registry responsibilities

| Specialist | Responsibility or purpose in the registry | Absent from the catalog | Assessment |
|---|---|---|---|
| Shopify | Storefronts, themes, apps, extensions, APIs, checkout, admin and configuration | Storefront and theme capability; apps and extensions; storefront and admin API capability; checkout extensibility; webhooks | Important gaps. Each needs an approved Shopify source page first |
| Shift4Shop | Catalog, orders, customers, integrations, extensions, settings | Catalog; orders; customers; integrations; extensions | Important gaps. Blocked: no approved source |
| WordPress & WooCommerce | Themes and plugins, hooks and extensions, orders, checkout, hosting dependencies | Orders API; hooks and extensions; checkout customization; plugin and theme architecture; hosting dependencies | Important gaps. WordPress core has no approved source |
| BigCommerce | Storefronts, APIs, customizations, extensions, workflows, plan dependencies | Catalog list endpoint (UNKNOWN until its page is approved); plan-dependent feature; checkout; webhooks; apps | Gaps. Order data is UNSUPPORTED_SOURCE. The scenarios document already names the list endpoint and plan case |
| Magento / Adobe Commerce | Modules, storefront customizations, workflows, architecture, integrations | Event-driven integration (the events page is approved, but no capability is registered); shared PHP extension statements; module architecture; checkout | The events page is approved but not registered. Shared PHP has no capability |
| Standalone Applications | Architecture options, API, data, security, QA, deployment, non-functional requirements | Security and non-functional requirements; deployment and infrastructure; data model | Technology-neutral. Capabilities can be written without a source, but every answer is a recommendation, not evidence |
| Middleware Applications | Orchestration, transformation and synchronization, authentication, retries, idempotency, observability | API orchestration; data transformation and synchronization; idempotency; observability; recovery | Technology-neutral. Same caveat as Standalone |

## 3. Platform and edition gaps

- Magento Open Source has no feature-level approved source. Any feature capability for it is UNSUPPORTED_SOURCE by design (MAGENTO-01).
- Adobe Commerce pages are approved for three overview topics only. Endpoint-level capabilities need separate approved pages (ADOBE-01 scope).
- The shared PHP page supports shared statements only. Edition-exclusive extension claims need separate pages.

## 4. Proposed expansion (not authorized)

Candidate capabilities for WDS to consider, in priority order:

1. Magento/Adobe: event-driven integration (Adobe Commerce only). The approved events page exists, so this is the most immediate gap.
2. BigCommerce: product list endpoint and plan-dependent feature. Both are named in the scenarios document and need their pages approved first.
3. WooCommerce: checkout customization through hooks. Named in the scenarios document (WooCommerce scenario 2).
4. Shopify: storefront API read and webhooks. Needs an approved Shopify page per capability.
5. Standalone and Middleware: nonfunctional-requirement and recovery capabilities. Technology-neutral, so no source is needed for the design guidance itself.

Each candidate needs a registry ID, the terms that match it, a named source, and WDS approval. None is added to the catalog by this proposal.

## 5. Capability definitions awaiting official evidence

Every one of the 12 registered capabilities awaits official evidence. Platform statements about them remain PENDING OFFICIAL EVIDENCE until a real page is retrieved and checked.
