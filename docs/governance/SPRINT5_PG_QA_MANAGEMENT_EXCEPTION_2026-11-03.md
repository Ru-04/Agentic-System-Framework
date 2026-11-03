# M2 Sprint 5: PG QA management exception (3 November 2026)

## Recorded decision

**PG QA — PASS REPORTED TO WDS; MANAGEMENT ACCEPTED WITHOUT PERSONAL PG ATTESTATION.**

This is an explicit WDS management exception to the Sprint 5 requirement for a personally attributable PG review record. It is recorded as a management decision, not as evidence of PG's review.

| Field | Value |
|---|---|
| Approver | WDS Authorized Approver. The directive does not state the approver's name; WDS to add it |
| Decision date | 3 November 2026 |
| Channel | Formal WDS closure directive, pasted into the Sprint 5 session (chat) |
| Affected gate | Gate 7, independent QA PASS, Sprint 5 QA evidence requirement only |
| Basis stated by WDS | PG informed WDS management that all tested functionality works correctly and that no defects were found |

## Limitations

- No PG signature, review timestamp, reviewed SHA, scope reviewed or independence statement exists. None is recorded here and none has been fabricated.
- PG's findings and test details are not on record. The reviewed SHA is not stated.
- The exception applies **only** to the Sprint 5 QA evidence requirement. It does not waive:
  - technical evaluation requirements (gates 1, 3, 4, 5);
  - security, source-integrity or CI requirements (gate 2 is met on `b885ad7`);
  - remediation verification (gate 8);
  - any Sprint 6 requirement. It **does not** apply to Sprint 6 D-13, which needs its own independent re-QA on the candidate tip.

## Effect on Sprint 5 status

Recording this exception clears gate 7 only, and only as a management exception. It does not close Sprint 5.

Sprint 5 remains **NOT YET ACCEPTABLE**. Open gates:

- Gate 1: WDS scope decision.
- Gate 3: Shopify relevance pending. Real-citation row not measured.
- Gate 4: AS's 55 labels against `P001–P055` are not on record. The submitted `Shopify_55_Pairs_AS_Approval_Review_DRAFT.docx` contains no judgments and uses `S5-SH-DRAFT` IDs.
- Gate 5: one verified real-documentation claim; four unknowns.
- Gates 8 and 9: follow from the above.

Sprint 6 is unaffected. Its Step 2 remains gated on D-13 and D-10.
