# Sprint 6 End-to-End Integration Contract, v1 (3 November 2026)

**Contract identifier:** `sprint6-e2e/v1`
**Status: PROPOSED. NOT APPROVED.** This document is the single end-to-end contract that WDS directive D-2 (amended 3 November 2026) requires. Its approval is a separate WDS act. Until WDS approves it, no engineering on the integration may start against it, and nothing in it is an approved endpoint, table, role or value unless the text says so.
**Scope:** WebDesk Foundation, the AI Engine, and the seven Specialist Agents, as the code stood on the refs in section 0.
**Authoring basis:** read-only analysis. No `src/`, `tests/` or `migrations/` file was changed. No test, migration or database command was run.

---

## 0. Citation rule and source key

Every claim cites a bracketed source key. Each key resolves to one file path at one commit SHA, and the blob SHA is given where a file was read directly. Keys with a line number point to that line at that SHA. Where a claim relies on a discovery file, the key names the file under `docs/integration-contract/`, and the SHA is that branch's head, not the analysis base.

| Key | File (path) | SHA read | Blob (first 10) |
|---|---|---|---|
| APP | `docs/governance/SPRINT6_WDS_APPROVALS_2026-11-03.md` | `05b03e8` (branch `claude/sprint5-specialist-evaluations`) | `85b24b7d94` |
| GOV | `docs/governance/SPRINT6_GOVERNANCE_RECORDS_2026-11-03.md` | `05b03e8` (last changed `889c143`) | `7902b7f195` |
| S01 | `docs/governance/SPRINT6_STAGE0_STAGE1_RECORD_2026-11-02.md` | `05b03e8` (last changed `e901e29`) | `c706b4dc20` |
| S5C | `docs/governance/SPRINT5_FINAL_CLOSURE_RECORD_2026-11-03.md` | `05b03e8` (last changed `f9d1232`); lines 1 to 40 only | `af46f2a22c` |
| DSC-NN | `docs/integration-contract/NN-*.md` (00 to 10) | `9ca38ba` (branch `claude/integration-contract-discovery-cdfe14`); analysis base `6c458c8` | 10 = `6cf470d332` |
| AICON | `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` | `5974d59`; identical at `967d895` and `3a38685` | `b887777051` |
| F-AI | `src/webdesk/api/ai.py` (Foundation) | `5974d59`; identical at `3a38685` | `7e5c7d0b1a` |
| F-0041 | `migrations/versions/0041_ai_read_v1.py` | `5974d59` | `4e1ca62932` |
| F-APP | `src/webdesk/api/app.py` | `5974d59` | `294d75a46a` |
| F-RT | `src/webdesk/api/routes.py` | `5974d59` | `4e9dfecadd` |
| F-JOBS | `src/webdesk/runs/jobs.py` | `5974d59` | `049418965e` |
| F-RBAC | `src/webdesk/rbac/matrix.py` | `5974d59` (Role enum lines 22 to 26) | not recorded |
| F-INT | `docs/FOUNDATION_INTEGRATION_P2_P7.md` | `5974d59` | `74efe0614d` |
| F-R4 | `WebDesk_Agentic_Requirement_Platform_Specs/PHASE1_R4_OPTION_A_IMPLEMENTATION_CONTRACT.md` | `5974d59` | `1aceadd1ef` |
| R-SCH | `WebDesk_Agentic_Requirement_Platform_Specs/REQUIREMENT_SCHEMA.md` | `5974d59` | `add34264d9` |
| R-REG | `WebDesk_Agentic_Requirement_Platform_Specs/AGENT_REGISTRY.yaml` | `5974d59` (lines 398, 407 cited) | not recorded |
| F-IDEM | `src/webdesk/idempotency/service.py` | `5974d59` | not recorded |
| F-0007 | `migrations/versions/0007_intake_and_execution.py` | `5974d59` (line 114) | not recorded |
| A-CT | `src/webdesk_ai/contracts.py` (AI Engine line A) | `967d895` | `e4bdbf7d0f` |
| A-CL | `src/webdesk_ai/foundation/client.py` | `967d895` | `92d614a726` |
| A-OR | `src/webdesk_ai/orchestration.py` | `967d895` | `00f345c1ec` |
| A-BA | `src/webdesk_ai/specialists/base.py` | `967d895` | `41dc211c2a` |
| A-CA | `src/webdesk_ai/catalog.py` | `967d895` | not recorded |
| A-MO | `src/webdesk_ai/models.py` | `967d895` | `fa243f40dd` |
| A-SH | `src/webdesk_ai/specialists/shopify.py` | `967d895` | not recorded |
| S-AD | `src/webdesk/specialists/adapter_v02.py` (adapter 0.2) | `05b03e8`; identical at `027f352` | `68ea439537` |
| S-CT | `src/webdesk/specialists/contract.py` (contract 1.0.0) | `05b03e8` | `4786470bb2` |
| S-AU | `src/webdesk/specialists/authority.py` | `05b03e8` | `d5364f9cc3` |
| S-CA | `src/webdesk/specialists/catalog.py` | `05b03e8` | `3f1b40d01b` |
| S-ER | `src/webdesk/specialists/errors.py` | `05b03e8` | `fcbbfdcad0` |
| S-WS | `src/webdesk/specialists/workspace.py` | `05b03e8` | `7352266a23` |
| S-HA | `src/webdesk/specialists/harness.py` | `05b03e8` | `e20837f8f5` |
| S-DR | `docs/governance/DECISION_RECORD_2026-10-22.md` (D07, line 19) | `05b03e8` | `b8b886c509` |
| S-MDR | `docs/governance/MANAGEMENT_DECISION_REGISTER_2026-10-26.md` (ARCH-01 to 03, INT-01, INT-02) | `05b03e8` | `2c96f1e6c7` |
| S-ADR | `docs/governance/ARCHITECTURE_DECISION_RECORD_2026-10-26.md` | `05b03e8` | `95d2e47157` |
| S-PROP | `docs/governance/ADAPTER_CONTRACT_PROPOSAL_2026-10-26.md` | `05b03e8` | `779a5fbd93` |

Refs used as the integration baseline (section 2): Foundation candidate `5974d59` (`feature/foundation-integration-p2-p7`, one commit past `6c458c8`; ancestor of `5974d59` is `3a38685`); Foundation main `3a38685` (`feature/increment-1-foundation`); AI Engine line A `967d895` (`claude/ai-engine-contract-alignment-834e49`); specialist branch `claude/sprint5-specialist-evaluations` at `05b03e8`.

**Discovery files:** the discovery set [DSC-00] to [DSC-10] was read at its head `9ca38ba`. Its analysis base was `6c458c8`, which is an ancestor of `5974d59`. The candidate moved only by `5974d59` (commit "record ruling 5 and the verified delta review of 6c458c8"), which changes `docs/FOUNDATION_INTEGRATION_P2_P7.md` only. [DSC-01] and [DSC-03] therefore describe the pre-`5974d59` candidate. Their Foundation line-level claims were re-checked where this contract depends on them.

---

## 1. Authority, scope and what this contract is not

### 1.1 In-force decisions this contract implements

