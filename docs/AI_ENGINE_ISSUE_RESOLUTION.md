# AI Engine Issue Resolution (AI-4.1)

- **Branch:** `feature/ai-engine`
- **Baseline:** `829688e` (AI-4)
- **Scope:** known issues from AI-1 through AI-4, plus the contract stabilization they require.
- **Not in scope:** AI-5 (independent integration review), which has not started.
- **Status of this work:** implemented and verified in the working tree. Not committed, pushed or merged.

## 1. Status definitions

- **Resolved:** the issue is fixed in code, covered by tests, and needs no further approval to stay closed. Some resolved items still carry a *remaining approval* note.
- **Blocked:** the issue depends on a conflict inside the approved specifications. It is recorded as a specification amendment required before integration.
- **Deferred:** the issue is real but belongs to production functionality, a governance decision or Foundation integration. It is intentionally not implemented in this prototype.

## 2. Compatibility safeguards applied (step 3)

Every contract change in this increment is **additive and defaulted**. No field was renamed or removed. Consumers were identified by searching the source tree before each change.

| Change | Default | Consumers identified |
|---|---|---|
| `ProjectContext.status` (new) | `active` | `adapters/foundation.py` (fixture load), `requirement_analysis/agent.py` (refuses non-active), `specialists/task_builder.py` (refuses non-active), `specialists/execution.py` (denies non-active), `demo/workflow.py`, tests |
| `Claim.conflict_refs` (new) | `[]` | `contracts/specialist.py` (cross-check), `shopify/agent.py` (writes), `specialists/validation.py`, `demo/workflow.py` (traces), tests |
| `SpecialistInvestigationResult.assumptions` (new) | `[]` | `shopify/agent.py` (writes), `specialists/validation.py`, `demo/workflow.py` (unresolved items, traces), tests |
| `SpecialistInvestigationResult.conflicts` (new) | `[]` | `shopify/agent.py` (writes), `specialists/validation.py`, `demo/workflow.py` (unresolved items, traces), tests |
| `CollectedEvidence.conflict_group` (new, not a contract) | `None` | `evidence/lookup.py`, `shopify/synthetic_evidence.py`, `shopify/agent.py`, `specialists/execution.py` (delegation) |
| `EvidenceLookup.conflict_group_of` (new protocol method) | n/a | `MockEvidenceLookup`, `_RecordingLookup` in `specialists/execution.py` |
| `TrackedGap.status` values (widened) | `open` | `demo/model.py`, `demo/gaps.py`, tests |
| `RequirementTrace` fields `operator_decision`, `assumption_keys`, `conflict_keys` (new) | `None` / `[]` | demo report consumers (none outside this package) |
| `Investigation` literal value `rejected_by_operator` (new) | n/a | demo report consumers (none outside this package) |
| `DemonstrationReport.operator_selection` (new) | `None` | demo report consumers (none outside this package) |

Foundation-owned models and persistence were **not** modified. All edits are under `ai_engine/` and `docs/`.

## 3. Issue register

### 3.1 AI-1 review findings and remaining gaps

