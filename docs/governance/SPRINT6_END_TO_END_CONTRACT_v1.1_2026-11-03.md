# Sprint 6 End-to-End Integration Contract, v1.1 (3 November 2026)

**Contract identifier:** `sprint6-e2e/v1.1`
**Supersedes:** `sprint6-e2e/v1` (`docs/governance/SPRINT6_END_TO_END_CONTRACT_v1_2026-11-03.md`, commit `2a46503`). v1 is kept unedited as the historical record.
**Status:** APPROVED by WDS as reported, with the decisions in `docs/governance/SPRINT6_OPEN_DECISION_REGISTER_2026-11-03.md` (the register). Approval is recorded as reported: not a signed approval. Implementation status is separate. Approval of a decision is not evidence that code exists or that tests pass (section 17).

### Approval record (v1.1)

| Field | Record |
|---|---|
| Approver | WDS Authorized Approver, identified by role only. No personal name given |
| Date | 3 November 2026 |
| Channel | WDS directive in the Sprint 6 chat, 3 November 2026. Two records of it: (a) the formal directive pasted by the requesting user into the contract session; (b) a relayed statement from the sibling session `local_795729d4-e173-40dc-8d80-2a3c4467ea8e`, which states the same approval. The sibling session is a relay, not the approver |
| Approved as reported | OPEN-01 to OPEN-26 as set out in the register; D-4 amendment D-4-A (AI Engine Lineage B as intended authoritative implementation); Foundation-issued single-use operator confirmations; adapter v0.3 as an explicitly versioned breaking change; all seven specialist integrations; evidence persistence and the necessary migrations; Foundation worker-owned orchestration; candidate-specific D-13 disposition for `5974d59` (accepted, with the narrow personal-attestation exception); G0 baseline of 1,031 passed on `5974d59` (accepted) |
| Not approved | Production; independent QA of the final integration candidate (remains open); any push or merge of other teams' branches |

### Package items without a specific WDS answer

The approval covers the direction of each item. The items below have no specific answer in the directive. They are **not** inferred. Each one is a contract-owner definition that WDS has not confirmed, or a fact that is not yet available.

| ID | What is missing | What v1.1 currently says | Needed |
|---|---|---|---|
| OPEN-03 | The exact adapter 0.3 field set is not approved; only the version and its breaking nature are | Section 6.3 field list | WDS or Specialist-team confirmation of the field list |
| OPEN-05 | Which clock is the "authoritative trusted time" | Database transaction clock (`now()`), section 8.4 | Confirmation of the clock authority |
| OPEN-07 | The validated mapping table between AI and adapter vocabularies | Table in section 10.4 (contract-owner derivation) | Confirmation of the table |
| OPEN-08 | Only the three values and their meaning are approved; the required citation count and the relation to relevance are the contract owner's reading | Section 10.2 | Confirmation of the rules |
| OPEN-11 | "Validate the actual relationship through Foundation" cannot be done: no workspace entity exists on `5974d59` | Section 7.1 (blocked, D-DEP-1) | A Foundation design decision. No answer exists yet |
| OPEN-13 | Lineage B is selected "subject to source integrity, final contract compatibility and verification" | Section 2.3 conditions | The conditions are met, or not, by evidence. None is met yet |
| OPEN-14 | "Appropriate provenance" is not defined by the directive | Section 10.1 fields | Confirmation of the provenance fields |
| OPEN-17 | The "restricted authority" is not named | `webdesk_worker` EXECUTE-only guard function (section 9.3) | Confirmation of the role and function |
| OPEN-18 | The directive approves "minimum required new migration revisions", but does not approve the revision list | Proposed list R-1 to R-4 (section 11.3) | Confirmation of the list |
| OPEN-21 | "Subject to confirming its current source and compatibility" is not yet confirmed | Section 5.3, D-DEP-6 | Specialist-team confirmation |

Items answered in full by the directive, with no gap: OPEN-01, 02, 04, 06, 09, 10, 12, 15, 16 (after checking), 19, 20, 22, 23, 24, 25, 26. OPEN-04 was verified against the matrix (section 3.4).

Corrections to the record: the sibling session's message describes the approval as given in the chat. The contract records it as reported. The sibling's instruction not to push is followed in this step: no push is made.
**Scope:** three workstreams: WebDesk Foundation; AI Engine (Lineage B, section 2); seven Specialist Agents (through adapter v0.3).
**Authoring basis:** read-only analysis plus contract-owned edits. No `src/`, `tests/` or `migrations/` file was changed in producing v1.1.

---

## 0. Citation rule and source key

Each bracketed key resolves to one file at one commit or blob. Keys with a line number point to that line at that SHA. The v1 source key (sections 0 to 19 of v1) still applies, with these additions:

| Key | File | SHA read | Blob (first 10) |
|---|---|---|---|
| REG | `docs/governance/SPRINT6_OPEN_DECISION_REGISTER_2026-11-03.md` | this branch, commit of v1.1 | not applicable |
| G0 | `docs/governance/SPRINT6_G0_EVIDENCE_2026-11-03.md` | `05b03e8` | `e25b09adc6` |
| B-ORCH | `ai_engine/src/ai_engine/orchestration/registry_map.py` (Line B) | `0389318` | not recorded |
| B-REG | `ai_engine/src/ai_engine/specialists/registry.py` (Line B) | `0389318` | not recorded |
| B-SEL | `ai_engine/src/ai_engine/selection/operator.py` (Line B) | `0389318` (blob `2a31e4b4a6`) | `2a31e4b4a6` |
| B-RTE | `ai_engine/src/ai_engine/routing/explicit.py` (Line B) | `0389318` (blob `8e46048355`) | `8e46048355` |
| B-FAR | `ai_engine/src/ai_engine/adapters/foundation_ai_read.py` (Line B) | `0389318` (blob `568a17477c`) | `568a17477c` |
| B-EVD | `ai_engine/src/ai_engine/contracts/evidence.py` (Line B) | `0389318` | not recorded |
| B-CMN | `ai_engine/src/ai_engine/contracts/common.py` (Line B) | `0389318` | not recorded |
| SHOP | `src/webdesk/specialists/platforms/shopify.py` | `05b03e8` | `f5123bac8a` |
| MTX | `src/webdesk/rbac/matrix.py` (Foundation) | `5974d59` | not recorded |
| RUN7 | `migrations/versions/0007_intake_and_execution.py` (Foundation) | `5974d59` | not recorded |
| RUN50 | `migrations/versions/0050_durable_execution.py` (Foundation) | `5974d59` | not recorded |