| Decision | Status and source | Effect on this contract |
|---|---|---|
| D-1 `ai-read/v1` | Approved for read-only, non-production; approver/date/channel for D-AI-1 to D-AI-5 not recorded in the repository [APP §D], [GOV §3] | Foundation to AI read surface is fixed by [AICON] |
| D-2 | Amended: one versioned end-to-end contract, covering the 14 areas in the directive [APP §E], [GOV §4] | This document. Sections 3 to 16 map one-to-one to the 14 areas |
| D-3 | Adapter v0.2 for isolated development and conformance only [APP §E], [GOV §4] | Adapter v0.2 [S-AD] is the only specialist envelope in code. It is not approved for Foundation connection |
| D-4 | AI Engine line A for step 2; engine selection still required [GOV §4] | Line A is the baseline in this contract. Line B is excluded (OPEN-13) |
| D-5 | **Amended:** AI recommends, operator confirms, trusted authorization verified, approved specialist executes [GOV §4] | Sections 5 and 8 |
| D-6 | Unchanged: no Foundation credential for specialists; actor derived from session proof [GOV §4], [S01 D-6] | Section 3.3 |
| D-7 | **Amended:** minimum secure persistence for findings, evidence, citations, digests, applicability, status and audit; least privilege; workspace isolation [GOV §4] | Sections 9 to 11. Design is PROPOSED |
| D-8 | **Amended:** minimum additional migrations required by the contract; single Alembic head; head remains `0059` until then [GOV §4] | Section 11.3. No migration is approved by this document |
| D-9 | **Amended:** specialist execution in controlled development and integration environments only; production stays disabled [GOV §4], [APP §E] | Sections 5 and 13 |
| D-10 | Ruling 5 confirmed by AS (2 Nov, relayed 3 Nov); register entry not yet updated [GOV §2] | Dependency; OPEN-19 |
| D-13 | Management exception to the personal review record for `5974d59` only; independent QA of the final Sprint 6 candidate not started [APP §A, §F] | Gate in section 17 |
| D-14 | `runs/jobs.py` lease API approved, test T7 required [S01 D-14] | Section 16 |

### 1.2 In scope

- The Foundation to AI Engine read path (`ai-read/v1`), already approved, and the human routes that issue and revoke AI principals.
- The AI Engine's execution responsibilities, as built on line A.
- Specialist routing and invocation, as amended by D-5 and D-9.
- The persistence minimum required by D-7 (amended), as a proposal.

### 1.3 Out of scope (not approved and not defined here)

- Production deployment, hosting, external model transmission (contract [AICON] section 13A; readiness items C-1 to C-21 in `docs/FOUNDATION_PRODUCTION_READINESS_ASSESSMENT.md`).
- Any live model provider. Line A ships a scripted model only ([A-MO] lines 4 to 5 and line 192: `provider` defaults to `scripted`; no API key is read).
- Specialist live execution against live vendor data.
- Phase 8 and Phase 9 documentation branches [DSC-09 D-15].
- Any AI write path beyond the proposal in section 9. D-AI-4 in [AICON] section 2 requires a separate, independently enforced write contract.

---

## 2. As-built component inventory

| Component | Ref and source | What exists in code | What does not exist |
|---|---|---|---|
| Foundation | `5974d59` [F-AI], [F-APP], [F-0041] | Five `GET /v1/ai/...` routes; two human POST routes for principal issue and revoke; `ai_principals` table with TTL CHECK ≤ 15 minutes and one live principal per run ([F-0041] lines 135 to 148); `fn_issue_ai_principal_with_proof` and `fn_ai_resolve` (per [DSC-05 §1.5]) | Any requirement, evidence, citation, finding or analysis-result table (migration table list, `5974d59`: no such table); any specialist or operator-confirmation table; any `workspace` table |
| AI Engine, line A | `967d895` [A-CT], [A-CL], [A-OR], [A-BA], [A-MO], [A-CA] | Pydantic common contracts with `extra="forbid"`; `FoundationReadClient` with an injected transport; `run_workflow` stage graph; `route_requirements` (recommendations only); `run_specialist` with a separate process and a timeout; scripted model | A transport that reaches Foundation (the client docstring says none ships in this increment, [A-CL] lines 1 to 10); a provider; any persistence |
| AI Engine, line B | `15d660a`, `0389318` [DSC-01 §B] | Separate `ai_engine/` package with its own Foundation read adapter | Excluded from this contract (OPEN-13) |
| Specialist adapter | `05b03e8` / `027f352` [S-AD], [S-HA], [S-AU], [S-CA] | Adapter 0.2 envelope; `call_adapter`; capability resolution; action allowlist; harness contract 1.0.0; declaration-only authority check | Operator confirmation produced by a Foundation proof path (`operator_confirmed` is a caller boolean, [S-AD] line 61); actor from proof (`actor_id` is a caller string, [S-AD] line 54); run-time enforcement of authority (QA-07, [DSC-03 §10]) |
| Specialists (seven) | [S-CA] `SpecialistId` (seven values); [A-CA] (five descriptors, Shopify the only implementation) | Shopify on both lines; six platform modules on the specialist branch under `src/webdesk/specialists/platforms/` | Approved source allowlists for six of seven specialists ([DSC-03 §8]); a live execution path (blocked by D-9) |

**Contract-level gap that makes this an integration design rather than a wiring task:** no approved text specifies how the AI Engine is started, how its requests reach Foundation at runtime, or how a specialist result reaches a Foundation record. OPEN-15 and OPEN-17.

---

## 3. Foundation identity and authorization ownership (area 1)

### 3.1 Human identity

- Foundation owns human identity and sessions. Every human route requires `Authorization: Bearer <session token>`. The actor comes from the session, never from the request body [F-RT] (module docstring, line 3).
- Sessions are validated only by the trusted authentication authority. Without it every request is refused [F-APP] (lines 30 to 31).
- Privileged mutations are authorized by operation proofs. The actor is derived from authenticated proof bound to a session and a scoped operation and resource. A parameter or a mutable GUC is not proof [F-R4] (decision line 3; rule 2 at line 12). Proof issuance and consumption are owned by Foundation SQL functions. The proof-issue function is defined in migration 0039 and carried into the AI migration at [F-0041] line 69.

### 3.2 AI principal

Owner: Foundation. Source: [AICON] sections 3 to 5, implemented in [F-AI] and [F-0041].

- Issued only by the human route `ai.principal.issue` with a proof whose resource is the run's project, for role `Analyst` with membership required ([AICON] section 3.1; [F-0041] operation rule insert).
- Revoked by the human route `ai.principal.revoke` ([AICON] section 4).
- Bound to one project, one run and one human (`bound_user_id`). Never an Administrator, never a human, never holds an operation proof ([AICON] section 2 D-AI-1).
- Verified on every request in PostgreSQL: not revoked, `now() < expires_at`, run status active, project active, bound human active and with read right ([AICON] section 3.2).
- TTL 15 minutes, enforced by a CHECK constraint ([F-0041] line 145).

### 3.3 Specialist identity (D-6)

- A specialist holds no Foundation credential and no AI principal ([GOV §4] D-6; [S01] D-6).
- `actor_id` in every specialist envelope is derived by WebDesk from the authenticated session proof and never supplied by the caller ([GOV §4] D-6; [F-R4] line 12).
- Current code does not meet this. [S-AD] line 54 takes `actor_id` as a caller `NonBlank` string. This is a required change, and it is listed in section 15 as adapter 0.3 (proposed). The mechanism for deriving it is an engineering choice to be tested by T14 ([DSC-07 T14]).

### 3.4 Authorization ownership matrix

