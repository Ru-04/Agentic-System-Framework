# Sprint 2 decision register

**Scope:** decisions on the M1 Sprint 2 evidence and Shopify work. Each entry is effective on the date shown. Earlier records are not reinterpreted or backdated. Approver identity and signature for each entry were **not provided in the record** and are left blank.

## Decisions S2-D07 to S2-D12 (effective 22 October 2026)

| ID | Decision (as approved) | Effect and status | Not authorized |
|---|---|---|---|
| **S2-D07** | Shopify Help Center (`help.shopify.com`): retrieval of official documentation by permitted, compliant access methods. Respect access restrictions. Do not bypass HTTP 403 or anti-bot protection. Use an authorized browser or an officially supported access method where permitted. Capture URLs, dates, provenance and access failures. Report evidence gaps if access stays unavailable. | **Access verified for one page** through the built-in browser (`https://help.shopify.com/en/manual/products`, read 22 Oct 2026). The fetch client still receives HTTP 403. Browser text cannot be written to disk byte-exact by the tooling here, so it is **not ingested** into the evaluated corpus. Access failures are recorded as evidence gaps. | Bypassing 403 responses or anti-bot protection; crawling. |
| **S2-D08** | Add `shopify.com` to the vendor-document allowlist, restricted to official plan, pricing-tier and feature-availability documentation. No unrestricted crawling. | Scoped entries: `/pricing` and `/plus` on `shopify.com` and `www.shopify.com`. The bare domain redirects to `www`, so `www` is covered. **Flagged for decision-maker confirmation.** `/features` is excluded because it redirects into `/pos/features`. Both plan pages returned HTTP 403 to the fetch client, so **no plan document was retrieved**. | Other `shopify.com` paths; crawling. |
| **S2-D09** | Official Canadian government documentation for regulatory and tax-related investigation. Define and validate a restricted allowlist before fetching. Not legal or tax advice. | Two exact pages, validated 22 Oct 2026: the CRA "GST/HST and e-commerce" page (HTTP 200) and bulletin B-090 (HTTP 200). Both retrieved. Findings are regulatory background only and are marked as not legal or tax advice. | Any other `canada.ca` page; crawling. |
| **S2-D10** | Retain DIRECT, PARTIAL and IRRELEVANT. Do not weaken thresholds to improve coverage. Investigate why all 31 passages were PARTIAL. Improve relevance with independently labelled examples. Keyword overlap alone must not establish a capability. | Diagnosis in the evaluation record, section 4. The PARTIAL floor was **tightened** from two terms to three, which is not a weakening. Plural and hyphen folding added. Independent labels came from a separate AI agent, 55 pairs. Agreement is 46 of 55, but the floor was **tuned on those same labels** (record section 5). A finding still needs a topic or option signal in the cited passage. | Weakening thresholds; treating AI-agent labels as human labels. |
| **S2-D11** | AS remains the required independent human QA reviewer. Prepare all evidence and checklists. | Evidence package prepared: `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`. **AS's sign-off is pending.** No sign-off is recorded or implied. | Fabricating AS's signature; marking QA accepted. |
| **S2-D12** | Verify the GitHub Actions workflow for commit `99c4325`. Record run ID, URL, SHA, job results and status. Fix confirmed defects and rerun tests. | Run `39806794237`, `specialist-ci`, commit `99c4325`: **success**. Jobs `lint-type-unit` and `postgres-tests`: success. Verification for the commit that follows this register is pending. | Merging to a protected branch. |

## Earlier Sprint 2 decisions (for reference, not altered)

- 22 Oct 2026 management answers 1–6 (allowlist choice, origin enforcement, proxy policy, live retrieval window, cases, QA signatory). Recorded in `DECISION_RECORD_2026-10-22.md`.
- 22 Oct 2026 decisions 1–6 (live retrieval scope approved for the 16 recorded fetches; relevance; coverage; feasibility; QA package; CI). Recorded in `DECISIONS_SPRINT2_2026-10-22.md`.

## Open approvals that need the decision-maker

1. Confirm that `www.shopify.com` is within S2-D08 (the canonical host of `shopify.com`).
2. Decide whether `help.shopify.com` ingestion may proceed by transcription of browser reads. Transcription is weaker provenance and is not recommended as acceptance evidence.
3. Confirm the three-term PARTIAL floor, now that it is tuned on the 55 agent labels, or provide a held-out label set for validation.

## Approver

- Name, role and signature: **not provided in this record**.
- Effective date: 22 October 2026, as stated in the decision-maker's instruction. This is not a signature.

