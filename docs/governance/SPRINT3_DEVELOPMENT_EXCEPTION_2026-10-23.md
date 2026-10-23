# Development-progression exception — M2 Sprint 3 (effective 23 October 2026)

**Granted by:** WDS Authorized Approver (recorded as reported in chat, 23 October 2026). Approver name as provided: Arushi Sharma. Signature: not on file in this repository.

**Nature:** a new, limited exception to the frozen dependency that M2 begins only after Milestone 1 acceptance. It is a **development-progression** exception. It is **not** a declaration that Milestone 1 passed.

## Authorized scope
- Isolated, non-production implementation of the foundations of the six remaining specialists: Shift4Shop (formerly 3dcart), WordPress & WooCommerce, BigCommerce, Magento / Adobe Commerce, Standalone Applications, Middleware Applications.
- Use of the existing shared specialist contracts, harness, authority and evidence services. No change to them.
- Tests and representative FIXTURE evaluation data, labelled as fixtures.

## Restrictions
- No approved evidence source is configured for any Sprint 3 platform. No retrieval against any platform is authorized by this exception.
- No production activation, no protected integration, no deployment, no merge to protected branches.
- No live model calls (D09). Synthetic and fixture output is never presented as a real platform investigation (D11).
- No change to the frozen four-milestone, nine-sprint scope or sequence.
- No change to shared authority, database security or common contracts from within a specialist.

## Unresolved dependencies (not closed by this exception)
- Milestone 1 formal acceptance (Sprint 1 and Sprint 2 independent QA, human relevance evidence, specification version binding, final CI, independent Milestone 1 testing). See `MILESTONE1_ACCEPTANCE_TRACKER_2026-10-23.md`.
- QA-07 runtime authority enforcement: mandatory before applicable orchestrator execution and protected integration (Q7).
- Approved evidence sources per platform (D08): none approved for Sprint 3.

## Effect on existing records
- Preserves all prior approvals and decisions, including commit `6d480d0` and the Q1–Q11 record. This exception does not alter them.
