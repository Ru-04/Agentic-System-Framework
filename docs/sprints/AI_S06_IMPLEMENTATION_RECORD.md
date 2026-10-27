# AI-S06 Implementation Record (offline, isolated)

Status: **AI-S06 Offline Engineering: APPROVED / CLOSED** (WDS Project Owner, isolated development only). **AI-S06 Live Foundation-Authorized Execution: PENDING.** Not production-security certification and not full functional acceptance.

## Components (new package `ai_engine/src/ai_engine/orchestration/`)
- `registry_map.py`: identity map for the seven registered categories (capability, platform, collection,
  relevance, agent factory, evidence factory). Fails closed for unregistered IDs.
- `contracts.py`: `RecommendationProposal` (no execution authority, `authorises_execution` is always False),
  `OperatorConfirmation` (human, bound to actor, project, run, proposal; single use), audit events.
- `recommender.py`: proposes categories from requirements. Verifies every category against the registry.
  Refuses missing, duplicate or foreign-project requirement IDs.
- `gate.py`: confirmation gate. Refuses mock on the production path, non-human actors, proposer
  self-confirmation, transfer to another actor, binding mismatch, unproposed categories, expiry, and replay
  (ID or nonce reuse). A refused attempt consumes nothing.
- `workflow.py`: plain state machine: PROPOSED, then CONFIRMED (human-verified), then COMPLETED, PARTIAL or
  FAILED. Per-category execution through the AI-2 wrapper; bounded retry on transient failure; partial failure
  kept visible; correlation by requirement ID; overlaps reported; audit log.

## Orchestration flow
propose (recommend, no authority) → confirm (gate verifies operator binding; mock only in tests) → execute
(only in CONFIRMED; the same actor; each category gets its own requirements and its own collection if
authorised) → correlate → terminal state.

## Decisions and deviations
- LangGraph was **not** used. It is not installed or declared in `pyproject.toml`. Adding it changes
  dependencies and needs a separate decision. The state machine keeps the same node boundaries.
- Routing uses explicit platform naming for the five commerce categories. Their own relevance tests are broad
  (written for operator-selected runs) and would route every customer sentence to all five.
- Mock confirmation exists in offline tests only. It is not a Foundation-authenticated approval.
- Shift4Shop: legacy `CAP-3D-CART-SHIFT-SHOPIFY` only. Canonical `CAP-SHIFT4SHOP` is never recommended or
  accepted; it is not in the registry.

## Tests
`tests/test_ai_s06_orchestration.py`: 42 tests covering the section 6 requirements (no execution before
confirmation, recommendation is not authorisation, transfer, binding, proposer and system refusal, mock
refusal, expiry, replay, duplicate, unproposed categories, unregistered IDs, Shift4Shop legacy behaviour,
requirement-ID refusal, collection and project isolation, per-specialist evidence, partial failure visibility,
unverified claims, audit, and a seven-category end-to-end run).

Mutation checks (scratch copies): removing the actor-kind check, the ledger consume, the proposer check, the
partial-failure state logic, the collection authorisation, the routing test, or the confirmation state check
each makes at least one AI-S06 test fail.

## Seven-category synthetic integration (single run)
Run state COMPLETED. Each category: execution SUCCEEDED, specialist status COMPLETED, capability as registered
(Shift4Shop as the legacy identifier). Evidence counts per category: Shopify 3, WooCommerce 2, BigCommerce 3,
Shift4Shop 1, Magento 0, Standalone 2, Middleware 3. No overlaps for the seven requirements.

Observation (not changed): the AI-S04 Magento specialist returns COMPLETED with zero cited evidence for its
requirement. AI-S04 is an accepted engineering contract; the orchestrator passes its output through unchanged.
Raise for WDS decision if AI-S06 should report such a result as PARTIAL.

## Gate
pytest 1509 passed, 3 skipped (Foundation-environment tests); AI-S06 58 passed; ruff check and format clean;
strict mypy clean across 131 files.

## Remaining dependencies
Foundation: authenticated operator identity, session validation, approval persistence, durable run state,
audit persistence, requirement and collection reads (see `AI_FOUNDATION_READ_CONTRACT_AND_READINESS`).
Governance: structured routing policy (C-05), confirmer role (DEC-05), Shift4Shop registry migration
(D-01, D-15), LangGraph dependency decision.


## First independent QA and remediation

Findings and fixes (all in the AI-S06 package and its tests):
- B-1 (blocker): replay protection was per instance (a default private ledger). Fixed: the ledger is a required
  constructor argument with no default. It is still in memory; durable replay protection belongs to Foundation.
  Tests: a missing ledger is refused at construction; two orchestrators sharing one ledger refuse a replay.
- M-3: the mock allowance was a per-call flag. Fixed: it is set at construction (allow_mock_confirmations,
  default False). Production code must leave it False. Tests: refusal on an orchestrator built without it.
- M-4: execute-time refusals were not audited. Fixed: execution_refused events are recorded with the reason.
- M-5: an unexpected error left the run CONFIRMED, so it could be re-run. Fixed: an aborted run is FAILED
  (terminal) and records run_aborted. A specialist exception becomes a visible category failure
  (FAILED_VALIDATION, refusal "specialist raised <class name>"); the other categories still run.
  max_attempts below 1 is refused.
