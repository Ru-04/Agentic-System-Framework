# M1 Sprint 2 — Evidence package for QA sign-off

**Prepared for:** AS (designated human QA signatory, as provided by the decision-maker).
**Status:** evidence assembled. **No sign-off is recorded here.** AS's review and signature are required, and this package does not claim that human QA is complete.
**Branch:** `claude/webdesk-specialist-baseline-v1-3b21b1`. **Reviewed commit:** `81d7df8`.

## 1. Acceptance status at a glance

| Item | Status |
|---|---|
| Development authorization (non-production) | In place, per the 22 Oct 2026 amendment and decisions |
| Specification approval | **Not approved.** Reconciled package committed as PROPOSED for formal review |
| Sprint 2 implementation | Implemented and tested; partial against the Shopify objective (see section 6) |
| Sprint 2 QA and acceptance | **Not accepted.** Awaiting AS's review |
| Independent milestone acceptance (M1) | **Not started** |
| Production release | Not authorized |

## 2. Sprint 2 completion report

`docs/M1_S2_COMPLETION_REPORT.md`, including section 10 (run results) and section 11 (QA3 dispositions).

## 3. Independent QA3 report and defect dispositions

The QA3 agent was independent of the implementation. Its report (commit `45df73c`) listed 12 items. Each item and its disposition is in `docs/M1_S2_COMPLETION_REPORT.md`, section 11. Summary:

- Fixed in code, with regression tests: QA3-02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12.
- Open, for the decision-maker: QA3-01 (live-retrieval scope). **Resolved by decision 1 of 22 Oct 2026**, which approves the 16 recorded fetches for the recorded run only.
- The QA3 agent's suite result was 349 passing; the current suite is 369 passing, after the relevance work and the QA3 fixes.

## 4. Real investigation results for all 17 requirements

`docs/evaluation/SHOPIFY_REAL_INVESTIGATION_2026-10-22.md`. Each row gives the passages retrieved, the grade counts (DIRECT, PARTIAL), the status, the findings, the sources cited, the option classes with direct evidence, and the gap count.

Headline figures from that record:
- Requirements retained: **17**.
- Requirements with a DIRECT passage: **0**.
- Requirements with a cited finding (partial or direct): **6**.
- Requirements with no finding: **11**.
- Passage grades across all runs: 31 PARTIAL, 0 DIRECT, 0 IRRELEVANT.
- Feasibility: NOT DETERMINED for all 17.

## 5. Source provenance and citation evidence

- Corpus: 16 allowlisted `shopify.dev` pages, retrieved live on 22 Oct 2026 under decision 1. Each has a URL, a retrieval time, a character count and a SHA-256. The table is in the evaluation record, section 2. Page text is **not** stored in the repository.
- Every finding carries a citation: source ID, workspace ID and a character span. Each citation is checked before emission (`check_claim`). Option-class findings go through the same check.
- Citation check across the 17 live runs (scratch script, run after the final code): **15 findings, 0 citation failures, 0 stale findings.** Every emitted citation passed `check_claim`.
- Source origin is enforced in the record itself (approved proposal P1). Vendor records need an allowlisted HTTPS origin, and internal records need an `internal:` identifier.

## 6. Relevance evaluation results

Implementation: `src/webdesk/evidence/relevance.py`. Rules:
- DIRECT: at least three requirement terms, and at least half the requirement's terms, in the passage.
- PARTIAL: at least two requirement terms.
- IRRELEVANT: fewer than two terms. Such passages are never retrieved, because retrieval already requires two shared terms, so the IRRELEVANT branch is a safety net.

Results on the 17 requirements: 0 DIRECT, 31 PARTIAL. The thresholds were **not** loosened to change this result. Long requirements need many shared terms, so a differently worded but correct answer can grade as PARTIAL.

Limits of the grade:
- It is lexical only. It cannot confirm that a passage answers a requirement.
- Human review of the grades is needed. No human labelling has been done, so none is claimed.
- The unit tests (`tests/unit/test_relevance.py`) use **synthetic** labelled pairs to check the rules. They are not evidence about any platform.

## 7. Regression test evidence

Command: `uv run pytest tests/unit -q -p no:warnings`. Result: **369 passed**, 0 failed.

Per file (collected counts):

| File | Tests |
|---|---|
| `test_specialist_contract.py` (Sprint 1) | 15 |
| `test_specialist_harness.py` (Sprint 1) | 27 |
| `test_specialist_qa_regressions.py` (Sprint 1 QA) | 29 |
| `test_evidence_services.py` | 49 |
| `test_evidence_p1_p2.py` | 14 |
| `test_evidence_qa_regressions.py` (Sprint 2 QA2) | 29 |
| `test_shopify_specialist.py` | 10 |
| `test_shopify_options.py` | 10 |
| `test_relevance.py` | 11 |
| `test_s2_qa3_regressions.py` (Sprint 2 QA3) | 9 |
| Sprint 2 unit tests total (new in Sprint 2) | 132 |
| Pre-existing unit tests (Gate 1 foundation, before Sprint 1) | 166 |
| Unit suite total (166 + 71 Sprint 1 + 132 Sprint 2) | 369 |

Static checks, run on the reviewed code: `ruff check src tests migrations` clean; `ruff format --check` clean; `mypy` (strict, `src/webdesk`) clean.

Integration and hardening suites: they touch the database. Sprint 2 does not change them. Their last recorded run, on `5122012`, was 298 passing (the CI replay). They were not re-run for Sprint 2.

