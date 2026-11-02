# M3 Sprint 6: Stage 0 baselines and Stage 1 contract gate (2 November 2026)

**Status: Stage 0 and Stage 1 complete. Stage 2 to 6 NOT STARTED.** No approved end-to-end integration contract exists. Dependent integration is blocked, as the directive requires. Sprint 5 is not accepted, so the Sprint 6 dependency is also open.

This record verifies the read-only contract discovery on branch `claude/integration-contract-discovery-cdfe14` (commit `cecb0cc`, base `6c458c8`) against the current refs. Nothing was merged, pushed to a protected branch or implemented.

## Stage 0: baselines (SHAs verified 2 November 2026)

| Line | Branch | Head SHA | Notes |
|---|---|---|---|
| Foundation main | `feature/increment-1-foundation` | `3a38685` | Remote head `740b169` is the origin branch of the same name. Migration head `0041_ai_read_v1` |
| Foundation integration candidate | `feature/foundation-integration-p2-p7` | `5974d59` | Moved one commit past the discovery base (`6c458c8`). Ruling 5 recorded. Migration head `0059_int_mark_inputs_fence` |
| AI Engine line A | `claude/ai-engine-contract-alignment-834e49` (`src/webdesk_ai`) | `967d895` | Built on `3a38685`; its own commits touch no Foundation file |
| AI Engine line B | `feature/ai-engine` (`15d660a`); `integration/ai-s01-s02-s03` (`0389318`, `ai_engine/`) | `15d660a`, `0389318` | Not an ancestor of the candidate. Separate lineage |
| Specialists | `claude/sprint5-specialist-evaluations` | `027f352` | Sprint 5 branch, not accepted. Remote head `027f352` |
| Specialist baseline (named) | `claude/webdesk-specialist-baseline-v1-3b21b1` | `db9e785` | Historical baseline |

Other refs found: Foundation phase branches `feature/foundation-phase-2` to `-9` (migration heads `0046` to `0049` and others); specialist lanes at `5122012`; several `qa-*` detached worktrees. None of these is an approved integration baseline.

**Identifier conventions:** the two AI Engine lines use different package roots (`webdesk_ai` and `ai_engine`). Both are preserved by ARCH-03 until a functional-parity record and an approved migration decision. Neither has been merged, and no third engine was created.

**CI on these heads:** `027f352` is documentation only on top of `b885ad7`, which passed (`lint-type-unit` and `postgres-tests`, run 41423137005). The Foundation candidate's CI was not inspected in this record.

## Stage 1: contract classification

| # | Contract | Classification | Basis |
|---|---|---|---|
| C1 | `ai-read/v1` (Foundation to AI Engine, read endpoints) | **APPROVED** for read-only, non-production use | Self-declared in the contract and cited by ruling P-INC3-AI-SCAN-07. Approver, date and channel for D-AI-1 to D-AI-5 are **not recorded** |
| C2 | Specialist adapter (v0.1 ARCH-02; v0.2 INT-01) | **APPROVED** for isolated development and conformance tests only | Chat approval, recorded as reported. The proposal file still says "proposal only". Production excluded |
| C3 | Foundation Phase 2–7 integration record | **Engineering record, not a contract** | QA passed on `32c98f6`, not on the current tip. Ruling 5 applied after QA. Conflicting acceptance record for Phases 3 and 6 on `feature/foundation-phase-9` |
| C4 | Phase 1 R4 Option A (actor and session) | **NORMATIVE**, WDS-approved for the Foundation actor boundary | Not an AI or specialist identity contract |
| C5 | Specialist routing contract | **MISSING** (deferred to Sprint 6, not approved) | No routing text exists |
| C6 | Evidence and citation persistence | **MISSING** (a gap in v1) | No evidence, requirement or citation tables on any branch |
| C7 | Specification package | **Mixed. Not an integration contract** | Headers say "NOT implementation-approved" |
| C8 | Interface preparation document | **Preparation only** | Superseded in part by C2 |
| C9 | Whole-system contract (Foundation, AI Engine, seven specialists) | **MISSING** | No such document exists. Production readiness requires an explicit WDS production approval, which has not been given |

**Contradictions:** the adapter proposal (`ADAPTER_CONTRACT_PROPOSAL_2026-10-26.md`) says "proposal only", and the ADR approves "as proposed in" it. The Foundation Phase 9 acceptance record conflicts with the candidate's record for Phases 3 and 6.

## Consequence

Per the directive, dependent integration (Stage 2 onward) does not start. The following are **not** permitted now:
- Foundation to AI Engine integration beyond the approved read-only scope.
- Any specialist connection to Foundation or to the candidate.
- Operator-confirmed routing, requirement-to-specialist execution, evidence persistence and AI synthesis.
- Cross-team merges, protected-branch merges, production activation.

Stage 4 (independent QA) and Stage 5 (integration candidate) cannot start without an approved candidate. Stage 6 (acceptance) is blocked by Sprint 5 and by the open contract decisions.

## Consolidated WDS approval request (decisions D-1 to D-15)

The discovery branch lists these decisions in `docs/integration-contract/09-contract-approval-request.md`. The verified state is unchanged, except that the candidate tip has moved to `5974d59`, so D-13 now requires re-QA on that tip. The recommended choice for each is listed.

