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

## 9. Completion status, 26 October 2026

**Sprint 3 acceptance: NOT ACCEPTED.** Completion work is in place. Mandatory checks at the current head are NOT EXECUTED, and PG independent QA is not done.

1. Six specialist statuses: Shift4Shop, WooCommerce, BigCommerce, Magento, Standalone Applications and Middleware Applications each have a profile and the shared executable base (PlatformSpecialist) in src/webdesk. None has an approved evidence source. None has a real platform investigation. Synthetic AI-S04 agents exist in ai_engine for Shift4Shop, WooCommerce, BigCommerce and Magento only.
2. Architecture compatibility: docs/governance/ARCHITECTURE_COMPATIBILITY_ASSESSMENT_2026-10-26.md. No merge. Preferred direction WebDesk primary with adapters, pending WDS decision.
3. Files created or changed in this completion step: docs/governance/ARCHITECTURE_COMPATIBILITY_ASSESSMENT_2026-10-26.md (new); this report (section 9). Earlier Sprint 3 files: see sections 1 and 2.
4. Test results: ruff check src tests migrations passed and ruff format --check passed (155 files) at 2630ab6. Webdesk pytest tests/unit and mypy src/webdesk: NOT EXECUTED — APPLICATION CONTROL ERROR 4551. Last verified: 536 unit tests passed at e3ba3b7 (state at that commit; not a pass for 2630ab6). Strict mypy last verified clean at e3ba3b7. Integration and committed tests: 223 passed at an earlier code state; not re-run.
5. Remaining defects: (a) Standalone and Middleware have no AI Engine agent, so the two frameworks differ for them; (b) the two frameworks have no shared contract or adapter; (c) the working tree of the integration worktree has uncommitted edits to AI-S04 agents, not from this session; (d) declared actions are checked once per run, not during execution (QA-07 dependency).
6. PG independence and QA: declaration not completed. PG completes it personally. Independence PENDING. No PG review, finding or signature recorded.
7. Sprint 3 acceptance status: NOT ACCEPTED (see above).
8. Milestone 1 dependencies: PG independence and Sprint 1, 2 and 3 QA; 55-pair human labels (0 of 55); specification reconciliation with a version-bound approval; independent Milestone 1 testing; CI on the pushed commit (push deferred).
9. Sprint 4 readiness: NOT READY. Sprint 4 needs approved evidence sources per platform (none approved, D08), the architecture decision, and Sprint 3 acceptance. No Sprint 4 work has started.

## 10. Sprint 3 architecture and acceptance preparation (26 October 2026)
- Reviewed commit for Sprint 3 QA: webdesk `564d0d1` (this branch, local; push deferred). Reference commit for the platform code: `e3ba3b7` plus the governance commits after it. Integration reference: `052d853`.
- Architecture: `ADAPTER_CONTRACT_PROPOSAL_2026-10-26.md` (proposal; not implemented; WDS approval needed).
- Evidence sources: `OFFICIAL_EVIDENCE_SOURCE_REGISTER_2026-10-26.md` (nothing approved; default deny).
- Uncommitted integration changes: `UNCOMMITTED_CHANGES_STATUS_2026-10-26.md`.
- Tests: clean-room ai_engine at `052d853` 1257 passed, ruff clean. Webdesk pytest and mypy at `564d0d1`: NOT EXECUTED, APPLICATION CONTROL ERROR 4551. No authorized alternative runner available to this session; the first route is the GitHub specialist-ci run on a pushed commit (push deferred).
- Sprint 3 acceptance: NOT ACCEPTED. PG independence declaration: not completed by PG; PG completes it personally.