## 8. Security and sanitization verification

- **Sanitization.** The four Shopify briefs (`docs/evaluation/SHOPIFY_CASE_BRIEFS_SANITIZED.md`) contain no client names. The public-page slugs were removed; the mapping is held by the decision-maker, outside this repository. A search of the evaluation, evidence and governance documents for known client names found none.
- **Quarantine.** Instruction-like text is screened after Unicode normalization, and a whole record is quarantined if any of it matches. Quarantine is keyed by record identity, so a clean record cannot clear a flagged one that shares its ID.
- **Egress.** Vendor fetches are limited to exact allowlisted hosts over HTTPS on the default port, with no credentials in the URL and no redirects. Environment proxies are not used (approved proposal P2).
- **Authority.** Specialists declare actions; forbidden governance actions are refused. Declared-only enforcement is a known limit (QA-07), deferred to M3 S6 by decision.
- **Feasibility.** Never asserted by code. A test checks that output statements contain no feasibility claim.
- **No model calls.** No live model or provider is called. The semantic validator refuses to run.

## 9. Remaining source allowlist approvals

See `docs/governance/PROPOSED_ALLOWLIST_EXPANSION_2026-10-22.md`. In summary:
1. An approved access method for `help.shopify.com`, which is already listed but returns HTTP 403 to the fetch client. Eleven of the 17 requirements depend on sources this would unlock.
2. `shopify.com`, for plan-tier and feature-availability pages only. This needs a new-domain approval.
3. Any government source (for example, for Canadian tax rules). This needs a separate source-category approval under D08.

No new domain has been accessed.

## 10. GitHub CI for `81d7df8`

- Workflow: `specialist-ci`
- Run ID: **39805574221** (run number 7)
- URL: https://github.com/Ru-04/Agentic-System-Framework/actions/runs/39805574221
- Commit SHA: `81d7df8b…` (pushed from branch `claude/webdesk-specialist-baseline-v1-3b21b1`)
- Result: **success**
- Jobs: `lint-type-unit` — success; `postgres-tests` — success (integration, committed and hardening suites on PostgreSQL 16.4).
- Failed jobs: none.

Earlier runs on the same branch, for reference: `45df73c` run 39804483161 (success); `2b0cef2` run 39797667617 (success).

## 11. Outstanding limitations and risks

1. **No DIRECT evidence** for any of the 17 requirements under the lexical rule. Option coverage is therefore zero.
2. **Lexical grading.** Relevance is not verified by a human or a validated semantic method.
3. **Corpus coverage.** 16 pages, all from one host. Plan tier and version applicability are not verified.
4. **`help.shopify.com` blocked** (HTTP 403 to the fetch client).
5. **QA-07.** Authority is declared, not enforced at run time, until M3 S6.
6. **Specification not approved.** The reconciled package is for review only.
7. **No independent milestone testing** for M1 has been performed.

## 12. Readiness

- **For AS's review:** ready. This package and the referenced files are complete and internally consistent.
- **For M1 independent milestone testing:** **not ready.** Sprint 2 is not accepted, Sprint 1 is not formally accepted, and no independent milestone tester has been assigned.

## 13. Sign-off (to be completed only by AS)

- Signatory name: ______________________
- Role: ______________________
- Commit reviewed (SHA): ______________________
- Decision: [ ] PASS   [ ] FAIL   [ ] PASS WITH CONDITIONS (list below)
- Conditions: ______________________
- Date: ______________________
- Signature or approval reference: ______________________

*This package records no sign-off. AS's decision is recorded only in this section, once completed by AS.*

## Update 22 October 2026 — decisions S2-D07 to S2-D12 (supersedes the figures above where they differ)

- Relevance: PARTIAL floor tightened to three terms. Plural and hyphen folding added. Candidate ranking added (top 20, ranked by grade, then topic or option signal, then shared terms). Independent label check (AI agent, not human; 55 pairs): agreement 46 of 55 with the three-term floor, versus 29 of 55 with two terms. The floor was tuned on the same labels, so this is not validation.
- Current evaluation (17 requirements): **0 DIRECT, 15 PARTIAL, 31 IRRELEVANT passages**. **3 requirements** have a cited finding; **14** have none; 3 have partial evidence only.
- Sources: 16 shopify.dev pages and 2 CRA pages retrieved. The 2 Shopify plan pages (`shopify.com/pricing` and `/plus`, via `www`) returned HTTP 403 to the fetch client and were not retrieved. `help.shopify.com` returns HTTP 403 to the fetch client. A browser read of one help page succeeded, but its text was not ingested.
- Citations: 13 findings, 0 citation failures, 0 stale findings.
- Tests: unit suite passing (see the report for the count after this change).
- CI: run `39806794237` for `99c4325` succeeded (S2-D12). The commit that follows this update is verified separately.
- Sign-off: **AS's review and sign-off are still pending.** None is recorded.

## Superseded by QA4 response (later on 22 October 2026)

The figures in the sections above that give 15 PARTIAL, 3 requirements with findings, 13 findings, 46 of 55 agreement, and 369 or 370 tests are **superseded**. Current figures and dispositions: `docs/evidence/SPRINT2_QA4_RESPONSE.md`. Current: 389 unit tests passing; 0 DIRECT, 5 PARTIAL, 107 IRRELEVANT; 0 requirements with a cited finding.
