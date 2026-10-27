# AI-S09 Sprint Specification: Detailed Draft Statement of Work

**WDS-APPROVED SCOPE BASELINE — IMPLEMENTATION AUTHORIZED** (draft only)

Authority: WDS Project Owner master directive (26 October 2026). Parent: `AI_S05_S10_MASTER_SPRINT_PLAN.md`.

## 1. Purpose and approved functional scope

A mandatory MVP deliverable: a **Detailed WDS Draft Statement of Work**, assembled from approved inputs,
with traceability to requirements and evidence. The system produces a draft only.

## 2. Required sections (where supported by approved inputs)

1. Project overview.
2. Scope and objectives.
3. Requirement-to-deliverable mapping.
4. Proposed solution and architecture.
5. In-scope deliverables.
6. Exclusions and assumptions.
7. Integration dependencies.
8. Milestones and phases.
9. Resource-wise Low, Likely and High estimates (from AI-S08).
10. Risks and open clarification questions.
11. Acceptance criteria.
12. Client and WDS responsibilities.
13. Traceability to requirements and evidence.

A section with no supporting approved input is marked **"not supported by approved input"**. It is not
filled from inference.

## 3. Out of scope

- Any binding commercial, contractual or approval commitment.
- Signature, approval or issue of a SOW.
- House-format DOCX or PDF rendering until the template and section contract are supplied (PENDING D-10, M-8).
- Pricing, rates and payment terms.

## 4. Required interfaces and dependencies

- Inputs: approved requirements (Foundation, runtime); AI-S05 and AI-S04 findings; AI-S07 review; AI-S08 estimates.
- Output: `DraftSOW` proposal, versioned, with an input manifest listing every source revision.

## 5. Deliverables

- Offline draft assembler producing the sections above in a structured form (Markdown is out of scope for
  the contract; rendering is PENDING).
- Input manifest and traceability table.
- Tests and synthetic examples.

## 6. Security requirements

- Only the inputs passed to the assembler are used.
- No client data beyond the synthetic inputs in offline tests.
- The draft states that it is not an offer, not a commitment and not approved.

## 7. Human approval boundaries

- A human author reviews the draft. A human approver, distinct from the author, approves any version (SOW self-approval is prohibited).
- The system never sets an approved state.

## 8. Tests and evaluation scenarios

- Every requirement appears in the mapping or is listed as unmapped with a reason.
- A section without input is marked unsupported, not filled.
- The draft carries the "draft, not approved" statement on every page of its structured output.
- Estimates shown are the AI-S08 draft values, labelled as draft.
- An approved status or signature field cannot be set by the assembler.

## 9. Engineering acceptance criteria

Tests pass; independent QA reports no blocking finding; WDS accepts the draft-only scope.

## 10. External integration acceptance criteria (not claimed)

Approved WDS house-format rendering; Foundation approval workflow; client review.

## 11. Governance decisions still pending (PENDING)

- D-10 SOW template and section contract.
- Approver role and separation rule (REVIEW_POLICY Gate F).
- Client and WDS responsibility wording (approved text not supplied).

## 12. Definition of Done

Draft assembler tested offline; output labelled draft; PENDING items recorded; QA and WDS acceptance
recorded for the draft-only scope.