## Update after independent QA4 (commit fd83e7e)

- S2-D10 figures above (46 of 55; 15 PARTIAL; 3 requirements with findings) are **superseded**. Current figures: 0 DIRECT, 5 PARTIAL, 107 IRRELEVANT; 0 requirements with a cited finding; agreement 44 of 55 with generic words excluded (tuned, not validated). See `docs/evidence/SPRINT2_QA4_RESPONSE.md`.
- New decision needed (QA4-16 and section "What this means" in the QA4 response): how to treat requirements with fewer than three content terms, and whether to authorize human review or a D09 semantic validator for relevance.

## Decisions reported by the decision-maker after the QA4 response (22 October 2026)

| ID | Decision as reported | Effect and limit |
|---|---|---|
| **S2-R1** | Both: human review of the candidate passages, and a semantic validator for relevance. | **Human review:** a review sheet is prepared (`docs/evaluation/HUMAN_REVIEW_SHEET_SPRINT2.md`, 55 pairs). No reviewer has labelled anything yet. Passage text is in a scratch file that the decision-maker must arrange access to. **Semantic validator:** approval in principle only. D09 still requires an approved provider, exact model ID, credentials and usage budget. None of these was provided, so the validator stays **disabled**. |
| **S2-R2** | Handle requirements with too few specific terms on my own. | Implemented: a requirement with fewer than three specific terms gets a clarification request ("restate the requirement with the platform features it involves") rather than a relevance grade. No requirement among the 17 falls below the threshold, so no current result changes. |
| **S2-R3** | `www.shopify.com` is within S2-D08. | Confirmed. The scope on `www.shopify.com` is the same as on `shopify.com`. |
| **S2-R4** | "AS approves." | Reported by the decision-maker. **This is not AS's signed sign-off.** AS's own signed record, stating AS's name, role, date and the commit reviewed, is still required in `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`, section 13. No sign-off has been recorded on AS's behalf. |

## Human review and evaluation tooling (23 October 2026)

- Reviewer package prepared; access to passage text to be arranged by the decision-maker. Nothing labelled. AS is the proposed reviewer; no sign-off recorded.
- Label importer and metrics implemented and tested on synthetic files only. No threshold has been tuned against human labels, and none is held out yet.
- Semantic validator remains disabled (D09). Short-requirement clarification and `www.shopify.com` scope preserved and covered by regression tests.

## Decisions S2-D13 to S2-D17 (authorization date 23 October 2026)

Authorization date: 23 October 2026. These are new decisions. They do not backdate or reinterpret any earlier record. Approver identity and signature were **not provided in this record** and are left blank.

| ID | Decision | Exact scope | Restrictions | Status |
|---|---|---|---|---|
| **S2-D13** | Secure reviewer access: use an existing WDS-approved, access-controlled internal file-sharing method for the 55-pair reading file. | Access for the designated reviewer to the review material only. | Passage text stays outside GitHub. No unnecessary client or confidential information. Access controls and provenance preserved. If no approved method is available, the exact human action is reported. | **Pending human action.** This system has no access to WDS's internal file-sharing method, so the package has not been shared. The decision-maker must upload it through the approved method. |
| **S2-D14** | Independent human review: AS is the designated independent reviewer for all 55 pairs, subject to availability and independence. | 55 pairs listed in `HUMAN_REVIEW_SHEET_SPRINT2.md`. | AS classifies each pair independently. No prefilled labels, no fabricated results, no signing for AS. If AS cannot review, documented authorization is needed before any other reviewer is assigned. | **Pending.** No label has been assigned or recorded. |
| **S2-D15** | Frozen relevance thresholds for this evaluation. | DIRECT: at least 3 specific terms and at least 50% of the requirement's specific terms. PARTIAL: at least 3 specific terms. Platform-generic terms excluded. Retrieval: at least 2 shared terms, candidate limit 20. Clarification floor: 3 specific terms. | Only independently verified defects may be corrected. No threshold may be changed to raise DIRECT coverage. No tuning against the final evaluation data. Future tuning needs separate development labels and an untouched held-out set. Pinned by `tests/unit/test_frozen_thresholds.py`. | **In force.** |
| **S2-D16** | Semantic validator: defer live integration until D09 is separately completed. | D09 needs an approved provider, exact model ID, credentials and budget. | Semantic validator stays disabled. Sprint 2 completes on deterministic relevance only if it is independently validated against the acceptance criteria. | **In force.** Validator disabled (`DisabledSemanticValidator` raises). |
| **S2-D17** | Accelerated Sprint 2 completion: complete all independently executable engineering, testing, documentation and QA preparation now. | Formal closure requires: (1) completed independent human relevance review; (2) satisfactory evidence-validation results; (3) AS's actual signed QA acceptance; (4) successful GitHub CI against the final commit; (5) satisfaction of applicable specification and security acceptance requirements. | No requirement may be marked passed without evidence. No identity details or signatures are manufactured. | **In force.** Formal closure is **not** met (items 1, 2, 3 and 5 are open). |

