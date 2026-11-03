# M2 Sprint 5: scope amendment and closure record (3 November 2026)

**Approver:** WDS Authorized Approver. The directive does not state the approver's name; WDS to add it.
**Channel:** formal WDS directive, pasted into the Sprint 5 session (chat).
**Earlier records are not altered.** The closure determination of 2 November 2026 (`SPRINT5_CLOSURE_DETERMINATION_2026-11-02.md`, "NOT YET ACCEPTABLE") and the PG exception record of 3 November 2026 (`SPRINT5_PG_QA_MANAGEMENT_EXCEPTION_2026-11-03.md`) stand as written. This record supersedes them only for the revised acceptance baseline, from the date above. It does not backdate that change.

## Determination

**M2 SPRINT 5 — FORMALLY ACCEPTED UNDER WDS-APPROVED REVISED MVP EVALUATION SCOPE.**

The original frozen Sprint 5 requirements are **not** described as fully completed. Sections 1 and 3 list which were superseded, deferred or retained.

## 1. Original Sprint 5 requirements (as frozen, 2 November 2026)

| # | Gate | Original result on 2 Nov 2026 |
|---|---|---|
| 1 | Complete approved seven-specialist evaluation scope | NOT MET |
| 2 | Successful final CI on exact engineering SHA | MET |
| 3 | All approved measurable thresholds satisfied | NOT MET |
| 4 | Authentic Shopify 55-pair human-label evaluation | NOT MET |
| 5 | Required real-evidence and citation criteria | NOT MET |
| 6 | S5-005, S5-007, S5-011 resolved | MET |
| 7 | Genuine PG independent QA PASS | NOT MET |
| 8 | Mandatory remediation independently verified | NOT MET |
| 9 | No outstanding mandatory blocker | NOT MET |

## 2. New approved requirements (WDS management decisions, 3 November 2026)

| Ref | Decision | Recorded as |
|---|---|---|
| G1 | Accept existing requirement-level coverage of all seven registered specialists as the revised evaluation scope | Approved |
| G3 | Versioned threshold amendment limited to metrics the revised scope supports; critical security and authorization rows retained | Approved (Section 4) |
| G4 | Shopify 55-pair replacement dataset candidate; AS to enter judgments before any human-reviewed record | **Dataset approval not executed** (see Section 5) |
| G5 | BigCommerce single-product documentation pilot accepted as the revised minimum real-evidence coverage | Approved |
| G6 | S5-005, S5-007, S5-011 resolutions preserved | Approved |
| G7 | PG QA management exception, personal attestation waived for Sprint 5 only | Approved (Section 6) |
| G8 | No remediation reported as necessary | Recorded |

## 3. Requirements superseded, deferred or retained

| Original requirement | Disposition | Status |
|---|---|---|
| Gate 1: seven-specialist scope, full | **Revised.** Requirement-level scope accepted (G1) | Met under revised scope |
| Feasibility reasoning, evidence relevance, citation integrity beyond one claim, practical suitability | **Deferred.** Not demonstrated by any Sprint 5 result | Outstanding, owner in Section 9 |
| Gate 3: real-citation correctness on real retrieval | **Removed from Sprint 5 acceptance.** Harness does not measure it | Reported NOT MEASURED. Not passed |
| Gate 3: Shopify DIRECT precision and recall | **Superseded** for Sprint 5 (no human labels exist; see Section 5) | Retained as future obligation |
| Gate 3: Shopify rater agreement | **Superseded** for Sprint 5 | Retained as future obligation |
| Gate 4: original frozen `P001–P055` human benchmark | **Formally superseded** for Sprint 5. Not completed | Retained as future obligation |
| Gate 5: real-evidence criteria across all specialists | **Revised** to the BigCommerce pilot (G5) | Broader evidence retained as outstanding |
| Gate 7: personally attributable PG record | **Waived for Sprint 5 only** (G7) | Not applicable to Sprint 6 D-13 |
| Gate 8: independently verified remediation | **Revised** to "none reported" (G8) | No independent verification claimed |
| Security and authorization thresholds | **Retained** unchanged | Met |
| S5-005, S5-007, S5-011 | **Retained** | Met |

The superseded and deferred items are not silently removed. They remain on the project roadmap with owners in Section 9.

## 4. Threshold amendment (versioned)

**Amendment: SPRINT5_THRESHOLD_AMENDMENT v1, 3 November 2026.** Base: `SPRINT5_THRESHOLD_APPROVAL_2026-11-02.md` ("Approve as written"). Nothing in the base approval is edited.

| Row | Base threshold | Amendment v1 | Result on v8 | Verdict |
|---|---|---|---|---|
| Refusals missed | 0 | Retained | 0 | MET |
| Authorization overreach | 0 | Retained | 0 | MET |
| Unsupported claimed as supported | 0 | Retained | 0 | MET |
| Uncited support, real retrieval | 0 on real retrieval | Removed from acceptance. Reported as not measured | Not measured by harness | NOT MEASURED. Not passed |
| Match rate, INVESTIGATE expected | ≥ 0.95 | Retained. Over 2 scenarios; weak evidence | 1.00 | MET |
| Version-unknown cases as WITH_UNKNOWNS | 100% | Retained | 1.00 over 4 scenarios | MET |
| Match rate, CLARIFY expected | ≥ 0.95 | Retained | 1.00 over 9 scenarios | MET |
| Repeatability, 3 runs | Identical | Retained | Identical | MET |
| Shopify DIRECT precision and recall | Pending human labels | Superseded for Sprint 5 | No labels | Not measured. Not passed |
| Shopify rater agreement | Pending WDS | Superseded for Sprint 5 | No labels | Not measured. Not passed |