| Concern | Owner | Enforced by |
|---|---|---|
| Human session | Foundation authority | Foundation session check [F-RT] |
| Project and run read rights | Foundation | PostgreSQL functions, every request [AICON] §3.2, §5 |
| AI principal lifecycle | Foundation | Authority and guard functions [F-0041] |
| Operator confirmation of a specialist run | Foundation (proposed, section 8) | PostgreSQL proof and a Foundation-issued confirmation record |
| Specialist action allowlist | WebDesk adapter | Declaration check only, not run-time ([S-AU] lines 4 to 7; QA-07) |
| Routing | WebDesk (`routing authorization` in ARCH-02, [S-MDR] line 12) | Operator confirmation plus adapter check. Routing itself is not implemented |

---

## 4. AI Engine execution responsibilities (area 2)

The AI Engine is a consumer. It holds one credential, the AI principal, and reads through `ai-read/v1` only ([AICON] principle 1; [A-CL] docstring). Its responsibilities on line A are:

1. **Read.** Fetch run metadata, project metadata, readable source versions, segments and content, through `FoundationReadClient` only ([A-CL] lines 1 to 10; response limits in [AICON] section 6). The client refuses a response whose contract header differs ([A-CL] `CONTRACT_HEADER`, `RESPONSE_CONTRACT_HEADER`, lines 27 to 29).
2. **Analyse.** Run `run_workflow` ([A-OR] line 127): analysis stage, clarification stage, routing recommendation stage, specialist stage, review package.
3. **Recommend routing.** `route_requirements` ([A-BA] line 97) emits `RoutingRecommendation` values with `RoutingOutcome` in {selected, not_selected, clarification_needed, unsupported, unavailable} ([A-CT] lines 96 to 102). The registry sets `machine_routing_enabled: false` ([A-BA] line 3). Recommendations never start work.
4. **Invoke specialists, but only for authorized categories.** Line A runs a category only if it is in `WorkflowConfig.authorized_categories` ([A-OR] lines 103 and 219). **This is a caller-supplied configuration, not an operator confirmation.** It conflicts with D-5 and is OPEN-03. Under this contract, the authorization for each specialist invocation must come from the Foundation confirmation record in section 8.
5. **Run each specialist bounded.** `run_specialist` runs the specialist in a separate process with a wall-clock bound and a per-execution nonce ([A-BA] lines 243 to 262). Default bound: 10 seconds ([A-OR] line 106). Failures become a status, never a partial output.
6. **Return a review package.** The result is a `ReviewPackage` with `sow_published: false`, `foundation_writes: 0`, `machine_routing_enabled: false` ([A-OR] lines 80 to 82). It is a proposal for a human.
7. **Model.** A scripted model is the only adapter ([A-MO] line 192). Live model execution is disabled by the adapter contract ([S-MDR] INT-02; [S-AD] docstring). Any provider is blocked until WDS approves one ([A-MO] lines 4 to 5).

**Not an AI Engine responsibility:** approving a requirement, committing an estimate, publishing scope, writing to Foundation, deciding governance status ([A-OR] lines 9 to 10; [AICON] §14).

---

## 5. Specialist routing and invocation (area 3)

### 5.1 Required flow (D-5, amended)

```
1. AI Engine      produces RoutingRecommendation (proposal, non-executing)            [A-BA] route_requirements
2. Operator       confirms the recommendation through a Foundation human route        section 8 (PROPOSED)
3. Foundation     verifies the operator proof, the binding and the expiry             section 8
4. Foundation     issues one single-use confirmation reference for that invocation    section 8
5. Adapter        refuses unless the reference is valid for this exact envelope      section 6.3 (adapter 0.3, PROPOSED)
6. Harness        runs the approved specialist, bounded, with actor from proof       [S-HA], [A-BA] run_specialist
7. Result         returns to Foundation as a proposal, never as an approved record    section 9
```

Step 2 is a human decision and must not be automated. Step 6 runs only in a controlled development or integration environment (D-9). Live model execution stays disabled ([S-MDR] INT-02).

### 5.2 Current code against this flow

- `call_adapter` refuses when `operator_confirmed` is false ([S-AD] lines 133 to 136). It trusts the caller's boolean when true. This does not meet D-5. Breaking change: section 15.
- `resolve_capability` maps a specialist to one canonical capability ID ([S-AD] lines 92 to 102, [S-CA]).
- `check_allowed_actions` refuses forbidden and unknown actions, and any action the provider did not declare ([S-AD] lines 104 to 118).
- The forbidden list is `approve_artifact`, `grant_permission`, `modify_routing`, `accept_inferred_requirement`, `write_requirement`, `resolve_blocker` ([S-AU] lines 27 to 35). This is a declaration check, not run-time enforcement (QA-07).

### 5.3 Catalog and invocation coverage

| Specialist (`SpecialistId`, [S-CA]) | Capability ID, [S-CA] | AI Engine descriptor, [A-CA] | Implementation on line A | Approved source allowlist |
|---|---|---|---|---|
| `shopify` | `CAP-ECOMMERCE` | `shopify_specialist` | Yes ([A-SH]) and on the specialist branch | Shopify entries only ([DSC-03 §8]) |
| `shift4shop` | `CAP-3D-CART-SHIFT-SHOPIFY` | `3dcart_shift4shop_specialist` | No (descriptor only) | None |
| `wordpress_woocommerce` | `CAP-WORDPRESS-WOOCOMMERCE` | `wordpress_woocommerce_specialist` | No | None |
| `bigcommerce` | `CAP-BIGCOMMERCE` | `bigcommerce_specialist` | No | None |
| `magento_adobe_commerce` | `CAP-MAGENTO-ADOBE-COMMERCE` | `magento_adobe_commerce_specialist` | No | None |
| `standalone_applications` | `CAP-STANDALONE-APPLICATIONS` | not present | No | None |
| `middleware_applications` | `CAP-MIDDLEWARE-APPLICATIONS` | not present | No | None |

Identifier mismatch: OPEN-12. Source allowlists for six specialists: OPEN-22. The table shows that no specialist other than Shopify can be invoked on any line, and that invocation for six of seven is blocked by OPEN-22 even after OPEN-12 is resolved.

### 5.4 Routing rules that are approved and must hold

- A specialist is never selected by the specialist itself. Routing changes are forbidden to specialists ([S-AU] `modify_routing`).
- AI may recommend. An authorized WDS operator confirms before execution ([S-DR] D07, line 19).
- Routing itself is Sprint 6 work ([S-DR] D07; [DSC-02 C5]). This section is the proposal for it. It is not approval.

---

## 6. Request and response schemas (area 4)

### 6.1 Foundation to AI Engine, `ai-read/v1` (APPROVED)

Five `GET` endpoints, each with `Authorization: AI-Principal <token>` and `X-AI-Contract-Version: ai-read/v1` ([AICON] section 6; [F-AI] lines 91 to 100 check both). Response shapes are in [AICON] section 6.1. Their field lists are not repeated here.

| # | Method and path | Response | Source |
|---|---|---|---|
| 1 | `GET /v1/ai/runs/{run_id}` | `contract, run_id, project_id, state, status, revision, is_stale, failure_class, created_at, updated_at` | [AICON] §6.1; [F-AI] line 323 |
| 2 | `GET /v1/ai/runs/{run_id}/project` | `contract, project_id, name, data_classification, status, revision` | [AICON] §6.1; [F-AI] line 352 |
| 3 | `GET /v1/ai/runs/{run_id}/source-versions` | `contract, items[], next_cursor` | [AICON] §6.1; [F-AI] line 376 |
| 4 | `GET /v1/ai/runs/{run_id}/source-versions/{source_version_id}/segments` | `contract, source_version_id, items[], next_cursor` | [AICON] §6.1; [F-AI] line 413 |
| 5 | `GET /v1/ai/runs/{run_id}/source-versions/{source_version_id}/content` | Stored bytes, `Content-Type` = stored MIME, at most 10 MiB | [AICON] §6; [F-AI] line 457 |