Line A keys (`A-CT`, `A-CL`, `A-OR`, `A-BA`, `A-MO`, `A-CA`, `A-SH`) are unchanged from v1 and cite Line A at `967d895`. Line A is historical for Sprint 6 after amendment D-4-A (section 2).

Discovery files `[DSC-NN]` remain at `9ca38ba`, with analysis base `6c458c8`.

---

## 1. Authority, decisions and scope

### 1.1 Decisions in force

| Decision | Status in v1.1 | Source |
|---|---|---|
| D-1 `ai-read/v1` | Approved, read-only, non-production. Approver, date and channel for D-AI-1 to D-AI-5 are still not recorded in the repository. This is a provenance gap, not a scope change | `APP` section D |
| D-2 | Amended. Satisfied by this contract | `APP` section E |
| D-3 | Adapter 0.2 for isolated work. Superseded for production-shaped envelopes by adapter 0.3 (OPEN-03) | REG OPEN-03 |
| D-4 | Original decision preserved. **Amended by D-4-A: Lineage B** | REG section 2 |
| D-5 | Amended and approved: Foundation-issued confirmation is the sole authority | REG OPEN-03, section 8 |
| D-6 | Unchanged: no Foundation credential for specialists; actor from proof | `GOV` section 4 |
| D-7 | Amended: minimum secure persistence. Mapping approved (OPEN-07, OPEN-08) | REG |
| D-8 | Amended: minimum new revisions beyond `0059`, single head, each verified (OPEN-18) | REG |
| D-9 | Amended: controlled development and integration only; production disabled | `GOV` section 4 |
| D-10 | Ruling 5 approver recorded as AS (OPEN-19) | REG OPEN-19 |
| D-13 | Management disposition recorded for `5974d59`. Independent QA of the final candidate remains open (OPEN-20) | REG OPEN-20 |
| D-14 | `runs/jobs.py` lease API, test T7 required | `S01` |

### 1.2 Scope

- The Foundation to AI Engine read path (`ai-read/v1`), and the human routes that issue and revoke AI principals.
- The AI Engine workflow on Lineage B (section 4).
- Specialist routing and invocation through adapter v0.3 (section 5).
- Persistence and audit of integration results (sections 9 to 11, 14).

### 1.3 Out of scope

- Production deployment, hosting, and external model transmission ([AICON] section 13A; readiness C-1 to C-21).
- Any live model provider. Lineage B's model port has to be checked separately before any provider is used (section 4.4).
- Live specialist execution against live vendor data (D-9).
- Phase 8 and Phase 9 documentation branches (D-15).

---

## 2. Engine selection: Lineage B (amendment D-4-A)

### 2.1 Selection

Per the approved directive, the intended authoritative AI Engine for Sprint 6 is **Lineage B**, anchored at historical candidate `0389318` on `integration/ai-s01-s02-s03`. The original D-4 choice of Line A (`967d895`) is preserved in the register and is not used as the Sprint 6 target.

### 2.2 Why Lineage B covers the three workstreams here

- **Specialist catalog:** Lineage B's `registry_map.py` [B-ORCH] lists all seven categories, each with the `CAP-*` capability ID that the specialist catalog uses [S-CA]. Line A lists five [A-CA].
- **Operator selection:** `selection/operator.py` [B-SEL] records explicit operator decisions as attributed claims. It states that this is not authorization, which matches section 8.
- **Explicit routing:** `routing/explicit.py` [B-RTE] runs a specialist only when the operator names the capability and category. It checks the pair against the registry and never chooses a specialist itself.
- **Foundation read client:** `adapters/foundation_ai_read.py` [B-FAR] sends `AI-Principal` and `X-AI-Contract-Version` on every request, and checks `X-AI-Contract` on every response ([B-FAR] lines 178 to 179, 252, 264).

### 2.3 Conditions before any Lineage B code enters the integration

Each condition has an owner. None is met by this contract alone.

1. **Pin.** Use the exact SHA `0389318`. A later Line B commit needs a new compatibility review (AI Engine team).
2. **Blob identity.** Check `foundation_ai_read.py` and the contract files it imports against [AICON] (AI Engine team, QA owner).
3. **Shopify re-point.** `registry_map.py` must point the Shopify category at the canonical adapter-governed module [SHOP] (OPEN-21). The Line B `ai_engine/shopify` path must not run in integration (AI Engine team).
4. **Client conformance.** The Line B Foundation client must pass the same conformance tests as the Foundation side (T2, T11 in section 17). This is a test run, not done here.
5. **Packaging.** Line B's `ai_engine` root differs from Line A's `webdesk_ai`. Imports and packaging change accordingly (AI Engine team).

### 2.4 What Line B does not yet prove

