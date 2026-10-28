# Specialist documentation coverage report (28 October 2026)

**Status: DRAFT. Not an evidence-verification report.**

## 1. Completed specification files

Seven master specifications (20 sections each), all in `docs/specialists/`: `shopify.md`, `shift4shop.md`, `wordpress_woocommerce.md`, `bigcommerce.md`, `magento_adobe_commerce.md`, `standalone_applications.md`, `middleware_applications.md`.

## 2. Supporting knowledge assets

| Asset | Path | Notes |
|---|---|---|
| Machine-readable knowledge (seven) | `docs/specialists/knowledge/<specialist>.json` | Capabilities, clarification rules, unsupported behaviour, proposed feasibility classes, estimation placeholders, QA checklist |
| Shared source manifest | `docs/specialists/knowledge/sources.json` | 12 entries, each with a status and an approval reference |
| Generator | `docs/specialists/_gen_specs.py` | Produces the seven master specifications |
| Validation tests | `tests/unit/test_specialist_documentation.py` | 65 tests |
| Index | `docs/specialists/README.md` | Files, authority, status vocabulary |

Not produced: separate API reference index, data model index, integration pattern files, and evaluation scenario files per specialist. Those are either content that is pending official evidence, or are covered by the master specifications and the shared Sprint 5 draft. Creating them now would add empty files or duplicate catalogs.

## 3. Capability catalog coverage

| Specialist | Canonical ID | Capabilities | Edition split |
|---|---|---|---|
| Shopify | CAP-ECOMMERCE | 1 | Not applicable |
| Shift4Shop | CAP-3D-CART-SHIFT-SHOPIFY (legacy) | 1 | Not applicable |
| WordPress & WooCommerce | CAP-WORDPRESS-WOOCOMMERCE | 3 | Not applicable |
| BigCommerce | CAP-BIGCOMMERCE | 1 | Not applicable |
| Magento / Adobe Commerce | CAP-MAGENTO-ADOBE-COMMERCE | 4 | Adobe Commerce 2, Magento Open Source 2 |
| Standalone Applications | CAP-STANDALONE-APPLICATIONS | 1 | Not applicable |
| Middleware Applications | CAP-MIDDLEWARE-APPLICATIONS | 1 | Not applicable |

Total: 12 capabilities, matched to the code catalog by tests.

## 4. Source evidence coverage

| Status | Count | Sources |
|---|---|---|
| APPROVED AND ACTIVE | 0 | None |
| APPROVED BUT INACTIVE | 6 | Shopify, WooCommerce, BigCommerce product page, Adobe Commerce exact pages, Adobe shared PHP page, Magento Open Source release notes |
| DISCOVERY ONLY | 1 | Shift4Shop (3dcart) |
| DEFERRED | 1 | Adobe Commerce marketplace (proposal, not approved) |
| REJECTED | 2 | Adobe frontend-core (excluded), devdocs.magento.com |
| NO APPROVED SOURCE | 2 | WordPress core documentation, technology-neutral placeholder |

Real evidence retrieved and checked for the documentation: **none**. A Sprint 2 Shopify corpus exists outside the repository, in a session scratchpad, with a metadata file of hashes. It is not a governed record, so this package does not treat it as verified evidence. Governance must decide whether it is admissible.

## 5. Missing real documentation

Every platform fact in the seven master specifications is PENDING OFFICIAL EVIDENCE, UNKNOWN, NOT APPLICABLE or REQUIRES PROJECT-SPECIFIC INPUT. This includes architecture, ecosystems, extension mechanisms, endpoints, data models, integration APIs, customization, limits and versions.

## 6. Missing source approvals

- Activation of each APPROVED BUT INACTIVE source (see `docs/governance/SOURCE_ACTIVATION_REQUEST_2026-10-28.md`).
- Ownership confirmation: WooCommerce, BigCommerce, Adobe (partial), Magento release notes (partial).
- Shopify: the S2-D07 to S2-D09 decision record was not located in the repository.
- Shift4Shop: ownership not verified; activation not requested.
- WordPress core: no approved source.
- Standalone and Middleware: WDS must name a technology and a product.

## 7. Documentation validation test results

- `tests/unit/test_specialist_documentation.py`: 65 tests passed locally.
- Full unit suite: 838 passed locally, ruff and strict mypy clean.
- Checks include: registry ID consistency; capability match against the code catalog; no duplicate capability definitions; source status against the engine boundaries; no source active; no rejected or deferred source in use; edition separation for Magento; all 20 sections in order; allowed labels only; backticked repository paths exist.

## 8. CI evidence

Pending. Recorded against the commit that pushes this package once CI reports on it.

## 9. Independent QA readiness

Not submitted. The package has no PG review. Delivery to PG has not been evidenced. The package should be reviewed on the commit that pushes it.

## 10. Remaining Sprint 4 completion blockers

1. PG personal review, declaration and attestation.
2. Frozen acceptance criteria not located; PROPOSED reconciliation still awaiting WDS approval.
3. Source activation approvals and ownership confirmations.
4. Real documentation retrieval, once sources are activated.
5. Shopify 55-pair human evaluation (0 of 55).
6. The Sprint 2 allowlist conflict (`VENDOR_ALLOWLIST` covers Shopify only).