No other AI route exists in v1. Any other method returns 405 ([AICON] section 6).

### 6.2 Human routes for AI principal lifecycle (APPROVED by contract §3 and §4)

| Route | Proof operation | Response | Source |
|---|---|---|---|
| `POST /v1/runs/{run_id}/ai-principal` as written in [AICON] §3.1 | `ai.principal.issue` | `{contract, principal_id, token, expires_in_seconds}`, token shown once | [F-AI] line 268 |
| `POST /v1/runs/{run_id}/ai-principal/revoke` as written in [AICON] §4 | `ai.principal.revoke` | `{contract, revoked}` | [F-AI] line 296 |

**The code mounts these at `/runs/{run_id}/ai-principal` without `/v1`** ([F-AI] lines 268 and 296; [F-APP] line 46). The contract says `/v1/runs/...`. Canonical path: OPEN-02.

### 6.3 Specialist envelope

Adapter 0.2 as built ([S-AD] lines 46 to 89):

- Request: `adapter_contract_version "0.2"`, `request_id`, `workspace_id`, `actor_id` (caller string, non-compliant, see 3.3), `specialist_id`, `capability_id`, `requirement_ids` (min 1), `evidence_refs` (EvidenceRef: `workspace_id, source_id, locator`, [S-CT]), `task`, `allowed_actions` (min 1), `operator_confirmed` (caller boolean, non-compliant, see 5.2). Unknown fields refused.
- Response: `adapter_contract_version`, `specialist_contract_version "1.0.0"`, `request_id`, `workspace_id`, `specialist_id`, `capability_id`, `registry_version`, `status` in {completed, incomplete, failed}, `findings[]` (statement, `evidence_status` in {cited, unverified}, `evidence_refs`), `unknowns[]`, `error_code`, `confidence` (always None), `confidence_status` ("not_assessed") ([S-AD] lines 72 to 89).

**Proposed adapter 0.3 (PROPOSED, not approved; breaking change, section 15):**

- Remove `actor_id` and `operator_confirmed` from the caller-supplied request.
- Add `confirmation_ref`: an opaque, single-use reference issued by Foundation (section 8). The adapter refuses unless Foundation verifies it for the exact `(run_id, project_id, specialist_id, capability_id, requirement_ids digest, allowed_actions digest)` of this envelope.
- Add `actor_ref`: set by Foundation from the proof, not by the caller.
- Add `run_id` and `project_id` (UUID) so that the envelope carries the Foundation identifiers (section 7).
- Keep `confidence_status: "not_assessed"` and `extra="forbid"`.

### 6.4 AI Engine result envelope (line A, as built)

`AgentExecutionResult` ([A-CT] line 349): `agent_id`, `agent_kind` (requirement_analysis or specialist), `status` (AgentStatus, [A-CT] line 104), `started_at`, `finished_at`, `errors`, `output` (`RequirementAnalysisResult` line 238 or `SpecialistInvestigationResult` line 334). `ReviewPackage` ([A-OR] lines 85 to 90) wraps stage records and `ReviewFlags`.

Persisted form: section 9.

---

## 7. Project and requirement identifiers (area 5)

| Identifier | Owner | Type and format | Source | Status |
|---|---|---|---|---|
| `project_id` | Foundation | UUID | [AICON] §5; [A-CT] `ProjectContext` line 146 | APPROVED |
| `run_id` | Foundation | UUID | [AICON] §6.1; [A-CT] `RequirementAnalysisResult` line 239 | APPROVED |
| `source_id`, `source_version_id`, `segment_id` | Foundation | UUID | [AICON] §6.1; [A-CT] `SourceReference` lines 135 to 143 | APPROVED |
| `version` (source version number) | Foundation | integer ≥ 1 | [A-CT] line 140 | APPROVED |
| `requirement_id` (AI proposal) | AI Engine, local | `^REQ-[0-9]{3,}$` | [A-CT] line 27 | Local only. No persisted requirement table ([AICON] §12). OPEN-10 |
| `question_id` (AI proposal) | AI Engine, local | `^Q-AI-[0-9]{3,}$` | [A-CT] line 28 | Local only. OPEN-10 |
| `workspace_id` | Specialist side | `NonBlank` string | [S-CT], [S-WS] | No Foundation counterpart. The candidate has no `workspace` table ([F-0041] and all migrations). OPEN-11 |
| `specialist_id` | Specialist side | enum, 7 values | [S-CA] | Conflicts with AI Engine `category_id` (5 values) and capability IDs. OPEN-12 |
| `category_id` | AI Engine | string, 5 values | [A-CA] | OPEN-12 |
| `capability_id` | Specialist side | `CAP-*` string | [S-CA] `REGISTRY_CAPABILITY_IDS` | OPEN-12 |
| `confirmation_id` | Foundation (proposed) | UUID | section 8 | PROPOSED |
| `correlation_id` | Foundation | UUID, from `X-Correlation-Id` or generated | [F-AI] lines 91 to 100; [AICON] §10 | APPROVED |

**Proposed binding until OPEN-10 and OPEN-11 are decided:**

- A proposal requirement is identified by the pair `(run_id, requirement_id)`. It is not a global identifier. Two runs may reuse `REQ-001` without collision.
- `workspace_id` in any specialist envelope equals the Foundation `project_id` of the run. Mapping, not a new concept. This is a proposal and needs WDS approval (OPEN-11).

---

## 8. Operator-confirmation lifecycle (area 6)

This section is PROPOSED. It implements D-5 (amended) and D07. No approved text defines a confirmation record, a confirmation TTL or an operator role.

### 8.1 Rules that are already in force

- A caller-supplied Boolean is never sufficient. Operator confirmation must be produced by WebDesk's proof path ([GOV §4] D-5; [DSC-10 D-5]).
- The operator must be authenticated, bound to the project, the specialist and the capability (D-5 amended; section 8.2).
- An authorized WDS operator confirms before execution ([S-DR] D07).

### 8.2 Binding

A confirmation is valid only for the exact tuple below. Any difference refuses the run.

| Field | Source of value |
|---|---|
| `run_id` | Foundation run, must be `queued`, `running` or `waiting_human` ([AICON] §3.2 condition 3) |
| `project_id` | Foundation run's project; must be `active` |
| `specialist_id`, `capability_id` | The recommendation the operator confirmed (section 5.1 step 1) |
| `requirement_ids_digest` | SHA-256 over the sorted requirement proposal IDs for this run |
| `allowed_actions_digest` | SHA-256 over the sorted allowed actions, subset of the adapter's known actions |
| `operator_user_id` | From the operator's authenticated session and operation proof, never from the request body |
| `operation` | `specialist.execution.confirm` (PROPOSED name; not in the operation CHECK list, see 11.3) |

### 8.3 Lifecycle states

| State | Entry | Exit | Enforced by |
|---|---|---|---|
| `requested` | AI Engine recommendation is submitted to Foundation (route not defined, OPEN-15) | `confirmed`, `refused`, `expired` | Foundation |
| `confirmed` | Operator proof verified and the binding matches | `consumed`, `revoked`, `expired` | Foundation |
| `consumed` | The adapter uses the reference once for one execution | Terminal | Foundation, atomic with the execution record |
| `revoked` | Explicit revocation by an authorized operator, or run leaves an active status | Terminal | Foundation |
| `expired` | `now()` reaches `expires_at` | Terminal | Foundation, checked on every use |
| `refused` | Proof or binding check fails | Terminal | Foundation. Denial is neutral to the caller (section 12) |

