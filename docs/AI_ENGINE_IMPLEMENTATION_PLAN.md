# AI Engine (Track B) — Implementation Plan

- **Branch:** `feature/ai-engine`
- **Worktree:** `D:\WDS\Agentic System FrameWork\.claude\worktrees\webdesk-ai-engine-af7c07`
- **Base commit:** `af37f7b` (Foundation Increment 3 Phase 1 A2, identical to `feature/increment-1-foundation`)
- **Status:** Planning + first increment (AI-1). Not pushed, not merged. Requires explicit approval before any push or merge.
- **Specification baseline:** `WebDesk_Agentic_Requirement_Platform_Specs/` at v0.3.10 (`working_draft_unapproved`). The AI engine is governed by `GOVERNANCE.md`, `REQUIREMENT_SCHEMA.md`, `AGENT_REGISTRY.yaml`, `SERVICE_CATALOG.yaml`, `DECISION_REGISTER.md`.

## 1. Specification inspection summary

| Area | Finding | Consequence for Track B |
|---|---|---|
| Canonical schema | `REQUIREMENT_SCHEMA.md` §2 enums, §3 ID prefixes, §4 entities, §4.3.1 routing metadata and specialist output contract | Contracts reuse these names and enums verbatim |
| Routing | `AGENT_REGISTRY.yaml` `machine_routing_enabled: false`; `structured_rules_status: pending_controlled_vocab_and_predicates_C05` | No machine routing. Specialist selection is an explicit, labelled input until C-05 is approved |
| Registry | All entries `status: proposed`; registry `working_draft_unapproved` | Agents run only against synthetic fixtures; registry status is recorded on each result |
| Specialist categories | Seven logical categories (`GOVERNANCE.md` §5.3); WordPress+WooCommerce is one category | Shopify is the only specialist in scope |
| LLM provider | D-12: provider configurable, provider/model/budget/data-processing policy OPEN | Provider is a protocol only. No LLM is called. Agents are deterministic |
| Evidence | D-02: internal RAG first, then approved live vendor docs; allowlist OPEN and default-deny (C-06) | Shopify evidence is synthetic mock only, typed as `synthetic_mock` |
| Evidence status | `unverified` until checked; mock evidence can never be `verified` | Enforced in contract validators |
| Requirement origin | D-07: AI-inferred requirements can enter committed scope only after explicit human acceptance | AI output is `ai_proposed`; `accepted_for_scope` is rejected at contract level |
| Estimates | D-04: AI proposes, authorised reviewer approves; no numeric estimates without basis | Out of scope for AI-1 |
| Hosting / retention | D-16 deferred; D-13 open | No deployment, no production data handling |
| Identifiers | Foundation generates all IDs (`REQUIREMENT_SCHEMA.md` §3) | AI emits local `proposal_key`s; Foundation assigns `REQ-`, `Q-` etc. |

## 2. Repository layout decision

The AI engine lives in a top-level `ai_engine/` directory with its own `pyproject.toml` and `uv.lock`, using a `src/` layout.

Reasons:
- It does not touch the Foundation root `pyproject.toml`, `uv.lock`, `src/webdesk` or `tests/`, so there are no merge conflicts with Track A.
- The Foundation test suite (`testpaths = ["tests"]`) does not collect AI tests, and AI tests do not import `webdesk`.
- The only dependency on Foundation is the read-only contract shape, not code.

Target layout:

```
ai_engine/
  pyproject.toml
  src/ai_engine/
    contracts/              # Stage 1: versioned typed contracts (AI-1)
    requirement_analysis/   # Stage 2: Requirement Analysis Agent (AI-1)
    adapters/               # Foundation read port + mock Foundation adapter (AI-1)
    specialists/            # Stage 3: registry loader (AI-1); framework (AI-2, planned)
    shopify/                # Stage 4 (AI-3, planned)
    routing/                # Stage 3 (blocked on C-05 for machine routing)
    evidence/               # evidence status policy (AI-2, planned)
  fixtures/                 # synthetic data only
  tests/
docs/AI_ENGINE_IMPLEMENTATION_PLAN.md
```

