# Sign-off locations and pre-filled fields — 23 October 2026

**Rule for this index:** factual fields (commit SHAs, CI run IDs, document names, names as stated by the approver) are pre-filled. **Signatures, dates, decisions, attestations and the reviewer's own labels are never pre-filled.** Each person completes their own items.

**Reference values (verified in the repository and CI on 23 October 2026):**
- Latest commit: `871c6d6` (decision record Q1–Q11 correction). Latest code commit: `52eb202`.
- CI for `871c6d6`: run `39951048192`, status completed, conclusion **success**. URL: https://github.com/Ru-04/Agentic-System-Framework/actions/runs/39951048192
- CI for `52eb202`: run `39944926908`, success. CI for `54aef28`: run `39940330312`, success.

## 1. Sprint 2 QA sign-off — signed by AS personally

- **Location:** `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`, section 13 ("Sign-off (to be completed only by AS)").
- **Who writes:** Arushi Sharma (AS), personally.
- **Pre-filled (factual):** reviewed commit `871c6d6`; code state `52eb202`; CI run `39951048192` (success).
- **Blank, for AS:** signatory name confirmation, role, date, decision (PASS / FAIL / PASS WITH CONDITIONS), conditions, signature.
- **Blocker:** independence. The repository shows AS as author of the work under review. See `AS_APPROVALS_RECORD_2026-10-23.md`, section 3.

## 2. Sprint 1 human QA sign-off — signed by the human QA signatory

- **Location:** `docs/M1_S1_HUMAN_QA_CHECKLIST.md`, section G ("Sign-off (to be completed only by the human QA signatory)").
- **Who writes:** the human QA signatory. Named by the approver as AS. The same independence blocker applies, because the Sprint 1 implementation commits (`cce425f`, `a9482d2`, `84bc7db`, `5122012`) are also authored by AS.
- **Pre-filled (factual):** Sprint 1 implementation commits listed above; Sprint 1 CI run `39796042409` on `5122012` (success).
- **Blank:** signatory name confirmation, role, date, decision, signature.

## 3. 55-pair human relevance review — completed by the reviewer

- **File to complete:** `reviewer_labels_TO_FILL.csv` (staged locally in the review package; see section 9).
- **Who writes:** the independent reviewer, personally. Each label is the reviewer's own judgement.
- **Pre-filled:** the 55 pair IDs (`P001`–`P055`), the header exactly as the importer requires. Nothing else.
- **Blank:** `label`, `reviewer`, `confidence`, `uncertain`, `comment`. The system does not pre-fill labels, reviewer names or uncertainty.
- **Status:** **0 of 55 returned.**

## 4. Specification version approval — WDS Authorized Approver

- **Location:** `docs/governance/SPEC_BASELINE_APPROVAL_RECORD_2026-10-23.md`, section 7 (Signature fields); `docs/governance/DECISION_RECORD_Q1_Q11_2026-10-23.md` (Signature fields).
- **Who writes:** the WDS Authorized Approver.
- **Pre-filled:** approver name **as stated by you in chat: Arushi Sharma**; role "WDS Authorized Approver"; version binding option "(A)" as selected earlier, with the note that Q1 controls and requires a newly reconciled version.
- **Blank:** signature or approval reference, and the date of the binding decision.
- **Still open:** the reconciled seven-document version (Q1) does not exist yet. Approval cannot bind to it until it is produced, reviewed and hashed.

## 5. Consolidated specification review — authorized independent reviewer

- **Location:** `docs/spec-reconciliation/CONSOLIDATED_REVIEW_PACKAGE.md`, section 8 (findings table), section 9 (corrections), section 10 (approval fields).
- **Who writes:** an authorized independent reviewer, not the authors of the specifications.
- **Pre-filled:** document list and versions (section 1 of the package).
- **Blank:** all findings, corrections, decision and signature. **Not started.**

## 6. WDS management sign-off (already recorded)

- **Location:** `docs/governance/MANAGEMENT_SIGNOFF_SPRINT2_2026-10-23.md`, section 7.
- **Who writes:** the WDS Authorized Approver. Management approval was recorded on 23 October 2026. It is not AS's QA signature.
- **Pre-filled:** approver name "Arushi Sharma" as stated; date 23 October 2026; role.
- **Blank:** signature or approval reference (approver only).

## 7. AS approval statements (recorded as chat approvals)

- **Location:** `docs/governance/AS_APPROVALS_RECORD_2026-10-23.md`, section 6.
- **Who writes:** AS, personally, if she is confirmed eligible.
- **Pre-filled:** full name "Arushi Sharma"; role "Technical Lead and Project Manager".
- **Blank:** date and signature.

## 8. Independence statement (Q2) — AS, in writing

- **Location:** no document exists yet. Create one at `docs/governance/INDEPENDENCE_STATEMENT_AS.md`, or equivalent, and have AS write it.
- **Who writes:** AS, personally. The statement must say whether she authored, directed or materially contributed to the work under review.
- **Blank:** all content. The system will not draft or complete it.
- **Status:** not received. The repository shows AS as commit author for all Sprint 1 and 2 work.

## 9. Secure transfer of the review material — decision-maker or WDS file administrator

- **Location:** `docs/evidence/SPRINT2_HANDOFF_FOR_AS.md` ("Secure transfer — exact steps"), to record the upload.
- **Files to upload (three only):** `reviewer_reading_file.md`, `reviewer_labels_TO_FILL.csv`, `README.txt`. Checksums in `MANIFEST.sha256`.
- **Local folder (this machine):** `C:\Users\baps\AppData\Local\Temp\claude\D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1\ba29eeca-4c47-42ca-a887-facf1ad7e2ae\scratchpad\review_package`
- **Do not upload:** the private grades file, in the sibling folder `…\scratchpad\private_do_not_transfer\pairs_for_cli_PRIVATE.json`.
- **Blank:** upload system name, link or item ID, date, uploader. **The transfer has not been made.**

## Summary of blockers, with owner

1. Independence of AS (Q2): WDS Authorized Approver to decide (a) or (b) in chat.
2. Transfer of the review material: decision-maker or WDS file administrator.
3. 55 labels: independent reviewer.
4. Sprint 2 and Sprint 1 signatures: the people named in sections 1 and 2, after item 1 is resolved.
5. Reconciled seven-document version and its review: system (to produce), authorized reviewer (to review), WDS Authorized Approver (to approve).