| ID | Decision | Recommendation | Blocks |
|---|---|---|---|
| D-1 | Record approver, date and channel for `ai-read/v1` (D-AI-1 to D-AI-5) | Approve as recorded, with those details added | Foundation to AI read (step 2) |
| D-2 | Next step: component-pair only, or end-to-end contract first | Component-pair for steps 2 to 4; end-to-end before any specialist connects | Step 2 onward |
| D-3 | Authoritative specialist adapter document | v0.2 as implemented, proposal superseded, for isolated tests only | Step 6 |
| D-4 | AI Engine target line | Line A (`967d895`) for step 2; line B waits for a parity record | Step 2 |
| D-5 | Specialist routing deferred; operator confirmation only from WebDesk's proof path | Approve both | Routing |
| D-6 | Specialist identity: no Foundation credential; actor derived from session proof | Approve both | Step 6 |
| D-7 | Evidence vocabulary mapping; evidence persistence out of scope for the next steps | (2) yes; (1) mapping later | Evidence |
| D-8 | Migration freeze at `0059`; `0027` of the specialist branch not merged; new revisions need approval | Approve all three | Any schema change |
| D-9 | Accept declaration-only specialist authority (QA-07) for isolated conformance tests only | Accept for conformance only | Step 6 |
| D-10 | Ruling 5 confirmed with approver, date and channel, or reverted | Confirm, then re-QA | Step 2 |
| D-11 | Security findings F-2 (search_path) and F-7 (outbox `now()`) | Accept F-2 for non-production with tracking; fix F-7 before outbox work | Production and outbox |
| D-12 | Authoritative record for Phase 3 and Phase 6 acceptance | Candidate record until `356fb3c`'s directive is evidenced | Step 2 |
| D-13 | Merge sequence and re-QA of the candidate on its current tip | Approve | Step 2 |
| D-14 | `runs/jobs.py` lease API and test T7 | Approve, with T7 required | Foundation change |
| D-15 | Phase 8 and 9 documentation branches | Exclude; treat separately | Integration scope |

**The directive asks for one request.** Reply "approve as recommended" for all, or give individual IDs. Nothing dependent starts until D-1, D-2, D-3, D-4, D-8, D-10, D-12 and D-13 are settled for the first step.

## Sprint 5 dependency

Sprint 5 is not accepted (see `SPRINT5_CLOSURE_DETERMINATION_2026-11-02.md`). Sprint 6 cannot be accepted on top of an unaccepted Sprint 5 specialist line. Gate 4 (AS labels) and gate 7 (PG review) remain open.

## Independent QA and merge

Not started. There is no integration candidate that has been approved for QA, and no merge is authorized.

## WDS decision recorded (2 November 2026): "Approve as recommended"

All of D-1 to D-15 are approved as recommended in the discovery request. The recorded choices are:

| ID | Recorded choice |
|---|---|
| D-1 | `ai-read/v1` approved as recorded; approver, date and channel to be added to `GOVERNANCE_DECISION_REGISTER.md` by WDS |
| D-2 | Component-pair integration for steps 2 to 4 (Foundation with AI Engine, read-only, non-production). An end-to-end contract is required before any specialist connects (step 6) |
| D-3 | Specialist adapter v0.2 as implemented, for isolated development and conformance only. `ADAPTER_CONTRACT_PROPOSAL_2026-10-26.md` marked superseded |
| D-4 | AI Engine target line A (`claude/ai-engine-contract-alignment-834e49` at `967d895`) for step 2. Line B waits for a parity record |
| D-5 | Specialist routing deferred. `operator_confirmed` only from WebDesk's proof path, never from the caller |
| D-6 | Specialists hold no Foundation credential and no AI principal. `actor_id` derived from authenticated session proof |
| D-7 | Evidence persistence out of scope for the next steps. Mapping between evidence vocabularies deferred |
| D-8 | Migrations `0001`–`0059` frozen. Specialist `0027_proof_gated_token_issuance` not merged. Future schema changes need their own approval |
| D-9 | Declaration-only specialist authority accepted for isolated conformance tests only. No live specialist execution |
| D-10 | Ruling 5 confirmed. Re-QA on the current candidate tip is required (see D-13) |
| D-11 | F-2 (search_path) accepted for non-production with a tracking item, fix before production. F-7 (outbox `now()`) fixed before any outbox integration |
| D-12 | Candidate record governs Phase 3 and Phase 6 acceptance until the directive in `feature/foundation-phase-9` commit `356fb3c` is evidenced |
| D-13 | Merge sequence approved. Candidate re-QA on its current tip (`5974d59`) is a gate before step 2 |
| D-14 | `runs/jobs.py` lease API approved as the single contract, with test T7 required before any Foundation change |
| D-15 | Phase 8 and Phase 9 documentation branches excluded from integration and handled separately |

## Gates now open before step 2

1. **D-13 re-QA on `5974d59`.** This requires an independent reviewer. PG has declined to send evidence, so the only available route is a WDS-named reviewer with a personally attributable record, or a WDS management waiver recorded as such.
2. **D-10 ruling 5 record.** Add the approver, date and channel to `FOUNDATION_INTEGRATION_P2_P7.md`.
3. **D-1 approver details** added to the governance decision register.

Step 2 engineering (Foundation read endpoints with the AI Engine line A client, PostgreSQL integration tests) has not started. It needs an isolated integration branch created from `5974d59`. No other team's branch or worktree is modified.

No merge, protected-branch change or production activation is authorized by these decisions.
