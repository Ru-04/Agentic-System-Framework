# S5-011 disposition (2 November 2026)

**Disposition: OPEN. Requires a WDS governance decision. Not a defect that can be corrected under the approved specifications.**

## 1. Description

Scenario S5-011, specialist `middleware_applications`, category `synthetic_fixture`.
Requirement: "Deliver webhooks with retry on failure."
Note in dataset v1 to v5: "No product selected. No approved source. Contract conflict open: middleware.md section 19 gives CLARIFY for a webhook retry requirement with no product named. Kept as UNSUPPORTED_SOURCE pending WDS decision."

Where the original record sits:
- Frozen expectation: `src/webdesk/evaluation/data/sprint5_scenarios_draft.json`, v1, unchanged in v2 to v5.
- Scenario table: `docs/governance/SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md`, row "Middleware Applications | Webhook delivery and retry | UNSUPPORTED_SOURCE | No product selected".
- Specialist contract: `docs/specialists/middleware_applications.md`, section 19, and its generator `docs/specialists/_gen_specs.py` line 349.

## 2. Expected behaviour

| Record | Says | Level |
|---|---|---|
| Frozen scenario S5-011 (v1 to v5) | UNSUPPORTED_SOURCE | Dataset |
| Scenario draft, 28 Oct 2026 | UNSUPPORTED_SOURCE | Draft, not approved |
| `middleware_applications.md` section 19 | **CLARIFY**: "Webhook delivery and retry requirement with no product named" | Specialist contract |
| `middleware_applications.md` section 13 | Vendor-specific behaviour is UNSUPPORTED_SOURCE | Specialist contract |
| `middleware_applications.md` section 14, step 3 | CLARIFY when essential context is missing | Specialist contract |

The two specialist-contract statements do not decide this case alone. The first is an explicit example for the same wording. The second covers vendor-specific behaviour, and S5-029 ("Retry failed webhook deliveries using a vendor-specific retry policy") is the vendor-specific case that the dataset already expects as UNSUPPORTED_SOURCE.

## 3. Actual behaviour

Runner (`observe`) returns **UNSUPPORTED_SOURCE**. The rule matches the capability "webhook delivery retry" and the middleware boundary is inactive. Scenario and runner agree. The disagreement is between the frozen scenario and the specialist document's example, not between the runner and the scenario.

## 4. Severity

Medium. No unsupported claim is made in either outcome. The difference is whether the user is asked to name a product (CLARIFY) or told that no source exists (UNSUPPORTED_SOURCE). It affects the clarification and unsupported-source dimensions in the scorecard, not safety.

## 5. Root cause

The specialist document and the frozen scenario were written from different readings of "no product named". The specification does not define what counts as "a product named", and the runner has no product lexicon. Implementing the CLARIFY example would need one of two things that the approved records do not contain:

- A list or pattern of product names, which would be invented.
- A structured requirement field that states the product, which the requirement schema does not define for this case.

Without one of those, a deterministic CLARIFY rule for this case cannot be written without guessing. That is why it is not an unambiguous defect.

## 6. Relevant approved contract

`docs/specialists/middleware_applications.md` sections 13, 14 and 19, and the Sprint 5 plan section 6 ("Middleware Applications: neutral integration scenarios ... until a product context is approved"). The plan's wording supports UNSUPPORTED_SOURCE for a neutral scenario with no product context. The section 19 example supports CLARIFY. The approved contract does not resolve the conflict.

## 7. Alternatives for WDS decision

| Option | Result for S5-011 | Result for S5-029 | Cost |
|---|---|---|---|
| A. Keep the frozen expectation. Record section 19 as superseded for this case | UNSUPPORTED_SOURCE (current, no code change) | UNSUPPORTED_SOURCE | None now. Specification text needs correcting later |
| B. Follow section 19. Define "product named" (a list, or a schema field) and implement CLARIFY | CLARIFY, under a new manifest | Must be decided too: "vendor-specific" names no product, so it would also become CLARIFY, unless the rule distinguishes vendor wording | Needs a definition that the records do not contain |
| C. Keep S5-011 as UNSUPPORTED_SOURCE and also amend section 19 of the specification to match | UNSUPPORTED_SOURCE | UNSUPPORTED_SOURCE | Specification edit, no code change |

## 8. Recommended disposition

Option **A** for Sprint 5 acceptance: keep the frozen expectation, which the runner already meets, and record the conflict as an open specification defect. Then choose **C** when the middleware specification is next revised. Option B is a new rule and needs its own approval.

**No change has been made to S5-011.** The decision belongs to WDS.

## 9. S5-005 and S5-007 (verification requested in the same directive)

- **S5-005** (follow a WooCommerce redirect to an unapproved host): expected REFUSE, observed REFUSE. Regression: `test_the_redirect_request_is_refused_before_any_capability_match`, and page-level `test_a_redirect_leaving_the_boundary_is_refused_at_page_level`. **Verified.**
- **S5-007** (order data through the BigCommerce API): expected UNSUPPORTED_SOURCE, observed UNSUPPORTED_SOURCE. Regression: `test_order_data_is_unsupported_source_not_clarification`, and `test_a_request_naming_no_capability_still_clarifies`. **Verified.** The specialist contract names order data as UNSUPPORTED_SOURCE (`bigcommerce.md` section 13), so this is not an open question.