- Its test suite was not run in this session.
- Its base is older than the Foundation candidate (`af37f7b`; [DSC-01 §B]). It shares no merge ancestry with `5974d59`. An integration step must therefore be a reviewed file-list merge, not a branch merge.

---

## 3. Foundation identity and authorization ownership

### 3.1 Human identity

- Foundation owns human identity and sessions. Human routes require `Authorization: Bearer <session token>`, and the actor comes from the session, never from the body [F-RT] line 3.
- Sessions are validated only by the trusted authentication authority ([F-APP] lines 30 to 31).
- Privileged mutations are authorized by operation proofs. The actor is derived from authenticated proof bound to a session and a scoped operation and resource. A parameter or a mutable GUC is not proof [F-R4] line 12.

### 3.2 AI principal

Unchanged from v1, section 3.2. Issued and revoked by human routes only, bound to one project, one run and one human, TTL 15 minutes, verified in PostgreSQL on every request ([AICON] sections 3 to 5; [F-0041] lines 135 to 151).

Route path (OPEN-02): **`POST /v1/runs/{run_id}/ai-principal`** and **`POST /v1/runs/{run_id}/ai-principal/revoke`**. The code at `5974d59` mounts them without `/v1` ([F-AI] lines 268 and 296). Section 6.2 records the change.

### 3.3 Specialist identity (D-6)

A specialist holds no Foundation credential and no AI principal. `actor_id` is derived by Foundation from the authenticated session proof and is never supplied by the caller (D-6). Adapter 0.2 takes `actor_id` from the caller [S-AD] line 54. Adapter 0.3 removes it (section 6.3).

### 3.4 Operator role and rule (OPEN-04)

- The authorized operator is the Foundation **`Approver`** role [F-RBAC] line 25.
- The matrix cell for Approver is `GRANTED` for the relevant view actions: an active role assignment **and** an active project access grant whose `permitted_actions` contains the operation key [F-RBAC] (module header, cell rules).
- A role name supplied by a caller grants nothing. The database rule must check the role assignment and the grant, not the request body.
- The database rule for `specialist.execution.confirm` is a row in `operation_authorization_rules` (section 11.3). Its exact form is verified by the Foundation team against the `GRANTED` semantics before the migration is accepted.

### 3.5 Authorization ownership matrix

| Concern | Owner | Enforced by |
|---|---|---|
| Human session | Foundation authority | Foundation session check [F-RT] |
| Project and run read rights | Foundation | PostgreSQL functions, each request ([AICON] §3.2, §5) |
| AI principal lifecycle | Foundation | Authority and guard functions ([F-0041]) |
| Specialist execution confirmation | Foundation | Operation proof, Approver role and grant, single-use confirmation record (section 8) |
| Specialist action allowlist | WebDesk adapter | Declaration check plus adapter 0.3 binding ([S-AU]; QA-07) |
| Routing | WebDesk | Explicit operator selection [B-RTE] plus confirmation (section 5) |

---

## 4. AI Engine execution responsibilities (Lineage B)

The AI Engine is a consumer. It holds only the AI principal and reads through `ai-read/v1` ([AICON] principle 1).

1. **Read.** Fetch run, project, source versions, segments and content through the Foundation read client [B-FAR]. Refuse any response whose contract header differs.
2. **Analyse.** Requirement analysis runs in `ai_engine/requirement_analysis/` and `orchestration/workflow.py`. Output is proposals.
3. **Select explicitly.** An operator names requirement proposals for investigation [B-SEL]. This is an attributed claim, not authorization. Section 8 supplies the authorization.
4. **Route explicitly.** A specialist runs only when an operator names the category and capability, and the pair exists in the registry [B-RTE]. Automatic routing is disabled (registry `machine_routing_enabled: false`, cited in [B-RTE] header).
5. **Invoke bounded.** A specialist runs with a wall-clock bound. A failure becomes a status; a partial output is not returned (Line A pattern, [A-BA] `run_specialist`; Line B equivalent to be confirmed under condition 4).
6. **Return proposals.** The result is a review package for a human. It never writes to Foundation and never approves scope ([AICON] §14).
7. **Model.** A scripted model is the only adapter used in integration ([A-MO] line 192). Any live provider needs separate approval and a check of Lineage B's model port (`llm/adapters.py`, `llm/port.py`) against [AICON] §13A.

**Not AI Engine responsibilities:** authorizing its own privileged execution (OPEN-15), writing to Foundation (OPEN-17), issuing AI principals or operator confirmations, deciding governance status.

---

## 5. Specialist routing and invocation

### 5.1 Required flow

```
1. AI Engine        names a category and capability explicitly (routing/explicit.py)       [B-RTE]
2. Operator         confirms through a Foundation human route, Approver role and grant    section 8
3. Foundation       verifies proof, role, grant, binding and expiry; issues confirmation  section 8
4. Foundation       the worker starts the execution with the confirmation reference        section 9.3, OPEN-15
5. Adapter 0.3      refuses unless the reference is valid for this exact envelope          section 6.3
6. Harness          runs the approved specialist, bounded, actor from proof                [S-HA]
7. Result           persisted by the worker as a proposal, never as an approved record    section 9.3
```

Step 2 is a human decision and must not be automated. Live model execution stays disabled, and live source access stays fail-closed (OPEN-22).

### 5.2 Current code against this flow

Adapter 0.2 still accepts `operator_confirmed` and `actor_id` from the caller ([S-AD] lines 54 and 61). Adapter 0.3 replaces them (section 6.3). This is a breaking change and is handed to the Specialist team (section 18).

### 5.3 Seven-specialist mapping (OPEN-12, OPEN-21, OPEN-22)

