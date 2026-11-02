# Phase 4 governance provenance matrix (2026-10-28)

This matrix separates governance provenance from engineering completion. Engineering can be complete while a decision is
unattributed. Nothing here supplies a missing approver, timestamp, channel or signature. Where a value is absent, the cell
says so.

Governance rule applied: `WebDesk_Agentic_Requirement_Platform_Specs/GOVERNANCE.md` requires that the approving user,
decision, timestamp, artifact version or hash, review result and any accepted exceptions are recorded for a decision.

## 1. Decisions and their records

| Decision | Record | Approver identity | Approval timestamp | Channel | Artifact version or hash | Decision wording | Status |
|---|---|---|---|---|---|---|---|
| P-0: Increment 3 hardening plan (Phase 4 section) as non-production engineering baseline | `P4-GOV-2026-10-28` | **missing** | **missing** | relayed in chat, 2026-10-28 | **missing** (plan file `docs/INCREMENT_3_HARDENING_PLAN.md` is not hashed or versioned in the record) | relayed text, restated in the register | recorded as relayed; provenance incomplete |
| H-DEC-3: configurable non-production limits; values provisional | `P4-GOV-2026-10-28`, amended | **missing** | **missing** | relayed, 2026-10-28 | **missing** | relayed; 20 MiB input limit and PDF expansion application added as amendments | recorded as relayed; provenance incomplete |
| H-DEC-4: process timeout plus input pre-check for non-production Windows | `P4-GOV-2026-10-28` | **missing** | **missing** | relayed, 2026-10-28 | **missing** | relayed | recorded as relayed; provenance incomplete |
| H-DEC-5: DOCX table-cell locator extension | `P4-GOV-2026-10-28` | **missing** | **missing** | relayed, 2026-10-28 | **missing** | relayed | recorded as relayed; provenance incomplete |
| H-DEC-6: HTML-only email, partial or unextractable | `P4-GOV-2026-10-28`, amended by `WDS-QA02-RULING-2026-10-28` | **missing** | **missing** | relayed, 2026-10-28 | **missing** | the original wording is superseded: zero-segment results are unsupported | recorded as relayed; provenance incomplete |
| EML offset semantics (`start_offset`/`end_offset`, normalized text) | `P4-GOV-2026-10-28`, amended | **missing** | **missing** | relayed, 2026-10-28 | **missing** | relayed; field names aligned to REQUIREMENT_SCHEMA section 4 | recorded as relayed; provenance incomplete |
| QA-02 ruling: partial needs a committed segment and a flag; zero segments are not partial | `WDS-QA02-RULING-2026-10-28` | **missing** | **missing** | relayed, 2026-10-28 | **missing** | quoted in the register | recorded as relayed; provenance incomplete |

Reading the table: "relayed" means the instruction reached the engineering session in the chat, pasted by the account that
holds the sales address. It does not identify a WDS approver. No cell has been filled from inference.

## 2. Required information against available evidence

| Required by GOVERNANCE.md | Known evidence | Missing evidence | Responsible authority |
|---|---|---|---|
| Approving user (identity) | The chat account that relayed the text | The named WDS approver and their role | WDS governance owner (named in GOVERNANCE.md as "to be assigned") |
| Decision | Register text, relayed wording | A WDS-authored decision record | WDS governance owner |
| Timestamp | Relay date 2026-10-28 | The approval time as WDS records it | WDS governance owner |
| Artifact version or hash | Commit SHAs of the implementation (`cb93047`, `8d5b039`, `8040f9e`, `f03698d`, `17c825b`) | A WDS statement binding the decision to a specific commit or document hash | WDS governance owner, with engineering supplying the hash |
| Review result | Developer and independent-QA reports (not independent) | An independent reviewer's result | Independent QA reviewer named by WDS |
| Accepted exceptions | Known residuals listed in `PHASE4_PDF_CONTAINMENT.md` section 6 and the QA remediation matrix | WDS acceptance of each residual, or a decision that each blocks production | WDS governance owner |

## 3. Gap classification

Each gap is classified separately from engineering completion.

| Gap | Blocking non-production acceptance | Blocking production readiness | Documentation correction | Informational |
|---|---|---|---|---|
| Approver identity missing for all decisions | **Yes** (formal acceptance cannot be recorded) | **Yes** | No | No |
| Approval timestamp missing | **Yes** | **Yes** | No | No |
| Artifact version or hash missing | **Yes** (a decision cannot be tied to a commit) | **Yes** | No | No |
| Channel recorded only as "relayed" | **Yes** | **Yes** | No | No |
| H-DEC-4 (Windows memory containment) relayed as non-production only | No, if WDS confirms the scope | **Yes**, for any Windows production run | No | No |
| H-DEC-3 numeric limits provisional | No | **Yes** (production values need WDS) | No | No |
| Phase 3 lease ordering unverified locally | No | **Yes** (integration) | Yes (already corrected in `limits.py`) | No |
| Phase 2 and 3 migrations (`0044`, `0045`, `0050`, `0051`) not on this branch | No | **Yes** (merge reconciliation) | Yes (dependency register) | No |
| Ruling's text lacks the approving user | **Yes** | **Yes** | No | No |

## 4. What the engineering record can and cannot assert

It can assert: which commits implement which decision; the text that was relayed; the amendments made in the register;
and the tests that exercise each decision.

It cannot assert: that any named person approved any decision; the time of any approval; that any artifact was reviewed
by WDS; or that formal WDS acceptance has occurred. The Phase 4 documents must not say otherwise. The corrected plan status
line (`docs/INCREMENT_3_HARDENING_PLAN.md`, line 3) already says the approval is relayed and incomplete.

## 5. Requests to WDS (for the governance owner)

1. Name the approver for each decision in section 1, or confirm that the relayed text is the decision.
2. Provide the approval date and time for each decision.
3. Confirm the channel (for example, a WDS-signed document or a register entry they author).
4. Bind each decision to an artifact version: a commit SHA or a document hash, as WDS prefers.
5. Decide whether the H-DEC-4 Windows containment residual is accepted for non-production only, and whether production
   requires a further decision.
6. Confirm the QA-02 ruling wording, or supply a replacement.

## Provenance matrix update (2026-10-29)

The WDS-DECISIONS-2026-10-29 authorization is recorded in `docs/GOVERNANCE_DECISION_REGISTER.md`. Its approver identity,
approval channel and time as WDS records them, and its exact wording, remain missing. Administrative attestation is the only
outstanding record requirement for the engineering decisions. QA-05 and QA-06 are not waived. Production containment and
production limits are unchanged.
