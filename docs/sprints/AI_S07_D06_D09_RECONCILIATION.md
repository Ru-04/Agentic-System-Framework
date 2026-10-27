# AI-S07 Decision Reconciliation: D-06, D-09 and D-EVB-1

Status: reconciliation entry for WDS acceptance. Governing text is quoted as found in the WDS specification folder. Nothing in the governing policy was modified.

## 1. WDS decisions applied to AI-S07 (isolated engineering)

- **D-EVB-1 (approved by WDS for isolated engineering):** EVIDENCE_BACKED is an independent Governance Reviewer assessment of whether a candidate claim is adequately supported by admissible evidence. It is not a specialist-declared VERIFIED status, not Foundation source verification, not human approval, not materiality, and not commercial acceptance.
- **Verification-authority boundary (approved by WDS):** Foundation or an authorised WDS-controlled process owns source identity, access and verification provenance. A specialist may propose claims and citations but may not issue verification. AI-S07 may assess evidence sufficiency from the admitted and authorised context. AI-S07 must not modify authoritative evidence records or promote their verification status. AI-S07 findings stay separate from source verification and human approval records.

## 2. Governing text, as found

**D-06** (`WebDesk_Agentic_Requirement_Platform_Specs/DECISION_REGISTER.md`, line 12): status "CONFIRMED — predicates to detail". Decision: "Deterministic materiality, `unassessed` acts as material; only Technical Reviewer may downgrade with audited rationale; objective criticality triggers for security, privacy, data integrity, payment, access control and fundamental feasibility, unknown not safe". Open: "Specific deterministic triggers, non-downgradeable classes, and evidence verification actor policy to detail (C-02)."

**D-09** (same file, line 15): status "CONFIRMED". Decision: "Critical governance findings never waivable in MVP; always block final approval until resolved or formally evidence-reclassified". Open: "Audited finding disposition, no `accepted_risk` for critical; align H-11/X-08."

**Supporting text:** `GOVERNANCE.md` line 273 (D-09: final gate fails while any critical finding is open, active, risk-accepted or insufficiently resolved; evidence-based reclassification is a separate authorised decision with old and new severity, cited evidence and audit). `REVIEW_POLICY.md` lines 98, 185, 193 (critical findings cannot become `accepted_risk`; a Technical Reviewer may record evidence-backed reclassification with actor, evidence and audit). `REQUIREMENT_SCHEMA.md` line 403 (`FindingReclassification` is independent of waiver and may not be proposed as an executable action by an LLM). `ARCHITECTURE.md` line 317 (D-06: Technical Reviewer may downgrade materiality only by reasoned audited action; additional hard restrictions await policy definition). `ARCHITECTURE.md` line 321 and `REQUIREMENT_SCHEMA.md` line 426 (verification actors remain pending).

## 3. Reconciliation against the approved boundary

| Boundary item | Governing text | Status |
|---|---|---|
| Foundation or WDS-controlled process owns verification provenance | Verification actors "remain pending" (ARCHITECTURE line 321); C-02 "evidence verification actor policy to detail" (DECISION_REGISTER line 12) | Consistent. The actor policy itself is still to be detailed. AI-S07 relies on the caller-supplied admitted record and does not name an actor |
| Specialist may propose but not issue verification | Specialist output contract refuses VERIFIED claims and verified served evidence (`contracts/specialist.py`, `contracts/evidence.py`) | Consistent and enforced in code |
| AI-S07 assesses sufficiency; does not modify or promote records | `REQUIREMENT_SCHEMA.md` line 178 provides `verification_actor_id` and `verification_at` as optional claim fields; the reviewer does not write them | Consistent. The reviewer never writes to records or to these fields |
| Findings separate from verification and approval | D-09 and REVIEW_POLICY line 185: a critical finding blocks approval until resolved or reclassified by an authorised reviewer | Consistent. Findings are `proposed`, `authorises_anything` is False. Blocking effect on approval is a Foundation dependency (no approval module exists in AI-S07) |
| Reclassification is a separate authorised action | D-09; REQUIREMENT_SCHEMA line 403; REVIEW_POLICY line 98 | Consistent. The reviewer never reclassifies a severity |
| No critical waiver | D-09; REVIEW_POLICY line 193 | Consistent. The reviewer has no waiver or acceptance path |

## 4. Conflicts and open items (not resolved here)

1. **Severity vocabulary (needs WDS mapping; not a boundary conflict).** REVIEW_POLICY §3 defines `critical`, `major` and `minor`. The reviewer uses `BLOCKER`, `MAJOR`, `MINOR` and `NOTE`. Its BLOCKER findings cover cross-project and mismatched evidence, which the policy would likely classify as critical, and also unbound claims. Proposed mapping for WDS confirmation: BLOCKER and critical; MAJOR and major; MINOR and minor; NOTE and informational. No policy text was changed.
2. **D-06 predicates and C-02 verification actor policy.** Still to be detailed by WDS. AI-S07 neither defines nor assumes the verification actor.
3. **D-06 reclassification authority.** Only the Technical Reviewer may downgrade materiality with audited rationale. AI-S07 has no materiality function and does not downgrade anything.
4. **Blocking effect of BLOCKER findings on approval.** D-09 requires critical findings to block approval. No approval module exists in AI-S07, so the blocking effect is a Foundation dependency. `ReviewReport.has_blocker` is the signal Foundation must consume.
5. **Tie to H-11 and X-08.** D-09 asks to align these items. They are outside AI-S07 and remain open.

## 5. Conclusion

The approved boundary is consistent with the governing text as found. No material conflict requires WDS to modify authoritative policy before AI-S07 engineering proceeds. Items 1 to 5 above remain open and are recorded for WDS. D-06 and D-09 are not claimed resolved in full.
