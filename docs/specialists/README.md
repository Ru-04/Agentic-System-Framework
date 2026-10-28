# Specialist documentation package (M2 Sprint 4 workstream, 28 October 2026)

**Status: DRAFT FOR REVIEW. No platform fact in this package is verified.** No documentation source has been retrieved. Every platform statement is labelled PENDING OFFICIAL EVIDENCE until a real page is retrieved and checked under an activated approval.

## Files

| Specialist | Master specification | Machine-readable companion |
|---|---|---|
| Shopify | `shopify.md` | `knowledge/shopify.json` |
| Shift4Shop (3dcart legacy) | `shift4shop.md` | `knowledge/shift4shop.json` |
| WordPress & WooCommerce | `wordpress_woocommerce.md` | `knowledge/wordpress_woocommerce.json` |
| BigCommerce | `bigcommerce.md` | `knowledge/bigcommerce.json` |
| Magento / Adobe Commerce | `magento_adobe_commerce.md` | `knowledge/magento_adobe_commerce.json` |
| Standalone Applications | `standalone_applications.md` | `knowledge/standalone_applications.json` |
| Middleware Applications | `middleware_applications.md` | `knowledge/middleware_applications.json` |

Shared: `knowledge/sources.json` (one source manifest for all seven). `_gen_specs.py` generates the seven master specifications. The JSON knowledge files were generated from `src/webdesk/investigation/specialists.py` and `src/webdesk/specialists/catalog.py`.

## Authority

- Canonical capability IDs come from `WebDesk_Agentic_Requirement_Platform_Specs/AGENT_REGISTRY.yaml` and `src/webdesk/specialists/catalog.py`. They are not duplicated or replaced here.
- Source approvals come from the decision register and source records named in `knowledge/sources.json`.
- Consistency is enforced by `tests/unit/test_specialist_documentation.py`.

## Source statuses

Vocabulary: APPROVED AND ACTIVE, APPROVED BUT INACTIVE, DISCOVERY ONLY, UNVERIFIED, DEFERRED, REJECTED, NO APPROVED SOURCE. No source is APPROVED AND ACTIVE.
