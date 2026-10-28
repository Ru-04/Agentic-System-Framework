# Sprint 4 QA package update: real-evidence pilot (28 October 2026)

Supplements `SPRINT4_INDEPENDENT_QA_PACKAGE_2026-10-28.md`. Reviewer: PG, appointed as Sprint 4 QA reviewer.

## Commits to review
- Original engineering baseline: `58d1a39` (CI run #36, SUCCESS).
- Documentation package: `492e52e` (CI run #42, SUCCESS).
- Retrieval provenance: `93df9d9` (CI run #43, SUCCESS).
- Ownership verification: `5c21a09` (documentation only).
- Pilot activation and tests: `8c65b88` (CI run #45, SUCCESS).
- Decision S4-PILOT-EVIDENCE-01 implementation: the commit that records this update. Its CI result is recorded only against its own SHA.

## What PG should check
1. Only two boundaries are active: WooCommerce docs and the BigCommerce product page (`ACTIVE_BOUNDARIES`).
2. BigCommerce statements are scoped to single-product retrieval; the other operations are partial or unknown (`COVERAGE`).
3. WooCommerce: no version inferred; no variation-pricing claim without one sentence containing both terms; not-found responses excluded.
4. Citation locators are passage digests.
5. Pilot results: `docs/governance/SOURCE_PILOT_RESULTS_2026-10-28.json`.
6. Coverage report: `docs/specialists/REAL_EVIDENCE_COVERAGE_2026-10-28.md`.

## Reviewer record (PG to complete personally; not filled in by engineering)
- Independence declaration: PENDING (PG).
- Findings and severity: PENDING (PG).
- QA decision (PASS / PASS WITH CONDITIONS / FAIL / BLOCKED): PENDING (PG).
- Attestation: PENDING (PG).

WDS management's reported PASS (S4-QA-01) is not PG's review. It stays distinct from PG's personal evidence, which is not in the repository.