- m-1: recommend() has a test for its own registry verification. m-2: confirm after completion is refused and tested.
- m-3, m-4: routing tightened. "WordPress" alone no longer routes to WooCommerce; a commerce term must be nearby.
  "Big-Commerce" and "Big Commerce" route. The misspelling "Magneto" is not accepted.
- m-7: requirement IDs must match the REQ- pattern. m-8: a tautological test was removed.
- n-1: authorises_execution is now a read-only property that always returns False.
- n-3: file count corrected (131).

Residual risks for WDS decision (not fixed here):
- R-1 (QA M-1): run_specialist (AI-2, accepted contract) is public and can run any agent without an orchestrator
  or confirmation. AI-S06 cannot gate it without changing AI-2. Options: gate it in AI-2 (needs authorisation), or
  accept it as a residual risk and restrict callers by review.
- R-2 (QA M-2): OperatorConfirmation is an unsigned in-process record. The gate checks shape and binding, not
  authenticity. Real authorisation needs Foundation-issued, verifiable operator proof. Until then the gate is not a
  security control on its own.
- R-3 (QA m-5): the AI-S04 Magento specialist returns COMPLETED with zero cited evidence; the run reports COMPLETED.
  This is passed through unchanged.
- R-4: orchestration state is in memory. It is not durable run state.


## Focused re-verification and minor items

- Focused verification of the remediation: PASS. Ledger required and shared; mock allowance construction-time;
  execution refusals audited; aborted run terminal; specialist exceptions contained; ID format; authorises_execution
  read-only; nine guard mutations all caught.
- Minor fixed: a specialist exception after an earlier transient status is now a visible failure (test added).
- Minor fixed: a second execute after a run has ended is refused with "this run has already ended".
- Minor open (accepted routing limit): the WooCommerce routing window (40 characters after "WordPress") can still
  route a WordPress non-commerce sentence that mentions a shop. Pattern-based matching; the specialist's own
  refusal and the operator confirmation remain the controls.
- Minor noted: the middleware application relevance adds the middleware category to some ERP and sync sentences
  that also name a commerce platform. This is overlap by design.


## WDS formal acceptance record

Accepted (offline engineering, isolated development): structured specialist recommendations; operator-confirmation
workflow simulation; multi-specialist coordination; run state and lifecycle handling; specialist error and failure
visibility; requirement and project binding; specialist selection integrity; offline seven-specialist integration
tests; evidence and result traceability.

Not accepted: the three skipped Foundation-environment tests (not counted as passed); live execution; production security.

Mock confirmation: an offline test device only. A mock confirmation is not a Foundation-authenticated approval and is
refused unless the orchestrator is constructed with allow_mock_confirmations=True. Production code must not set it.

Unimplemented Foundation-issued operator authority: the operator's identity, permissions, and the authoritative
confirmation decision are issued and checked by Foundation, not by this package. Until then no live execution is
possible through this package.

R-1 (direct-execution integration blocker, open): run_specialist (AI-2) is unchanged and remains callable for trusted
isolated code and tests. Direct execution without an authoritative, confirmed selection is prohibited in any live
integrated workflow. Before runtime activation: identify every callable execution entry point; prevent external
callers from bypassing the confirmed orchestration path; establish a Foundation-controlled execution-authority
boundary; verify operator authentication and project/run authorisation; bind the approved selection to the actual
requirements and specialist identities; reject expired, revoked, reused or mismatched authorisation; test bypass
attempts independently. Do not expose unrestricted run_specialist through a live API. Any production-facing change
to the accepted AI-2 contract needs a separately reviewed integration change.

R-2 (confirmation-authenticity integration blocker, open): OperatorConfirmation is an unsigned in-process record,
accepted for offline synthetic testing only. It is not proof of an operator's identity or authority. Before live
execution, Foundation must authenticate the operator, enforce permissions, issue or validate the authoritative
confirmation, bind it to project, run, selected specialists, requirement revisions and lifecycle state, revalidate
authorisation at execution, fail closed on denied, expired, stale and replayed confirmations, and audit approval and
execution events. No AI-owned authentication authority will be implemented.

Accepted routing limitation: the WooCommerce pattern-matching ambiguity (a WordPress sentence that mentions a shop may
produce an incorrect recommendation) is accepted for isolated development only. Recommendations are proposals and
never authorise execution. Controls that must remain: an authorised operator confirms selection; the selected
specialist validates its task and refuses unsupported requests; unsupported or ambiguous routing stays visible.
Deterministic pattern matching is not complete semantic routing.

Final test results at acceptance: pytest 1509 passed, 3 skipped (Foundation-environment tests); AI-S06 58 passed;
ruff check and format clean; strict mypy clean across 131 files.

Local completion commit: recorded in the commit message and in the handoff note AI_S07_HANDOFF_FROM_AI_S06.md.

Historical QA dispositions are kept above (first QA, focused verification, minor items).