| Issue ID | Original problem | Decision / spec reference | Files and contracts affected | Resolution implemented | Tests added | Final status | Remaining approval |
|---|---|---|---|---|---|---|---|
| AI-1-R1 | Keyword classification to `shopify_specialist` looked like routing while machine routing is disabled | WDS decision: classification is a non-authoritative proposal only; C-05 | `requirement_analysis/agent.py` (proposal kept), `demo/workflow.py` (no longer used to select) | Investigation now requires an explicit operator decision (see AI-4.1-2). Classification never selects, routes or executes | `test_operator_selection.py::test_omitted_proposals_have_no_decision_even_when_shopify_relevant`, demo tests | Resolved | None for the proposal; C-05 remains open for any automatic routing |
| AI-1-R2 | AI output could carry Foundation IDs (`REQ-`, `Q-`, `CLAIM-`, `SOL-`) | REQUIREMENT_SCHEMA 3 | `contracts/analysis.py`, `contracts/specialist.py`, `contracts/common.py` (`proposal_key_is_namespaced`) | Fixed in AI-2; re-verified | `test_ai1_regressions_and_evidence.py`, `test_ai41_contracts.py::test_ai_output_never_carries_foundation_identifiers` | Resolved | None |
| AI-1-R3 | Evidence provenance not enforced; `EvidenceKind` extension | REQUIREMENT_SCHEMA 4.4, 9.3 | `contracts/evidence.py` | Verified internal evidence needs source version and hash (AI-2). `EvidenceKind` kept as an AI-local extension (item 6) | `test_ai1_regressions_and_evidence.py::test_verified_internal_evidence_needs_version_and_hash` | Resolved (AI-local) | Approval needed if the approved schema must carry `EvidenceKind` (EK-1) |
| AI-1-R4 | Crash on over-length goal/constraint sentences; normalization could exceed 1000 characters | Defensive validation | `requirement_analysis/agent.py` | Fixed in AI-2 | `test_ai1_regressions_and_evidence.py` | Resolved | None |
| AI-1-R5a | Clear requirements emitted as `normalized` although only whitespace was normalized | REQUIREMENT_SCHEMA 5 | `requirement_analysis/agent.py` | Emits `captured` (AI-2) | `test_ai1_regressions_and_evidence.py::test_clear_requirement_is_captured_not_normalized` | Resolved | None |
| AI-1-R5b | Conflicting requirements: spec Example E says `needs_clarification`; section 6 and GOVERNANCE 6 say blocked | REQUIREMENT_SCHEMA 5, Example E; GOVERNANCE 6 | `requirement_analysis/agent.py` (`_status_for`) | Unresolved material conflicts are `blocked`. Clarification need stays visible through attached question keys. The spec contradiction is recorded as amendment A-4 | `test_requirement_analysis.py::test_unresolved_conflicts_are_blocked_and_keep_their_clarification_links` | Blocked (spec conflict) | Specification amendment A-4 to define blocked and needs-clarification as independent indicators |
| AI-1-R6 | Specialist output names and embedded evidence differ from 4.3.1; status enum undefined in spec | REQUIREMENT_SCHEMA 4.3.1 | `contracts/specialist.py` | Field names unchanged. Status vocabulary frozen and tested | `test_ai41_contracts.py::test_specialist_status_vocabulary_is_unchanged` | Deferred | Specification alignment of 4.3.1 field names |
| AI-1-R7 | Missing spec fields: `text_excerpt_hash`, `created_at`, `revision`, `is_stale`, `input_revision_hash` | REQUIREMENT_SCHEMA 4.2, 3.1 | `contracts/source.py`, `contracts/analysis.py` | Server-owned fields belong to Foundation and are not AI outputs (documented). `text_excerpt_hash` needs the Foundation segment model | None (documented) | Deferred | Foundation segment model and server-owned field ownership |
| AI-1-R8 | `ScopeCommitment` and `CriticalityAssessment` enums absent | REQUIREMENT_SCHEMA 9.1; D-06 | none | Not added: D-06 is undecided. No gate can depend on it yet | None | Deferred | D-06 criticality predicates |
| AI-1-R9 | Proposal prefixes overlapped Foundation prefixes | REQUIREMENT_SCHEMA 3; G9 | `contracts/common.py` (`FOUNDATION_ID_PREFIXES`) | Namespace check rejects Foundation prefixes; test-covered | `test_ai1_regressions_and_evidence.py::test_proposal_key_may_not_reuse_a_foundation_prefix` | Resolved for prototype | G9: WDS sign-off before persistence |
| AI-1-R10a | Routing metadata missing: `platform_refs`, `application_types`, `service_pattern_ids`, `assigned_capabilities` | REQUIREMENT_SCHEMA 4.3, 4.3.1 | `contracts/requirement.py` | Trigger signals are recorded in `RoutingRecord` (AI-2). The others are not added in this increment | None | Deferred | Routing metadata design under C-05 |
| AI-1-R10b | `specialist_recommendation` origin excluded from AI output | GOVERNANCE 18 / D-07 | `contracts/requirement.py` (`AI_PROPOSAL_ORIGINS`) | Exclusion kept deliberately: an AI recommendation must not become a requirement origin | `test_contracts_source_requirement.py::test_ai_cannot_produce_specialist_recommendation_origin` | Deferred (governance) | WDS ruling on whether specialist recommendations may appear as origins |
| AI-1-R11a | `ProjectContext` had no status, so archived projects were not refused | REQUIREMENT_SCHEMA 4.1 | `contracts/project.py`, analysis, task builder, execution | `status` added (additive, default `active`) and enforced in all three (see AI-4.1-12) | `test_ai41_contracts.py` (archived denial, default and invalid status) | Resolved, pending amendment A-1 | Amendment A-1 |
| AI-1-R11b | `StatementKind.AMBIGUITY` never emitted | Plan 3.3 | `contracts/analysis.py` | Ambiguities are expressed as clarification questions. The enum value is retained for compatibility | None | Deferred (low priority) | None |
| AI-1-R11c | Registry status `proposed` not guarded at runtime | G12 | `specialists/registry.py` | Not guarded. Results record `registry_version`; prototype runs on synthetic data only | None | Deferred | G12: registry approval |
| AI-1-R12 | Plan claims inaccurate ("no machine routing" and evidence set by retrieval) | Plan review | `docs/AI_ENGINE_IMPLEMENTATION_PLAN.md` | Corrected in plan sections 8 and 11 | None (documentation) | Resolved | None |