| Specialist (`SpecialistId`, [S-CA]) | AI Engine category (Lineage B, [B-ORCH]) | Capability (`CAP-*`) | Canonical implementation | Approved source entries | Integration status |
|---|---|---|---|---|---|
| `shopify` | `shopify_specialist` | `CAP-ECOMMERCE` | [SHOP] (adapter-governed) | Shopify only ([DSC-03 §8]) | Conformance and authorized integration tests. Live source access fail-closed until approved |
| `shift4shop` | `three_d_cart_shift_shopify_specialist` | `CAP-3D-CART-SHIFT-SHOPIFY` (legacy ID, canonical `CAP-SHIFT4SHOP` not in registry) | Platform module on the specialist branch | None | Conformance tests. Live refused |
| `wordpress_woocommerce` | `wordpress_woocommerce_specialist` | `CAP-WORDPRESS-WOOCOMMERCE` | Platform module on the specialist branch | None | Conformance tests. Live refused |
| `bigcommerce` | `bigcommerce_specialist` | `CAP-BIGCOMMERCE` | Platform module on the specialist branch | None | Conformance tests. Live refused |
| `magento_adobe_commerce` | `magento_adobe_commerce_specialist` | `CAP-MAGENTO-ADOBE-COMMERCE` | Platform module on the specialist branch | None | Conformance tests. Live refused |
| `standalone_applications` | `standalone_applications_specialist` | `CAP-STANDALONE-APPLICATIONS` | Platform module on the specialist branch | None | Conformance tests. Live refused |
| `middleware_applications` | `middleware_applications_specialist` | `CAP-MIDDLEWARE-APPLICATIONS` | Platform module on the specialist branch | None | Conformance tests. Live refused |

Notes:

- The `SpecialistId` set is the canonical identifier set. Category and capability are mapped to it, not the reverse.
- The Shift4Shop capability ID is the legacy one. Changing it is a registry migration and is not in scope (`B-ORCH` docstring).
- "Platform module on the specialist branch" means the module is `src/webdesk/specialists/platforms/<name>.py` on `claude/sprint5-specialist-evaluations`. Confirming each module's current source is a Specialist team task (section 18).

### 5.4 Rules that must hold

- A specialist never selects another specialist. Routing changes are forbidden to specialists ([S-AU] `modify_routing`).
- Only an Approver with an active grant can confirm execution (section 8).
- Unapproved external documentation sources are never invoked (OPEN-22).

---

## 6. Request and response schemas

### 6.1 Foundation to AI Engine, `ai-read/v1` (APPROVED, unchanged)

Five `GET` endpoints under `/v1/ai/...`, each with `Authorization: AI-Principal <token>` and `X-AI-Contract-Version: ai-read/v1` ([AICON] section 6; [F-AI] lines 91 to 100 check both). Response shapes are in [AICON] §6.1 and are not repeated here.

### 6.2 Human routes for AI principal lifecycle (canonical path, OPEN-02)

| Route | Operation proof | Response |
|---|---|---|
| `POST /v1/runs/{run_id}/ai-principal` | `ai.principal.issue` | `{contract, principal_id, token, expires_in_seconds}`, token shown once |
| `POST /v1/runs/{run_id}/ai-principal/revoke` | `ai.principal.revoke` | `{contract, revoked}` |

Foundation change required: move the two routes from `/runs/...` to `/v1/runs/...` ([F-AI] lines 268 and 296). Change only these two. Regression tests must show that the old path returns 404 and that the five `/v1/ai` GET routes are unchanged. Owner: Foundation team.

### 6.3 Specialist envelope

**Adapter 0.2 (as built, to be superseded):** request fields in [S-AD] lines 46 to 61, including caller `actor_id` and `operator_confirmed`. Response fields in [S-AD] lines 72 to 89.

**Adapter 0.3 (APPROVED, breaking change, OPEN-03):**

- **Request** (`extra="forbid"`):
  - `adapter_contract_version`: `"0.3"`.
  - `request_id`, `workspace_id` (see OPEN-11 and section 7), `run_id` (UUID), `project_id` (UUID).
  - `specialist_id` (one of seven), `capability_id` (canonical for that specialist, section 5.3).
  - `requirement_ids` (run-scoped, section 7), `evidence_refs`, `task`, `allowed_actions`.
  - `confirmation_ref`: opaque, single-use reference issued by Foundation (section 8). Replaces `operator_confirmed`.
  - **Removed:** `actor_id` and `operator_confirmed`. Both are set by Foundation, not the caller.
- **Foundation-set fields:** `actor_ref` (derived from the proof, section 3.3) is passed to the harness, not accepted from the envelope.
- **Verification:** the adapter refuses unless Foundation verifies `confirmation_ref` for the exact tuple `(run_id, project_id, specialist_id, capability_id, requirement_ids digest, allowed_actions digest)`.
- **Response:** as adapter 0.2, with `adapter_contract_version: "0.3"`. `confidence_status` stays `"not_assessed"`.
- **Version handling:** the adapter refuses any other `adapter_contract_version`. It does not fall back.

### 6.4 AI Engine result envelope

Line B's `contracts/` package defines the envelope (`B-CMN`, `B-EVD`). Line A's [A-CT] envelope is historical. The result is a review package with proposals and no approval flag. Persisted form: section 9.

---

## 7. Identifiers

