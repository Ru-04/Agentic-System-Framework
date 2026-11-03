# Sprint 6 OPEN decision register (3 November 2026)

**Applies to:** `docs/governance/SPRINT6_END_TO_END_CONTRACT_v1.1_2026-11-03.md` (contract `sprint6-e2e/v1.1`).
**Supersedes:** the OPEN list in contract `sprint6-e2e/v1` (commit `2a46503`). That list stays as the historical record and is not edited.

## 0. Approval record

| Field | Record |
|---|---|
| Approving authority | WDS Authorized Approver, identified by role only. No personal name was supplied, and none is recorded here |
| Channel | Formal WDS directive "FORMAL APPROVAL OF SPRINT 6 OPEN DECISIONS", pasted by the requesting user into this Claude Code session |
| Date | 3 November 2026 (session date; the pasted directive states no separate date) |
| Nature | Recorded **as reported**. This is not a signed approval, not a personal signature, and not independent QA. No approval was backdated |
| Scope | OPEN-01 to OPEN-26, and the D-4 amendment in section 2 |

The directive also says: "Do not ask me to approve the same decisions again." Items below are therefore recorded as decided, not as pending.

## 1. Resolution table

Status key. **Decided**: the approved choice is recorded in v1.1. **Handoff**: the choice is recorded, but the implementation belongs to an owner team and is not done in this session. **Verified-here**: a fact the decision depends on was checked in this session.