### Preserved decisions (not changed by S2-D13 to S2-D17)

- Short requirements with fewer than three specific terms require clarification (regression-tested).
- `www.shopify.com` is within the restricted S2-D08 scope (regression-tested).
- No unauthorized external browsing. No live semantic-model call before full D09 approval.
- No production activation. No change to the frozen 4-milestone, 9-sprint plan.

## Decisions S2-D18 to S2-D23 (authorization date 23 October 2026)

Authorization date: 23 October 2026. These are new decisions, not retroactive approvals. Approver identity and signature were **not provided in this record** and are left blank.

| ID | Decision | Exact scope | Restrictions | Status |
|---|---|---|---|---|
| **S2-D18** | Evidence quarantine ordering: eligibility and quarantine checks run before the retriever candidate limit. | `RetrievalQuery.admit` is applied inside the retriever, before ranking and the limit. The specialist builds it with `make_admission`. | Quarantined records must not consume candidate slots. Invalid or restricted records must not displace valid evidence. Source identities and citation references are preserved. Covered by positive, negative, boundary and regression tests. | **Implemented and tested** (`tests/unit/test_s2_remediation.py`). |
| **S2-D19** | Targeted `-es` plural normalization for recall. | Sibilant endings only (`sses`, `shes`, `ches`, `xes`) on words of five or more letters. One canonical form per word. | Thresholds unchanged. No excessive stemming. Recorded limits: "caches" does not match "cache"; "APIs" is not folded. Coverage not increased artificially. | **Implemented and tested.** |
| **S2-D20** | Mandatory workspace filtering before ranking and limiting. | Enforced in `InMemoryRetriever.search` before any scoring; the specialist adds no evidence outside its workspace. | Cross-workspace evidence never appears in unauthorized results and does not consume candidate slots. Any confirmed cross-workspace exposure is acceptance-blocking. | **Implemented and tested.** No exposure found in regression tests. A production retriever must meet the same contract; none exists in this repository. |
| **S2-D21** | Independent human review: AS is the designated reviewer; secure delivery of the 55-pair reading file through an approved WDS-controlled channel. | 55 pairs. AS classifies each pair, records uncertainty and comments, returns the label file, reviews the QA evidence, and signs the QA record. | No fabricated labels, reviewer statements or signatures. | **Pending human action.** This system has no access to the WDS-approved file-sharing method, so the file has not been delivered. See `docs/evidence/SPRINT2_HANDOFF_FOR_AS.md`. |
| **S2-D22** | Consolidated independent review of the seven reconciled specification documents. | Governance, Architecture, Service catalog, Agent registry, Requirement schema, Review policy, Evaluation plan. | Proposed specifications become authoritative only after an authorized reviewer explicitly approves the reviewed version. No automatic approval. | **Review package prepared** (`docs/spec-reconciliation/CONSOLIDATED_REVIEW_PACKAGE.md`). **Review not performed.** |
| **S2-D23** | Accelerated execution: routine Sprint 2 remediation, regression testing, feature-branch commits, GitHub CI and report preparation. | Within the approved Sprint 2 scope only. | No automatic merge. No protected-branch change. No production deployment or activation. No unauthorized model calls. No bypass of human QA or specification gates. | **In force.** |

S2-D15 (frozen thresholds), S2-D16 (semantic validator disabled), S2-D13 and S2-D14 remain in force. Thresholds are unchanged by S2-D18 to S2-D20.

## Specification baseline approval (recorded 23 October 2026, as reported)

- A WDS Authorized Approver's approval on 23 October 2026 of the "reconciled seven-document specification package" and of Sprint 2 engineering progress is recorded as reported. Approver name and signature are not in this environment and are not recorded.
- **Version binding is open.** No revised seven-document set exists in the repository. The seven documents are the unchanged 0.3.10 drafts, whose headers say NOT implementation-approved. The approval is therefore not bound to any specification revision. See `docs/governance/SPEC_BASELINE_APPROVAL_RECORD_2026-10-23.md`, section 4, for the three options the approver must choose between.
- Gate 1 authorization and the 22 October amendment are preserved unchanged.
