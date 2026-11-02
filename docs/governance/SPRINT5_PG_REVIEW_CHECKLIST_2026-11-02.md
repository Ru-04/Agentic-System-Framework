# M2 Sprint 5: PG review checklist and result form (2 November 2026)

Prepared by the development team. PG is not asked to author a package. PG reads the code and tests, then completes section 3 personally. **Nothing below is PG's statement.** Until PG completes section 3, the status is **READY — DELIVERY PENDING**.

## 1. Code identity (fill from git at the time of delivery)

| Item | Value |
|---|---|
| Branch | `claude/sprint5-specialist-evaluations` |
| Reviewed SHA | **[final SHA, to be recorded by the team at delivery]** |
| Predecessors in scope | `dc1dda7` (threshold approval record); `ed8c714` (dataset v4 and scorecard); activation and policy commits from 2 November 2026 |
| CI for the reviewed SHA | **[to be recorded]** |

## 2. Review checklist for PG (check the code, not the summary)

Each item names the file to check.

1. **Redirect policy.** A request to follow a redirect is refused before any capability match. `src/webdesk/investigation/specialists.py` (`PROHIBITED_OPERATIONS`, `decide`). A fetched redirect leaving the boundary is refused. `src/webdesk/investigation/retrieval.py`, `engine.py`.
2. **Unapproved capability.** A named capability with no approved source (order data) returns UNSUPPORTED_SOURCE, not CLARIFY. `specialists.py` (`UNAPPROVED_CAPABILITIES`).
3. **Evidence policy (Decision 3).** Headings, titles and navigation are never passages. Passages come from prose blocks of at least four words, and from code and API specification blocks. `retrieval.py` (`_SubstantiveExtractor`, `_MIN_PROSE_WORDS`, `_NON_BODY_TAGS`). Tests: `tests/unit/test_sprint5_activation.py`.
4. **Activation.** Only the boundaries in `engine.py` `ACTIVE_BOUNDARIES` are active: WooCommerce, BigCommerce, Adobe Commerce exact pages, Magento release notes. Shopify and Adobe shared PHP are not. `docs/specialists/knowledge/sources.json` agrees with the engine (`test_specialist_documentation.py`).
5. **Shopify restricted policy (Decision 2).** No whole-host authority in `allowlist.py` (`SPRINT2_ALLOWLIST`, `PROPOSED_SHOPIFY_ALLOWLIST`) or `engine.py` (`SHOPIFY_INACTIVE`). Only the S2-D08 plan pages and the CRA pages are scoped.
6. **Middleware (Decision 1).** Webhook retry, error recovery, idempotency and synchronisation are recognised. The evidence outcome stays UNSUPPORTED_SOURCE. The missing context is a clarification. No product is hardcoded. `specialists.py` (`MIDDLEWARE_CONTEXT_NOTE`), `docs/specialists/knowledge/middleware_applications.json`.
7. **Runner.** Activity is per capability boundary. An Adobe-only capability requested for Open Source is not applicable (ADOBE-01). `src/webdesk/evaluation/runner.py`.
8. **Frozen datasets.** Each dataset matches its manifest. v1 to v3 expectations unchanged. v4 to v6 changes are listed in their manifests. `tests/unit/test_sprint5_harness.py`.
9. **Scorecard.** Requirement-level only. Citation correctness on real retrieval is reported as not measured. Shopify relevance is THRESHOLD PENDING. `src/webdesk/evaluation/scorecard.py`.
10. **Real evidence.** The record is `docs/governance/SPRINT5_REAL_EVIDENCE_2026-11-02.json`. Under the current policy the BigCommerce verified citation is withdrawn (its endpoint line sits in a script payload). Confirm the record says so.

## 3. PG result (to be completed only by PG)

| Field | Entry |
|---|---|
| PG name | _Not provided_ |
| Role and authority for this review | _Not provided_ |
| Independence declaration (PG's own words) | _Not provided_ |
| Reviewed SHA | _Not provided_ |
| Scope reviewed (which items in section 2) | _Not provided_ |
| Method (what PG ran or read) | _Not provided_ |
| Findings (defects, with file and line) | _Not provided_ |
| Decision: PASS, PASS WITH CONDITIONS, or FAIL | _Not provided_ |
| Date and signature | _Not provided_ |

## 4. Management-reported feedback

None has been received in this conversation. Any verbal feedback from PG is recorded as **management-reported only** until traceable written evidence exists. It does not count as a PG review.

## 5. Status

**READY — DELIVERY PENDING.** The team cannot deliver to PG: no PG channel is confirmed, and PG's independence for this scope is not established.