### 3.2 AI-2 governance and contract gaps

| Issue ID | Original problem | Decision / spec reference | Files and contracts affected | Resolution implemented | Tests added | Final status | Remaining approval |
|---|---|---|---|---|---|---|---|
| AI-2-G1 | An agent that built an invalid record crashed the execution wrapper instead of returning a status | AI-2 review | `specialists/execution.py` | `pydantic.ValidationError` from the agent maps to `failed_validation` | `test_ai41_contracts.py::test_agent_building_an_invalid_record_becomes_failed_validation` | Resolved | None |
| AI-2-G2 | Archived projects could still receive new specialist tasks and runs | Item 12; REQUIREMENT_SCHEMA 4.1 | `specialists/task_builder.py`, `specialists/execution.py` | Denied with `permission_denied` (execution) and a task-build refusal | `test_ai41_contracts.py::test_archived_project_task_is_refused`, `::test_archived_project_execution_is_denied_even_with_a_valid_task` | Resolved | A-1 |
| AI-2-G3 | Evidence served during a run was not linked to conflicts | REQUIREMENT_SCHEMA 6.8 | `specialists/validation.py` | Conflict evidence must have been served to the run | `test_ai41_contracts.py::test_validation_reports_conflict_evidence_not_served` | Resolved | None |
| AI-2-G4 | Explicit routing record could be mistaken for automatic routing | AGENT_REGISTRY `machine_routing_enabled: false` | `routing/explicit.py`, `demo/workflow.py` | Routing record remains explicit; `machine_routing_enabled` fixed to `False` in the report | `test_demo_end_to_end.py` routing tests (AI-4) | Resolved | C-05 for any automatic routing |
| AI-2-G5 | Requirement snapshot and project revision could go stale between tasking and execution | Plan 3 | `specialists/execution.py` | Snapshot re-checked; revision checked | `test_specialist_execution.py` (snapshot changed, revision changed, missing requirement) | Resolved | None |
| AI-2-G6 | Invalid snapshot hash format | Contract | `contracts/specialist.py` | Hash must be 64 lowercase hex | `test_contracts_evidence_specialist.py::test_specialist_task_hash_must_be_sha256` | Resolved | None |
| AI-2-G7 | Service-pattern references not validated against a catalog | SERVICE_CATALOG; item 10 | `contracts/specialist.py` | Kept empty until an authorised catalog exists | `test_ai41_contracts.py::test_service_catalog_references_stay_empty` | Deferred | Authorised catalog |

