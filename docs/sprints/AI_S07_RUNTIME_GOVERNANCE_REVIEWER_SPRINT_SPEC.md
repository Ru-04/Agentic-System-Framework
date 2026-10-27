# AI-S07 Sprint Specification: Runtime Governance Reviewer

**WDS-APPROVED SCOPE BASELINE — IMPLEMENTATION AUTHORIZED** (policy-independent parts only)

Authority: WDS Project Owner master directive (26 October 2026). Parent: `AI_S05_S10_MASTER_SPRINT_PLAN.md`.

## 1. Purpose and approved functional scope

An independent reviewer of specialist findings. It checks coverage, evidence, citations, unsupported
claims, conflicts and missing information, and it recommends corrections or human review. It does not
approve anything.

## 2. In scope (policy-independent)

- Independent review of specialist findings.
- Requirement coverage checks: every requirement in the task is either investigated or reported as skipped.
- Evidence availability and citation checks: every citation resolves to served evidence.
- Unsupported claim detection: a claim with a verified status and no admitted evidence is flagged.
- Conflict and risk identification.
- Missing-information reports.
- Review recommendations and findings.
- Traceability to requirements and sources.

## 3. Out of scope

- Autonomous approval of client requirements, materiality, estimates or SOW commitments.
- Policy-dependent lifecycle states (PENDING A-4, C-15).
- Blocked versus clarification decisions (PENDING A-4).
- Authority rules for who may accept a finding (PENDING D-05 and file 02 §9).
- Any change to the specialist that produced the finding.

## 4. Required interfaces and dependencies

- Input: `SpecialistInvestigationResult` and the originating `SpecialistTask` (AI-S05 and AI-S04 outputs).
- Context: requirement IDs and the admitted evidence set, read-only.
- Output: `ReviewFinding` records (proposed; shape PENDING review).
- Independence: the reviewer is a separate component from the generating specialist and shares no
  state with it. The reviewer does not import specialist code.

## 5. Deliverables

- Offline reviewer module with the checks in section 2.
- `ReviewFinding` proposal contract (PENDING review).
- Tests for each check, with synthetic findings that are deliberately defective.

## 6. Security requirements

- The reviewer reads only the result and the context it is given.
- It cannot change a result, a status or a requirement.
- It never returns a verified status.

## 7. Human approval boundaries

- A finding is a recommendation. A human decides.
- The reviewer does not set materiality (D-06) or accept scope (D-07).

## 8. Tests and evaluation scenarios

- Each check flags its defect class (coverage gap, citation outside served set, unsupported verified claim,
  unreported conflict, missing requirement IDs).
- A clean result produces no blocking finding.
- The reviewer does not modify its input (asserted by comparing before and after).
- The reviewer imports no specialist module.

## 9. Engineering acceptance criteria

Checks and tests pass; independent QA reports no blocking finding; WDS accepts the policy-independent
scope only.

## 10. External integration acceptance criteria (not claimed)

Governance review against Foundation's approved review workflow and authority rules.

## 11. Governance decisions still pending (PENDING)

- A-4, C-15 (lifecycle and blocked versus clarification).
- GP-1 confirmation (AI output may not assert verified status).
- D-05 and file 02 §9 (who may accept findings).

## 12. Definition of Done

Policy-independent checks implemented and tested offline; PENDING items recorded; no finding treated as
approval; QA and WDS acceptance recorded for the offline scope.