## 3. Integration boundaries with Foundation

### 3.1 Ownership of fields

| Contract | Foundation-owned (read by AI, never written by AI) | AI-proposed (validated before any persistence) |
|---|---|---|
| `ProjectContext` | `project_id`, `project_revision`, `name`, `data_classification`, `access_boundary_id`, `platforms`, `application_types` | none |
| `SourceSegment` | `segment_id`, `source_id`, `source_version`, `project_id`, locator, `text`, `source_trust`, `extraction_version` | none (immutable input) |
| `SourceReference` | `source_id`, `source_version`, `segment_id` | `relation`, `supporting_quote` (must be a substring of segment text) |
| `AtomicRequirement` | `requirement_id` (assigned only by Foundation, `None` for proposals) | everything else; `review_state` is fixed to `proposed_pending_human_review` |
| `ClarificationQuestion` | `question_id` (Foundation) | `proposal_key`, `question_text`, `reason`; status fixed to `open` |
| `EvidenceReference` | `evidence_id`, `project_id`, checked timestamp | `relevance_summary`, `limitations` (kind and status are set by the retrieval layer, not the model) |
| `Claim` | `claim_id` (Foundation) | claim text, claim type, feasibility, verification task |
| `SpecialistTask` | `task_id`, `project_id`, `project_revision`, `requirement_ids`, `routing_outcome` | `investigation_questions` (deterministic framing) |
| `SpecialistInvestigationResult` | `task_id` echo | candidate solutions, claims, risks, questions, `status` |
| `AgentExecutionResult` | `execution_id`, `run_id`, timestamps, registry and catalog versions | `status`, `validation_errors` |

### 3.2 Read and write ports

- `FoundationReadPort` (AI-1): `get_project(project_id)` and `list_source_segments(project_id, max_classification)`. The mock adapter refuses cross-project reads and any segment classified above `max_classification`. Authorization is decided by Foundation; the port only enforces what Foundation passes in.
- No write port in AI-1. Candidate persistence is deferred until the Foundation `WorkflowRun` service exists. Persistence will use candidate tables or a candidate payload, never approved `Requirement`, `ScopeItem` or `Estimate` tables.
- The AI engine has no database access, no auth, no role logic and no SOW write path.

### 3.3 Prohibited paths (enforced by design)

- No import of `webdesk` and no SQL.
- No LLM call in AI-1. The provider protocol is defined but raises `ProviderNotConfiguredError` by default (D-12).
- No network access. The evidence source is a fixture.
- Source text is data. Instruction-like text is recorded as an ambiguity and never executed or treated as an approval.

## 4. Specification gaps and unresolved decisions

