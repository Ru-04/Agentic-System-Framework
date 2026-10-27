# AI-S09 Governance and Foundation Dependency Register

Status: register for the draft SOW sprint. Entries marked OPEN need a WDS or Foundation decision. Nothing here is decided by the engine.

## Governance decisions

| Ref | Decision | Status | Effect on AI-S09 |
|---|---|---|---|
| D-10 | House SOW template, section contract, wording conventions, DOCX and PDF export acceptance | OPEN | No DOCX or PDF is produced. Structure is a proposal. |
| D-05 | Roles; no self-approval; SOW approver must differ from preparer and submitter | OPEN (Foundation action matrix) | The approval placeholder is `pending_human_approval` with no approver. |
| Gate F (REVIEW_POLICY) | Approver separation and deny-by-default authorisation | OPEN (Foundation) | Documented in the approval rule; not enforced in the engine. |
| Gate D (REVIEW_POLICY) | No commitment without an explicit commitment | Policy text present; enforcement is Foundation | The engine never sets commitment; every item is a proposal. |
| Gate E (REVIEW_POLICY) and D-09 | Critical findings are not waivable; block final approval until resolved or reclassified | Policy text present; enforcement is Foundation | Blockers stay visible in `risks`. Severity classes (critical, major, minor) are not computed by this engine; the governance review's findings are carried as status and blocking requirements. The engine offers no waiver. |
| REQUIREMENT_SCHEMA 9.1 | Materiality defaults to `unassessed`, which gates as material | Policy text present | The engine makes no materiality determination. |
| REQUIREMENT_SCHEMA 9.1 | Criticality predicates for security, privacy, data integrity, payments, access control, feasibility | OPEN (versioned deterministic policy) | Not computed. |
| D-07 | Acceptance of inferred requirements | OPEN | Inferred origin is shown as such; no acceptance is recorded. |
| D-06 and C-02 | Evidence verification actor policy | OPEN | Governance status is copied; verification authority is not assumed. |
| D-04 and C-08 | Reference estimate dataset and authorised historical data | OPEN | Estimate values come from AI-S08 bases; no reference data is used here. |
| D-14 | Role holders and role set for allocation | OPEN | Resource lines carry disciplines only. |
| R-1, R-2 | Ungated `run_specialist`; unsigned confirmations | OPEN (inherited) | Specialist and confirmation inputs are not authenticated here. |

## Foundation services required for authority

| Service | Needed for | Current state |
|---|---|---|
| Authoritative requirement records and revisions | Revision identity, origin, approval status | Not available; supplied as input |
| Approval workflow for SOW versions (prepare, review, approve, reject) | Any approved state | Not available; output is `pending_human_approval` |
| Approver assignment and separation enforcement | Gate F, D-05 | Not available |
| Authoritative draft persistence and audit | Version history, tamper evidence | Not available; `compare_versions` is in-memory only |
| Collection and project authorisation | Cross-project and collection isolation | Project mismatch refused; collections not modelled |
| Governance findings as authoritative records | Blocking effect on approval | Summary copied from the review |
| Estimate approval and commitment records | Any numeric commitment | Not available |
| House template renderer (authorised integration) | DOCX and PDF | Not available |

## Foundation tests

The three Foundation integration tests remain visibly skipped. They are not claimed as passed. Their environment checks have not run.
