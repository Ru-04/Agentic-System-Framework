# AI-S10 MVP Functional and Production Gap Assessment

Status: Stage 1. Severity is the author's assessment, for QA to confirm or change. No gap is marked as
closed by this document.

## 1. Functional gaps

| ID | Gap | Evidence | Severity | Route |
|---|---|---|---|---|
| FG-1 | No real intake-to-requirement path is evaluated against a live model | EXT-01 blocked (D-12) | Major | Real-provider evaluation after D-12 |
| FG-2 | Evidence sufficiency is lexical, not semantic | EVID-16 open limitation | Critical | Governance and semantic evaluation approach |
| FG-3 | Operator confirmation is unsigned and in-process | R-2; EXT-06 blocked | Major | Foundation-issued authorisation |
| FG-4 | Direct execution of specialists bypasses the gate | R-1; SEC-09 open limitation | Critical | Gate all execution paths; re-test |
| FG-5 | No durable, tamper-evident audit of runs, confirmations, refusals | SEC-18 blocked | Major | Foundation persistence |
| FG-6 | No WDS house SOW template; no DOCX or PDF export | SOW-13 blocked; D-10 | Major | Approved template and export tests |
| FG-7 | Estimates have no reference dataset; no numbers from unverified bases | D-04; EST-06 | Major (for estimates to be used) | Approved reference data |
| FG-8 | Roles and allocation not modelled beyond disciplines | D-14 | Minor | Role decision |
| FG-9 | Criticality and materiality not assessed | D-06 (`unassessed`) | Major | Predicates decision |
| FG-10 | Inferred requirement acceptance not defined | D-07 | Major | Decision |
| FG-11 | Execution envelope may read as complete when evidence is unavailable | C-15; REC-03 observation | Major | Envelope semantics decision |
| FG-12 | Requirement extraction has no executed catalogue scenario | Traceability matrix (PIPE-04 delegated) | Minor | Add scenario |

## 2. Production gaps

| ID | Gap | Evidence | Severity | Route |
|---|---|---|---|---|
| PG-1 | No production security or readiness review | EXT-04 blocked | Critical | External review after Foundation |
| PG-2 | No retention or deletion policy for evaluation data or AI outputs | D-13 | Major | WDS decision |
| PG-3 | Real-data use not approved; the engine refuses `synthetic: false` | DEC-09; `DATA_NOT_APPROVED` | Major | WDS decision |
| PG-4 | No numerical release thresholds | PENDING WDS Technical Lead | Major | WDS Technical Lead |
| PG-5 | No human UAT | EXT-03 blocked | Major | Stage D |
| PG-6 | No real-platform or vendor-documentation validation | SPEC-15, SPEC-16 blocked | Major | Source-access approval |
| PG-7 | Failure modes under production load, concurrency and network faults are not tested | Not in catalogue | Major | Load and fault tests |
| PG-8 | No deployment, operations, monitoring or rollback procedure | Not in scope of any sprint so far | Major | Post-MVP work |

## 3. What is not claimed

- No functional or production completeness. The MVP is not production-ready.
- No security control is claimed as passed where a limitation remains (R-1, R-2, EVID-16).
- No Foundation, real-provider, real-platform or human evaluation has run.