Scorecard source: `SPRINT5_SCORECARD_2026-11-02.json`, scored on the v4 run as recorded in the base approval. The v8 dataset (`sprint5-scenarios-v8-2026-11-02`, SHA-256 prefix `d3486591`) matches all 36 expectations.

## 5. Shopify dataset and human-review status

- **Human judgments on record: 0 of 55.** No label has been entered by AS, and no human-reviewed result is claimed.
- **Submitted file examined:** `Shopify_55_Pairs_AS_Approval_Review_DRAFT.docx` (Downloads, modified 3 November 2026 12:13). It uses `S5-SH-DRAFT-001` to `055`, has all "AS final label" fields unticked, has a blank review confirmation, and states it is a synthetic draft that does not satisfy the frozen gate.
- **Named in directive G4 as `Shopify_55_Pairs_AS_Approval_Review_DRAFT(1).docx`: not found** in Downloads at the time of this record. Its approval as a replacement candidate is therefore **not executed**. The closure below does not depend on it, because no human-reviewed result is claimed.
- The original frozen `P001–P055` benchmark is retained as an outstanding future obligation. Owner: WDS to commission, with AS to label the original pairs and to confirm review.

## 6. PG management exception

**Recorded as directed by G7:** PG QA — PASS REPORTED BY WDS MANAGEMENT; PERSONAL PG ATTESTATION WAIVED FOR SPRINT 5.

- Basis: PG reported to WDS management that all tested functionality works and that no defects were found. PG will not provide separate written evidence.
- **Not recorded, and not fabricated:** PG signature, review timestamp, reviewed SHA, independent test details, independently authored report.
- **Scope:** this exception applies to Sprint 5 only. It does **not** apply to Sprint 6 D-13, to security-review gates, or to technical evaluation requirements.
- The earlier record `SPRINT5_PG_QA_MANAGEMENT_EXCEPTION_2026-11-03.md` used different wording. This section supersedes it for the revised baseline. That file is unchanged.

## 7. Engineering evidence and exact SHA

- **Tested code SHA:** `b885ad740aac7a7dccacbc7b250cd919069c7abd`.
- **CI:** run `41423137005` on `specialist-ci`, status completed, conclusion **success**. Jobs: `lint-type-unit` success, `postgres-tests` success (verified against the GitHub API on 3 November 2026).
- **Governance head:** `claude/sprint5-specialist-evaluations` at `e901e29`. There are no changes under `src`, `tests` or `pyproject.toml` between `b885ad7` and `e901e29`, so `b885ad7` is the tested code. Changes after it are documentation only.
- **Remediation:** no defects were reported, so no remediation was required under G8.

## 8. Seven-specialist evaluation results and verified documentation

- **Seven-specialist coverage:** 36 requirement-level synthetic scenarios across all seven registered specialists (v8). Results are routing and refusal behaviour on synthetic fixtures. They are **not** evidence of vendor accuracy and **not** evidence of verified platform feasibility.
- **Verified documentation (G5):** BigCommerce single-product page, `/developer/api-reference/rest/admin/catalog/products/get-product` (exact page, not a subtree). The page digest and passage digest reproduced on a live fetch recorded on 2 November 2026. This proves that one cited passage supports one stated claim. It does **not** prove any other specialist's documentation investigations.
- **S5-011:** resolved by the WDS middleware decision. Not reopened.

## 9. Outstanding technical limitations and future ownership

| Item | Status | Owner |
|---|---|---|
| Original frozen `P001–P055` Shopify human benchmark | Superseded for Sprint 5; outstanding | WDS to commission; AS to label original pairs |
| Replacement dataset approval (G4 file `(1)`) | Not executed; file not located | WDS to confirm the file |
| Real-citation correctness on real retrieval | Not measured by harness; outstanding | Sprint 6 or later evaluation owner, to be named by WDS |
| Feasibility reasoning and practical suitability | Not demonstrated; outstanding | WDS to assign |
| Evidence relevance and documentation coverage for six specialists beyond BigCommerce | Outstanding | WDS to assign |
| Capability-accuracy evidence is over 2 scenarios | Weak; noted | Evaluation owner |
| PG personally attributable QA record | Waived for Sprint 5 only | PG, if WDS requires it later |
| Sprint 6 D-13 independent re-QA on `5974d59` | Separate. Still required | PG or a WDS-named independent reviewer |
| Sprint 6 D-10 register entry for ruling 5 approver | Outstanding | WDS |

## 10. Sprint 6 readiness

- Sprint 5 acceptance under the revised scope removes the Sprint 5 dependency that the Sprint 6 stage record listed as open.
- It does **not** authorize Sprint 6 Step 2 or any integration. Step 2 still requires D-13 (independent re-QA, PG record) and D-10 (register entry).
- No Foundation, AI Engine or specialist branch is merged under this record.

## 11. Commit and push status

This record is written in the worktree at `docs/governance/`. It is **not committed or pushed**, because this directive does not ask for it. Committing needs a separate instruction.