### 8.4 Expiry and revocation

- Expiry: PROPOSED ≤ 15 minutes, aligned with the AI principal TTL in [AICON] §4. No approved value exists (OPEN-05).
- Single use: a confirmation is consumed by one execution. A retry requires a new confirmation.
- Revocation: an authorized operator may revoke a `confirmed` reference before it is consumed. Revocation is audited (section 14).
- Run termination: any transition of the run out of `queued`, `running`, `waiting_human` expires its open confirmations, matching [AICON] §4.

### 8.5 Operator role

No approved text names the role. The candidate's roles are `Analyst`, `TechnicalReviewer`, `Approver` and `Administrator` ([F-RBAC] lines 23 to 26). Choosing one is a WDS decision (OPEN-04).

---

## 9. Run status and persistence (area 7)

### 9.1 Three status vocabularies, no approved mapping

| Source | Values | Source |
|---|---|---|
| Foundation run `status` | `queued, running, waiting_human, blocked_pending_decision, completed, failed, cancelled` | [AICON] §6.1 |
| Foundation run `state` | values of `workflow_runs.state` CHECK | [AICON] §6.1 |
| AI Engine `AgentStatus` | `completed, completed_with_gaps, failed, timeout, invalid_output` | [A-CT] lines 104 to 110 |
| Adapter `status` | `completed, incomplete, failed` | [S-AD] line 84 |

No approved text maps these. OPEN-16. The mapping below is PROPOSED.

| AI Engine or adapter outcome | Proposed Foundation run effect |
|---|---|
| `completed` | Run may move to `completed` only through a Foundation service |
| `completed_with_gaps` or adapter `incomplete` | Run stays `running` or `waiting_human`, with gaps recorded |
| `failed`, `timeout`, `invalid_output`, adapter `failed` | Run `failed` only if a system-level failure; otherwise the specialist result is recorded as failed and the run continues |
| Operator decision outstanding | `blocked_pending_decision` (per [AICON] §4 terminal list) or `waiting_human` |
| Cancellation | `cancelled` through the existing Foundation path |

**Rule:** no AI Engine or specialist output changes a Foundation run status directly. Foundation services compute the status from recorded results ([AICON] §14).

### 9.2 Persistence (D-7 amended, minimum)

D-7 (amended) requires minimum secure persistence for findings, evidence, citations, digests, applicability, status and audit. No such table exists on the candidate. The design below is PROPOSED and needs approval under D-8 (section 11.3).

Entities (proposed, names not approved):

| Entity | Minimum fields | Notes |
|---|---|---|
| `ai_result` | `result_id`, `run_id`, `project_id`, `agent_kind`, `agent_status`, `contract_version`, `registry_version`, `output_sha256`, `created_at` | Owner Foundation. No raw prompt or model response ([AICON] §10) |
| `ai_finding` | `finding_id`, `result_id`, `run_id`, `statement`, `evidence_status` (see OPEN-07), `created_at` | A proposal. Never approved scope ([AICON] §14) |
| `citation` | section 10.3 fields | Evidence and citation structure |
| `specialist_execution` | `execution_id`, `run_id`, `confirmation_id`, `specialist_id`, `capability_id`, `adapter_contract_version`, `request_sha256`, `response_sha256`, `status`, `started_at`, `finished_at` | Hashes only, matching [S-AD] `audit_record` |
| `operator_confirmation` | section 8 | Lifecycle table |

**Forbidden in every persisted row:** token values, token hashes, source content beyond the approved segment text reference, prompts, full model responses, specialist task text ([S-AD] `audit_record` docstring; [AICON] §10).

### 9.3 Write boundary (D-AI-4 requires it; not defined)

- No AI write endpoint exists in v1 ([AICON] §2 D-AI-4, §8).
- The later write contract must specify a Foundation-controlled, independently enforced run- or job-scoped authorization boundary ([AICON] §2 D-AI-4).
- **Proposed (PW-1):** persistence is performed by a Foundation worker or service function, not by an HTTP route, and only for a run that is active and whose confirmation is valid. No AI principal and no specialist credential can write. Writer identity is OPEN-17.

---

## 10. Evidence and citation structures (area 8)

### 10.1 Two evidence families plus one specialist shape

| Family | Structure | Source | Digest | Applicability |
|---|---|---|---|---|
| A. Foundation source citation | `SourceReference`: `source_id, source_version_id, version, segment_id, relation` in {supports, contradicts, context}, `supporting_quote` ≤ 300 chars | [A-CT] lines 135 to 143 | Available in Foundation: `source_segments.text_content_hash`, SHA-256 hex ([F-0007] line 114). Not returned by `ai-read/v1` ([AICON] §6.1) | Version only |
| B. External documentation evidence | `EvidenceReference`: `evidence_id, origin, publisher, document_url, checked_at, applies_to_platform, applies_to_version, evidence_status, relevance_summary, limitations` | [A-CT] lines 271 to 292 | None | Platform and version. No edition field |
| C. Specialist evidence reference | `EvidenceRef`: `workspace_id, source_id, locator` | [S-CT] | None | None |

### 10.2 Outcomes

The directive requires **supported, unsupported and unknown** outcomes. No approved text defines these values:

- [AICON] has no supported, unsupported or unknown evidence outcome. The evidence vocabulary in the approved-looking schema is `verified, partially_verified, unverified, conflicting, not_applicable` ([R-SCH] line 24; `WebDesk_Agentic_Requirement_Platform_Specs/GOVERNANCE.md` line 59).
- `unsupported` appears only as a routing outcome ([A-CT] line 100) and a source parse status ([R-SCH] line 126).

Therefore the citation check outcome is **OPEN-08**. Proposed: a separate column `check_outcome` in {supported, unsupported, unknown}, stored next to `evidence_status`, and never mapped to `verified` or `partially_verified` without WDS approval. [AICON] §14 forbids AI output from creating verified status.

### 10.3 Citation record (PROPOSED)

| Field | Required | Basis |
|---|---|---|
| `citation_id` | yes | Foundation UUID |
| `run_id`, `project_id` | yes | Section 7 |
| `family` | yes | A, B or C (section 10.1) |
| `source_url` | for B | `document_url` [A-CT] line 275; must be https and allowlisted ([DSC-03 §8], QA2-07) |
| `source_version_id`, `segment_id`, `version` | for A | [A-CT] lines 135 to 143 |
| `passage_digest` | yes for A and B | SHA-256 hex. For A, copy `source_segments.text_content_hash`. For B, computed at check time over the normalized passage text. **No approved field exists for B** (OPEN-09) |
| `checked_at` | for B | [A-CT] line 276 |
| `applies_to_platform`, `applies_to_version`, `applies_to_edition` | yes | `applies_to_edition` is not in [A-CT]. [R-REG] lines 398 and 407 require edition capture. OPEN-09 |
| `evidence_status` | yes | AI vocabulary (OPEN-07) |
| `check_outcome` | yes | supported, unsupported, unknown (OPEN-08) |
| `relevance_summary`, `limitations` | yes | [A-CT] lines 280 and 281 |

**Hard rule from the approved text:** a synthetic fixture can never be verified ([A-CT] lines 283 to 292, `_origin_limits_status`). Approved external evidence needs a document URL and a check time.

### 10.4 Specialist findings

A specialist finding is `cited` only with at least one evidence reference ([S-CT] `_cited_requires_evidence`). Otherwise it is `unverified`. Adapter 0.2 has no `verified` value ([S-AD] line 68). Mapping to Foundation is OPEN-07 and OPEN-14.