| # | Gap / open decision | Source | Impact | Handling in this work |
|---|---|---|---|---|
| G1 | Structured routing predicate vocabulary and router are not approved | `AGENT_REGISTRY.yaml` C-05 | Cannot select specialists automatically | No router. Specialist selection is an explicit input with `routing_outcome` and rationale |
| G2 | LLM provider, model, budget, token ceilings, failure behaviour and data-processing policy | D-12 / M-13 | No live model use | Provider protocol only; agents deterministic |
| G3 | Canonical names and alias mapping for `CAP-3D-CART-SHIFT-SHOPIFY`, `CAP-ECOMMERCE`, `CAP-INTEGRATION-SOFTWARE` | D-15 | Alias risk | No new IDs for these. Only `CAP-ECOMMERCE` (Shopify) is used, with its registry name |
| G4 | Vendor domain allowlist (default deny) | D-02 / C-06 | No live vendor research | Shopify evidence is `synthetic_mock` only |
| G5 | Criticality trigger predicates (security, privacy, data integrity, payments, access control, feasibility) | D-06 | Cannot compute criticality | Criticality is not produced; `materiality` defaults to `unassessed`, which gates as material |
| G6 | Full requirement acceptance eligibility predicates | D-08 / H-16 | Cannot accept requirements | Not implemented. AI never accepts |
| G7 | Dependency and conflict semantics (what counts as a conflict beyond timing contradictions) | `REQUIREMENT_SCHEMA.md` §4.9 | Conflict detection is partial | Deterministic conflict rule for a small timing vocabulary; documented limit |
| G8 | Specialist output DTO is listed as later-phase open | `REQUIREMENT_SCHEMA.md` §9.5 | DTO may change | Specialist contracts versioned as `0.1.0`; marked provisional |
| G9 | No ID prefixes exist for `SPT-` (specialist task), `EXEC-` (agent execution), `CAND-`/`QPROP-` (AI proposal keys), `CLAIM-` (claim, used in spec example) | `REQUIREMENT_SCHEMA.md` §3 lists only `PRJ, SRC, REQ, EVD, Q, SOL, SCOPE, RISK, ASM, EXC, REV, FIND, RUN, DEC, SOW` plus examples | ID collision or drift | Proposed prefixes used. Need WDS approval before persistence |
| G10 | Specialist and capability IDs: `specialist_category` strings | `GOVERNANCE.md` §5.3 | Naming drift | Used exactly as in registry: `shopify_specialist` |
| G11 | `Requirement` lifecycle has no `ai_proposed` state | `REQUIREMENT_SCHEMA.md` §5 | AI outputs must map to existing states | AI proposals use `captured`, `normalized`, `needs_clarification` or `blocked`; `ai_proposed` is a review-state field, not a lifecycle state |
| G12 | Registry status is `proposed` for every entry | `AGENT_REGISTRY.yaml` | Agent may not be approved to run | Results record `registry_version`; prototype runs only on synthetic data |
| G13 | Restricted-class content handling for AI | `REQUIREMENT_SCHEMA.md` §3.1 (F-2) | AI must not index restricted content | Mock refuses above `max_classification`; no restricted fixture |

## 5. Increment plan

| Increment | Scope | Status |
|---|---|---|
| **AI-1** | Stage 1 contracts; Stage 2 Requirement Analysis Agent (deterministic); mock Foundation read port; registry loader (read-only); unit and contract tests | Built in this worktree |
| AI-2 | Specialist framework: shared interface, task builder, output validator, evidence status policy, execution result wiring | Planned. Routing contract needs C-05 decision for anything machine-driven |
| AI-3 | Shopify Specialist with `synthetic_mock` evidence; unsupported-request handling; unsupported-claim tests | Planned. Blocked on G4 only for any live evidence, not for mock |
| AI-4 | Synthetic end-to-end demonstration and human-review-required output | Planned after AI-2 and AI-3 |

Stop points: no disputed routing rule (G1), no live LLM (G2), no vendor retrieval (G4), no real client data, no Foundation writes, no push or merge.

## 6. Verification plan

- Unit tests for each contract validator (valid and invalid cases).
- Contract tests that check source-reference integrity against segments and original-wording preservation.
- Behavioural tests for the Requirement Analysis Agent on a synthetic brief: atomic extraction, missing information, conflict, specialist classification proposal, instruction-like text, and AI-inferred origin separation.
- Registry compatibility test against the real `AGENT_REGISTRY.yaml` in the spec folder.
- Foundation boundary test: cross-project and above-classification reads are refused.
- Run: `uv run pytest` from `ai_engine/`, plus `uv run ruff check` and `uv run mypy src/ai_engine` (strict).
- The Foundation test suite is not changed and is not run as part of AI-1 acceptance, because nothing under `src/webdesk` or `tests/` is modified.

## 7. AI-2: specialist framework (implemented)

Scope: shared specialist interface, explicit routing record, requirement-to-task builder, task and
result validation, evidence policy, unsupported-claim handling, and the execution wrapper. No
platform specialist, no live evidence, no LLM, no Foundation storage.

