# M2 Sprint 3 completion report — foundations and QA status (23 October 2026)

**Status: foundations implemented, defects from review fixed, local verification passed. Sprint 3 is NOT formally accepted.** Independent QA by a qualified reviewer has not been performed. The review described below was an automated review by the assistant and is not independent QA under Q2.

## 1. Scope delivered
- Shared platform base and profile model: `src/webdesk/specialists/platforms/generic.py`.
- Six platform modules, each a profile plus subclass: `shift4shop.py` (canonical name "Shift4Shop (formerly 3dcart)", per Q3), `wordpress_woocommerce.py`, `bigcommerce.py`, `magento_adobe_commerce.py`, `standalone_applications.py`, `middleware_applications.py`.
- Tests: `tests/unit/test_m2_s3_platforms.py`. All evidence used is FIXTURE data, labelled as such, built with test-only helpers.

## 2. Six-specialist QA results
| Check | Result |
|---|---|
| Contract (input validation, extra fields refused) | Passed |
| Profile matches catalog identifier, no approved source in code | Passed |
| Missing approved source: no retrieval, stated plainly | Passed (zero retriever calls) |
| Retrieval failure yields `failed` | Passed |
| Workspace isolation at retrieval and post-filter | Passed |
| Origin outside the approved source is never cited | Passed (added after review) |
| Fixture origin (`fixture://`) is never citable | Passed (added after review) |
| Instruction-like passage and instruction-like source id excluded and counted | Passed (added after review) |
| Forbidden authority refused by the shared harness | Passed |
| No Shopify wording in output for non-Shopify platforms | Passed (defect fixed, see 4) |
| No native coverage without DIRECT evidence | Passed |

## 3. Limitations that remain (accepted, documented)
- **Fixture provenance is by convention.** A fixture can be built with a permitted-looking origin, because the test helper bypasses the origin check. Production code cannot reach the fixture helper through the approved path, but nothing in the output marks a record as a fixture. The output does not carry a fixture marker. Accepted for Sprint 3; a production retrieval path must not be enabled without a provenance marker.
- **Shared origin rule.** The approved-source check uses each profile's allowlist, but the global origin rule still applies in the Sprint 2 layer. Test configuration applies the Shopify allowlist to all six profiles; this is test-only and is not a platform approval.
- **Option classes are not assessed.** No option-class indicators are defined for any Sprint 3 platform, so no native, app or custom option is ever reported. The option-coverage gaps are reported as unknowns.
- **Coverage on the cap path.** When findings reach the cap, the output stops early and reports the cap. Coverage recorded so far is not extended, so coverage can only be under-reported.
- **Candidate-limit message** counts unfiltered passages from the retriever. Low.
- **Direct `run()` / `investigate()` calls** skip the harness. The harness is the supported entry point; direct calls are a development convenience.

## 4. Defects found in review and fixed
Review by an automated reviewer (read-only) raised eight issues. Fixed:
1. Shopify labels and the Shopify plan clarification were used for all six platforms. Fixed with neutral labels and a neutral clarification.
2. The profile's approved source was checked only for `None`; origins were not checked. Fixed: a passage is citable only if its origin is permitted by the profile's approved source.
3. Fixture origins were not refused. Fixed: `fixture://` origins are not permitted, so they are not cited.
4. Instruction screening depended on the retriever honouring the admission predicate. Fixed: screening is applied again after retrieval.
5. Source identifiers were not screened. Fixed: instruction-like source identifiers are excluded.
6. Substring topic matching produced false signals (for example "event" in "prevents", "log" in "technology", "app" in "apply", "plan" in "explanation"). Fixed with whole-word matching and corrected stems.

Not changed: item 6 of the review (declared actions are the same for every platform and are checked once before the provider runs). Refusal of forbidden actions is tested and working; per-run enforcement is the QA-07 dependency already recorded.

## 5. Verification (commit to be recorded in the git log of this branch)
- `ruff check src tests migrations`: passed.
- `ruff format --check src tests` (CI scope): passed. Three older migration files are outside the CI format scope and were not changed.
- `mypy --strict src/webdesk`: passed, 82 source files.
- `pytest tests/unit`: 536 passed.
- `pytest tests/integration tests/committed` against a scratch PostgreSQL database created for this check and dropped afterwards: 223 passed.
- `tests/hardening` requires CI-provisioned roles and was **not** run locally. It is run by the `postgres-tests` job in CI.

## 6. GitHub CI
Recorded separately in the commit and in section 8 once checked. Do not treat any CI result as passed without the run evidence.

## 7. Not done (explicit)
- No approved evidence source for any Sprint 3 platform (D08). No real platform investigation was run.
- No live model call (D09). No production activation. No merge to a protected branch.
- Sprint 3 formal acceptance and independent QA: not performed.

## 8. Dependencies and owners
- Approved evidence source per platform (D08): WDS Authorized Approver. Proposals in `SPRINT4_EVIDENCE_SOURCE_PROPOSALS_2026-10-23.md`.
- QA-07 runtime authority enforcement: required before any integration. Owner: engineering, scheduled for M3 S6.
- Independent Sprint 3 QA: a qualified reviewer who did not author this work. Not assigned.
