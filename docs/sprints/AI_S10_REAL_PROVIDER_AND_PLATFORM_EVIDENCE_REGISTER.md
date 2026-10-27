# AI-S10 Real-Provider and Platform Evidence Validation Register

Status: **none of these checks has run.** Each is blocked on an approval or environment that does not exist.
Nothing here is a pass. The synthetic specialist tests (SPEC-01 to SPEC-14) use `synthetic_mock` evidence
only and say nothing about real vendor documentation or real platforms.

## A. Gates outside synthetic evaluation

| ID | Class | Scenario | Gate | Status | Approval or input missing |
|---|---|---|---|---|---|
| EXT-01 | C real-provider | Real-provider semantic evaluation of requirement analysis | Live LLM calls | Blocked, not run | LLM provider and model decision (D-12); budget; data-processing policy; live-call approval |
| EXT-02 | D vendor/sandbox | Authorised test-store and sandbox investigation | Sandbox access | Blocked, not run | Source-access approval; sandbox credentials. None granted |
| SPEC-15 | D vendor/sandbox | Vendor-documentation validation for each of the seven specialists | Documentation retrieval | Blocked, not run | Approved source-access matrix and per-vendor allowlist (D-02). None granted |
| EXT-03 | E human workflow | Full-platform human workflow and UAT | Human participants, Foundation UI | Blocked, not run | Foundation UI; human participants; Stage D approval |
| SPEC-16 | E platform | Real-platform acceptance for each of the seven platforms | Platform access | Blocked, not run | Platform approval; no sandbox or test store authorised |
| SOW-13 | E platform/template | WDS house-template fidelity and DOCX/PDF export | Approved template and export | Blocked, not run | Approved house template and section contract (D-10); export acceptance tests. No DOCX or PDF is produced |
| EXT-04 | F production | Production security and readiness checks | Production environment | Blocked, not run | Production environment; configuration decisions; external review |

## B. The seven platform categories in scope

Each has a synthetic specialist test only. None has real-platform or vendor-documentation evidence.

| Category | Specialist (identity) | Real-platform evidence (SPEC-16) | Vendor documentation (SPEC-15) |
|---|---|---|---|
| shopify | `shopify_specialist` | Not run | Not run |
| WordPress / WooCommerce | `wordpress_woocommerce_specialist` | Not run | Not run |
| BigCommerce | `bigcommerce_specialist` | Not run | Not run |
| 3dcart / Shift4Shop shift to Shopify | `three_d_cart_shift_shopify_specialist` | Not run | Not run |
| Magento / Adobe Commerce | `magento_adobe_commerce_specialist` | Not run | Not run |
| Standalone applications | `standalone_applications_specialist` | Not run | Not run |
| Middleware applications | `middleware_applications_specialist` | Not run | Not run |

AI-S04 platform tests (BigCommerce, Magento, Shift4Shop, WooCommerce: 67 tests) are synthetic engineering
tests. They do not replace SPEC-15 or SPEC-16.

## C. Rule applied

Each external gate is listed separately and is not aggregated into any synthetic percentage. A
synthetic result for a platform must not be read as platform acceptance.
