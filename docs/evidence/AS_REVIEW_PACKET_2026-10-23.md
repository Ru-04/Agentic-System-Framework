# Review packet for AS — M1 Sprint 2 (and Sprint 1 human QA)

**Prepared:** 23 October 2026. **Commit reviewed:** `f5ad091` (code state `52eb202`; CI run `39944926908` success on `52eb202`).
**Purpose:** give AS everything needed to review, answer the open questions, and sign the QA records. **Nothing in this packet is signed or answered on AS's behalf.**

## A. Decisions already recorded (for reference)

- WDS management sign-off of the QA review and Sprint 2 progress, 23 October 2026 (`docs/governance/MANAGEMENT_SIGNOFF_SPRINT2_2026-10-23.md`). This is **not** AS's QA sign-off.
- Specification version binding: option **(A)** selected in the decision-maker's reply of 23 October 2026. Recorded in `docs/governance/BLOCKER_RESPONSES_2026-10-23.md`. The approver's identity and signature are still needed.

## B. What AS must do

1. **Read the human review material** through the approved WDS channel (see section F). Passage text must not be stored in GitHub.
2. **Classify the 55 pairs** as DIRECT, PARTIAL or IRRELEVANT, using `docs/evaluation/HUMAN_REVIEW_PROTOCOL.md`. Do not consult any system grade.
3. **Answer the open questions in section C**, in chat, with your decision. My suggestions are shown beside each question. They are suggestions only.
4. **Review the Sprint 2 evidence** (`docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`) and the QA records (`docs/evidence/QA4_INDEPENDENT_REVIEW_RECORD.md`, `docs/M1_S2_COMPLETION_REPORT.md` section 11).
5. **Sign the Sprint 2 QA record** personally: `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`, section 13.
6. **Sign the Sprint 1 human QA checklist** personally: `docs/M1_S1_HUMAN_QA_CHECKLIST.md`, section G. Your signature there is the Sprint 1 human QA sign-off.

## C. Open questions — AS decides, with suggestions

| # | Question | My suggestion | AS decision |
|---|---|---|---|
| Q1 | Specification binding (option A): the seven 0.3.10 drafts, approved only with an explicit exception to their "NOT implementation-approved" headers. Accept A? | **Accept A, limited to non-production development.** The exception should name CR-01 (readiness wording) and CR-08 (operator confirmation before execution) as open. No production use until the reviewed text is re-hashed. | |
| Q2 | Human review of the 55 pairs: will you perform it, or name another independent reviewer? | You perform it. If you cannot, name the reviewer and record the authorization before any other person labels. | |
| Q3 | Shift4Shop identity: keep `CAP-3D-CART-SHIFT-SHOPIFY` as the legacy alias, and the canonical name "Shift4Shop (formerly 3dcart)"? | **Yes**, as already recorded (D06). Propose a new canonical identifier (for example `CAP-SHIFT4SHOP`) as a separate, later migration. | |
| Q4 | Lexical relevance grades: accept that Shopify capability cannot be shown by keyword matching alone, so Sprint 2 acceptance depends on your human review? | **Yes.** Treat the system grades as a method, not as evidence. Acceptance needs your labels. | |
| Q5 | Shopify plan pages (`shopify.com/pricing`, `/plus`) returned HTTP 403. Accept as an evidence gap, or authorize a specific approved access method? | **Accept as a gap** for Sprint 2. Plan-tier claims stay unverified and are reported as clarification questions. | |
| Q6 | `help.shopify.com`: one page was readable through the approved browser. Accept browser-captured text with provenance, or keep it out of evidence? | **Keep it out of evidence** for Sprint 2. Transcription is weak provenance. Revisit only with a proper capture method. | |
| Q7 | QA-07 (specialist authority declared, not enforced at run time): keep deferred to M3 S6? | **Keep deferred**, and make run-time enforcement a hard gate before any integration. | |
| Q8 | Production retriever: require the contract check (`tests/unit/test_retriever_contract.py`) before any production use? | **Yes.** No production retriever is built in Sprint 2. | |
| Q9 | Canadian tax sources (CRA e-commerce page and B-090): accept as regulatory background, marked "not legal or tax advice"? | **Yes**, with that marking kept in every output that cites them. | |
| Q10 | `www.shopify.com` within the S2-D08 scope (decision-maker confirmed): confirm? | **Confirm**, as already recorded. | |
| Q11 | Short requirements (fewer than three specific terms): accept the clarification-request handling? | **Yes.** None of the 17 requirements is affected. | |

## D. Evidence index

- Remediation: QA4-06, QA4-08, QA4-15 closure, `docs/evidence/SPRINT2_QA_CLOSURE_QA4.md`.
- QA reviews and dispositions: `docs/evidence/QA4_INDEPENDENT_REVIEW_RECORD.md`; QA3 in `docs/M1_S2_COMPLETION_REPORT.md`, section 11.
- Automated tests: 437 unit tests passing at `52eb202`. Ruff, format and strict mypy clean. Integration and hardening suites: run in CI job `postgres-tests`, green on `52eb202`.
- Shopify investigation across 17 requirements: `docs/evaluation/SHOPIFY_REAL_INVESTIGATION_2026-10-22.md`. Current result: 0 DIRECT, 5 PARTIAL, 111 IRRELEVANT passages; **0 requirements with a cited capability finding.**
- Specification review package: `docs/spec-reconciliation/CONSOLIDATED_REVIEW_PACKAGE.md`; hashes in `docs/governance/SPEC_BASELINE_APPROVAL_RECORD_2026-10-23.md`.
- Transfer material and manifest: `docs/evidence/SPRINT2_HANDOFF_FOR_AS.md`.

## E. What the current evidence shows (for your judgement)

- The engineering controls work: workspace isolation, quarantine ordering and citation integrity are tested.
- The Shopify capability question is **not answered** by the evidence. No requirement has reliable DIRECT evidence in the approved sources.
- The reasons, in order: the corpus does not cover most requirements (42 of 140 requirement terms never appear in it); keyword matching is limited; plan pages and help-centre pages are blocked.

## F. Human handoff (external action)

- The three transfer files are staged locally: `reviewer_reading_file.md`, `reviewer_labels_TO_FILL.csv`, `README.txt`, with `MANIFEST.sha256`. Folder: the scratchpad `review_package` folder for this session.
- **The transfer has not been made.** The decision-maker must upload the three files to the approved WDS file-sharing system, restricted to AS, and confirm the checksums.
- The private file `pairs_for_cli_PRIVATE.json` (system grades) **must not be transferred**.

## G. Status

- Sprint 2: **BLOCKED — HUMAN OR EXTERNAL ACTION REQUIRED.** Open: human labels (0 of 55), AS QA signature, Q1 to Q11 answers.
- Sprint 1: formal human QA sign-off **not yet signed**.
- Milestone 1: not closed. Independent Milestone 1 testing not started. M2 Sprint 3 not started.

## H. Sign-off fields (AS only)

- AS full name: ______________________
- Role: ______________________
- Date: ______________________
- Reviewed commit: ______________________
- Sprint 2 QA decision: [ ] ACCEPT  [ ] ACCEPT WITH CONDITIONS  [ ] REJECT
- Signature: **to be completed by AS only**