| Module | Purpose |
|---|---|
| `specialists/base.py` | `SpecialistAgent` protocol, read-only `SpecialistContext`, error taxonomy |
| `specialists/task_builder.py` | Builds `SpecialistTask` from Foundation-identified requirements; SHA-256 snapshot hash |
| `specialists/validation.py` | Checks a result against its task, requirements and the evidence actually served |
| `specialists/execution.py` | `run_specialist`: binding checks, snapshot re-check, evidence recording, status mapping |
| `routing/explicit.py` | `ExplicitSelection` checked against the registry; `RoutingRecord` with spec log fields |
| `evidence/lookup.py` | Lookup port; mock is synthetic-only, project-filtered, default-deny on collections |
| `evidence/policy.py` | Conservative status roll-up; unsupported-claim reasons |

Routing remains explicit: `ExplicitSelection.basis` is fixed to `explicit_human_input_pending_C05`.
No code selects a specialist.

## 8. AI-1 independent review: disposition

A read-only review of commit `aacba1b` against the specifications produced twelve findings. Each is
listed below with its disposition. "Fixed" means a regression test now covers it.

| # | Finding | Disposition |
|---|---|---|
| 1 | Keyword-based `shopify_specialist` classification sits awkwardly beside `machine_routing_enabled: false` | **Open decision.** Kept as an analysis proposal, not a route. Needs WDS ruling on whether classification counts as routing before AI-3 |
| 2 | AI output could carry Foundation IDs (`REQ-`, `Q-`, `CLAIM-`, `SOL-`) | **Fixed** for analysis and specialist output. Persisted states remain Foundation's responsibility |
| 3 | Evidence provenance not enforced; `EvidenceKind` is an extension | **Partly fixed.** Verified internal evidence needs `source_version` and hash; lookup enforces project and allowlist. `EvidenceKind` extension **open** for ruling |
| 4 | Crash on over-length goal/constraint sentences; normalization could exceed 1000 characters | **Fixed** and regression-tested |
| 5 | Clear requirements emitted as `normalized` although only whitespace was normalized; spec contradiction on conflicting status (Example E vs §6) | `normalized` → `captured` **fixed**. Conflict status **open** (spec contradiction) |
| 6 | Specialist output field names and embedded evidence differ from §4.3.1; no output integrity check | Integrity check **added** (`validation.py`). Field-name alignment **open** |
| 7 | Missing spec fields: `text_excerpt_hash`, `created_at`, `revision`, `is_stale`, `input_revision_hash`, `source_id`/version on evidence | **Open.** Server-owned fields are documented as Foundation's; `text_excerpt_hash` still needed |
| 8 | `ScopeCommitment` and `CriticalityAssessment` enums absent | **Open.** Deferred per G5, but the gate cannot be expressed yet |
| 9 | Proposal-key prefixes overlapped Foundation prefixes | **Fixed** for Foundation prefixes. `STMT`, `CONF`, `APROP`, `QPROP` not yet in G9 approval |
| 10 | Routing metadata fields (`platform_refs`, `application_types`, `service_pattern_ids`, trigger signals); `specialist_recommendation` origin excluded | Trigger signals **added** in `RoutingRecord`. Others **open** |
| 11 | No project status (archived refusal); no ambiguity statements; registry status `proposed` unguarded | **Open** |
| 12 | Plan claims that were inaccurate (3.1 says retrieval, not the model, sets evidence kind and status; G9 omits STMT, CONF, APROP) | **Noted.** 3.1 describes intended retrieval-layer behaviour; the lookup port now enforces project and allowlist, but no retrieval layer exists yet. G9 gap is row 9 |

Requirement lifecycle: AI output is now limited to `captured`, `needs_clarification` and `blocked`.

## 9. AI-3: Shopify Specialist (implemented, synthetic only)

