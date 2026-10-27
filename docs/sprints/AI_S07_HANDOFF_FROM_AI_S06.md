# AI-S07 Handoff from AI-S06

Status: handoff preparation only. Not an approval of AI-S07 implementation. AI-S07 isolated implementation
may proceed only within the previously approved contract-first scope.

Baseline: AI-S06 offline engineering commit `5350649b9d17b974ae498a73121f1ba8489b358d` (on
`integration/ai-s01-s02-s03`). AI-S05 closure: `84812b01d1f1ee752b3e5be505907bf42733ff2d`.

## 1. Inputs the reviewer receives (read-only)

- `SpecialistInvestigationResult` from each specialist (AI-S01 to AI-S05 contracts, unchanged): claims with
  evidence references and statuses, candidate solutions, risks, assumptions, conflicts, clarification questions,
  dependencies, evidence records.
- The originating `SpecialistTask` (requirement IDs, collections, registry and catalog versions, selection rationale).
- AI-S06 `OrchestrationResult`: per-category outcomes, the requirement correlation map, overlaps, and the audit log.
- The requirement records (Foundation IDs) and the evidence admitted for the project. Revisions are required
  but not yet present in the AI-side requirement contract (see section 4).

## 2. Proposed output contract (to be designed, not final)

A `ReviewFinding` proposal per issue, with: finding ID, requirement IDs, category, severity, defect class
(coverage gap, citation outside served set, unsupported verified claim, unreported conflict, missing evidence,
stale evidence, unsupported claim), evidence references, and a recommendation (correction or human review).
A finding is a recommendation. It never sets a verified status, materiality, an estimate, or an approval.

## 3. Interfaces to build (offline, contract-first)

- Coverage check: every requirement in a task is investigated or listed as skipped (AI-S06 already records this).
- Evidence availability and citation check: every citation resolves to served evidence for that category's collection.
- Unsupported-claim check: a claim with a verified status and no admitted evidence is flagged.
- Conflict and risk check: conflicts are reported with both sides cited; risks name every topic.
- Missing-information report: gap questions are preserved from specialists and from AI-S06 correlation.
- Traceability: findings link to requirement IDs and evidence references.

The reviewer must be separate from the generating specialist, must not import specialist code, and must not modify its
input (test by comparing before and after).

## 4. Runtime authority and Foundation dependencies (blockers for live use)

- R-1 (open): `run_specialist` is ungated AI-2 code. The reviewer must not depend on the confirmed path being the only
  path. Review inputs are trusted only once Foundation-controlled execution authority exists.
- R-2 (open): confirmations are unsigned. Review of a run must check the Foundation-issued authorisation record, which
  does not exist yet.
- Requirement revisions and approval states must come from Foundation-authorised reads (not yet implemented).

## 5. Governance decisions still open (do not finalise by assumption)

- A-4: blocked versus needs-clarification. Until decided, the reviewer reports open gaps as clarification
  questions only; it does not assign a blocked state.
- C-15: evidence-unavailable run status. Until decided, a task with no evidence is reported as PARTIAL with
  per-topic gaps, the rule already used by AI-S05 and AI-S06.
- GP-1: AI output may not assert verified status. Assumed fail-closed in the reviewer (no verified status is ever emitted).
- D-05 and file 02 section 9: who may accept or waive a finding. Not decided; the reviewer cannot accept findings.
- D-06 and D-07: materiality and acceptance of inferred requirements. Not decided; out of scope for the reviewer.

## 6. Proposed independent review tests (offline)

- A reviewer never upgrades a claim to verified, even when evidence is present.
- Each defect class in section 2 is detected by a discriminating fixture (a deliberately defective result).
- Findings never assign approval, materiality, estimate or SOW wording (sweep test).
- Cross-project and cross-collection citations are flagged, never accepted.
- A clean result yields no blocking finding; a partial result keeps its gaps visible.
- The reviewer's output is identical across runs (determinism).
- The reviewer does not import specialist modules (static check).

## 7. Not in scope for AI-S07

Live review against Foundation authority; policy-dependent lifecycle states; any change to the AI-2 contract;
any new specialist; SOW or estimate generation (AI-S08, AI-S09).