| Identifier | Owner | Type | Status |
|---|---|---|---|
| `project_id` | Foundation | UUID | Approved ([AICON] §5) |
| `run_id` | Foundation | UUID | Approved ([AICON] §6.1) |
| `source_id`, `source_version_id`, `segment_id` | Foundation | UUID | Approved |
| `version` (source version) | Foundation | integer ≥ 1 | Approved |
| Requirement reference | AI Engine, run-scoped | `(run_id, REQ-NNN)`, `REQ-NNN` matches `^REQ-[0-9]{3,}$` | Approved (OPEN-10) |
| Question reference | AI Engine, run-scoped | `(run_id, Q-AI-NNN)` | Approved (follows OPEN-10) |
| `workspace_id` | Specialist side | string | Distinct from `project_id`. Relationship to be validated through Foundation (OPEN-11, D-DEP-1) |
| `specialist_id` | Canonical | enum, seven values ([S-CA]) | Approved (OPEN-12) |
| `category_id` | AI Engine | string (section 5.3) | Mapped to `specialist_id` |
| `capability_id` | Canonical | `CAP-*` (section 5.3) | Mapped to `specialist_id` |
| `confirmation_id` | Foundation | UUID | Approved (section 8) |
| `correlation_id` | Foundation | UUID from `X-Correlation-Id` or generated | Approved ([AICON] §10) |

### 7.1 `workspace_id` and `project_id` (OPEN-11)

- The two identifiers stay distinct. No global alias.
- The specialist envelope carries a `workspace_id`. Foundation must derive it for the run and validate that it belongs to the run's project and to the requesting Approver's authorization.
- **Current state:** no workspace entity exists on `5974d59` (no migration creates one). The relationship therefore cannot be validated yet. This is dependency D-DEP-1 (section 18). Until it exists, a specialist run without a validated `workspace_id` is refused, not defaulted to `project_id`.

---

## 8. Operator-confirmation lifecycle (OPEN-03, OPEN-04, OPEN-05, OPEN-06)

### 8.1 Rules

- A caller-supplied Boolean is never sufficient.
- The operator must be authenticated, hold the active `Approver` role, and hold an active project access grant for the project whose `permitted_actions` contains `specialist.execution.confirm` (section 3.4).
- Confirmation is produced only by the Foundation proof path.
- Expiry uses the database transaction clock (`now()`), the same authority as the AI principal TTL.

### 8.2 Binding

A confirmation is valid only for the exact tuple below. Any difference refuses the execution.

| Field | Source |
|---|---|
| `run_id` | Foundation run; state must be an active status (section 9.1) |
| `project_id` | Foundation run's project; must be `active` |
| `specialist_id`, `capability_id` | The recommendation the operator named (section 5.1, step 1) |
| `requirement_ids_digest` | SHA-256 over the sorted run-scoped requirement references |
| `allowed_actions_digest` | SHA-256 over the sorted allowed actions |
| `operator_user_id` | From the authenticated session and operation proof |
| `operation` | `specialist.execution.confirm` (OPEN-06) |

### 8.3 Lifecycle states

| State | Entry | Exit |
|---|---|---|
| `requested` | Operator names a category and capability (Line B routing) | `confirmed`, `refused`, `expired` |
| `confirmed` | Proof, role, grant and binding verified | `consumed`, `revoked`, `expired` |
| `consumed` | Used once by one execution, atomically with the execution record | Terminal |
| `revoked` | Explicit revocation by an Approver, or the run leaves an active status | Terminal |
| `expired` | `now()` reaches `expires_at` | Terminal |
| `refused` | A check fails | Terminal, neutral to the caller (section 12) |

### 8.4 Expiry

- At most 15 minutes after `confirmed`. Checked on every use, at the consume step, inside the same transaction.
- Expiry uses the database clock. Application clocks are not used. The test clock `webdesk_test_clock` is test-only.

### 8.5 Operator role

Approver, with the grant rule in section 3.4 (OPEN-04).

---

## 9. Run status and persistence

### 9.1 Status mapping (OPEN-16, corrected)

The Foundation run lifecycle is defined by two CHECK constraints in `0007` [RUN7] lines 77 to 90, and extended by later migrations [RUN50]:

- `state` values: `created, intake_pending, parsing, intake_complete, requirements_extraction, clarification_pending, routing_pending, specialist_investigation, evidence_validation, scope_drafting, independent_review, changes_required, approval_pending, approved, rejected, superseded, blocked_pending_decision, failed, cancelled`.
- `status` values: `queued, running, waiting_human, blocked_pending_decision, completed, failed, cancelled`.
- **Pairing rule** [RUN7] line 97: `status = 'blocked_pending_decision'` requires `state = 'blocked_pending_decision'`.

The approved mapping, with the pairing rule applied:

| AI Engine or adapter outcome | Foundation effect (by a Foundation service only) |
|---|---|
| Analysis in progress | `status = running`; `state` as the workflow stage (for example `requirements_extraction`, `routing_pending`, `specialist_investigation`) |
| Operator confirmation outstanding | `status = waiting_human`; `state` unchanged from the stage that is waiting |
| Operator decision that blocks scope | `status = blocked_pending_decision` **and** `state = blocked_pending_decision` (paired) |
| `completed` | Run `status = completed` only after the Foundation worker validates the result |
| `completed_with_gaps`, adapter `incomplete` | Run stays `running` or `waiting_human`; gaps recorded |
| `failed`, `timeout`, `invalid_output`, adapter `failed` | Specialist or step recorded as failed. Run `status = failed` **only** for a system-level failure. This follows [R-SCH] line 77: run-level `failed` is reserved for system-level failures |
| Cancellation | `status = cancelled` through the existing Foundation path |

**Rule:** no AI or specialist output changes a Foundation status directly. The worker records the result, then a Foundation service computes the status.

**Remaining check (Foundation team):** the state transition function is not fully read here. Each transition in this table must be checked against it before the mapping is implemented.

### 9.2 Persistence (D-7 amended, minimum)

