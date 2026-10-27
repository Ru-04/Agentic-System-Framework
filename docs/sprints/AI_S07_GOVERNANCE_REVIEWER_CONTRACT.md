# AI-S07 Governance Reviewer Contract

Status: engineering contract for the offline reviewer. Interpretation D-EVB-1 (section 5) is approved by WDS for isolated engineering. The D-06 and D-09 verification-authority boundary is reconciled in `AI_S07_D06_D09_RECONCILIATION.md`. This contract is not formal acceptance.

## 1. Why specialists cannot self-verify

A specialist produces candidate findings, hypotheses, citations, assumptions, risks, questions and evidence gaps. It may not declare a claim verified by setting a status. The specialist output contract (`ai_engine/contracts/specialist.py`) refuses VERIFIED and PARTIALLY_VERIFIED claim statuses and refuses verified served evidence. The reviewer does not relax that contract. Verification authority is not decided yet (decision register D-06 and D-09 are open), so no specialist output can establish verification.

## 2. What EVIDENCE_BACKED means

A requirement is `EVIDENCE_BACKED` when the independent reviewer finds at least one claim, bound to that requirement, that cites admitted evidence passing every gate in section 3. It means: the admitted record, as recorded by its caller, supports the requirement, subject to the reviewer's deterministic checks.

## 3. What EVIDENCE_BACKED does not mean

It is not:
- a specialist VERIFIED claim (the reviewer never reads claim status as proof);
- human requirement approval;
- business materiality (D-06) or criticality;
- authorisation to execute a specialist (R-1 remains open);
- an approved estimate;
- a binding SOW commitment;
- a change to any Foundation-owned approval or lifecycle state.

## 4. Gates for backing (all must hold)

Review-level precondition: the review must supply `as_of` and `stale_after` (a freshness window) and an authorised collection set. Without them nothing is backed, and the review reports `MISSING_REVIEW_PARAMETER` (MINOR, escalated to a human). This is fail-closed for backing; it does not refuse the review.

For a requirement R and claim C in a specialist output routed to R:
1. C's subject references include R, and R was routed to that specialist (claim-to-requirement binding).
2. C cites evidence E that the output served (claim-to-evidence binding).
3. E is in the admitted set, with the same evidence ID.
4. E's project equals the review's project (project identity).
5. E is of kind approved internal or official vendor documentation (admissibility by kind).
6. E's recorded status is verified or partially verified, with its recorded provenance. For approved internal evidence: source ID, source version and content hash. For official vendor documentation: publisher, applicable platform version, content hash and an https source URL (recorded verification provenance). The reviewer re-checks this provenance itself, so a record built without it, for example by an unvalidated copy, is not backed.
7. The served copy of E equals the admitted E on every field except status, and its status is unverified or equal to E's status (served-copy consistency, section 5).
8. E's collection is in the authorised set, when an authorised set is supplied; an unknown collection fails closed (collection identity).
9. E is not superseded by a caller-supplied successor.
10. E is fresh under the caller's window, when one is supplied; the limit is inclusive (freshness).
11. E's relevance summary shares a significant term with the claim text or the requirement statement (relevance screen, not semantic relevance).
12. C's own status is not CONFLICTING or NOT_APPLICABLE, and no conflict record disputes R.

Upstream claim status (for example an UNVERIFIED claim) is not a gate. A claim declaring VERIFIED without verifiable admitted evidence is a separate blocker (`UNSUPPORTED_VERIFIED_CLAIM`).

## 5. Served-copy consistency and interpretation D-EVB-1

The specialist validator (`contracts/specialist.py`) refuses VERIFIED and PARTIALLY_VERIFIED served evidence, but it accepts served copies with other statuses (for example CONFLICTING or NOT_APPLICABLE). AI-S03 states that served evidence status is unverified in the ingestion path. The directive's MAJOR-2 wording could then read as making any status difference fatal, which would make EVIDENCE_BACKED unreachable from validated output for verified records. The approved directive (section C) resolves this: a served status that is unverified or equal to the admitted status is acceptable.

Interpretation D-EVB-1 (approved by WDS for isolated engineering):
- The served copy's `evidence_status` is a non-authoritative projection. It may be unverified or equal to the admitted status.
- The admitted record is the sole verification authority for the reviewer.
- Any other field difference (identity, project, kind, source ID, source version, content hash, checked-at time, source URL, publisher, applicability, limitations, relevance summary) is a `SERVED_RECORD_MISMATCH` and never backs.
- A served status other than unverified or equal to the admitted status is a `SERVED_RECORD_MISMATCH` and never backs.
- A duplicated served ID is ambiguous and is a mismatch in any order.

Proposed smallest amendment, for WDS review only (not applied): add to the served-evidence rules in AI-S03 and the specialist contract: "A served EvidenceReference is a copy of an admitted record. Its evidence_status is always unverified. Every other field must be identical to the admitted record. The admitted record, not the served copy, is the authority for verification status."

## 6. Finding classes and status precedence

Finding classes are listed in `governance/contracts.py` (`DefectClass`). Requirement status precedence: blocker present, then UNSUPPORTED; then conflict or cross-specialist divergence, then CONFLICTED; then the gates in section 4, then EVIDENCE_BACKED; then a produced but unbacked result, then NOT_EVIDENCE_VERIFIED; otherwise UNSUPPORTED.

A COMPLETED output with no evidence served is NOT_EVIDENCE_VERIFIED with a MAJOR `NOT_EVIDENCE_VERIFIED` finding. Served but unused evidence is a MINOR `MISSING_EVIDENCE` finding. In every case where nothing backs, the status is never evidence-verified.

## 7. Fail-closed input rules

`ReviewInput` refuses at construction: empty run or project ID; naive `as_of`; non-positive window; a window without `as_of`; duplicate specialist category; an output belonging to another category; an admitted key that does not match its record; naive `checked_at`; `checked_at` after `as_of`.

## 8. Escalation and audit

- Findings whose action is `human_review` are escalations (`ReviewReport.escalations`). A finding is a recommendation; a human decides.
- `input_fingerprint` is a SHA-256 over the run and project identifiers, requirement and admitted-evidence IDs, outcome identifiers and statuses, served-evidence IDs, and the window, collection, and supersession parameters. It is a correlation key, not a content hash.
- `authorises_anything` is always False.

## 9. Out of scope

Lifecycle states (A-4, C-15), blocked versus clarification decisions (A-4), finding acceptance (D-05), materiality (D-06), scope acceptance (D-07), confirmation authenticity (R-2), and any specialist execution.

## 10. Foundation dependencies for real authority

See the implementation record, section 8: authoritative requirement and source reads, verified provenance from the admission authority, collection authorisation, authoritative supersession and conflict data, and durable tamper-evident audit persistence.
