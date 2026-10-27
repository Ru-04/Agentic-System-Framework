# AI-S06 Sprint Specification: Orchestration and Human-Confirmed Routing

**WDS-APPROVED SCOPE BASELINE — IMPLEMENTATION AUTHORIZED** (contract-first, offline)

Authority: WDS Project Owner master directive (26 October 2026). Parent: `AI_S05_S10_MASTER_SPRINT_PLAN.md`.

Runtime activation is **not** authorised by this label. It needs Foundation-authenticated actor identity,
project permissions, authorised selection records and an approved structured routing policy. Those are
PENDING (section 11).

## 1. Purpose and approved functional scope

Coordinate specialist work inside one project:

- LangGraph-based workflow coordination (offline, with mock confirmation).
- Requirement-driven specialist recommendations.
- Structured specialist selection proposals.
- Mandatory authorised operator confirmation before any execution.
- Multiple specialist execution within a project.
- Run lifecycle and retry behaviour.
- Correlation of specialist findings.
- Conflict and dependency handling.
- Result traceability and audit integration.

## 2. In scope

- Contracts for `SelectionProposal` and `SelectionConfirmation` (see section 4; PENDING review).
- Recommendation logic that proposes, never selects.
- A workflow graph that stops at the confirmation gate.
- Multi-specialist fan-out over the approved categories, one task per category, each with its own
  identity.
- Correlation of findings by requirement ID, with conflicts and dependencies carried through.
- Offline run lifecycle: queued, running, waiting for confirmation, completed, failed, cancelled.
- Bounded retry for transient failures only, as typed by the specialist layer.

## 3. Out of scope

- Any execution without confirmation.
- Real Foundation permission checks (contract only; mock in offline work).
- Changes to AI-1 execution controls. They are not modified.
- Automatic routing from registry text. The structured router is not approved.
- Governance review (AI-S07) and estimation or SOW (AI-S08, AI-S09).

## 4. Required interfaces and dependencies

Proposal (AI to Foundation, proposed shape):

- `proposal_key`, `project_id`, `requirement_ids` (Foundation IDs), `capability_id`,
  `specialist_category_id`, `rationale`, `registry_version`, `proposed_at`.
- Writes only a proposal. No execution field exists.

Confirmation (human to Foundation, proposed shape):

- `confirmation_id`, `proposal_key`, `confirmed_by` (Foundation actor ID), `confirmed_at`,
  `confirmed_set` (must be a subset of the proposal).
- Refused if the confirmer is the proposer, or a system actor (DEC-05). Refusal code `SELF_CONFIRMATION_REFUSED`.

Dependencies: AI-S05 specialists; AI-2 execution wrapper; Foundation read contract (runtime only).

## 5. Deliverables

- Offline contracts for proposal and confirmation (Pydantic, strict).
- Recommendation module (deterministic, synthetic).
- Workflow module with a LangGraph graph **if the library is approved for the environment**; otherwise a
  plain state machine with the same states, with the library choice recorded as PENDING.
- Mock confirmation provider for tests only.
- Regression and adversarial tests for each area in section 8.

## 6. Security requirements

- No specialist runs unless a confirmation record exists for it. The mock confirmer is test-only.
- AI output cannot set a confirmation field. A confirmation from the AI component is refused.
- Confirmed set must be a subset of the proposed set.
- Cross-project requirement IDs are refused.
- Audit: every proposal, confirmation and refusal produces a record (offline: in memory; runtime: Foundation audit).

## 7. Human approval boundaries

- A human confirms the selection. The AI proposes.
- Only an authorised human confirms. Administrator role alone does not confirm (file 02 §2.1).
- Blocked versus needs-clarification outcomes are NOT decided here (PENDING A-4).
- Partial-result status for unresolved conflicts is NOT decided here (PENDING C-15).

## 8. Tests and evaluation scenarios

- Proposal contains no execution field; a proposal alone runs nothing.
- Execution before confirmation is refused, and no specialist code runs.
- Self-confirmation and system-actor confirmation refused (mock actors).
- Confirmed set outside the proposal refused.
- Requirement IDs from another project refused.
- Multi-specialist fan-out: each specialist's results carry its own identity; no result borrows another's.
- Conflicting findings across specialists are carried through, not merged.
- Retry: transient errors retried up to a bound; permanent refusals never retried.
- Cancel during a run stops later work; a late result is discarded and audited.
- Duplicate delivery of the same result yields one stored record.
- Provider-independence and no-network checks, as for AI-S05.

## 9. Engineering acceptance criteria

1. Tests in section 8 pass with the full gate green.
2. No AI-1 control file is modified (verified by diff).
3. Independent QA reports no blocking finding.
4. WDS accepts the offline scope.

## 10. External integration acceptance criteria (not claimed)

- Foundation-authenticated confirmation against the real session and permission model.
- Authorised selection records persisted by Foundation.
- Approved structured routing policy in force.

## 11. Governance decisions still pending (PENDING)

- A-4 blocked versus needs-clarification.
- C-15 evidence-unavailable run status.
- DEC-05 selection confirmer role (Technical Reviewer proposed; not approved).
- Structured routing predicates (not approved; directive section 12 and file 02 §6).
- Whether LangGraph is an approved dependency for the target environment.

## 12. Definition of Done

Contracts and tests reviewed; workflow runs offline with mock confirmation only; PENDING items recorded;
independent QA filed; WDS acceptance recorded for offline scope only.
