# Independent QA review package for PG — Sprint 1, Sprint 2, Sprint 3 (23 October 2026)

**Purpose:** evidence index for the nominated independent reviewer. **This package is not QA.** It records what exists and where. It does not record any result, finding, sign-off or approval, and it does not replace the reviewer's own work.

**Access condition:** PG must confirm access to the repository branch `claude/webdesk-specialist-baseline-v1-3b21b1`. The reviewed commits are on that branch.

## 1. Sprint 1 — implementation and tests
- Implementation: `src/webdesk/specialists/` (contract, errors, authority, workspace, harness, mock, catalog).
- Tests: `tests/unit/test_specialist_contract.py`, `tests/unit/test_specialist_harness.py`, `tests/unit/test_specialist_qa_regressions.py`.
- Reports: `docs/M1_S1_SPRINT_COMPLETION_REPORT.md`, `docs/M1_S1_QA_CLOSURE_REPORT.md`, `docs/M1_S1_FINAL_GATE_REPORT.md`.
- Human QA sign-off: **not given**. Section G of `docs/M1_S1_HUMAN_QA_CHECKLIST.md` is unsigned.

## 2. Sprint 2 — relevance evaluation and remaining human-label requirements
- Evidence services: `src/webdesk/evidence/` (sources, retrieval, allowlist, untrusted, citations, http_vendor, relevance, evaluation, evaluation_cli).
- Shopify specialist: `src/webdesk/specialists/platforms/shopify.py`, `shopify_options.py`.
- Evidence package: `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md` (section 13 unsigned).
- Human relevance: **0 of 55 pairs labelled.** The reading file is staged outside the repository and has not been transferred. The label template is in the staged package, not in the repository.
- Result to date: 0 DIRECT, 5 PARTIAL, 111 IRRELEVANT passages (per the Sprint 2 record). Zero requirements with cited capability findings.
- Governance records: `docs/governance/MANAGEMENT_SIGNOFF_SPRINT2_2026-10-23.md`, `docs/governance/AS_APPROVALS_RECORD_2026-10-23.md`, `docs/governance/DECISION_RECORD_Q1_Q11_2026-10-23.md`.

## 3. Sprint 3 — six-specialist foundations
- Shared base and profiles: `src/webdesk/specialists/platforms/generic.py`.
- Six modules: `shift4shop.py`, `wordpress_woocommerce.py`, `bigcommerce.py`, `magento_adobe_commerce.py`, `standalone_applications.py`, `middleware_applications.py`.
- Tests: `tests/unit/test_m2_s3_platforms.py`. All evidence is FIXTURE data.
- Completion report: `docs/governance/M2_S3_COMPLETION_REPORT.md`.
- Sprint 3 is **not** accepted. No approved evidence source is configured for any platform (D08).

## 4. Security and workspace isolation tests
- Workspace isolation and quarantine: `tests/unit/test_evidence_services.py`, `tests/unit/test_evidence_qa_regressions.py`, `tests/unit/test_s2_qa3_regressions.py`, `tests/unit/test_s2_qa4_regressions.py`, `tests/unit/test_m2_s3_platforms.py`.
- Allowlist and path scope: `tests/unit/test_allowlist_scopes.py`.
- Database hardening: `tests/hardening/`, run in CI only (requires provisioned roles).
- Local results at commit `e3ba3b7` code state: unit 536 passed; integration and committed 223 passed (scratch database). Hardening not run locally.

## 5. GitHub CI evidence
- Workflow: `.github/workflows/specialist-ci.yml` (jobs `lint-type-unit`, `postgres-tests`).
- Recorded successful runs (GitHub Actions, branch `claude/webdesk-specialist-baseline-v1-3b21b1`): run 39944926908 (`52eb202`); run 39940330312 (`54aef28`); run #21 on `c54a868` completed successfully (2m 24s).
- `e3ba3b7` and `abf13a9`: check the Actions page for the branch before relying on them. A push of `ae289aa` is blocked (see the tracker).

## 6. Outstanding specification approvals and acceptance restrictions
- Seven specification drafts at `0.3.10-foundation-gate1-review`: **not approved**. Q1 requires a reconciled version, bound to a commit and hashes. None exists.
- Sprint 2 acceptance: not met (human labels, signed QA, specification question).
- Sprint 1 acceptance: not met (human QA not signed).
- Sprint 3 acceptance: not met.
- Milestone 1: not closed. See `docs/governance/MILESTONE1_ACCEPTANCE_TRACKER_2026-10-23.md`.
- Restrictions in force: no production activation, no live model call (D09), no merge to protected branches, no approved evidence source for any Sprint 3 platform.

## 7. What PG must do (not done by the assistant)
1. Confirm role and qualifications, and record them.
2. Confirm PG did not implement or author Sprint 1–3 work.
3. Confirm access to the QA evidence.
4. Perform the QA and record findings.
5. Sign personally. The assistant has not entered any signature or approval for PG.

## 8. Combined package: heads and sprint-separate decisions (26 October 2026)
- **Heads:** integration `2988913` (local); webdesk `72355df` (local; remote `abf13a9`; push deferred).
- **Independence declaration:** `docs/governance/PG_INDEPENDENCE_DECLARATION_TEMPLATE_2026-10-26.md`. Blank. PG completes it personally.
- **Specialist matrix:** `docs/governance/SPECIALIST_IMPLEMENTATION_MATRIX_2026-10-26.md`.
- **AI-S04 scope reconciliation:** `docs/governance/AI_S04_SCOPE_RECONCILIATION_2026-10-26.md`.
- **Test status:** `docs/governance/TEST_EVIDENCE_REGISTER_2026-10-26.md`. Webdesk pytest and mypy at the current head are NOT EXECUTED: APPLICATION CONTROL ERROR 4551.
- **Decisions made separately, one per sprint:** Sprint 1 acceptance; Sprint 2 acceptance (human review 0/55); Sprint 3 acceptance; Milestone 1 acceptance. Each is a separate PG decision (PASS, PASS WITH CONDITIONS or FAIL). The combined package does not merge them.