### 3.3 AI-3 specification gaps S1 to S6

| Issue ID | Original problem | Decision / spec reference | Files and contracts affected | Resolution implemented | Tests added | Final status | Remaining approval |
|---|---|---|---|---|---|---|---|
| S1 | No assumptions field; assumptions were stored as dependencies | REQUIREMENT_SCHEMA 4.3.1 | `contracts/specialist.py` (`SpecialistAssumption`, `assumptions`), `shopify/agent.py` | Separate structure. Shopify plan premise moved from dependencies to assumptions | `test_ai41_contracts.py::test_assumption_is_separate_from_dependencies`, `::test_shopify_plan_premise_is_reported_as_assumption_not_dependency`, `test_demo_end_to_end.py::test_assumptions_are_separate_from_dependencies` | Resolved, pending amendment A-3 | A-3 |
| S2 | No conflict references on claims | REQUIREMENT_SCHEMA 6.8 | `contracts/evidence.py` (`Claim.conflict_refs`), `contracts/specialist.py` (`SpecialistConflict`, cross-checks), `shopify/agent.py` | Explicit two-way references between conflicts and claims; evidence IDs retained on both | `test_ai41_contracts.py` conflict tests, `test_demo_end_to_end.py::test_specialist_conflict_is_referenced_by_claim_and_trace` | Resolved, pending amendment A-2/A-3 | A-2, A-3 |
| S3 | Conflicting evidence cannot be expressed on a synthetic `EvidenceReference` (synthetic must be unverified) | REQUIREMENT_SCHEMA 4.4; GOVERNANCE evidence rules | `contracts/evidence.py` unchanged; conflict recorded at specialist level citing both records | Conflict record cites both unverified records; no evidence is promoted | `test_ai41_contracts.py::test_shopify_conflict_is_an_explicit_record_linked_to_its_claim` | Deferred | Governance ruling on how conflicting evidence states should be represented |
| S4 | Service catalog not loaded | SERVICE_CATALOG; item 10 | none | Kept empty | `test_ai41_contracts.py::test_service_catalog_references_stay_empty` | Deferred | Authorised catalog |
| S5 | Platform version unknown; no platform claim can be verified | REQUIREMENT_SCHEMA 9.3 | none | Unknown retained as unknown in every claim | `test_ai41_contracts.py::test_unknown_platform_version_stays_unknown_in_every_claim` | Deferred | Client-supplied platform version |
| S6 | `[stance:...]` tags placed in evidence text could be read as evidence metadata | Item 8 | `shopify/synthetic_evidence.py`, `evidence/lookup.py` | Stance text removed. Contradiction groups held in `CollectedEvidence` beside the record, reachable only through the lookup port, never serialised | `test_ai41_contracts.py::test_contradiction_metadata_never_appears_in_evidence_output`, `::test_mock_lookup_exposes_groups_only_through_the_port`, `::test_stance_tagged_text_is_not_treated_as_conflict_evidence` | Resolved | None |

### 3.4 AI-4 operator confirmation and demonstration limitations

