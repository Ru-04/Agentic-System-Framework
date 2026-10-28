# AI-S10 Governance Policy Decision Register (Stage 3)

Status: every decision below is **open**. AI-S10 does not decide any of them. Where code applies a fail-closed
default, that is a technical control, not a recorded decision. The IDs are as used in the AI-S07 to AI-S09
records and the AI-engine governance documents in `docs/`.

| ID | Decision | Current state in code | AI-S10 evidence (Stage 3) | Decision owner |
|---|---|---|---|---|
| A-4 | Blocked versus needs-clarification | Blocked for unresolved conflicts; specifications are drafts (C-4) | `EXT-08` open governance limitation | WDS ruling |
| C-15 | Execution envelope semantics: whether `succeeded` may mean complete when the output is `evidence_unavailable` or `partial` | The envelope reports `succeeded` for both | `REC-03` is an **open limitation** linked to C-15: the withheld category runs with no evidence, reports `evidence_unavailable`, and the execution reports `succeeded`. Recorded as the limitation; not a pass of the acceptance expectation | Engineering with WDS |
| GP-1 | AI output may not assert verified status | Fail-closed in the reviewer; no verified status is ever emitted | `SPEC-13`, `SEC-12`, `S01-05` pass as technical controls; the policy itself is not recorded | WDS |
| D-05 | Roles; no self-approval; SOW approver differs from preparer and submitter | Approval placeholder `pending_human_approval`; no approver recorded | `SEC-13`, SOW approval checks pass; role policy open | WDS (Foundation action matrix) |
| D-06 | Criticality predicates; materiality stays `unassessed` | Not implemented | `EXT-08` | WDS |
| D-07 | Acceptance of inferred requirements | Inferred origin shown; no acceptance recorded | `REQ-08` passes (inferred never accepted); acceptance policy open | WDS |
| D-10 | SOW house template, section contract, DOCX/PDF export | No DOCX or PDF produced | `SOW-13` blocked | WDS |
| D-04 | Reference estimate dataset | No reference data; numbers only from AI-S08 bases | `EST-06`, `SEC-03` pass with no numbers from unverified bases | WDS |
| C-08 | Authorised historical data | Historical references refused unless the project is authorised | `SEC-15` passes | WDS |
| D-14 | Role holders and role set for allocation | Resource lines carry disciplines only | No scenario; open | WDS |
| R-1 | Direct specialist execution: `run_specialist` is public and runs any agent | Remains callable (accepted AI-2 code) | `SEC-09` is an **open limitation**: a direct call with no confirmation, actor or proposal returns an execution | Engineering with WDS |
| R-2 | Operator confirmations are unsigned in-process records | Gate checks shape and binding, not authenticity | `EXT-06` blocked on Foundation | Engineering with WDS |
| D-12 | LLM provider, model, budget, data-processing policy | No live LLM call path; offline deterministic LLM only | `EXT-01` blocked; `LLM-01`..`LLM-03` offline only | WDS |
| D-13 | Retention and deletion of evaluation data and AI outputs | Open | Spec section 11; no scenario | WDS |
| DEC-09 | Real-data use | `synthetic: false` refused: fixture ingestion raises `ValueError` ('real data is refused') | Not run; no real data used | WDS |
| D-02 | Source-access matrix and per-vendor allowlist | None granted | `SPEC-15` blocked | WDS |
| **STL-05** | **Stale input rejection (spec section 8)**: the spec says stale inputs are rejected. The accepted AI-S07/S08/S09 contracts flag, exclude or mark `needs_inputs`, and never refuse the operation | Flagging behaviour is what the engine implements. Only operator-selection staleness is a genuine rejection (`STL-04`) | `STL-05` **blocked**: the criterion cannot pass until WDS decides. If refusal is required, the change is an upstream AI-S08/AI-S09 correction through the permitted process | **WDS (new in Stage 3)** |
| **UD-01** | **Upstream defect (AI-S09)**: the SOW does not compare the estimate's governance fingerprint with the governance review's | A mismatched estimate is accepted with no integrity issue | `UD-01` **open limitation**; the fix is outside AI-S10 scope and needs the permitted upstream change | **Engineering with WDS (new in Stage 3)** |
| — | Numerical release thresholds | **PENDING WDS Technical Lead** (spec section 7); not set | Counts only | WDS Technical Lead |

## Limits of this register

- Decision rows were confirmed by search matches in the sprint records and governance documents, not by a full
  read of each cited source. Each must be read in full before a ruling is taken.
- A fail-closed default in code is not a decision. Every row stays open until WDS records a ruling.
