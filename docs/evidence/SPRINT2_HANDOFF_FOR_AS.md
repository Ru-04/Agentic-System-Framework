# Sprint 2 — handoff for AS (independent human review and QA)

**Prepared 23 October 2026. Commit under review: `b999725` (CI run 39937348393: success, both jobs). Any later commit must be re-reviewed.**

This handoff lists only the actions that require you personally. Nothing has been labelled or signed on your behalf.

## What you are asked to do

1. **Read the material** provided through the approved secure channel (S2-D13). It is the reviewer reading file and the blank label template. Passage text is not in the repository.
2. **Classify each of the 55 pairs independently** as DIRECT, PARTIAL or IRRELEVANT, using the definitions in `docs/evaluation/HUMAN_REVIEW_PROTOCOL.md`. Do not consult any system grade or AI-agent label; none is shown.
3. **Fill the label template:** `label`, `reviewer` (your name), `confidence` (high, medium or low), `uncertain` (yes or no), and an optional `comment`. Leave a row blank only if you deliberately do not label it.
4. **Return the completed template** through the approved channel. The decision-maker will run `python -m webdesk.evidence.evaluation_cli --pairs <pairs> --labels <your-file>`.
5. **Verify the evidence** in `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`, the current commit's test results, and CI run `39937348393` (or a later run for the commit you review).
6. **Record your decision personally** in section 13 of `SPRINT2_EVIDENCE_PACKAGE.md`: your name, role, date, reviewed commit SHA, findings, and recommendation (PASS, FAIL or PASS WITH CONDITIONS). Sign it yourself.

## What the system currently shows (for context only; not a basis for your labels)

- Under the frozen rules, no requirement has reliable DIRECT evidence in the approved corpus. The Shopify specialist produces **no cited capability findings** for the 17 requirements.
- Coverage gaps, retrieval failures (HTTP 403 on Shopify plan pages and help.shopify.com) and the reasons are recorded in `docs/evaluation/SHOPIFY_REAL_INVESTIGATION_2026-10-22.md`.

## What is not your task

- Do not change any threshold or rule; they are frozen (S2-D15).
- Do not treat your review as Milestone 1 acceptance; that needs separate independent milestone testing.

## Secure transfer — exact steps (23 October 2026)

**Status:** the transfer has **not** been made. This environment cannot reach the WDS-approved file-sharing system, so the files below are staged locally for the decision-maker to upload.

**Files to transfer (and only these three):**

- `C:/Users/baps/AppData/Local/Temp/claude/D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1/ba29eeca-4c47-42ca-a887-facf1ad7e2ae/scratchpad/review_package/reviewer_reading_file.md` — the 55 pairs with requirement, source and passage text. Restricted.
- `C:/Users/baps/AppData/Local/Temp/claude/D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1/ba29eeca-4c47-42ca-a887-facf1ad7e2ae/scratchpad/review_package/reviewer_labels_TO_FILL.csv` — the blank label template with the exact importer header.
- `C:/Users/baps/AppData/Local/Temp/claude/D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1/ba29eeca-4c47-42ca-a887-facf1ad7e2ae/scratchpad/review_package/README.txt` — instructions for AS.
- `C:/Users/baps/AppData/Local/Temp/claude/D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1/ba29eeca-4c47-42ca-a887-facf1ad7e2ae/scratchpad/review_package/MANIFEST.sha256` — SHA-256 of the three files above, so AS can confirm the copy is intact.

**Do not transfer:** `C:/Users/baps/AppData/Local/Temp/claude/D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1/ba29eeca-4c47-42ca-a887-facf1ad7e2ae/scratchpad/private_do_not_transfer/pairs_for_cli_PRIVATE.json`. It contains the system's grades and must not reach the reviewer before the independent classification (S2-D21).

**Manual actions required (decision-maker or an authorized WDS file administrator):**

1. Upload the three files to the approved WDS file-sharing system. Restrict access to AS only.
2. Confirm that AS can open and download the files. Confirm the checksums match `MANIFEST.sha256`.
3. Record the upload in this handoff (system name, link or item ID, date, uploader). Do not record a link to passage text in the repository.

**Return path:** AS completes `reviewer_labels_TO_FILL.csv` and returns it through the same approved system. The decision-maker then runs, on the private pair file:

`python -m webdesk.evidence.evaluation_cli --pairs C:/Users/baps/AppData/Local/Temp/claude/D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-specialist-baseline-v1-3b21b1/ba29eeca-4c47-42ca-a887-facf1ad7e2ae/scratchpad/private_do_not_transfer/pairs_for_cli_PRIVATE.json --labels <returned-file>`

## Where each sign-off is recorded (human only)

- **Sprint 2 QA sign-off (AS):** `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md`, section 13, "Sign-off (to be completed only by AS)".
- **Sprint 2 independent human relevance review (AS):** the returned label file, with reviewer name, confidence and uncertainty per pair.
- **Sprint 1 formal human QA sign-off:** `docs/M1_S1_HUMAN_QA_CHECKLIST.md`, section G, "Sign-off (to be completed only by the human QA signatory)". Not signed.
- **Specification approval (authorized reviewer):** `docs/spec-reconciliation/CONSOLIDATED_REVIEW_PACKAGE.md`, section 10, and `docs/governance/SPEC_BASELINE_APPROVAL_RECORD_2026-10-23.md`, section 7 (version binding is still open).

No sign-off in any of these locations has been completed by this system.