| Issue ID | Original problem | Decision / spec reference | Files and contracts affected | Resolution implemented | Tests added | Final status | Remaining approval |
|---|---|---|---|---|---|---|---|
| AI-4.1-2 (D-OP) | Requirement selection inferred from keyword classification; no operator action | Item 2 | `selection/operator.py` (new), `demo/workflow.py`, `demo/cli.py` | Explicit `OperatorSelection` per proposal (confirm or reject). Investigation runs only for confirmed proposals. CLI requires `--operator` with any decision | `test_operator_selection.py` (15), demo tests `test_specialist_runs_only_for_the_confirmed_proposal` and others | Resolved | WDS policy approval for operator decisions as AI-side records |
| AI-4.1-3 | Non-selected requirements could be dropped from output | Item 3 | `demo/workflow.py`, `demo/model.py` | Every analysed proposal has a trace. Omitted proposals are `not_selected`; rejected are `rejected_by_operator`. Each has an unresolved item with its reason | `test_demo_end_to_end.py::test_omitted_proposals_are_kept_with_a_not_confirmed_reason`, `::test_rejected_proposals_are_kept_distinct_from_omitted` | Resolved | None |
| AI-4.1-binding | A selection could be applied to an analysis it was not made against | Item 2 (stale) | `selection/operator.py` | Fingerprint of the proposal content. Any change makes the selection stale and refused | `test_operator_selection.py::test_changed_proposal_makes_the_selection_stale`, `test_demo_end_to_end.py::test_stale_selection_is_refused_when_the_analysis_changes` | Resolved | None |
| AI-4.1-multi | Multiple selected requirements not exercised | Item 4 of tests | `demo/workflow.py` | Multiple confirmed proposals form one task | `test_demo_end_to_end.py::test_multiple_confirmed_requirements_are_investigated_together` | Resolved | None |
| AI-4-D1 | Demonstration operator identity is a label, not an authenticated identity | Foundation authentication out of AI scope | `selection/operator.py` | Recorded as a label; no authentication is implemented | None | Deferred | Foundation identity integration |
| AI-4-D2 | No Foundation persistence; mock IDs | Plan 3.2; D-PERS | `demo/workflow.py` (`assign_mock_ids`) | Labelled `mock_boundary_demo_only`; analysis untouched | `test_demo_end_to_end.py::test_mock_identifiers_are_labelled_and_leave_the_analysis_untouched` | Deferred | Foundation ID and persistence service |
| AI-4-D3 | Demonstration status vocabulary differs from specialist vocabulary | Intentional | `demo/model.py` | Documented mapping; not shared | None | Resolved | None |

### 3.5 Foundation contract compatibility concerns

| Issue ID | Concern | Decision / spec reference | Files and contracts affected | Resolution implemented | Tests added | Final status | Remaining approval |
|---|---|---|---|---|---|---|---|
| FC-1 | `ProjectContext.status` added; spec 4.1 names the field but the AI model did not carry it | REQUIREMENT_SCHEMA 4.1 | `contracts/project.py` | Additive, default `active`, same three values as the spec | archived and invalid-status tests | Addressed, pending amendment A-1 | A-1: confirm the AI read model mirrors Foundation status |
| FC-2 | `Claim.conflict_refs` and specialist `assumptions` / `conflicts` are not in the approved schema | REQUIREMENT_SCHEMA 4.3.1, 4.4, 6.8 | `contracts/evidence.py`, `contracts/specialist.py` | Additive, defaulted, validated. Not persisted | conflict and assumption tests | Addressed, pending amendments A-2 and A-3 | A-2, A-3 |
| FC-3 | Blocked versus needs-clarification distinction | REQUIREMENT_SCHEMA 5 and Example E; GOVERNANCE 6 | `requirement_analysis/agent.py` | Blocked used; clarification links kept | `test_requirement_analysis.py` (blocked test) | Blocked (spec conflict) | A-4 |
| FC-4 | Foundation-owned fields that AI output must not set | REQUIREMENT_SCHEMA 3 and 8 | all contracts | Enforced: `requirement_id`, `question_id`, `claim_id`, `solution_id` are rejected in AI output | `test_ai41_contracts.py::test_ai_output_never_carries_foundation_identifiers` | Resolved | None |
| FC-5 | `EvidenceKind` is not in the approved schema | Item 6 | `contracts/evidence.py` | Kept AI-local | `test_contracts_evidence_specialist.py` evidence tests | Resolved (AI-local) | Approval only if the schema must carry it |