Entities are as in v1 section 9.2: `ai_result`, `ai_finding`, `citation`, `specialist_execution`, `operator_confirmation`. Each is a new revision (section 11.3). Forbidden content is unchanged: no token, token hash, prompt, full model response, or task text.

### 9.3 Write boundary (PW-1, OPEN-15, OPEN-17)

- The Foundation worker persists integration results with restricted authority: a Foundation guard function executed by the `webdesk_worker` role, which holds EXECUTE only (pattern in [0031] lines 8 and 15).
- No public HTTP write route exists. No AI principal and no specialist credential can write.
- The worker starts authorized AI execution. The AI engine does not start its own privileged execution.

---

## 10. Evidence and citation structures

### 10.1 Two evidence families

| Family | Structure | Provenance requirement |
|---|---|---|
| A. Foundation source citation | `source_id`, `source_version_id`, `version`, `segment_id`, `relation`, `supporting_quote` (≤ 300 chars); passage digest copied from `source_segments.text_content_hash` ([F-0007] line 114) | Foundation source version, not quarantined, readable by the bound human. Passage digest from Foundation |
| B. External documentation citation | `evidence_kind`, `publisher`, `source_url` (https, allowlisted), `checked_at` (timezone aware), `content_hash` (passage digest), `applies_to_platform`, `applies_to_platform_version`, `applies_to_edition`, `evidence_status`, `check_outcome`, `relevance_summary`, `limitations` ([B-EVD]) | Approved external kind only. Synthetic or model-knowledge evidence is never verified |

Specialist evidence references in adapter 0.3 use family A or B. The adapter 0.2 `EvidenceRef` shape [S-CT] is superseded.

### 10.2 Check outcome (OPEN-08)

`check_outcome` is a separate field from `evidence_status` and from `relevance_summary`. Values are exactly:

- **`SUPPORTED`**: requires at least one substantiating citation in which the passage supports the claim. A claim with no substantiating citation cannot be `SUPPORTED`.
- **`UNSUPPORTED`**: requires evidence that establishes a limitation or an impossibility for the claim. An absence of evidence is not `UNSUPPORTED`.
- **`UNKNOWN`**: applies when evidence is insufficient or inconclusive. It is the default when neither of the above holds.

`check_outcome` never sets `evidence_status`. It never creates `verified` status (section 10.4).

### 10.3 Citation record

| Field | Required for | Source |
|---|---|---|
| `citation_id` | all | Foundation UUID |
| `run_id`, `project_id` | all | Section 7 |
| `family` | all | A or B |
| `source_url` | B | https, on the allowlist (section 13) |
| `source_version_id`, `segment_id`, `version` | A | Foundation |
| `passage_digest` | A and B | A: `text_content_hash`. B: `content_hash` (SHA-256 hex of the normalized passage at check time) |
| `checked_at` | B | timezone aware |
| `applies_to_platform`, `applies_to_platform_version`, `applies_to_edition` | B | `applies_to_edition` approved (OPEN-09) |
| `evidence_status` | all | AI vocabulary (section 10.4) |
| `check_outcome` | all | `SUPPORTED`, `UNSUPPORTED`, `UNKNOWN` (section 10.2) |
| `relevance_summary`, `limitations` | all | Free text, bounded length |

Synthetic or model-knowledge evidence can never be verified ([B-EVD] invariant).

### 10.4 Mapping between vocabularies (OPEN-07)

Separate vocabularies are kept. The mapping is explicit and validated. Any value not in the table is refused.

**AI `evidence_status`** (Line B `common.py` 150 to 155): `verified`, `partially_verified`, `unverified`, `conflicting`, `not_applicable`.

**Adapter `evidence_status`** (adapter 0.3, `cited` / `unverified`):

| Adapter value | Maps to AI `evidence_status` | Condition |
|---|---|---|
| `cited` | `unverified` | At least one citation; `check_outcome` is set by the check in 10.2. The adapter never produces `verified` |
| `unverified` | `unverified` | No citation is required |

**Hard rules:**

- No adapter output ever maps to `verified`, `partially_verified` or `conflicting`. `verified` and `partially_verified` are set only by a human Foundation workflow, consistent with [AICON] §14. `conflicting` is set only by Foundation review.
- A `cited` finding whose `check_outcome` is not `SUPPORTED` remains `unverified` and is reported with its outcome.
- The mapping is validated by table-driven tests (section 17).

---

## 11. Database ownership and migrations

### 11.1 Rules

- Foundation owns every persisted record ([AICON] §1, §12). The AI Engine and the adapter hold no database credential.
- The application role cannot read `ai_principals` ([F-0041] lines 149 to 151).
- SECURITY DEFINER functions pin `search_path`. Three existing functions do not (QA F-2, [DSC-05 §1.3]). SG-10 applies.

### 11.2 Existing tables

As in v1 section 11.2, from the `CREATE TABLE` inventory at `5974d59`. No requirement, evidence, citation, finding, AI result, specialist execution, operator confirmation or workspace table exists.

### 11.3 Migration list (OPEN-18, OPEN-06)

Minimum revisions beyond `0059`. Each is a new revision file, approved as part of this decision, with one Alembic head maintained.

| Proposed revision (name to be assigned by Foundation) | Purpose | Contents |
|---|---|---|
| R-1 operation | Canonical confirmation operation | Add `specialist.execution.confirm` to `operation_proofs` CHECK; add `operation_authorization_rules` row for Approver |
| R-2 confirmation | Single-use confirmations | `operator_confirmation` table with binding, expiry, state and single-use constraints; guard functions, owner `webdesk_guard_owner`, EXECUTE to `webdesk_worker` only |
| R-3 results | Integration results | `ai_result`, `ai_finding`, `citation`, `specialist_execution` tables with check constraints for `check_outcome` and `evidence_status` values; no direct grant to `webdesk_app` |
| R-4 scope | Workspace relationship (D-DEP-1) | Only if Foundation decides a scope entity is needed. Otherwise none |