Scope: investigate Shopify-specific requirements on the AI-2 interface. Outputs are structured,
unverified implementation options. Nothing is selected, verified or accepted.

| Module | Purpose |
|---|---|
| `shopify/agent.py` | `ShopifySpecialist` (`CAP-ECOMMERCE`, `shopify_specialist`) |
| `shopify/synthetic_evidence.py` | Eight synthetic placeholder records in `shopify_synthetic_patterns`; each is `synthetic_mock` and `unverified`, names no publisher, and carries a `[stance:…]` tag for deterministic contradiction scenarios |

Behaviour:

- Refuses non-Shopify platforms and requests with no Shopify-specific behaviour (`UnsupportedRequestError`, mapped to `unsupported_request` by the wrapper).
- Relevance is decided by the agent's own keyword test. It does not read the requirement's
  `specialist_category_ids`, which are a non-authoritative proposal (WDS decision). Machine routing stays disabled.
- Per Shopify-relevant requirement: options for native, third-party app, custom theme or application
  work, and API integration (only where the requirement is an integration). Each option is
  `not selected`, `unverified`, and lists its verification tasks.
- Claims: a platform hypothesis (`CONFLICTING` when the served records contradict each other),
  an implementation feasibility claim (`feasibility: unknown`), and for integrations an API-behaviour
  claim. No claim is ever `verified`.
- Clarification questions (QPROP keys) cover plan and permissions, measurable performance targets,
  integration source of truth and direction, conflicting availability, and the open allowlist (D-02)
  when no evidence source returns results.
- Status: `evidence_unavailable` with an empty allowlist; `partial` when some requirements fall
  outside Shopify scope (named in `dependencies`); otherwise `completed`.

Verification: 24 scenario tests in `tests/test_shopify_agent.py` cover native, app, custom, API,
unsupported (task and request), conflicting evidence, missing information, unavailable evidence,
mixed scope, provenance, reference preservation, and an end-to-end run from the synthetic brief.

### 9.1 Specification gaps surfaced by AI-3

| # | Gap | Effect | Handling |
|---|---|---|---|
| S1 | `SpecialistInvestigationResult` has no assumptions field (§4.3.1) | Assumptions cannot be recorded as such | Expressed as dependencies; no assumption is adopted |
| S2 | `Claim` has no conflict references (§6.8 requires them for conflicting evidence or feasibility) | Conflict is recorded by status and cited evidence IDs only | Conflict carried in `CONFLICTING` status and a risk; scope gate not yet built |
| S3 | `EvidenceReference` must be `unverified` for synthetic records, so conflicting evidence cannot be expressed on the record itself | Conflict exists only at claim level | Recorded as a claim; flagged for ruling with the EvidenceKind extension |
| S4 | No service-pattern IDs: `SERVICE_CATALOG.yaml` loader is not built | `service_pattern_ids` is empty | Deferred to a later increment |
| S5 | Platform version is unknown in every run; §9.3 requires a known version for verified platform claims | No platform claim can ever be verified in this prototype | Expected; blocks live verification until a version is supplied |
| S6 | Contradiction tags (`[stance:…]`) are a test-fixture convention | Not a spec construct | Documented as synthetic; do not carry into production retrieval |

### 9.2 Readiness for AI-4

Ready for a synthetic end-to-end demonstration: fixture brief → analysis → Foundation-style ID
assignment → explicit task → Shopify run → human-review-required output. The demonstration must
not approve requirements, estimates or SOW scope. It must not call a live LLM or vendor source.

## 10. AI-4: synthetic end-to-end demonstration (implemented, synthetic only)

### 10.1 Summary

`ai_engine/src/ai_engine/demo/` runs the whole isolated workflow on the synthetic eCommerce brief:

