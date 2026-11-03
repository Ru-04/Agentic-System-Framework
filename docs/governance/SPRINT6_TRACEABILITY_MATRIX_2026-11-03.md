# Sprint 6 decision-to-requirement-to-test traceability matrix (3 November 2026)

**Applies to:** contract `sprint6-e2e/v1.1` (`SPRINT6_END_TO_END_CONTRACT_v1.1_2026-11-03.md`) and register `SPRINT6_OPEN_DECISION_REGISTER_2026-11-03.md`.
**Status column:** "Not run" means no test was executed. "Recorded" means a prior recorded result exists for the stated SHA. Nothing here is declared passed.

| Decision | Requirement (contract v1.1 section) | Test ID(s) | Owner | Status |
|---|---|---|---|---|
| OPEN-01 Sprint 5 accepted | 1.1 (decision list) | Governance check: `f9d1232` ancestor of the specialist branch; deferred obligations listed in `S5C` section 4 remain on the roadmap | WDS, QA | Recorded (record exists). Ancestor check done in this session |
| OPEN-02 route path `/v1/runs/...` | 6.2, 3.2 | R-PATH-1: `POST /v1/runs/{run_id}/ai-principal` issues a principal. R-PATH-2: old path returns 404. R-PATH-3: five `/v1/ai` GET routes unchanged | Foundation | Not run. Code change not made here |
| OPEN-03 confirmation as sole authority; adapter 0.3 | 5.1, 5.2, 6.3, 8 | C-7: caller `operator_confirmed` boolean refused. A-1: adapter 0.2 envelope refused by 0.3. A-2: `actor_id` and `operator_confirmed` fields refused (`extra="forbid"`). A-3: `confirmation_ref` must bind the exact tuple. A-4: no version fallback | Specialist, AI Engine | Not run. Adapter still 0.2 |
| OPEN-04 Approver role, RBAC semantics | 3.4, 8.1, 8.5 | C-5: Approver role without project access grant refused. C-6: grant present but key absent from `permitted_actions` refused. C-5b: a request that names a role in its body is refused | Foundation | Not run |
| OPEN-05 expiry ≤ 15 min, trusted time | 8.3, 8.4 | C-3: confirmation refused after `expires_at`, checked at consume step. C-3b: expiry uses the database clock, not a request field | Foundation | Not run |
| OPEN-06 operation `specialist.execution.confirm` | 8.2, 11.3 | C-1: operation proof accepted only for this operation. Migration check: operation in `operation_proofs` CHECK; rule row present for Approver | Foundation | Not run |
| OPEN-07 separate vocabularies, explicit mapping | 10.4 | E-1: table test over all AI and adapter values. E-2: no adapter output maps to `verified`, `partially_verified` or `conflicting`. E-3: unknown value refused | AI Engine, Specialist | Not run |
| OPEN-08 `check_outcome` | 10.2, 10.3 | K-1: `SUPPORTED` requires a substantiating citation. K-2: `UNSUPPORTED` requires a limitation citation. K-3: `UNKNOWN` by default; absence of evidence is not `UNSUPPORTED` | AI Engine, Foundation | Not run |
| OPEN-09 `passage_digest`, `applies_to_edition` | 10.1, 10.3 | D-1: `passage_digest` is SHA-256 hex. D-2: `applies_to_edition` is stored and returned for family B | AI Engine, Foundation | Not run. Line B `content_hash` exists (`B-EVD`) |
| OPEN-10 `(run_id, REQ-NNN)` reference | 7 | ID-1: same `REQ-001` in two runs does not collide | AI Engine | Not run |
| OPEN-11 `workspace_id` distinct from `project_id` | 7.1, 18 (D-DEP-1) | W-1: specialist run without a validated `workspace_id` is refused, not defaulted. W-2: no global alias (`workspace_id` never equals `project_id` by default). Blocked until D-DEP-1 | Foundation | Blocked (D-DEP-1) |
| OPEN-12 seven canonical specialists | 5.3, 7 | M-1: `SpecialistId`, category and capability consistent across `S-CA`, `B-ORCH`, `B-REG`. M-2: all seven present | AI Engine | Not run |
| OPEN-13 Lineage B selected (D-4-A) | 2, 4, 5.3, 15 | LB-1: pin `0389318`. LB-2: blob identity of `foundation_ai_read.py` and imported contracts. LB-3: Line B Foundation client passes T2 and T11 | AI Engine, QA | Not run. Source-integrity check not done |
| OPEN-14 family A and B provenance | 10.1, 10.3 | P-1: family A requires Foundation source version and segment. P-2: family B requires approved external kind, `checked_at`, https `source_url` | AI Engine, Foundation | Not run |
| OPEN-15 worker initiates AI execution | 4, 5.1, 9.3 | W-3: AI principal cannot start privileged execution. W-4: only the worker role invokes the start function | Foundation | Not run. Worker adapter not built (D-DEP-2) |
| OPEN-16 status mapping, pairing rule | 9.1 | S-1: mapping table. S-2: `status = blocked_pending_decision` only with `state = blocked_pending_decision`. S-3: run `failed` only for system-level failure | Foundation | Not run. Transition function not fully read |
| OPEN-17 PW-1 writer, no HTTP write | 9.3, 11.4 | PW-1-1: no route under `/v1/ai` accepts a non-GET method (existing T9). PW-1-2: write only through the guard function executed by `webdesk_worker` | Foundation | Not run |
| OPEN-18 minimum migrations, single head | 11.3 | MG-1: single Alembic head after each revision. MG-2: isolated upgrade, downgrade one step, re-upgrade. MG-3: catalog equality. MG-4: no PUBLIC EXECUTE; `search_path` pinned | Foundation | Not run. No revision authored (D-DEP-3) |
| OPEN-19 AS as ruling 5 approver | 1.1 | Register record check: AS designation, date and channel match `GOV` section 2 | Foundation register owner | Recorded (`GOV` section 2) |
| OPEN-20 D-13 management disposition | 17 | G0 record: pytest 1031 passed, 0 failed, 0 skipped on `5974d59`. Independent QA of the final candidate | WDS, QA | Recorded (`G0` section 3). Independent QA not started |
| OPEN-21 one canonical Shopify | 5.3, 18 (D-DEP-6) | SH-1: exactly one Shopify implementation on the integration path. SH-2: Line B `ai_engine/shopify` not referenced by `registry_map` | AI Engine, Specialist | Not run |
| OPEN-22 seven in conformance; fail-closed live source | 5.3, 13 | F-1: six specialists without allowlist refuse live source access. F-2: no unapproved external source fetched. F-3: all seven run conformance | Specialist | Not run |
| OPEN-23 verification aligned to forbidden actions | 17 | T13 uses the `S-AU` forbidden list (`approve_artifact`, `grant_permission`, `modify_routing`, `accept_inferred_requirement`, `write_requirement`, `resolve_blocker`) | QA | Not run. Plan updated in v1.1 |
| OPEN-24 Phase 3 and Phase 6 states | 1.1 (recorded in register) | Record check against `FOUNDATION_INTEGRATION_P2_P7.md` rows 3 and 6 | Foundation register owner | Recorded. Phase 3 "final WDS acceptance not given"; Phase 6 "PENDING" |
| OPEN-25 audit event types | 14.2 | AU-1: each event type written with allowed fields only. AU-2: no token, hash, content, prompt or response in any row | Foundation | Not run |
| OPEN-26 scratch grants test-only | 13, 17 | G0-scope check: production role grants verified separately from the scratch cluster. No production claim | Foundation, QA | Not run. Scratch result recorded (`G0` section 2) |
| D-14 lease API, T7 | 16 | T7 (lock order probe, lease expiry, `LeaseLost`) | Foundation | Not run on current candidate |
| D-8 single head | 11.3 | MG-1 | Foundation | Not run |
| D-9 controlled environments | 13 | Environment check: production disabled in configuration | Foundation, QA | Not run |

## Summary

- **Decisions:** 26 OPEN items plus D-4-A amendment (with D-14, D-8, D-9 included as in force).
- **Recorded (evidence exists):** OPEN-01 (ancestor check), OPEN-19, OPEN-20, OPEN-24.
- **Blocked by a genuine dependency:** OPEN-11 (D-DEP-1).
- **Not run:** all other tests. No implementation test is declared passed.
- **Code and migrations owned by other teams:** OPEN-02, 03, 06, 15, 17, 18, 21, 22. Handed off. Not done in this session.