Each revision needs: single head check; isolated PostgreSQL upgrade and downgrade one step and re-upgrade; catalog comparison; privilege check (no PUBLIC EXECUTE, correct `search_path`). The frozen revisions `0001` to `0059` are unchanged.

### 11.4 Ownership

| Record | Owner | Writer | Reader |
|---|---|---|---|
| Projects, sources, versions, segments, runs, jobs | Foundation | Foundation services | AI Engine (read) |
| AI principals | Foundation | Guard functions | Foundation request path |
| Operator confirmations | Foundation | Guard functions (R-2) | Foundation; adapter receives a verified reference |
| Results, findings, citations, executions | Foundation | Worker guard function (PW-1, R-3) | Foundation |
| Audit events | Foundation | Foundation only | Foundation |

---

## 12. Error handling

- **Foundation `ai-read/v1`:** the table in [AICON] §9 is unchanged. Denials do not reveal the failing condition.
- **Human AI-principal routes:** the 403 `ai_principal_refused` in [F-AI] line 284 is a human-route refusal. It is kept, but its neutral wording is reviewed with OPEN-02 in the Foundation change.
- **Specialist:** harness codes in [S-ER] and adapter codes in [S-AD] lines 37 to 43. Mapping to one external outcome (`refused`, `failed`, `incomplete`), with detail in audit only. Mapping table is a test input (T17).
- **AI Engine client:** every [AICON] §9 status is mapped, and no failing condition is revealed. Tests T2 and T11.

---

## 13. Security boundaries

| Boundary | Rule | Source |
|---|---|---|
| AI identity | AI principal only; no human credential, no database credential, no operation proof, never Administrator | [AICON] §2 D-AI-1 |
| Operator confirmation | Only a Foundation-issued, single-use, operation-bound reference; Approver role and grant | Section 8 |
| Specialist identity | No Foundation credential, no AI principal; actor from proof | D-6; section 3.3 |
| Restricted content | Denied for every principal | [AICON] §2 D-AI-2, §5 |
| Quarantined content | Never returned, listed or acknowledged | [AICON] §5 |
| External transmission | Not authorized. `not_scanned` content is not sent to any external model | [AICON] §13A |
| Specialist authority | Declared, not enforced at run time (QA-07). No live execution until accepted | [DSC-03 §10]; D-9 |
| Source access | Only allowlisted https URLs; unapproved external sources never invoked. Live access fail-closed | OPEN-22; [DSC-03 §8] |
| Environment | Controlled development and integration only; production disabled | D-9 |
| Secrets | No token, password, connection string or session value in repository files, logs or reports | SG-11 |
| Scratch grants | Test-only. Production least privilege verified separately | OPEN-26; [G0] section 2 |

---

## 14. Audit

### 14.1 Existing (APPROVED)

Every AI read request writes one `audit_events` row in a transaction that survives refusal, with `ai.read.allowed` or `ai.read.denied` ([AICON] §10). No token, hash, content, segment text, prompt or response is recorded.

### 14.2 Event types (OPEN-25, approved)

| Event | When | Record refs (IDs only) |
|---|---|---|
| `ai.principal.issued`, `ai.principal.revoked` | Human route success and revoke | run, principal |
| `specialist.confirmation.requested`, `.confirmed`, `.refused`, `.revoked`, `.expired` | Section 8 lifecycle | run, confirmation, specialist |
| `specialist.execution.started`, `.completed`, `.refused` | Adapter call | run, execution, specialist, capability |
| `ai.result.persisted` | PW-1 write | run, result |

Each row carries `correlation_id`, `project_id`, `actor_type`, `actor_id_or_service` (the human, from proof, for operator events), `error_class` (internal reason only), and `redacted_details` with `request_sha256` and `response_sha256`. No `event_type` CHECK constraint was found in any migration on `5974d59`, so these names need no change to a constraint on that basis. Compatibility with existing audit rules is confirmed by the Foundation team at implementation.

---

## 15. Version compatibility

| Interface | Version | Breaking change |
|---|---|---|
| Foundation to AI read | `ai-read/v1` | None |
| Human AI-principal routes | Path `/v1/runs/...` (section 6.2) | Yes: path change for two routes |
| Specialist adapter | `0.3` (section 6.3) | Yes: `actor_id` and `operator_confirmed` removed from caller |
| Specialist harness | `1.0.0` | None |
| AI Engine (Lineage B) | To be declared at the pinned SHA `0389318`; Line B has no contract-version constant in the files read | Declare a version before integration (section 2.3, condition 1) |
| Specialist registry | `0.3.10-foundation-gate1-review` ([S-AD] line 33) | None |
| Migration chain | Head `0059`, plus revisions in section 11.3 | New revisions only |

Rules: an unknown version is refused, with no fallback ([AICON] §13). Adapter 0.3 refuses 0.2 envelopes.

---

## 16. Failure and recovery

