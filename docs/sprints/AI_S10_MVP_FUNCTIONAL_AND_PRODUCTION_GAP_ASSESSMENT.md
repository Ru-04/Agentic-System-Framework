# AI-S10 MVP Functional and Production Gap Assessment (Stage 3)

Status: Stage 3. Severity is the author's assessment, for QA to confirm or change. No gap is marked closed by
this document unless the scenario column says it is proven offline.

## 1. Functional gaps

| ID | Gap | Evidence | Severity | Status after Stage 3 | Route |
|---|---|---|---|---|---|
| FG-1 | No real intake-to-requirement path against a live model | `EXT-01` blocked (D-12) | Major | Open | Real-provider evaluation after D-12 |
| FG-2 | Evidence sufficiency is lexical, not semantic | `EVID-16` open limitation | Critical | Open | Governance and semantic evaluation approach |
| FG-3 | Operator confirmation is unsigned and in-process | R-2; `EXT-06` blocked | Major | Open | Foundation-issued authorisation |
| FG-4 | Direct specialist execution bypasses the gate | R-1; `SEC-09` open limitation | Critical | Open | Gate all execution paths; re-test |
| FG-5 | No durable, tamper-evident audit | `SEC-18` blocked | Major | Open | Foundation persistence |
| FG-6 | No WDS house SOW template; no DOCX or PDF export | `SOW-13` blocked; D-10 | Major | Open | Approved template and export tests |
| FG-7 | No reference dataset; no numbers from unverified bases | D-04; `EST-06` | Major | Open (guarded) | Approved reference data |
| FG-8 | Roles and allocation not modelled beyond disciplines | D-14 | Minor | Open | Role decision |
| FG-9 | Criticality and materiality not assessed | D-06 | Major | Open | Predicates decision |
| FG-10 | Inferred requirement acceptance not defined | D-07; `REQ-08` | Major | Open (never accepted) | Decision |
| FG-11 | Execution envelope may read as complete when evidence is unavailable | C-15; `REC-03` open limitation | Major | Open | Envelope semantics decision |
| FG-12 | **Stale input rejection (spec section 8)** | `STL-05` blocked; `STL-04` proves rejection for operator selections only | Major | Open: governance decision | WDS rule; upstream change if refusal is required |
| FG-13 | **Upstream: SOW does not compare governance fingerprints** | `UD-01` open limitation (AI-S09) | Major | Open: upstream | Permitted upstream correction and re-verification |
| FG-14 | Requirement extraction against a live model | `EXT-01` | Major | Open | Real-provider evaluation |
| FG-15 | AI-S05 breadth: 130 accepted tests, 2 catalogue scenarios | Traceability matrix | Minor | Open | Extend catalogue |

Closed offline by Stage 3 (executed and passing): replay enforcement (`RPL-01`..`RPL-07`); exact-reason
negative controls (`SEC-05`, `SEC-07`, `SEC-08`, `SPEC-08`); recovery after transient failure (`REC-04`); raised
exceptions not retried (`REC-05`); AI-S01 security boundaries (`S01-01`..`S01-07`); deterministic requirement
extraction (`REQ-01`..`REQ-08`); LLM-backed intake offline (`LLM-01`..`LLM-03`); cross-project isolation
(`XP-01`..`XP-06`, `SEC-01`); identifier traceability (`TRC-01`).

## 2. Production gaps

| ID | Gap | Evidence | Severity | Route |
|---|---|---|---|---|
| PG-1 | No production security or readiness review | `EXT-04` blocked | Critical | External review after Foundation |
| PG-2 | No retention or deletion policy for evaluation data or AI outputs | D-13 | Major | WDS decision |
| PG-3 | Real-data use not approved; `synthetic: false` refused | DEC-09; `DATA_NOT_APPROVED` | Major | WDS decision |
| PG-4 | No numerical release thresholds | PENDING WDS Technical Lead | Major | WDS Technical Lead |
| PG-5 | No human UAT | `EXT-03` blocked | Major | Stage D |
| PG-6 | No real-platform or vendor-documentation validation | `SPEC-15`, `SPEC-16` blocked | Major | Source-access approval |
| PG-7 | Production load, concurrency and network-fault behaviour not tested | Not in catalogue | Major | Load and fault tests |
| PG-8 | No deployment, operations, monitoring or rollback procedure | Outside every sprint so far | Major | Post-MVP work |

## 3. What is not claimed

- No functional or production completeness. The MVP is not production-ready.
- No security control is claimed as passed where a limitation remains (R-1, R-2, EVID-16, C-15, UD-01).
- No Foundation, real-provider, real-platform or human evaluation has run.
