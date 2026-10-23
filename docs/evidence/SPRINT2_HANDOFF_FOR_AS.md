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