| Failure | Behaviour |
|---|---|
| AI principal expired | 401. The AI Engine does not renew. A human issues a new principal |
| Run leaves an active status | Requests refused on the next request ([AICON] §4) |
| Operator confirmation expired | Refused at the consume step, atomically. Recorded in audit. A new confirmation is required |
| Specialist timeout | Process killed at the bound; no late result accepted |
| Specialist provider failure | `provider_failure`, retryable at the worker's discretion |
| Partial analysis | `completed_with_gaps`; no fabricated output |
| Worker lease lost | `LeaseLost`; lease 120 s; owner fence on `fn_worker_mark_inputs_changed` ([DSC-05 §3]; D-14) |
| Duplicate request | Idempotency key scoped to (actor, endpoint, key), 24 hours ([F-IDEM]). Reuse for specialist execution to be confirmed by the Foundation team |
| Migration rollback | Supported range down to `0058` and `0055_int_merge_p2_p3_p7` ([F-INT] ruling 4) |
| AI read rollback | Removes `/v1/ai` routes; Foundation otherwise unchanged |

**Recovery rule:** a refused or failed step is re-run only with a new operator confirmation, and a new principal where needed. No step retries silently across a confirmation boundary.

---

## 17. Test register (traceability in the matrix)

Test IDs from [DSC-07] stay. New test IDs are added for the decisions. Each gate names the SHA it must pass on. **No test is declared passed by this contract.**

| Gate | Tests | Status |
|---|---|---|
| G0 technical baseline | T0, T1, T6, T6a, T7, T8, T18 on `5974d59` | Recorded in [G0] section 3: pytest 1031 passed, 0 failed, 0 skipped; ruff; mypy strict; Alembic single head `0059`. Accepted ([APP] section B). T6 full matrix and T8 not in the G0 record |
| AI read path | T2, T3, T4, T5, T9, T10, T11 | Not run |
| Route path (new) | R-PATH-1 to R-PATH-3 | Not written. Owner: Foundation |
| Operator confirmation (new) | C-1 to C-7 (section 8 states, binding, expiry, reuse, role, grant, caller boolean refused) | Not written. Owner: Foundation |
| Adapter 0.3 (new) | A-1 to A-4 (0.2 refused; `actor_id` and `operator_confirmed` fields refused; `confirmation_ref` binding; no fallback) | Not written. Owner: Specialist team |
| Status mapping (new) | S-1 to S-3 (table; pairing rule; system-level failure only) | Not written. Owner: Foundation |
| Evidence mapping (new) | E-1 to E-3 (table-driven; no adapter output maps to verified) | Not written. Owner: AI Engine and Specialist |
| `check_outcome` (new) | K-1 to K-3 (SUPPORTED, UNSUPPORTED, UNKNOWN rules) | Not written. Owner: AI Engine |
| Seven-specialist mapping (new) | M-1 (SpecialistId, category, capability consistent across [S-CA], [B-ORCH], [B-REG]) | Not written. Owner: AI Engine |
| Single Shopify (new) | SH-1 (exactly one Shopify implementation on the integration path) | Not written. Owner: AI Engine |
| Fail-closed source (new) | F-1 (six specialists without allowlist refuse live source access) | Not written. Owner: Specialist |
| Lineage B integrity (new) | LB-1 (pin `0389318`; blob identity) | Not run. Owner: AI Engine and QA |
| Migrations | Each revision in 11.3: single head, isolated upgrade and downgrade, catalog, privilege | Not written |
| Audit (new) | AU-1 (event types written; no forbidden content) | Not written |
| Final integration QA | Independent, on the integration SHA | Not started ([APP] section F) |

---

## 18. Open items and handoffs

No OPEN item remains open in v1.1. Each decision is in the register (`REG`). The following genuine dependencies and handoffs remain, because they are implementation work.

| ID | Dependency or handoff | Owner | Blocks |
|---|---|---|---|
| D-DEP-1 | Scope entity or rule relating `workspace_id` to `project_id` (OPEN-11) | Foundation | Specialist runs |
| D-DEP-2 | Foundation worker adapter that starts authorized AI execution (OPEN-15, OPEN-17) | Foundation | Any end-to-end run |
| D-DEP-3 | Migration revisions in 11.3, each with isolated PostgreSQL evidence (OPEN-06, OPEN-18) | Foundation | Confirmation, persistence |
| D-DEP-4 | Adapter 0.3 implementation and tests (OPEN-03) | Specialist team | Specialist execution |
| D-DEP-5 | Lineage B integrity and conformance (section 2.3) | AI Engine team, QA | Engine integration |
| D-DEP-6 | Canonical Shopify module confirmed and reachable on the integration path (OPEN-21) | Specialist team, AI Engine team | Shopify conformance |
| D-DEP-7 | Route path change for two AI-principal routes, with regression tests (OPEN-02) | Foundation | Principal issuance on the canonical path |

Handoff rule: these are code or migration changes owned by Foundation, AI Engine or Specialist teams. They are not done in this contract and must not be made in another team's active worktree.

---

## 19. Verification record

**Read in this session for v1.1:** [REG] (written), [G0] (read in full), Line B at `0389318`: `selection/operator.py`, `routing/explicit.py`, `adapters/foundation_ai_read.py` (header and lines 170 to 180, 250 to 270), `orchestration/registry_map.py` (identity list), `contracts/evidence.py` (lines 31 to 75), `contracts/common.py` (lines 150 to 165), `specialists/registry.py` (function list); Foundation `5974d59`: `rbac/matrix.py` (header and cell rules), `migrations/0007` (lines 76 to 96), `0050` (grep), `0031` (header); `platforms/shopify.py` on `05b03e8` (header only).

**Not read in full:** Line B's `orchestration/workflow.py`, `llm/` and `governance/`; the Foundation transition function for run states; the Line B registry YAML; the Foundation worker code. Claims about them are limited to what was read.

**Not verified:** no test, lint, type check, migration or database command was run in this session. CI status could not be checked: `gh` is not installed, so the GitHub Actions status for the pushed commit was not read.

**Identifiers:** no token, password, connection string or session value appears in this document.