| ID | Approved resolution (summary) | Contract v1.1 section | Owner for implementation | Status | Verified-here facts (source) |
|---|---|---|---|---|---|
| OPEN-01 | Sprint 5 formally accepted under its WDS-approved revised MVP scope, on the latest verified closure records (`f9d1232` and any later valid successor). Deferred obligations preserved | 1.1, 18 | None | Decided | `f9d1232` is an ancestor of `claude/sprint5-specialist-evaluations` (`05b03e8`). Its §4 lists deferred and superseded obligations. Commit `608cf97` (Sprint 7/8 dependency audit) is not a closure successor |
| OPEN-02 | Canonical AI-principal route is `POST /v1/runs/{run_id}/ai-principal`, with revoke at `/ai-principal/revoke` under the same `/v1` prefix. Surgical code change and regression tests authorized | 6.2 | Foundation team (`src/webdesk/api/ai.py`, `app.py`) | Decided. **Handoff** | Code mounts at `/runs/{run_id}/ai-principal` (`ai.py` lines 268 and 296). Other human routes also lack `/v1` (`routes.py`). Change only the AI-principal routes; leave the others |
| OPEN-03 | Foundation-issued, trusted, single-use, operation-bound confirmation is the sole authority for specialist execution. Adapter v0.3 approved as an explicit breaking change | 5.1, 6.3, 8 | Specialist team (adapter) and AI Engine team (caller). Foundation issues the confirmation | Decided. **Handoff** | Adapter 0.2 takes caller `operator_confirmed` and `actor_id` (`adapter_v02.py` lines 54, 61). Line B already records operator choice as an attributed claim, not authority (`ai_engine/.../selection/operator.py` header) |
| OPEN-04 | Authorized Foundation `Approver` role. RBAC semantics to be verified; role name supplied by a caller grants nothing | 8.5 | Foundation team | Decided. **Handoff** | `matrix.py` line 25 (`APPROVER`). Approver rules are `GRANTED`: role assignment **and** an active project access grant whose `permitted_actions` contains the key (module header, cell rules). Database rule table is `operation_authorization_rules` (`0041` pattern) |
| OPEN-05 | Confirmation validity at most 15 minutes, enforced with authoritative trusted time | 8.4 | Foundation team | Decided. **Handoff** | Existing AI principal TTL uses a database CHECK and `now()` (`0041` line 145). Use the database transaction clock. `webdesk_test_clock` is test-only (`0046`) and must not be the authority in production |
| OPEN-06 | Canonical operation `specialist.execution.confirm`. Only the necessary migration changes | 8.2, 11.3 | Foundation team | Decided. **Handoff** | `operation_proofs` CHECK list is in migrations `0039` and `0042` (`0042` line 230 shows the pattern). Adding the operation needs one revision |
| OPEN-07 | Keep AI and adapter evidence vocabularies separate, with explicit validated mappings | 10.4 | AI Engine and Specialist teams | Decided | AI `EvidenceStatus` (`contracts.py` lines 35 to 41, Line A; `common.py` lines 150 to 155, Line B). Adapter `cited`, `unverified` (`adapter_v02.py` line 68). Mapping in v1.1 section 10.4 |
| OPEN-08 | New `check_outcome` with `SUPPORTED`, `UNSUPPORTED`, `UNKNOWN`. Rules in section 10.2. Kept separate from citation relevance | 10.2, 10.3 | Foundation team (storage) and AI Engine team (production of the value) | Decided | No approved text defined these values before this decision (v1 OPEN-08) |
| OPEN-09 | `passage_digest` and `applies_to_edition` approved for external evidence | 10.3 | Foundation (storage), AI Engine (production) | Decided | Line B `EvidenceReference.content_hash` (Sha256Hex) exists in `contracts/evidence.py` lines 44 to 66, on `0389318`. No `edition` field exists in any ref |
| OPEN-10 | Run-scoped requirement reference `(run_id, REQ-NNN)` until a separate persisted ID scheme is approved | 7 | AI Engine team | Decided | `REQ-NNN` pattern (`contracts.py` line 27, Line A) |
| OPEN-11 | `workspace_id` and `project_id` stay distinct. Relationship and authorization validated through Foundation. No global alias | 7 | Foundation team | Decided. **Handoff** | No `workspace` table or column exists in any Foundation migration on `5974d59`. The relationship therefore cannot yet be validated. Foundation must define the scope entity (dependency D-DEP-1 in section 4 of v1.1) |
| OPEN-12 | All seven canonical `SpecialistId` values, explicit mappings to AI Engine categories and `CAP-*` capabilities. Missing categories included | 5.3, 7 | AI Engine team (registry) | Decided | Line B `orchestration/registry_map.py` (on `0389318`) lists seven categories and matching `CAP-*` IDs. The category IDs differ from Line A (for example `three_d_cart_shift_shopify_specialist`) |
| OPEN-13 | **WDS selects AI Engine Lineage B** (anchored at `0389318`) as the intended Sprint 6 authoritative engine. Amends D-4 (section 2). Subject to source integrity, final contract compatibility and verification | 2, 4, 5.3, 15 | AI Engine team | Decided. **Handoff** | Line B tree exists at `0389318`: `ai_engine/src/ai_engine/{adapters,selection,routing,specialists,orchestration,...}`. Line B's Foundation client sends `AI-Principal` and `X-AI-Contract-Version` (`adapters/foundation_ai_read.py` lines 178 to 179). Source-integrity conditions are in section 2.3 |
| OPEN-14 | Foundation source citations use family A. External documentation citations use family B. Both need provenance | 10.1, 10.3 | Foundation (A), AI Engine (B) | Decided | `SourceReference` (Line A `contracts.py` line 135). Line B `EvidenceReference` carries `source_url`, `source_id`, `source_version`, `checked_at`, `publisher` (`evidence.py`) |
| OPEN-15 | A Foundation worker initiates authorized AI execution. AI must not authorize its own privileged execution | 4, 5.1, 9.3 | Foundation team | Decided. **Handoff** | Line A and Line B both have injected transports and no transport in the integration (`client.py` docstring; Line B `foundation_ai_read.py` header). The worker adapter does not exist yet |
| OPEN-16 | Approve the status mapping in v1 section 9.1 after checking exact values against the Foundation run lifecycle. Preserve terminal and failure semantics | 9.1 | Foundation team | Decided, **with corrections** | `0007` lines 77 to 90 (state and status CHECK). `blocked_pending_decision` status requires state `blocked_pending_decision` (`0007` line 97). Run-level `failed` is reserved for system-level failures (`REQUIREMENT_SCHEMA.md` line 77). Corrections in v1.1 section 9.1 |
| OPEN-17 | PW-1 approved. Foundation worker persists integration results with restricted authority. No public HTTP write route | 9.3, 11.4 | Foundation team | Decided. **Handoff** | `webdesk_worker` role and its EXECUTE grant pattern (`0031` lines 8 and 15). No write route exists |
| OPEN-18 | Minimum new migration revisions beyond `0059`. Single Alembic head. Each verified on isolated PostgreSQL, with security and backward-compatibility checks | 11.3 | Foundation team | Decided. **Handoff** | Head is `0059_int_mark_inputs_fence` on `5974d59` (`APP` section B, `G0` section 3). The revision list is in v1.1 section 11.3 and is not yet authored |
| OPEN-19 | AS recorded as the WDS-designated ruling 5 approver under D-10. No invented signature or personal approval | 1.1 | Foundation register owner | Decided | `GOV` section 2: approver AS, designated by WDS management, date 2 Nov 2026, channel WDS management confirmation through Claude Code, 3 Nov 2026. "Not a personal signature" |
| OPEN-20 | D-13 management disposition recorded: PG's reported PASS accepted for `5974d59`, with the narrow personal-attestation exception. Mandatory security tests and final integration QA preserved | 17 | Foundation team and WDS | Decided | `GOV` section 1 and `APP` section A. `G0` section 3: pytest 1031 passed, 0 failed, 0 skipped. `G0` section 5: development-team run, not independent QA |
| OPEN-21 | One canonical Shopify implementation: `src/webdesk/specialists/platforms/shopify.py`, subject to confirming source and compatibility. No duplicates | 5.3, 16 | Specialist team (confirm), AI Engine team (re-point registry) | Decided. **Handoff** | Canonical file blob `f5123bac8a` on `05b03e8`. Line B's `ai_engine/src/ai_engine/shopify/agent.py` is a duplicate and must not be on the integration path. Line A has `src/webdesk_ai/specialists/shopify.py` |
| OPEN-22 | All seven specialists supported in adapter conformance and authorized integration-test paths. No unapproved external documentation sources. Source-dependent live execution fail-closed until exact permissions are approved | 5.3, 13 | Specialist team | Decided | Only Shopify has approved source entries (`DSC-03` section 8). Live execution for others is refused |
| OPEN-23 | Verification plan aligned with the actual forbidden-action list. Tests added without weakening protections | 17 | QA owner | Decided | `authority.py` lines 27 to 35 (`FORBIDDEN_ACTIONS`). The discovery list (`route`, `accept`) is replaced |
| OPEN-24 | Record Phase 3 and Phase 6 states from genuine existing evidence. No inferred acceptance, no invented approval | 1.1 | Foundation register owner | Decided | `FOUNDATION_INTEGRATION_P2_P7.md` table rows 3 and 6 (`5974d59`): Phase 3 "final WDS acceptance not given"; Phase 6 "WDS formal acceptance PENDING". The Phase 9 commit `356fb3c` claim is not adopted |
| OPEN-25 | Audit event types in v1 section 14.2 approved, subject to compatibility with existing audit and security rules | 14.2 | Foundation team | Decided | No `event_type` CHECK constraint found in any migration on `5974d59` (static grep). The event names therefore need no migration on that basis. Existing `ai.read.*` rows unchanged |
| OPEN-26 | Scratch PostgreSQL grants accepted strictly as test-only. Production least privilege preserved and the required grants verified separately | 17 | Foundation team | Decided. **Handoff** | `G0` section 2. The grants are not production configuration |