---

## 11. Database ownership (area 9)

### 11.1 Rules that are already in force

- Foundation owns every persisted record. In v1 the AI Engine writes nothing ([AICON] §1 principle 2, §12).
- The AI Engine and the specialist adapter hold no database credential ([AICON] §1; [A-CL] docstring; [S-AD] docstring).
- The application role cannot read `ai_principals` ([F-0041] lines 149 to 151).
- SECURITY DEFINER functions pin `search_path`. Three existing functions do not (QA F-2, [DSC-05 §1.3]); SG-10 applies.

### 11.2 Tables that exist on the candidate (`5974d59`)

`account_activation_tokens, ai_principals, audit_events, audit_tombstones, contact_reservations, credentials, dependency_edges, idempotency_keys, in_app_alerts, operation_authorization_rules, operation_proofs, outbox_notices, project_access_grants, project_memberships, projects, rate_limit_events, restricted_content_grants, role_assignments, run_input_snapshots, sessions, setup_trust_ceremonies, source_read_grants, source_segments, source_versions, sources, user_contact_approvals, user_withdrawals, users, workflow_checkpoints, workflow_jobs, workflow_runs` (migration `CREATE TABLE` inventory at `5974d59`).

No table for requirements, evidence, citations, findings, AI results, specialist executions, operator confirmations or workspaces exists.

### 11.3 Migration policy (D-8, amended)

- Revisions `0001` to `0059` are frozen ([S01] D-8; [DSC-05 §1.1]).
- The specialist branch's `0027_proof_gated_token_issuance` is not merged. Its body differs from the candidate's `0027` under the same revision ID ([DSC-05 §1.1]).
- Every new schema change is a new revision after `0059`, approved separately ([S01] D-8).
- This contract proposes the new tables in 9.2 and the operator-confirmation operation name in 8.2. Each needs its own revision. The revision list and the operation CHECK change are OPEN-18.
- The single-head check (`scripts/migration_heads.py`) and the scratch-database up, down and up test (T6) apply to every new revision ([DSC-07 T6, T6a]).

### 11.4 Ownership table

| Record | Owner | Writer | Reader |
|---|---|---|---|
| Projects, sources, versions, segments, runs, jobs | Foundation | Foundation services | AI Engine (read only) |
| AI principals | Foundation | Authority and guard functions | Foundation request path |
| Audit events | Foundation | Foundation only | Foundation |
| AI results, findings, citations (proposed) | Foundation | Foundation worker (PW-1) | Foundation; AI Engine reads results only if a later contract allows it |
| Specialist executions (proposed) | Foundation | Foundation worker | Foundation |
| Operator confirmations (proposed) | Foundation | Foundation proof functions | Foundation; adapter receives only the verified reference |

---

## 12. Error handling (area 10)

### 12.1 Foundation `ai-read/v1` (APPROVED)

| Status | `error` | When | Source |
|---|---|---|---|
| 400 | `contract_version_unsupported` | Missing or unknown `X-AI-Contract-Version` | [AICON] §9; [F-AI] line 93 |
| 400 | `invalid_request` | Malformed identifier, cursor or limit | [AICON] §9 |
| 401 | `ai_credential_invalid` | Missing scheme, unknown, revoked, expired, run not active, project archived, bound human not permitted. One neutral message | [AICON] §9; [F-AI] line 96 |
| 404 | `not_found` | Out of scope, quarantined, restricted, not readable. One neutral message | [AICON] §9 |
| 405 | `method_not_allowed` | Non-GET on AI route | [AICON] §9 |
| 413 | `response_too_large` | Content above 10 MiB | [AICON] §9 |

Denials never reveal the failing condition. The reason goes only to the audit row ([AICON] §9, §10).

### 12.2 Human route errors

`ai_principal_refused` is returned as 403 when the authority refuses issuance ([F-AI] line 284). This reveals a condition. It is inside a human route, so the neutral rule of [AICON] §9 does not cover it. OPEN-02 can address this together with the path.

### 12.3 Specialist errors

- Harness codes ([S-ER] `SpecialistErrorCode`): `contract_version_unsupported, input_invalid, output_invalid, specialist_mismatch, workspace_mismatch, capability_denied, provider_failure`. Only `provider_failure` is retryable ([S-ER] `RETRYABLE_CODES`).
- Adapter codes ([S-AD] lines 37 to 43): `operator_confirmation_required, action_forbidden, action_unknown, capability_mismatch, request_invalid, authorization_refused`.
- Adapter refusals return `status: failed` with `unknowns: ["adapter refused the request: <code>"]` ([S-AD] `_refused`). The code is shown to the caller. Under 12.1's neutral rule, this is acceptable only for specialist-internal errors, not for Foundation denials.

**Proposed mapping (PROPOSED):** every adapter and harness code maps to exactly one external outcome in {`refused`, `failed`, `incomplete`}, and the detail is audit-only. A specialist error never exposes a Foundation credential, a session or an internal reason ([DSC-07 T17]). The mapping table is a test input.

### 12.4 AI Engine client errors

`FoundationReadError` subclasses ([A-CL] lines 41 to 76): `CredentialRejectedError`, `CredentialExpiredError` (client-side clock; no request is sent), `ResourceUnavailableError`, `VersionMismatchError`, `ScopeMismatchError`, `ContractViolationError`, `ResponseTooLargeError`, `FoundationUnavailableError`. The client must map every section 12.1 status and must not reveal the failing condition ([DSC-03 §7], T2 and T11).

---

## 13. Security boundaries (area 11)

| Boundary | Rule | Source |
|---|---|---|
| AI identity | AI principal only. No human credential, no database credential, no operation proof, never Administrator | [AICON] §2 D-AI-1, §3 |
| Human impersonation | Impossible. The bound human comes only from the proof | [AICON] §3.1 |
| Specialist identity | No Foundation credential, no AI principal. Actor from proof | D-6 [GOV §4]; section 3.3 |
| Restricted content | Denied for every principal, including with a restricted-content grant | [AICON] §2 D-AI-2, §5 |
| Quarantined content | Never returned, listed or acknowledged | [AICON] §5 |
| Content transmission | `not_scanned` content is readable by AI inside the Foundation boundary. It must not be sent to any external model. No policy exists to permit this | [AICON] §13A; readiness C-15 |
| Specialist authority | Declared only, not enforced at run time. No live specialist execution against Foundation data until run-time enforcement is accepted or the residual risk is accepted in writing | QA-07 [DSC-03 §10]; D-9 [GOV §4]; SG-8 [DSC-08] |
| Specialist source access | Only allowlisted https URLs. Shopify only is approved | QA2-07 [DSC-03 §8]; OPEN-22 |
| Environment | Controlled development and integration only. Production disabled | D-9 [GOV §4]; [APP §E] |
| Routing | No automatic routing. Operator confirmation from proof only | D-5; section 8 |
| Secrets | No token, password, connection string or session value in repository files, logs or reports | SG-11 [DSC-08] |
| Upload limit | 20 MiB parser and upload limit | [DSC-03 §8] |

---

## 14. Audit requirements (area 12)

### 14.1 Existing requirement (APPROVED)

- Every AI request, allowed or denied, writes one `audit_events` row, in a transaction that survives refusal. `event_type` is `ai.read.allowed` or `ai.read.denied`. `actor_id_or_service` is `ai-principal:<principal_id>` or `ai-principal:unresolved`. `correlation_id` from `X-Correlation-Id` ([AICON] §10). Requests refused before database work have no row (same section).
- Audit rows and logs carry no token, token hash, content, segment text, prompt or response ([AICON] §10; D-AI-5).