1. Load the synthetic brief through `MockFoundationAdapter` (project and segments, classification `internal`).
2. Run `RequirementAnalysisAgent` (AI-1). Output: proposals, goals, constraints, flagged text, conflicts, assumptions, dependencies, questions.
3. Assign mock requirement IDs (`REQ-MOCK-####`) through an explicitly named mock boundary. The analysis object is not modified.
4. Build a specialist task with the AI-2 task builder, using an explicit `ExplicitSelection` of `CAP-ECOMMERCE` / `shopify_specialist`. Routing stays disabled.
5. Run `ShopifySpecialist` (AI-3) through `run_specialist` (AI-2), with evidence served only from the authorised collection.
6. Assemble `DemonstrationReport`: per-requirement traces, evidence traces, unresolved items, provenance counts, tracked gaps, and fixed review flags.

### 10.2 Workflow boundaries

| Boundary | Enforced by |
|---|---|
| No Foundation persistence | `BoundaryRecord.persistence` is fixed to `none`; `foundation_writes` is fixed to `0`. The adapter has no write methods (tested). |
| Mock IDs are not Foundation IDs | `IdAssignment.assignment_authority` is fixed to `mock_boundary_demo_only`. IDs use the `REQ-MOCK-` prefix. Demo run IDs are never `RUN-`, which is a Foundation prefix. |
| Project isolation | The adapter refuses other projects; the demo probes this and records `cross_project_probe: refused`. The probe raises if the boundary is not enforced. |
| No automatic routing | `machine_routing_enabled` is fixed to `false`. The one routing record has trigger `explicit_selection`. |
| No approval | `ReviewState` fixes `approved_requirement_count=0`, `scope_committed=False`, `sow_generated=False`, `estimates_approved=False`, `implementation_solution_selected=False`, `human_review_required=True`. Pydantic rejects any other value. |
| No live calls | No LLM, no network, no vendor documentation; the evidence source is the synthetic Shopify collection. |
| Provenance is explicit | Every trace carries labels: `synthetic_fixture`, `inferred_analysis`, `mock_identifier`, `unverified_evidence`. `human_approved` exists as a label but is never produced. |
| Nothing dropped | Every analysed requirement has a trace. Requirements outside the explicit selection are `not_selected` and listed as unresolved. Failures are `unsupported_request` or `execution_failure` items. |
| Traceable keys | Analysis keys are scoped `analysis/...`. Specialist keys are scoped `SPT-DEMO-0001/...`, because both sides number from 001. |

Model and code locations: `demo/model.py` (demonstration-only output model, not a Foundation domain model), `demo/workflow.py` (workflow), `demo/gaps.py` (tracked gaps), `demo/cli.py` and `demo/__main__.py` (CLI).

### 10.3 Demonstration result (synthetic fixture)

- Status: `completed_with_unresolved_items`.
- Requirements: 9 analysed proposals (6 client-explicit, 3 system-inferred). One is investigated (the storefront wishlist requirement); eight are `not_selected`.
- Specialist: one task, `SPT-DEMO-0001`, execution `succeeded`. Three candidate options (native platform, third-party app, platform extension). Two claims: one `conflicting` (the wishlist evidence contradicts itself), one `unverified`.
- Evidence cited: three synthetic records (`EVD-SHP-SYN-0001`, `-0002`, `-0003`), all `synthetic_mock` and `unverified`.
- Unresolved items: 29 (12 clarification questions, 2 conflicts, 3 unconfirmed assumptions, 8 not-selected requirements, 2 risks, 1 dependency, 1 flagged instruction).
- Output size: about 52 KB of JSON. Two runs are byte-identical.

### 10.4 How to run

From the `ai_engine/` directory:

```bash
PYTHONPATH=src uv run python -m ai_engine.demo
```

To write the JSON to a file instead:

```bash
PYTHONPATH=src uv run python -m ai_engine.demo --out demo_report.json
```

Tests:

```bash
uv run pytest
uv run ruff check src tests
uv run mypy
```

### 10.5 Test results

