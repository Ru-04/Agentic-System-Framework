# Specialist integration report (26 October 2026, uncommitted)

**Status: partial. Real platform investigation is NOT complete for any specialist. No specialist meets MVP acceptance.** Work was limited by the approved boundaries: no approved vendor source, no real client data, no registry migration, and no live retrieval. This report does not claim MVP completion.

## 1. Canonical IDs (verified against the catalog and the registry)
| # | Category | Canonical ID (WebDesk catalog) | Registry name in `AGENT_REGISTRY.yaml` | Note |
|---|---|---|---|---|
| 1 | Shopify | `shopify` | Shopify specialist | Consistent |
| 2 | Shift4Shop (formerly 3dcart) | `shift4shop` | "3dcart / Shift4Shop Platform Specialist (legacy identifier)"; route `ROUTE-...-3DCART...`; legacy `CAP-3D-CART-SHIFT-SHOPIFY` | Legacy alias preserved. Registry migration needs WDS approval (not done) |
| 3 | WordPress & WooCommerce | `wordpress_woocommerce` | `CAP-WORDPRESS-WOOCOMMERCE`, category `wordpress_woocommerce_specialist` | Consistent in intent; ID spelling differs by suffix |
| 4 | BigCommerce | `bigcommerce` | Present in registry | Consistent |
| 5 | Magento / Adobe Commerce | `magento_adobe_commerce` | Present in registry | Edition split required (MAG-01) |
| 6 | Standalone Applications | `standalone_applications` | `ROUTE-STANDALONE-APPLICATIONS-001`, `CAP-STANDALONE-APPLICATIONS` | Technology-neutral (TECH-01) |
| 7 | Middleware Applications | `middleware_applications` | `ROUTE-MIDDLEWARE-APPLICATIONS-001` | Technology-neutral (TECH-02) |

**Registry compatibility finding:** the WebDesk catalog and the registry agree on all seven categories. They differ in identifier spelling (suffixes and the Shift4Shop legacy form). The catalog keeps the legacy Shift4Shop alias. No migration was made.

## 2. Five-platform source-access matrix (status)
| Platform | Source approval | Retrieval performed | Permitted now |
|---|---|---|---|
| Shopify | Not approved (candidate `shopify.dev` only) | None | Nothing beyond existing approved allowlist entries, which are not a basis for real investigation without WDS approval |
| WordPress & WooCommerce | Not approved | None | Nothing |
| BigCommerce | Not approved | None | Nothing |
| Shift4Shop | Not identified | None | Nothing |
| Magento Open Source / Adobe Commerce | Not approved | None | Nothing |

Standalone Applications and Middleware Applications: no source is possible until WDS names the technology or product (TECH-01, TECH-02).

## 3. Specialist implementation matrix
| Specialist | Shared placeholder or real? | Platform-specific code | Real investigation | Synthetic only |
|---|---|---|---|---|
| Shopify | Real code (WebDesk investigation, M1 S2); synthetic agent (AI Engine) | Shopify option classes, capability topics | **No**: 0 DIRECT evidence; no approved live source | Yes (AI Engine agent) |
| Shift4Shop | Profile in WebDesk; synthetic agent in AI Engine | Profile topics; no source | **No** | Yes |
| WordPress & WooCommerce | Profile; synthetic agent (AI Engine) | Profile topics; no source | **No** | Yes |
| BigCommerce | Profile; synthetic agent (AI Engine) | Profile topics; no source | **No** | Yes |
| Magento / Adobe Commerce | Profile; synthetic agent (AI Engine) | Profile topics; no source | **No** | Yes |
| Standalone Applications | Profile + shared base only | None (technology-neutral) | **No** | n/a |
| Middleware Applications | Profile + shared base only | None (technology-neutral) | **No** | n/a |

Branch audit: the six `feature/specialist-*` branches are all at `5122012` and contain no platform code. The platform code is on `claude/webdesk-specialist-baseline-v1-3b21b1` and `integration/ai-s01-s02-s03`.

## 4. Capability coverage against the requested list
For each specialist, the list in the task (capability identification, source discovery, technical constraints, requirement implications, citations, confidence and unknowns, unsupported-source handling, structured findings) is implemented as follows:
- **Capability identification** (keyword topics): implemented in the WebDesk base and profiles. Keyword matches are not capability claims.
- **Source discovery and evidence collection:** implemented only against approved allowlists. No allowlist is approved for any specialist except the Shopify entries already in the repository, so no discovery occurs for the other six.
- **Platform-specific technical constraints:** not implemented beyond Shopify. Not supported by evidence for the others.
- **Requirement implications:** not implemented.
- **Evidence citations:** implemented in the shared base and tested with fixture sources. Fixture citations are not evidence of a platform.
- **Confidence and unknowns:** unknowns are implemented (for example "no approved evidence source is configured"). Confidence scoring is not implemented.
- **Unsupported or inaccessible source handling:** implemented (failed or incomplete output, no retrieval without a source).
- **Structured findings for the AI engine:** the WebDesk output contract exists. The AI Engine side for the six non-Shopify specialists is synthetic.

## 5. Tests
- Webdesk unit tests: last verified 536 passed at `e3ba3b7`. **NOT EXECUTED at the current head**, Application Control error 4551. Contract, harness, workspace, authority and negative tests exist in the repository but could not be run at the current head.
- AI Engine clean-room at `052d853`: 1257 passed; ruff clean.
- No contract tests were added in this step, because no test could be executed to verify them.

## 6. Developer assignments and gaps
- **Standalone Applications:** no developer assigned in the four-developer allocation. Assignment is reported as BD (chat, 23 October). BD's acceptance into this lane is not recorded. Its lane is not complete.
- **Middleware Applications:** same. Assignment reported as BD. Not complete.
- **Shift4Shop:** developer B (allocation). Source not identified (SRC-02).

## 7. Remaining blockers
1. Approved official sources for each platform (SRC-01, SRC-02, and the technology or product for Standalone and Middleware).
2. Real-platform authorized test instances and test credentials (not granted).
3. Architecture integration: adapter implementation under ARCH-02, not started.
4. Registry migration for the Shift4Shop identifier: needs WDS approval.
5. Application Control error 4551: current-head tests not executed.
6. PG independent review and sign-off: pending.
7. Developer assignment for Standalone and Middleware: confirm BD or another developer.

## 8. Milestone and sprint status
- M1 S1 and S2: not accepted (human QA not signed; 55-pair relevance review at 0 of 55).
- M2 S3: foundations in place; not accepted; current-head tests not executed.
- M2 S4 and S5: not started (need approved sources and real-platform evidence).

## 9. What was not done, and why
- No vendor crawling, retrieval or search-result use as evidence.
- No real client data.
- No registry migration.
- No commit or push. This report and the other changes stay uncommitted, as the directive requires.
- No claim that any specialist meets real-investigation acceptance.

## Update 26 October 2026 (after adapter v0.2 commit 3969a8f)
- Seven categories: all seven resolve their canonical capability and run the foundation path through the adapter (tests in `test_adapter_v02.py`). Status for each: the same as the matrix above. No category is functional in the sense of real platform investigation.
- Shift4Shop: candidate `developer.3dcart.com`, ownership not verified (see `SHIFT4SHOP_SOURCE_DISCOVERY_2026-10-26.md`).
- Standalone and Middleware: technology-neutral; no technology selected; BD assignment approved (DEV-01), implementation evidence not yet recorded.