### 14.2 Proposed event types (PROPOSED)

| Event | When | Record refs (IDs only) |
|---|---|---|
| `ai.principal.issued`, `ai.principal.revoked` | Human route success and revoke | run, principal |
| `specialist.confirmation.requested`, `.confirmed`, `.refused`, `.revoked`, `.expired` | Section 8 lifecycle | run, confirmation, specialist |
| `specialist.execution.started`, `.completed`, `.refused` | Adapter call | run, execution, specialist, capability |
| `ai.result.persisted` | PW-1 write | run, result |

Each row carries `correlation_id`, `project_id`, `actor_type`, `actor_id_or_service` (the human, from proof, for operator events), `error_class` (internal reason, audit only) and `redacted_details` with the two hashes from [S-AD] `audit_record`: `request_sha256` and `response_sha256`. `audit_record` returns a dict today and persists nothing, so persistence is required (OPEN-25).

---

## 15. Version compatibility (area 13)

| Interface | Version today | Where declared | Breaking change needed |
|---|---|---|---|
| Foundation to AI read | `ai-read/v1` | [AICON] §13; [F-AI] line 34; [A-CL] line 27 | None. Additive fields allowed in v1; the AI client ignores unknown fields ([A-CL] `_WireModel`) |
| Human AI-principal routes | Contract §3 and §4 | [AICON] | Path change if OPEN-02 chooses `/v1` |
| Specialist adapter | `0.2` | [S-AD] line 30 | **Yes:** adapter 0.3 (section 6.3). Removing `actor_id` and `operator_confirmed` from the caller changes meaning |
| Specialist harness | `1.0.0` | [S-CT] | None |
| AI Engine common contracts | No version constant | [A-CT] (none), [DSC-03 §1] | Add an explicit version (PROPOSED: `ai-engine-contract/1`) |
| Specialist registry | `0.3.10-foundation-gate1-review` | [S-AD] line 33; [R-SCH] header | None |
| Foundation API version string | `0.3.10.0` | [F-APP] line 26 (FastAPI `version=`) | Not a contract. Do not rely on it |
| Migration chain | Head `0059_int_mark_inputs_fence`; 65 files | [DSC-01 §D] | New revisions only (section 11.3) |

**Rules:**

- An unknown contract version is refused. The server never falls back ([AICON] §13).
- Adapter 0.2 and 0.3 cannot be served by one code path without a version switch. The adapter refuses any `adapter_contract_version` other than the one it implements.
- Line A and line B both claim `ai-read/v1` ([DSC-03 §1]). Only line A is in this contract (OPEN-13).

---

## 16. Failure and recovery (area 14)

| Failure | Behaviour | Source |
|---|---|---|
| AI principal expired | Requests refused with 401. The AI Engine does not renew. A human issues a new principal (rotation revokes the old one) | [AICON] §3.1, §4 |
| Run leaves an active status | Requests refused on the next request. No stale window | [AICON] §4 |
| Bound human loses read right | Refused on the next request | [AICON] §3.2 condition 5 |
| Specialist timeout | Process killed at the bound; no late result accepted; nonce mismatch refused | [A-BA] `run_specialist` docstring |
| Specialist provider failure | `provider_failure`, retryable only at the orchestrator's discretion | [S-ER] `RETRYABLE_CODES`; retry policy beyond this belongs to the orchestrator (M3 S6) |
| Partial analysis | `completed_with_gaps`; gaps recorded; no fabricated output | [A-CT] `AgentStatus` |
| Model failure | Classified adapter error; retry per `RetryPolicy` ([A-MO] lines 88 to 130). No provider text is kept | [A-MO] `ModelError` docstring |
| Worker lease lost | `LeaseLost`; lease 120 seconds; owner fence on `fn_worker_mark_inputs_changed` | [DSC-05 §3]; D-14 [S01] |
| Duplicate request | Idempotency key scoped to (actor, endpoint, key), retained 24 hours. Proposed reuse for specialist execution, not yet approved | [F-IDEM] docstring |
| Foundation migration rollback | Supported range from head down to `0058` and `0055_int_merge_p2_p3_p7`; single-phase downgrade below them is unsupported | [DSC-03 §6]; ruling 4 [F-INT] |
| AI read rollback | Removes `/v1/ai` routes. Foundation behaviour otherwise unchanged | [DSC-06] rollback |
| Confirmation expiry during execution | Execution must check `expires_at` at the consume step, atomically. If expired, refuse and record | section 8 (PROPOSED) |

**Recovery rule:** a failed or refused step is re-run only by a new operator confirmation and a new principal where needed. No step retries silently across a confirmation boundary.

---

## 17. Test gates mapped to this contract

Test IDs are from [DSC-07]. Each gate names the SHA it must pass on.

| Gate | Tests | Covers | Status |
|---|---|---|---|
| G0 technical baseline | T0, T1, T6, T6a, T7, T8, T18 | Candidate tip | G0 accepted for `5974d59` [APP §B]. Independent QA not started [APP §F] |
| AI read path | T2, T3, T4, T5, T9, T10, T11 | Sections 6.1, 12.1, 13, 14.1 | Not run |
| Operator confirmation (proposed) | T14, T16 (new, after OPEN-03 and OPEN-04) | Section 8 | Not written |
| Specialist adapter | T13, T15, T17 | Sections 5.2, 10.4, 12.3 | Not run. T13 forbidden-action list must match [S-AU] (`modify_routing`, `accept_inferred_requirement` and others), not the wording in [DSC-07] |
| Persistence (proposed) | New tests for section 9 and 10: schema, isolation, digest, check outcome | Sections 9 to 11 | Not written. Needs OPEN-18 |
| Migration (proposed) | T6, T6a, T18 for each new revision | Section 11.3 | Not written |

Known: T9 requires that no table is created for requirements, evidence or citations. That is now an outdated check, because D-7 requires persistence. Replace it with the section 9 table list after OPEN-17 and OPEN-18 are decided.

---

## 18. Open items

Each OPEN item lists the two sources in conflict or the missing source, and the decision needed. None is resolved by this document.