| Check | Result |
|---|---|
| `pytest` (full suite) | 266 passed (238 existing AI-1 to AI-3 tests, plus 28 new end-to-end tests) |
| `ruff check src tests` | clean |
| `mypy` (strict, `src/ai_engine`) | clean |

New end-to-end coverage (`tests/test_demo_end_to_end.py`): workflow completion, review-flag immutability, boundary probe, mock-ID labelling, project isolation, source traceability from requirement to segment to task to evidence, scoped references, explicit selection and disabled routing, not-selected requirements listed rather than dropped, conflicts and questions staying visible, instruction-like text flagged, missing evidence as a gap, unsupported / transient / permission failures as observable outcomes, no-candidate runs, determinism, tracked gaps, and the CLI.

### 10.6 Outstanding specification and governance gaps

Every item below is listed in the demonstration output under `tracked_gaps`. None is resolved here.

| ID | Gap | Owner |
|---|---|---|
| S1 | Specialist output has no assumptions field (section 4.3.1) | Specification |
| S2 | `Claim` lacks conflict references required by section 6.8 | Specification |
| S3 | Conflicting evidence cannot be expressed on a synthetic `EvidenceReference` | Specification / EvidenceKind ruling |
| S4 | Service catalog loader not built; `service_pattern_ids` empty | Engineering |
| S5 | Platform version unknown; no platform claim can be verified | Client input |
| S6 | `[stance:...]` tags are a test-fixture convention | Engineering (remove from production retrieval) |
| C-05 | Structured routing predicates not approved; machine routing disabled | WDS |
| D-12 | LLM provider, model and data-processing policy undecided; no LLM called | WDS |
| D-02 / C-06 | Vendor evidence allowlist undecided; only synthetic evidence used | WDS |
| D-06 | Criticality predicates undecided; materiality stays unassessed | WDS |
| D-08 / H-16 | Acceptance eligibility predicates undecided; nothing accepted | WDS |
| G9 | Proposed ID prefixes (SPT, EXEC, CAND, QPROP, APROP, STMT, CONF) await approval | WDS |
| G11 | No `ai_proposed` lifecycle state | Specification |
| G12 | Registry entries are `proposed`; the registry is an unapproved draft | WDS |
| D-PERS | No Foundation persistence or WorkflowRun integration; IDs are mock-assigned | Foundation integration |
| D-OP | Operator confirmation of the requirement list is not modelled. The demo default selects requirements whose non-authoritative category proposal names `shopify_specialist`. | WDS / product |
| D-10 | No approved SOW template; no SOW is generated | WDS |
| D-04 | No reference estimate dataset; no estimates are produced | WDS |

### 10.7 Contract compatibility concerns found during AI-4

- The demonstration report embeds AI-1 to AI-3 contract objects unchanged. Only one non-contract change was made: a read-only `project_id` property on `MockFoundationAdapter`.
- The report is a separate model, not a contract. It must not be persisted as a Foundation record without a separate decision.
- Mock requirement IDs follow the `REQ-` pattern, so the contracts accept them. Only the labels separate them from Foundation IDs. Any future integration must strip or re-issue them.
- Analysis and specialist keys can collide because both number from 001. The report scopes them, but the contracts do not. This is a gap to raise with the specification owner.
- The `SpecialistInvestigationResult` status `evidence_unavailable` and the demonstration status `specialist_not_completed` use different vocabularies. This is intentional, but it needs a mapping if statuses are ever shared.

### 10.8 Integration readiness assessment

Ready for an isolated review of the workflow and its outputs. Not ready for Foundation integration:

- Needs a Foundation-owned ID assignment service in place of `assign_mock_ids`.
- Needs a Foundation-owned persistence path for candidate records (blocked by G9 and D-PERS).
- Needs operator confirmation of the requirement list (D-OP).
- Needs approval of the proposed ID prefixes and the EvidenceKind extension.
- Needs a decision on routing (C-05) before any automatic selection is considered.

Nothing has been pushed or merged. Push or merge requires explicit WDS approval.
