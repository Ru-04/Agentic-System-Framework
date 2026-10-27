# AI-S10 Governance Policy Decision Register

Status: every decision below is **open**. AI-S10 does not decide any of them. Where the code applies a
fail-closed default, that is a technical control, not a recorded decision. The IDs are as used in the
AI-S07 to AI-S09 records and the AI-engine governance documents in `docs/`.

| ID | Decision | Current state in code | AI-S10 evidence | Decision owner |
|---|---|---|---|---|
| A-4 | Blocked versus needs-clarification. Lifecycle state for unresolved conflicts | Blocked is used for unresolved conflicts. Specifications are drafts, so this is not settled (C-4) | EXT-08 (open limitation, governance) | WDS ruling |
| C-15 | Execution envelope semantics. Whether `succeeded` may mean complete when the output is `evidence_unavailable` or `partial` | The envelope reports `succeeded` for both | REC-03 observed it: withheld category reports `succeeded` with `evidence_unavailable`. Recorded as an observation, not a pass of the intended contract | Engineering with WDS |
| GP-1 | AI output may not assert verified status | Assumed fail-closed in the reviewer. No verified status is ever emitted | SPEC-13, SEC-14 pass as technical controls. The policy itself is not recorded | WDS |
| D-05 | Roles; no self-approval; SOW approver must differ from preparer and submitter | Approval placeholder `pending_human_approval`; no approver is recorded | SOW-11 passes (no autonomous approval). Role policy is open | WDS (Foundation action matrix) |
| D-06 | Criticality predicates. Materiality stays `unassessed` | Not implemented | EXT-08 | WDS |
| D-07 | Acceptance of inferred requirements | Inferred origin is shown as such; no acceptance is recorded | EXT-08 | WDS |
| D-10 | SOW house template, section contract, export | No DOCX or PDF produced; structure is a proposal | SOW-13 blocked | WDS |
| D-04 | Reference estimate dataset | No reference data used; estimate values come from AI-S08 bases | EST-06, SEC-03 pass with no numbers from unverified bases | WDS |
| C-08 | Authorised historical data | Historical references refused unless the project is authorised | SEC-15 passes | WDS |
| D-14 | Role holders and the role set for allocation | Resource lines carry disciplines only | No scenario; open | WDS |
| R-1 | Direct specialist execution: `run_specialist` is public and can run any agent without an orchestrator | Remains callable (AI-2 code, accepted contract) | SEC-09: **open_limitation**. The gate is not a production authorisation boundary | Engineering with WDS |
| R-2 | Operator confirmations are unsigned in-process records | The gate checks shape and binding, not authenticity | EXT-06: blocked on Foundation | Engineering with WDS |
| D-12 | LLM provider, model, budget, data-processing policy | No LLM call path; no LLM is called | EXT-01 blocked | WDS |
| D-13 | Retention and deletion of evaluation data and AI outputs | Open | Spec section 11 | WDS |
| DEC-09 | Real-data use | `synthetic: false` is refused with `DATA_NOT_APPROVED` | Not run; no real data used | WDS |
| D-02 | Source-access matrix and per-vendor allowlist | None granted | SPEC-15 blocked | WDS |
| — | Numerical release thresholds | **PENDING WDS Technical Lead** (spec section 7). Not set | Counts only; no threshold applied | WDS Technical Lead |

## Limits of this register

- Some decision rows were confirmed by reading the sprint records through search matches, not by a full
  read of each source document. Before a decision is taken, the cited source must be read in full.
- A fail-closed default in code is not a decision. Each row above stays open until WDS records a ruling.