## 4. Tests added or changed

Added:
- `tests/test_operator_selection.py`: 15 tests. Explicit decisions, rejection, omission, multiple selections, unknown and duplicate proposals, label required, stale analysis, cross-project selection, AI-side authority, and no changes to requirement records.
- `tests/test_ai41_contracts.py`: 33 tests. Archived and deleted project denial (analysis, task, execution), status defaults, conflict references in both directions, distinct evidence, assumption separation, Shopify conflict linkage, synthetic evidence provenance, contradiction metadata isolation, unknown platform version, empty service catalog, identifier separation, invalid-agent-output mapping, conflict evidence served checks, and backward compatibility.
- `tests/test_demo_end_to_end.py`: rewritten to 40 tests for the operator-driven workflow, including rejected and omitted requirements, stale and archived refusal, conflict and assumption references, failures, and the CLI.

Changed on purpose (behaviour change, not a regression):
- `tests/test_requirement_analysis.py::test_conflicting_requirements_need_clarification` is now `test_unresolved_conflicts_are_blocked_and_keep_their_clarification_links`. Conflicts are `blocked` per GOVERNANCE 6.
- `tests/test_shopify_agent.py::test_stance_tags_are_read_from_the_synthetic_records` is replaced by a test that contradictions are declared beside records and absent from summaries.
- Demo tests now require explicit operator confirmation. Previously nothing was selected by a default that the operator never made.

## 5. Verification

- `uv run pytest`: 326 passed.
- `uv run ruff check src tests`: clean.
- `uv run mypy` (strict, `src/ai_engine`): clean.
- Demonstration CLI determinism: two runs with the same inputs produce byte-identical JSON.

## 6. Resolved, blocked and deferred

**Resolved:** AI-1-R1, R2, R3 (AI-local), R4, R5a, R9 (prototype), R11a (pending amendment), R12; AI-2-G1, G2, G3, G4, G5, G6; S1, S2 (pending amendment), S6; AI-4.1-2, binding, multi, and the AI-4 omission and rejection handling; FC-1 (pending amendment), FC-2 (pending amendment), FC-4, FC-5.

**Blocked by an approved-specification conflict:** AI-1-R5b and FC-3, the blocked versus needs-clarification distinction (amendment A-4). Implemented per GOVERNANCE 6; the spec contradiction must be ruled on before integration.

**Deferred with justification:**
- AI-1-R6, R7, R8, R10a, R10b, R11b, R11c: production schema alignment, Foundation-owned fields, undecided criticality predicates, unregistered routing metadata, and a governance decision on specialist-recommendation origins.
- AI-2-G7, S4: no authorised service catalog exists.
- S3: governance decision on representing conflicting evidence states.
- S5: needs a client-supplied platform version.
- AI-4-D1, D2: Foundation identity, ID and persistence services are outside the AI engine.

## 7. Remaining governance decisions

1. **A-4:** blocked and needs-clarification as independent indicators (spec conflict; blocked is implemented).
2. **A-1, A-2, A-3:** approve the additive contract amendments before any integration.
3. **G9:** sign-off on the proposed ID prefixes (`SPT`, `EXEC`, `CAND`, `QPROP`, `APROP`, `SASM`, `STMT`, `CONF`, `RSKP`) before persistence.
4. **EK-1:** whether `EvidenceKind` must be part of the approved schema.
5. **S3:** representation of conflicting evidence states.
6. **D-OP:** WDS policy for operator decisions recorded as AI-side records.
7. **C-05, D-12, D-02/C-06, D-06, D-08/H-16, G12, D-10, D-04:** unchanged open decisions.

## 8. Readiness for AI-5 Independent Integration Review

Ready for review as an isolated prototype. Not ready for Foundation integration. Integration requires the approvals in section 7, a Foundation-owned ID service, and a Foundation persistence path. AI-5 has not been started.