| ID | Item | Sources | Decision needed |
|---|---|---|---|
| OPEN-01 | Sprint 5 acceptance status | [S01] (2 Nov): "Sprint 5 is not accepted"; Sprint 6 dependency open. [S5C] (3 Nov): "FORMALLY ACCEPTED UNDER WDS-APPROVED REVISED MVP EVALUATION SCOPE". [APP §F] (3 Nov) is silent | WDS to confirm which record governs the Sprint 5 dependency for Sprint 6 |
| OPEN-02 | Canonical path of the AI-principal routes | [AICON] §3.1 and §4: `/v1/runs/{run_id}/ai-principal`. [F-AI] lines 268 and 296 with [F-APP] line 46: `/runs/{run_id}/ai-principal` with no `/v1`. No other human route uses `/v1` ([F-RT]) | Choose the path. The code and the contract cannot both be right |
| OPEN-03 | Source of authorization for specialist invocation | [S-DR] D07 and [GOV §4] D-5 (operator confirmation). [S-AD] line 61 (`operator_confirmed: bool`). [A-OR] lines 103 and 219 (`authorized_categories`, caller config) | Confirm section 8 as the only source. Approve the breaking change to adapter 0.3 |
| OPEN-04 | Which role confirms as the "authorized WDS operator" | [S-DR] D07 says "authorized WDS operator". [F-RBAC] roles: Analyst, TechnicalReviewer, Approver, Administrator. Unclear whether "WDS operator" means a tenant user or WDS staff | Name the role and say whether WDS staff can act in the product |
| OPEN-05 | Confirmation TTL and single-use rule | No approved text. Section 8.4 proposes ≤ 15 minutes | Approve a value |
| OPEN-06 | Operation name and operation CHECK change | No approved name. The `operation_proofs` CHECK list is in [F-0041] | Approve the name, and include it in the D-8 migration list |
| OPEN-07 | Evidence status vocabulary | [A-CT] lines 35 to 41 and [R-SCH] line 24: verified, partially_verified, unverified, conflicting, not_applicable. [S-AD] line 68: cited, unverified. [DSC-05 §7] | D-7 (1) defers the mapping. Decide whether the mapping is needed for any Foundation write, and if so which table |
| OPEN-08 | Supported, unsupported and unknown outcomes | Required by the directive. Not in [AICON], [R-SCH] section 2, or `WebDesk_Agentic_Requirement_Platform_Specs/GOVERNANCE.md` line 59 | WDS to define the outcome set and its meaning, and whether it is stored with or instead of `evidence_status` |
| OPEN-09 | Passage digest and edition applicability for family B evidence | No approved field. [A-CT] lines 271 to 294 has `applies_to_version` only. [R-REG] lines 398 and 407 require edition | Approve `passage_digest` and `applies_to_edition` for family B |
| OPEN-10 | Persisted requirement identifiers | [A-CT] line 27: `REQ-NNN` is a proposal ID, local until a write contract. [AICON] §12: no requirement table. [GOV §4] D-7 requires persistence | Choose a persisted ID scheme (Foundation UUID, or `(run_id, REQ-NNN)`) |
| OPEN-11 | Workspace versus project | [S-CT] and [S-WS] use `workspace_id`. Foundation has `project_id` and no workspace table (section 11.2) | Approve `workspace_id = project_id` for this integration, or add a workspace concept (a much larger change) |
| OPEN-12 | Specialist identifiers | [S-CA]: 7 `SpecialistId` values and `CAP-*` capability IDs. [A-CA]: 5 `category_id` values (`shopify_specialist`, `3dcart_shift4shop_specialist`, and three more). Missing from [A-CA]: `standalone_applications`, `middleware_applications` | Approve one canonical mapping across the three vocabularies |
| OPEN-13 | AI Engine line | [GOV §4] D-4: line A for step 2, line B pending a parity record. [DSC-01 §B], [DSC-05 §4]: both claim `ai-read/v1`. [S01] ARCH-03 | Approve line A, or a parity record |
| OPEN-14 | Authoritative evidence reference | Family A (`SourceReference`), family B (`EvidenceReference`, [A-CT]) and family C (`EvidenceRef`, [S-CT]) differ and are not mapped ([DSC-03 §4]) | Choose which family a specialist finding must cite |
| OPEN-15 | Invocation and transport of the AI Engine | [A-CL] lines 1 to 10: no transport ships. No Foundation route starts an AI analysis run. No approved text names the trigger or the caller | Decide who calls the AI Engine (Foundation worker, or an external orchestrator) and how the request reaches Foundation |
| OPEN-16 | Status mapping | Three vocabularies (section 9.1). No approved mapping | Approve the mapping in 9.1 or a replacement |
| OPEN-17 | Writer of persisted AI results | [AICON] §2 D-AI-4: a later write contract must specify a Foundation-controlled boundary. [GOV §4] D-7: persistence required. This document proposes PW-1 (Foundation worker) | Approve PW-1, or name another writer |
| OPEN-18 | New migrations and their list | [GOV §4] D-8 permits the minimum. No list exists | Approve the revision list for section 9 and section 8, each with a T6 run on a scratch database |
| OPEN-19 | Ruling 5 provenance | [F-INT] lists rulings 1 to 4 only. [GOV §2] (D-10): register update pending. [DSC-05 §9] F-1 | WDS to confirm ruling 5 with approver, date and channel, or direct a revert |
| OPEN-20 | Which record governs the D-13 technical gate | [GOV §1]: "D-13 is therefore not passed on its technical evidence" (written earlier on 3 Nov). [APP §B] (later on 3 Nov): G0 technical evidence accepted for `5974d59` | WDS to confirm that [APP §B] supersedes [GOV §1] for the technical gate. Independent QA remains open either way ([APP §F]) |
| OPEN-21 | Shopify implementation identity | [A-SH] on line A and `src/webdesk/specialists/platforms/shopify.py` on the specialist branch ([DSC-05 §5]) | Choose one implementation for the integration |
| OPEN-22 | Source allowlists for six specialists | [DSC-03 §8]: only Shopify entries are approved. Six have none | Approve allowlists, or keep six specialists out of invocation |
| OPEN-23 | Forbidden-action list used by the test plan | [DSC-07 T13] names `route` and `accept`. [S-AU] lists `modify_routing`, `accept_inferred_requirement` and others | Align the test plan to [S-AU] |
| OPEN-24 | Phase 3 and Phase 6 acceptance | [F-INT] lines 16 to 23 (candidate: no final acceptance). `feature/foundation-phase-9` commit `356fb3c` records acceptance from "the official directive supplied in the project conversation" ([DSC-02 C3]) | Confirm the candidate record governs |
| OPEN-25 | Audit persistence for specialist events | [S-AD] `audit_record` returns a dict and persists nothing. [AICON] §10 `audit_events` exists | Approve the event types in section 14.2 |

**Resolved by approved decisions (not open):** D-3 (adapter 0.2 governs isolated work), D-5 routing deferral, D-6 actor derivation from proof, D-7 (2) persistence of AI output as proposal only, D-11 F-7 (outbox not in scope). Each has an implementation step still pending, listed in section 17.

---

## 19. Verification record

**Read directly in this session:** [APP], [GOV], [S01], [S5C] (first 40 lines), [AICON], [DSC-00] to [DSC-10] (at `9ca38ba`), [F-AI] (sections read by grep and key lines), [F-APP], [F-RT], [F-0041] (grep for table, check and operation lines), [F-R4] (lines 3 and 12), [R-SCH] (lines 1 to 30 and grep), [A-CT], [A-CL] (header and constants), [A-OR] (grep and key lines), [A-BA] (grep and key lines), [A-CA], [A-MO] (grep), [S-AD] (full), [S-CT] (first 80 lines), [S-AU] (first 70 lines), [S-CA], [S-ER], [S-WS], [S-HA] (first 30 lines), [S-DR] (line 19 via [DSC-02]).

**Not read in full:** [S5C] beyond line 40; [F-AI] full body; [A-OR] full body; [A-BA] `run_specialist` body; [S-HA] body; [DSC-11] to [DSC-13] (not in scope of the directive; present on the discovery branch). Claims that depend on these are cited from the summary text, and the cited line is the one that was read.

**Not verified:** no test, lint, type check, migration or database command was run. All statements about runtime behaviour are static readings. The discovery's test outcomes (for example T1 at `32c98f6`) are not re-verified.

**Not checked:** whether `docs/AI_FOUNDATION_READ_HANDOFF.md` or `docs/GOVERNANCE_DECISION_REGISTER.md` on `5974d59` contain approver details for D-AI-1 to D-AI-5 beyond what [DSC-02 C1] reports. The discovery grep found none. The governance register was not re-grepped in this session.

**Identifiers:** no token, password, connection string or session value appears in this document.