## 2. D-4 amendment (historical record preserved)

### 2.1 Original decision (not altered)

- **D-4, original (2 Nov 2026):** "Approve as recommended": AI Engine target line A (`claude/ai-engine-contract-alignment-834e49` at `967d895`) for step 2; line B waits for a parity record. Source: `SPRINT6_STAGE0_STAGE1_RECORD_2026-11-02.md` (blob `c706b4dc20`, branch `claude/sprint5-specialist-evaluations`, commit `05b03e8`), section "WDS decision recorded (2 November 2026)".
- **D-4, governance matrix (3 Nov 2026, before this directive):** "AI Engine line A for step 2. Engine selection still required." Source: `SPRINT6_GOVERNANCE_RECORDS_2026-11-03.md` section 4 (blob `7902b7f195`).

### 2.2 Amendment D-4-A (3 November 2026)

- **Decision:** WDS selects **AI Engine Lineage B**, anchored at historical candidate `0389318` (`integration/ai-s01-s02-s03`), as the intended authoritative engine for Sprint 6. This **amends** D-4 and supersedes the line A target for Sprint 6 integration.
- **Approver, channel, date:** as section 0.
- **Preserved:** the original D-4 text above stays in the record. Line A remains on its branch and is not deleted. The ARCH-03 rule (no early deletion) still applies.
- **Not implied:** this decision does not approve Line B's merge into the candidate. It sets the target. Section 2.3 lists the conditions that must hold before any merge.

