# AI-S08 Sprint Specification: Effort Estimation

**WDS-APPROVED SCOPE BASELINE — IMPLEMENTATION AUTHORIZED** (isolated, draft outputs only)

Authority: WDS Project Owner master directive (26 October 2026). Parent: `AI_S05_S10_MASTER_SPRINT_PLAN.md`.

## 1. Purpose and approved functional scope

Produce versioned, traceable **draft** effort estimates from requirements, specialist findings and
stated assumptions. Estimates are proposals. Foundation and authorised WDS reviewers hold approval
authority.

## 2. In scope

- Requirement-level and task-level work breakdown.
- Resource and role allocation.
- Low, Likely and High hour estimates.
- Dependencies and assumptions, each traced to its source.
- Reusable historical references, where authorised.
- Evidence references.
- Uncertainty and risk explanations.
- Versioned draft estimation outputs.

Estimation policy (D-04): explicit Low, Likely and High hour tasks per discipline. Missing basis
produces `needs_inputs`, never a plausible guess.

## 3. Out of scope

- Approved commitments of any kind.
- Commercial pricing or rates.
- Historical references without authorisation.
- The reference estimate dataset (PENDING D-04, C-08).
- Final numeric approval (human).

## 4. Required interfaces and dependencies

- Input: requirements with Foundation IDs (AI-S05 and AI-S04 findings; approved requirements from Foundation at runtime).
- Output: `EstimateProposal` (proposed shape PENDING review; file 02 §10.1).
- Dependency: AI-S07 review recommended before a proposal is shown to a reviewer.
- Seven disciplines per REQUIREMENT_SCHEMA §9.2 (cited by the architecture decision register; the schema
  section itself was not re-read in this pass and should be checked before implementation).

## 5. Deliverables

- Offline estimator with stated basis for each line.
- Versioned `EstimateProposal` outputs carrying `estimate_version` and the inputs' revisions.
- Tests and synthetic examples.

## 6. Security requirements

- No real client rates, staff or historical data.
- The estimator reads only the inputs it is given.
- Each estimate carries its source references, so no number appears without a basis.

## 7. Human approval boundaries

- Every estimate is `draft`. Only an authorised human approves a numeric estimate.
- The system never represents an estimate as a commitment.

## 8. Tests and evaluation scenarios

- Low ≤ Likely ≤ High for every line.
- A line with no basis is reported as `needs_inputs`, not given a number.
- A changed input revision marks the estimate stale.
- Every line traces to a requirement ID and to an assumption or evidence reference.
- No output carries an approved or committed status.

## 9. Engineering acceptance criteria

Tests pass; independent QA reports no blocking finding; WDS accepts the isolated scope.

## 10. External integration acceptance criteria (not claimed)

Estimates checked against approved WDS reference ranges and authorised historical data.

## 11. Governance decisions still pending (PENDING)

- D-04 and C-08 reference estimate dataset.
- D-14 role holders and the role set for allocation.
- Disciplines list confirmation.

## 12. Definition of Done

Versioned draft estimator tested offline; no approved or committed status produced; PENDING items recorded;
QA and WDS acceptance recorded for the isolated scope.
