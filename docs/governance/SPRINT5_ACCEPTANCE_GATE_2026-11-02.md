# M2 Sprint 5: acceptance gate evaluation (2 November 2026)

**Result: CONDITIONAL AUTHORIZATION — NOT EFFECTIVE.** Sprint 5 is not accepted. Several mandatory gates are not met, and the WDS pre-authorized conditional acceptance cannot take effect until they are. No approval has been recorded, and Sprint 5 is not marked complete.

Final engineering SHA and CI result: see section 4.

## 1. Gate results

| # | Gate | Result | Evidence and exact remaining blocker |
|---|---|---|---|
| 1 | Complete approved seven-specialist evaluation scope | **NOT MET** | 30 requirement-level scenarios across all seven specialists (`sprint5_scenarios_v5.json`). Real evidence exists for 2 active sources (5 pages). Five specialists have no active source. The scope is not complete: real evidence and human labels do not cover the specialists, and the citation-integrity and workspace-authorization dimensions are not scored by the scenarios |
| 2 | Successful final CI on the exact engineering SHA | **PENDING** | See section 4. Local checks pass; PostgreSQL and hardening tests were not run here |
| 3 | All approved measurable thresholds satisfied | **NOT MET** (incomplete) | Six measurable rows MET (`SPRINT5_SCORECARD_2026-11-02.json`). Not measured by the harness: citation correctness on real retrieval. Pending: Shopify relevance and agreement |
| 4 | Authentic Shopify human-label evaluation | **NOT MET** | 0 of 55 labelled. AS is appointed but has not supplied judgments. Passage text is not available in the repository. Agreement needs a second rater and an adjudicator, neither appointed |
| 5 | Required real-evidence and citation criteria | **NOT MET** | One verified claim, narrow (BigCommerce single product, v3). No citation for any Adobe or Magento capability: no activated page states a version. Open defect: headings can still supply a passage (`SPRINT5_REAL_EVIDENCE_REPORT_2026-11-02.md`, section 4) |
| 6 | S5-005, S5-007 and S5-011 resolved or validly dispositioned | **NOT MET** | S5-005 and S5-007: resolved and verified. S5-011: **OPEN**, a governance decision that WDS has not made (`SPRINT5_S5-011_DISPOSITION_2026-11-02.md`) |
| 7 | Genuine PG independent QA PASS covering the final code | **NOT MET** | READY — DELIVERY PENDING. No delivery channel, and PG's independence is not confirmed. No PG evidence exists, and none is created here |
| 8 | Mandatory QA remediation independently verified | **NOT MET** | Cannot be verified without PG's findings. Remediation is not NOT REQUIRED: no PG PASS exists |
| 9 | No outstanding mandatory security, scope or acceptance blocker | **NOT MET** | Blockers: Shopify source reconciliation (boundary broader than the decisions, `help.shopify.com` and `shopify.dev` as whole hosts; S2-D08 unconfirmed; ownership not recorded); S5-011; Shopify labels; PG QA |

## 2. Exact blockers, in the order they can be cleared

1. **PG delivery and independent review.** Needs a PG delivery channel and PG's personal independence declaration, review, findings and attestation. Claude cannot supply these.
2. **AS's labels for the 55 pairs.** Needs the passage package released through an approved channel, and AS's own judgments. Claude cannot supply these.
3. **Second rater and adjudicator** (only if WDS approves an agreement measurement).
4. **WDS decision on S5-011**: options A, B or C in the disposition record.
5. **WDS decision on Shopify boundary scope**: confirm S2-D08, restrict `help.shopify.com`, remove or justify `shopify.dev`, correct the S2-D09 citation.
6. **Engineering, which I can do next**: resolve the heading-passage defect with a WDS-approved rule, and re-run the full CI on the final SHA.
7. **Specialist coverage beyond requirement-level routing.** Five specialists need an approved source, which requires ownership verification and explicit authorization first.

## 3. Changes made in this cycle

- **Sources activated** (management section 2): Adobe Commerce exact pages (`ADOBE_COMMERCE_EXACT`) and the Magento Open Source release-notes page. Recorded in `docs/specialists/knowledge/sources.json`, the engine's `ACTIVE_BOUNDARIES`, and `SPRINT5_SOURCE_ACTIVATION_MATRIX_2026-11-02.md`.
- **Shopify: not activated.** Reconciled; not eligible (matrix, section 4).
- **Defect fixed**: the document title could supply a passage (regression test `test_the_document_title_cannot_supply_a_passage`).
- **Runner**: activity is now per capability boundary, not per specialist, and an Adobe-only capability requested for Open Source is not applicable (ADOBE-01).
- **Dataset v5** (new manifest): S5-008 and S5-024 changed from UNSUPPORTED_SOURCE to INVESTIGATE_WITH_UNKNOWNS, because of the activation. Nothing else changed. v1 to v4 are unchanged.
- **Tests updated** where they pinned the pilot-only activation set. Each change is a listed activation, not a relaxation.

## 4. Engineering verification

- Local: `ruff check`, `ruff format`, `mypy --strict`, full unit suite (see the commit message and the PR-free status below). PostgreSQL and hardening tests are skipped here (no database configured).
- CI: the final SHA and its CI result are recorded in the chat report, not in this file, because a file in the commit cannot name its own commit.

## 5. Recommendation

HOLD. Do not record Sprint 5 acceptance. Sprint 6 preparation is not started and is not authorized by this record.

## 6. Update, 2 November 2026 (second cycle)

- Gate 5 (real evidence): the verified-claim count is now **zero**. The BigCommerce claim is withdrawn under Decision 3 (see `SPRINT5_REAL_EVIDENCE_REPORT_2026-11-02.md`, section 7). Gate 5 is not met.
- Gate 6: S5-011 is resolved under WDS Decision 1 (middleware, 2 November 2026). Its evidence outcome stays UNSUPPORTED_SOURCE, and the specification is corrected. S5-005 and S5-007 are unchanged.
- Gate 9: the Shopify restricted-source policy is applied in code (Decision 2). S2-D08 is still unconfirmed.
- Gates 4 and 7 are unchanged: no human labels, and no PG review.