### 2.3 Source-integrity and compatibility conditions for Lineage B

These are required before any Line B code enters the integration. Each has an owner.

1. **Pin.** The integration uses the exact SHA `0389318`. Any later Line B commit needs a new compatibility review (AI Engine team).
2. **Blob identity.** The Foundation read client `ai_engine/src/ai_engine/adapters/foundation_ai_read.py` and the contract files it imports are checked against the contract (AI Engine team).
3. **Shopify re-point.** `registry_map.py` must point the Shopify category at the canonical adapter-governed module (OPEN-21). The Line B `ai_engine/shopify` path must not run in integration (AI Engine team).
4. **Foundation client conformance.** The Line B client must satisfy the same contract tests as the Foundation side (T2, T11 in the test register). This is a test run, not done here (QA owner).
5. **Mismatch note.** Line B's `ai_engine` root differs from the `webdesk_ai` root of Line A. Packaging and import paths change accordingly (AI Engine team).

## 3. Reconciliations (contradictions resolved, not historical approvals invented)

| Contradiction | Resolution | Source of the resolution |
|---|---|---|
| D-4 line A (2 Nov) versus line B (3 Nov directive) | Amendment D-4-A, with original preserved | Section 2 |
| OPEN-04 "role" versus RBAC `GRANTED` semantics | Confirmation requires role **and** project access grant with the operation key | `matrix.py` cell rules |
| Run status `blocked_pending_decision` in the v1 mapping | Status and state must both be `blocked_pending_decision` | `0007` line 97 |
| Shopify: two implementations (Line A, Line B) plus the canonical adapter module | One canonical module, others not on the integration path | OPEN-21 |
| Sprint 5 acceptance (2 Nov "not accepted" versus 3 Nov closure) | Closure record `f9d1232` governs; 2 Nov statement superseded for Sprint 5 status only | OPEN-01 |
| D-13 technical gate (3 Nov management record versus later G0 record) | Disposition recorded as in OPEN-20 | `GOV` section 1, `APP` section A, `G0` section 5 |

## 4. Items not closed by this register (genuine dependencies)

- **D-DEP-1 Workspace entity.** OPEN-11 cannot be fully validated until Foundation defines how `workspace_id` relates to `project_id`. No such table exists on `5974d59`.
- **D-DEP-2 Worker adapter.** OPEN-15 and OPEN-17 need a Foundation worker that calls the AI Engine. No such code exists on any ref checked.
- **D-DEP-3 Migrations authored.** OPEN-06 and OPEN-18 are decided, but no revision file exists. Each needs an isolated PostgreSQL run before it counts.
- **D-DEP-4 Adapter 0.3 implementation.** OPEN-03 is decided, but the adapter code is still 0.2.
- **D-DEP-5 Line B verification.** OPEN-13 is decided, but no test was run on Line B in this session.
- **D-DEP-6 Canonical Shopify source.** OPEN-21 is decided, but the canonical module is on the sprint 5 branch and must be merged or referenced through an approved step.

No implementation test is declared passed by this register. A decision being approved does not mean the code exists.
