# AI Engine Independent Review (AI-5)

- **Branch:** `feature/ai-engine`
- **Reviewed commit:** `c159fac` (AI-4.1)
- **Type:** review-only. No fixes were implemented. Nothing was committed, pushed or merged.
- **Method:** repository inspection, the two register documents, independent runs of `pytest`, `ruff` and strict `mypy`, and two independent read-only reviews (contracts and governance; runtime, isolation and security). Reviewer claims were re-checked against the code before being recorded here. Where a reviewer's section citation could not be verified against the specification text, it is marked as such.
- **Independent check results at review time:** `pytest` 326 passed; `ruff check src tests` clean; `mypy` strict clean across 38 source files; working tree clean.

## 1. Verdict

| Scope | Verdict |
|---|---|
| Continued isolated development (synthetic data, no Foundation, no LLM) | **CONDITIONALLY READY**: after the P0 items in section 8 |
| Foundation integration | **NOT READY** |
| Production deployment (including any live LLM or RAG) | **NOT READY** |

The engine's safety core holds: no path reaches Foundation storage, no network or LLM module is imported, mock evidence cannot be verified, AI output cannot set approved states, and archived projects are denied at the three entry points. The findings below are about the strength of the gates (operator confirmation, evidence scope, conflict and status rules) and about the accuracy of the register. They are fixable in isolated development, but they must be fixed before the engine is treated as having working governance controls.

## 2. Verification of AI-4.1 resolutions

| Register item | Claimed resolution | Reviewed result |
|---|---|---|
| AI-4.1-2 (D-OP) operator confirmation | Explicit, per-proposal, bound to analysis | **Partly verified.** Explicit and required before any specialist runs (`demo/workflow.py`). Not auditable (label only, no actor identity or timestamp) and forgeable in-process (finding S-1). Mutable decisions (S-2). Register marks D-OP `closed`; that is an overclaim (C-13) |
| AI-4.1-binding | Any change makes the selection stale | **Not verified.** The fingerprint omits conflicts, questions, assumptions, statements, source references, category proposals, confidence, rationale and validation errors (S-3). Register is wrong |
| AI-4.1-3 rejected and omitted kept | Every proposal traced, reasons recorded | **Verified.** Traces and unresolved items cover all proposals |
| AI-4.1 multiple selection | Multiple confirmed form one task | **Verified** by tests |
| AI-4.1 archived denial | Analysis, task, execution refuse | **Verified** at `requirement_analysis/agent.py:199`, `specialists/task_builder.py:51`, `specialists/execution.py:115`. Trusts caller-supplied project status (S-11) |
| AI-4.1 bidirectional conflicts | Conflicts and claims reference each other | **Partly verified.** Conflict-to-claim direction is checked (`contracts/specialist.py:216-220`). Claim-to-conflict is only an existence check (`:225-228`). Duplicates and evidence membership unchecked (C-6) |
| AI-4.1 assumptions independent of dependencies | Separate structures | **Verified** (`contracts/specialist.py` `assumptions` field; Shopify plan premise is an assumption; external-access note is a dependency) |
| AI-4.1 stance tags removed | Not in evidence text or output | **Verified.** No `conflict_group` in any serialized output; the lookup is the only path |
| AI-4.1 blocked status | Unresolved conflicts are blocked | **Implemented as a draft choice**, not approved text. The register's wording "approved specifications" is incorrect (C-4) |
| AI-4.1 invalid agent output maps to failed validation | Contract errors become a status | **Verified** for `ValidationError` raised inside an agent. Agent self-reported `FAILED_VALIDATION` still yields execution `succeeded` (S-6) |
| AI-4.1 EvidenceKind AI-local | Kept AI-local | **Verified as a decision.** Remains an open approval item (EK-1) |
| AI-4.1 synthetic evidence unverified | Enforced | **Verified** (`contracts/evidence.py` validator; `MockEvidenceLookup` refuses non-synthetic at construction) |

## 3. Contract compatibility matrix

Consumers were identified by search. "Default safe" means existing JSON or callers behave as before.

| Change | Type | Consumers | Default safe | Spec alignment | Status |
|---|---|---|---|---|---|
| `ProjectContext.status` | Additive field, default `active` | adapter fixture load; analysis; task builder; execution; demo | Yes for old payloads, but a missing status is treated as active (C-10) | REQUIREMENT_SCHEMA 4.1 lists status as required | Pending A-1 |
| `Claim.conflict_refs` | Additive field, default `[]` | specialist validator; Shopify agent; validation; demo traces | Yes | REQUIREMENT_SCHEMA 4.4 already lists `contradiction_refs` (line 178), a different name (C-11) | Pending A-2 |
| `Claim` CONFLICTING now requires `conflict_refs` | Tightening of an existing field | Shopify agent; tests | Breaking for any caller that previously built conflicting claims without references | Matches 6.8 intent | Pending A-2 |
| `SpecialistInvestigationResult.assumptions` | Additive, default `[]` | Shopify agent; validation; demo | Yes | Not in REQUIREMENT_SCHEMA 4.3.1 | Pending A-3 |
| `SpecialistInvestigationResult.conflicts` | Additive, default `[]` | Shopify agent; validation; demo | Yes | Not in REQUIREMENT_SCHEMA 4.3.1 | Pending A-3 |
| `EvidenceLookup.conflict_group_of` | New required protocol method, no default | `MockEvidenceLookup`; `_RecordingLookup` | **Breaking** for any other lookup implementation (C-11) | Test-only metadata | Internal |
| `CollectedEvidence.conflict_group` | Additive, default `None` | lookup; synthetic evidence; Shopify agent | Yes | Not a contract | Internal |
| `RequirementStatus.BLOCKED` used for conflicts | Behaviour change (previously `needs_clarification`) | analysis agent; tests | Behavioural change | Draft conflict between Example E and section 6 (C-4) | Pending A-4 |
| `TrackedGap.status` widened | Additive values | demo gaps; tests | Yes | Not a contract | Internal |
| Demo report fields (`operator_selection`, trace reference lists, `rejected_by_operator`) | Additive | demo consumers only | Yes | Not a Foundation contract | Internal |
| Foundation-owned models and persistence | None changed | none | n/a | n/a | Verified by inspection |

No field was renamed or removed. Enum members checked against REQUIREMENT_SCHEMA section 2 match.

## 4. Governance decision register

The reviewed items are treated as **proposed resolutions pending formal specification approval**. None is an approved Foundation amendment, and no code, test or document should describe them as one.

| ID | Item | Current treatment in code | Required before integration | Owner |
|---|---|---|---|---|
| A-1 | `ProjectContext.status` | Additive, default `active` | Approved amendment; decide whether missing status is refused (C-10) | WDS / Foundation |
| A-2 | `Claim.conflict_refs` | Additive; conflicting claims must cite | Approved amendment; align name with `contradiction_refs` or record divergence (C-11) | WDS / Foundation |
| A-3 | Specialist `assumptions` and `conflicts` | Additive | Approved amendment to REQUIREMENT_SCHEMA 4.3.1 | WDS / Foundation |
| A-4 | Blocked versus needs-clarification | Blocked used for unresolved conflicts | WDS ruling; the specifications are drafts, so this is not settled (C-4) | WDS |
| EK-1 | `EvidenceKind` extension | AI-local | Approval if the schema must carry it | WDS |
| S3 | Conflicting evidence states on synthetic records | Conflict recorded at specialist level | Governance ruling on representation | WDS |
| D-OP | Operator confirmation policy | Explicit AI-side record; marked `closed` in gaps (incorrect, C-13) | WDS policy; reopen until approved | WDS |
| G9 | Proposed ID prefixes | Used; list incomplete (`SOLP`, `CLM` missing, C-12) | WDS sign-off on the full list before persistence | WDS |
| C-05 | Structured routing predicates | Machine routing disabled | Approved routing vocabulary before any automatic routing | WDS |
| D-12 | LLM provider, model, budget, data policy | No LLM call path | Decision before any LLM use | WDS |
| D-02 / C-06 | Vendor evidence allowlist | Synthetic only | Allowlist decision before any live retrieval | WDS |
| D-06 | Criticality predicates | Not implemented; `unassessed` | Predicates; also gates C-3 | WDS |
| D-08 / H-16 | Acceptance eligibility predicates | Nothing accepted by AI | Predicates before any acceptance workflow | WDS |
| G12 | Registry approval | All entries `proposed`; no runtime guard | Approved registry | WDS |
| D-10 | SOW template | No SOW generated | Approved template | WDS |
| D-04 | Reference estimate dataset | No estimates generated | Dataset and approval | WDS |
| D-PERS | Foundation persistence and WorkflowRun integration | Not built; mock IDs | Foundation design and approval | Foundation |

## 5. Findings

Severity: Critical, High, Medium, Low, Info. File references are to `ai_engine/src/ai_engine/` unless shown otherwise. Items marked **(verified)** were re-checked by the lead reviewer against the code.

### 5.1 Contracts and governance

| ID | Severity | Finding | Location | Specification / governance | Impact | Recommended correction |
|---|---|---|---|---|---|---|
| C-1 | High | A candidate solution can carry `verified` or feasible status with no evidence. There is no evidence field on `CandidateSolution`. | `contracts/specialist.py` (`CandidateSolution`, validator near lines 152-167) | REQUIREMENT_SCHEMA 4.6, 6.7; GOVERNANCE 6 ("a plausible implementation path is not proof of feasibility") | An AI output can present an unsupported option as verified | Forbid AI-set `verified` on candidates, or require served and verified evidence IDs |
| C-2 | High | Specialist output accepts a `question_id` and any status. The result validator checks only claim and solution IDs. **(verified: no `question_id` check in `specialist.py`)** | `contracts/specialist.py` (`SpecialistInvestigationResult` validator); `contracts/clarification.py` (validator allows `question_id` with any status when `proposal_key` is absent) | REQUIREMENT_SCHEMA 4.5 (waiver needs an authorised human); section 3 | A specialist can emit a Foundation-shaped question, including a waived or answered one | Forbid `question_id` and any non-open status in AI output |
| C-3 | High | `Claim.materiality` is unrestricted. An AI output can set `non_material`. **(verified: `contracts/evidence.py:165` default only, no validator)** | `contracts/evidence.py` (`Claim`) | D-06: only an authorised reviewer may downgrade; REQUIREMENT_SCHEMA 9.1 | Silent materiality downgrade of a claim | Apply the same restriction used by `AtomicRequirement` (`contracts/requirement.py` materiality validator) |
| C-4 | High | Blocked status is presented as approved specification text. The specifications are labelled draft and not implementation-approved, and Example E says `needs_clarification`. The register says "approved specifications". | `requirement_analysis/agent.py` (`_status_for`, around line 120); `docs/AI_ENGINE_ISSUE_RESOLUTION.md` (AI-1-R5b, FC-3) | REQUIREMENT_SCHEMA header and section 7 Example E; GOVERNANCE header and section 6; GOVERNANCE line 24 says a contradiction MUST be logged and resolved before implementation or release (verified by the lead reviewer) | An unapproved choice is recorded as settled | Relabel as a draft choice in the register; keep a separate clarification indicator; WDS ruling on A-4 |
| C-5 | Medium | Two timing statements in one segment produce an error string only; no conflict record is created and both requirements stay `captured`. | `requirement_analysis/agent.py` (`_add_conflicts`, around lines 336-341) | REQUIREMENT_SCHEMA section 6 (conflicting sources must both be preserved); GOVERNANCE 6 | A real conflict goes unrecorded | Record the conflict and block both candidates |
| C-6 | Medium | Bidirectional conflict references are partly enforced. Claim-to-conflict is an existence check only. Duplicate keys are accepted in `claim_proposal_keys` and `conflict_refs`. Conflict evidence need not appear among the claims' evidence. **(verified: `specialist.py:216-228`)** | `contracts/specialist.py`; `contracts/evidence.py` (`conflict_refs`) | REQUIREMENT_SCHEMA 6.8 | Dangling or inconsistent conflict links are possible | Make the link sets equal in both directions; deduplicate; check evidence membership |
| C-7 | Medium | The proposal-key namespace check is not applied to specialist output. The analysis result applies it; the specialist result does not. The register marks AI-1-R9 and FC-4 resolved without this path. | `contracts/specialist.py` (validator); `contracts/common.py` (`proposal_key_is_namespaced`) | REQUIREMENT_SCHEMA 3 | A claim, solution or risk key could look like a Foundation ID | Apply the check to every AI-produced key |
| C-8 | Medium | Evidence status is model-supplied on claims, candidate solutions and risks. `policy.py` says status is never raised by the model; `rollup_status` is not called by any agent. | `contracts/evidence.py` (`Claim.evidence_status`); `contracts/specialist.py` (`CandidateSolution`, `RiskProposal`); `evidence/policy.py` (docstring and `rollup_status`) | REQUIREMENT_SCHEMA 6 items 3 and 7 | The stated control is not in force | Derive status from served evidence in the validator; correct the docstring |
| C-9 | Medium | Foundation-shaped identifiers reach analysis output. A question with only `related_requirement_ids` passes. The demo sets `requirement_id` on a copy via `model_copy`, which skips validation. | `contracts/analysis.py` (around lines 142-148); `contracts/clarification.py`; `demo/workflow.py` (`assign_mock_ids`) | REQUIREMENT_SCHEMA 3 | Mock IDs look like Foundation IDs inside AI objects | Validate mock IDs outside the analysis record; forbid question IDs in analysis regardless of references |
| C-10 | Medium | `ProjectContext.status` defaults to `active`. A payload without status is treated as active and analysed. | `contracts/project.py` (line 24) | REQUIREMENT_SCHEMA 4.1 lists status as required; section 6 item 14 forbids implied confirmation | An archived project could pass if status is omitted | Make status required, or refuse when absent |
| C-11 | Medium | Naming and protocol divergence. The approved schema already names `contradiction_refs`; the code uses `conflict_refs`. `EvidenceLookup.conflict_group_of` is a new required method. A-2's source cites "REQUIREMENT_SCHEMA 6.8", which is not a heading in that file. | `contracts/evidence.py`; `evidence/lookup.py` (protocol); `demo/gaps.py` (A-2 source) | REQUIREMENT_SCHEMA 4.4 (`contradiction_refs`, verified) | Integration friction; breaking change for other lookups | Rename to `contradiction_refs` or record the divergence; document the protocol change as breaking; correct the citation |
| C-12 | Medium | The G9 list omits prefixes in use: `SOLP` and `CLM`. | `shopify/agent.py` (around lines 253, 277, 308); `demo/gaps.py` (G9); `docs/AI_ENGINE_IMPLEMENTATION_PLAN.md` (G9) | WDS G9 sign-off requirement | An unapproved prefix is in use | Add to G9 and to every list |
| C-13 | Medium | D-OP is marked `closed` in the gap register, while its own title says WDS policy approval is still needed. A-4 is `open` in the gap register and `Blocked` in the issue register. | `demo/gaps.py` (D-OP entry; A-4 entry); `docs/AI_ENGINE_ISSUE_RESOLUTION.md` | WDS governance treatment | Gaps appear resolved when they are not | Set D-OP to `open` pending approval; reconcile A-4 wording; add a blocked value only if the register needs it |
| C-14 | Low | Specialist conflicts do not block the requirements they concern. Analysis conflicts do. | `shopify/agent.py` (conflict creation); `requirement_analysis/agent.py` | REQUIREMENT_SCHEMA section 6 item 8 | Inconsistent conflict treatment | Document or propagate |
| C-15 | Low | Execution envelope reports `succeeded` when the output status is `evidence_unavailable` or `partial`. | `specialists/execution.py` (around line 180) | Envelope semantics | Consumers may read success as completeness | Document, or map to a distinct status |
| C-16 | Low | A scope note is stored in `dependencies`. | `shopify/agent.py` (around lines 118-122) | Assumption and dependency separation (AI-4.1-4) | Minor category mixing | Move to a risk or note field |
| C-17 | Low | The phrase "No approved Foundation contract" overstates the status of draft specifications. | `specialists/execution.py` (around line 116) | Draft status of specifications | Overclaim in messages | Reword |

### 5.2 Runtime, isolation and security

| ID | Severity | Finding | Location | Specification / governance | Impact | Recommended correction |
|---|---|---|---|---|---|---|
| S-1 | High | The operator selection is forgeable in-process. Its label is free text, the fingerprint is public, and `verify_selection` checks only consistency. A hand-built selection with an arbitrary label runs the specialist. A `model_copy` with an empty label also passes. | `selection/operator.py` (`OperatorSelection` around lines 44-60; `verify_selection` lines 130-139); `demo/workflow.py` (around lines 210-213) | REQUIREMENT_SCHEMA 9.4 (explicit authenticated user action); GOVERNANCE 11; D-08 | The confirmation gate is advisory, not an authority check | Re-validate in `verify_selection`; require a non-empty label; record decision time and an actor identifier; the authoritative actor check belongs to Foundation |
| S-2 | Medium | Decisions are mutable after creation. The list is not frozen, and duplicate checks run only at construction. Appending a conflicting decision causes an uncaught `ValidationError` in `run_investigation`. Clearing decisions silently removes a rejection. | `selection/operator.py:53` (list); `common.py:23-25` (frozen model does not freeze lists); `demo/workflow.py` (around line 272) | Auditability | Silent loss of a rejection; uncaught error | Use tuples; re-check duplicates in `verify_selection`; raise `SelectionError` |
| S-3 | High | The analysis fingerprint covers only a few fields. Statements, conflicts, questions, assumptions, source references, category proposals, confidence, rationale and validation errors are not covered. Injected instruction flags or cleared conflicts do not make a decision stale. | `selection/operator.py:77-95` (`analysis_fingerprint`) | Register item AI-4.1-binding; REQUIREMENT_SCHEMA 9.4 | An operator decides on an incomplete view; the register overclaims | Hash the full analysis payload, excluding run and timestamp fields |
| S-4 | Low | `run_investigation` never compares the project with the analysis or selection project. A mismatch is refused only incidentally, by the task builder, and not at all when there are no candidates. | `demo/workflow.py` (`run_investigation`, around lines 195-213); `specialists/task_builder.py:66-67` | Project isolation (REQUIREMENT_SCHEMA 4.1) | Weak explicit boundary | Add an explicit check at the entry point |
| S-5 | High | The evidence allowlist and project scope are enforced by the agent, not by the wrapper. The recording lookup forwards the agent's `project_id` and `allowed_collections`. **(verified: `specialists/execution.py:49`)** | `specialists/execution.py` (`_RecordingLookup.search`, around lines 46-54) | Evidence isolation; GOVERNANCE 9 and 10 (tools selected by application allowlist) | An agent can read a collection outside the task's allowlist | Override both parameters with the task's values inside the recording lookup |
| S-6 | Medium | An agent's self-reported `FAILED_VALIDATION` produces execution `succeeded`. Only `UNSUPPORTED_REQUEST` is mapped. **(verified: `specialists/execution.py:172`)** | `specialists/execution.py` (around line 172) | Execution envelope semantics | A failed output reads as success in the envelope and the demo | Map `FAILED_VALIDATION` explicitly |
| S-7 | Medium | A verified official-vendor evidence record is accepted by the wrapper from any non-mock lookup. Only the mock refuses non-synthetic evidence. Shape checks only. | `evidence/lookup.py` (`MockEvidenceLookup` refusal only, around lines 54-57); `contracts/evidence.py` (around lines 95-104); `specialists/validation.py` (no kind check) | D-02 / C-06 (only approved sources); GOVERNANCE 10 | A future or custom lookup could supply unvetted vendor documentation as verified | Reject non-synthetic served evidence in the wrapper unless an authorised Foundation lookup is injected |
| S-8 | Medium | The snapshot binding covers requirements only. Changes to classification, access boundary or platforms between task build and execution are not detected. Status and revision are checked. | `specialists/task_builder.py` (`requirement_snapshot_hash`, around lines 29-36); `specialists/execution.py` (around lines 134-137) | REQUIREMENT_SCHEMA 4.1 and F-2 (classification and boundary); section 3 | A task can run after the project's classification or boundary changed | Include the project boundary fields in the binding and compare them at execution |
| S-9 | Low | Validation gaps. Claim subjects other than requirements are not checked. `service_pattern_ids` are not checked. Duplicate evidence across two conflicts is allowed. | `specialists/validation.py` (around lines 59-64); `contracts/specialist.py` (around lines 74-75) | REQUIREMENT_SCHEMA 6 item 11 (project boundary) | Cross-scope references possible | Check every subject type and every reference field |
| S-10 | Low | The audit trail is a label and a rationale per decision. There is no decision time, actor identifier or selection identifier. The report timestamp is a fixed constant. | `selection/operator.py` (around lines 44-54); `demo/workflow.py` (`DEMO_TIMESTAMP`, line 82) | GOVERNANCE 13 (audit records) | Decisions cannot be attributed or ordered | Add actor, time and selection identifiers when Foundation supplies them |
| S-11 | Low | The archived check trusts the caller-supplied project object. Nothing re-reads Foundation status. | `specialists/execution.py` (around line 115) | REQUIREMENT_SCHEMA 4.1 | A stale "active" object bypasses denial | Re-check status from the authoritative source at integration |
| S-12 | Info | The synthetic gate holds. A fixture is accepted only if it declares `synthetic: true`. Any file that declares it is accepted by design. | `adapters/foundation.py:52`; `tests/test_adapter_registry.py` | Synthetic-only restriction | None now; a file must still be labelled | Keep; audit fixture provenance before any use |
| S-13 | Info | Register overclaims: AI-4.1-binding (see S-3) and AI-2-G5 (the snapshot does not cover project boundary fields, see S-8). | `docs/AI_ENGINE_ISSUE_RESOLUTION.md` | Register accuracy | Correct the register |

### 5.3 Verified correct

- No specialist runs without a selection (`demo/workflow.py`: candidates empty when selection is absent).
- The requirement snapshot covers the full requirement record, so status, wording, source references and categories are bound.
- Project status is checked first in execution, and in the task builder and the analysis entry point.
- Requirement drift and project revision drift are refused at execution.
- Output checks refuse: wrong task ID, requirement outside the task, a one-field evidence difference, unserved evidence, a conflicting-versus-unverified conflict, and orphan conflict references.
- `MockEvidenceLookup` refuses non-synthetic records at construction, returns nothing for an empty allowlist, and applies collection and project filters.
- `conflict_group` does not appear in any serialized output.
- Models are frozen for attribute assignment, and claim subjects must match the claim's project.
- Imports are limited to the standard library, pydantic and yaml. No network, LLM, vendor, subprocess, database or credential modules. The only file write is the CLI `--out` option.
- The Foundation port exposes two read methods and no write methods.
- Enum members match REQUIREMENT_SCHEMA section 2 for the enums checked.
- AI proposal origins and statuses exclude `accepted_for_scope`, `verified` and `specialist_recommendation`. Priority, materiality and evidence status are pinned on requirements. Analysis pins `human_review_required` and `scope_committed`.

### 5.4 Uncertain points

- Section citations from the runtime reviewer were taken from the review brief; only the `contradiction_refs` location was checked against the specification text by the lead reviewer.
- Whether blocked is the correct long-term status is a WDS ruling (A-4).
- Findings C-1, C-2 and S-1 are established by code reading. Probes for S-1, S-2, S-3, S-5, S-6, S-7 and S-8 were run by the runtime reviewer outside the repository; the probe outputs are not reproduced here.

## 6. Contract compatibility assessment

- Additive changes are backward compatible for JSON and for callers that do not use the new fields.
- `EvidenceLookup.conflict_group_of` and the tightened `Claim` conflicting rule are breaking for other implementations and for callers that built conflicting claims without references. Neither has consumers outside the test suite and this package.
- The contracts diverge from the approved schema in two places: the conflict-reference name (C-11) and the specialist assumption and conflict fields (A-3). Both must be approved or renamed before integration.
- No Foundation-owned model or persistence was changed.

## 7. Foundation integration entry criteria

Integration must not begin until all of the following are met:

1. Authoritative approval records for A-1, A-2, A-3, A-4 (or a different ruling), EK-1 (or confirmation that it is not needed), and G9 in full.
2. A Foundation-owned identity and authorization service that supplies the operator or actor identity for every decision (replacing the label in S-1 and S-10).
3. A Foundation-owned ID assignment service and persistence path. Mock IDs must not be persisted (D-PERS).
4. Foundation-supplied project status, classification and access boundary at every entry point, re-read from the authoritative store (S-8, S-11).
5. Evidence supplied only through an authorised Foundation lookup with collection and project scope enforced by the wrapper (S-5, S-7).
6. Contract compatibility tests against the approved Foundation schema, using the amended names.
7. Retention and deletion treatment decided (D-13), because decisions and AI outputs will be stored.
8. The P0 and P1 backlog items below closed and re-reviewed.

## 8. Prioritized remediation backlog

Remediation is listed for WDS prioritisation. No item has been implemented.

**P0: before continued isolated development relies on the governance gates**
1. S-1: re-validate and require a label in `verify_selection`; add decision time and actor identifier fields.
2. S-2: freeze decisions as tuples; re-check duplicates; raise `SelectionError` on mutation.
3. S-3: hash the full analysis payload, excluding run and timestamp fields.
4. S-5: override search collections and project in the recording lookup with the task's values.
5. C-1: forbid AI-set `verified` on candidates, or require served evidence.
6. C-2: forbid `question_id` and non-open status in specialist output.
7. C-3: restrict `Claim.materiality` as `AtomicRequirement` does.
8. C-4: relabel the blocked choice in the register as a draft ruling; correct AI-1-R5b and FC-3.

**P1: before any integration design review**
9. S-6: map `FAILED_VALIDATION` explicitly.
10. S-7: reject non-synthetic served evidence in the wrapper.
11. S-8: bind project boundary fields in the snapshot and compare at execution.
12. C-5: record same-segment conflicts and block both candidates.
13. C-6: make bidirectional conflict links exact and deduplicated; check evidence membership.
14. C-7: apply the namespace check to specialist output.
15. C-9: keep mock IDs out of analysis records.
16. C-12 and C-13: correct G9, D-OP and A-4 entries in gaps and register.
17. S-4: explicit project check at the `run_investigation` entry point.

**P2: hygiene and robustness**
18. C-8: derive evidence status from served evidence; correct the policy docstring.
19. C-10: make `ProjectContext.status` required.
20. C-11: rename or record the divergence; document the breaking protocol change; correct the citation.
21. C-14, C-15, C-16, C-17: propagate or document conflict blocking, envelope status, scope note and wording.
22. S-9: check all subject types and reference fields.
23. S-10: add audit identifiers when Foundation supplies them.
24. S-11: document that archived status is caller-supplied until integration.

**Missing negative tests to add with P0 and P1 (from the runtime review):**
- Selection with an empty label, constructed or copied; duplicate or appended decisions.
- Analysis changed in statements, conflicts, source references or category proposals, with the selection still accepted.
- Agent-supplied collection list or project identifier in search.
- A non-mock lookup serving a verified official record.
- Agent-reported `FAILED_VALIDATION` producing execution success.
- Project classification, boundary or platforms changed between task and execution.
- Candidate-solution subjects with a foreign identifier; two conflicts citing the same evidence.
- `run_investigation` with a project differing from the analysis project.

## 9. Production LLM and RAG readiness assessment

**Verdict: NOT READY.** Nothing in the engine calls an LLM, and nothing should until the following are settled:

- **D-12:** provider, model pinning, token and latency budgets, failure behaviour and data-processing policy are undecided. The engine has only a provider protocol concept, not an implementation.
- **D-02 / C-06:** the vendor allowlist and default-deny policy are undecided. Retrieval would be unbounded.
- **RAG:** no retrieval index, access-controlled document store, chunking or ACL enforcement exists. The synthetic lookup is not a substitute.
- **Prompt injection:** coverage is limited to hand-written sentences in the analysis tests. GOVERNANCE 9 requires direct, indirect, encoded and multi-document tests, which do not exist.
- **Evaluation:** no benchmark, seeded defect set or numeric thresholds exist (D-14). REVIEW_POLICY and EVALUATION_PLAN are not yet implemented.
- **Provenance:** no model identifier, prompt version or settings are recorded in outputs, which GOVERNANCE 224 requires for every run.
- **Hosting:** D-16 is deferred, so network egress and secrets handling are unknown.

Deterministic components (analysis rules, validators, selection, execution) are not affected by these gaps and remain testable in isolation.

## 10. Items for WDS review before the next increment

1. Confirm the verdict: CONDITIONALLY READY for isolated development after the P0 backlog; NOT READY for Foundation integration and production.
2. Rule on A-4, and decide whether the register's "approved specifications" wording is withdrawn (C-4).
3. Decide whether the contract naming (C-11) should follow `contradiction_refs`.
4. Confirm the G9 list and the D-OP treatment (C-12, C-13).
5. Authorise or defer the P0 backlog. No remediation is authorised by this review.

## 11. AI-5.1 disposition of findings (added after remediation)

This section records what happened to the findings above. The original findings are unchanged. Details are in `docs/AI_ENGINE_AI51_REMEDIATION.md`, sections 2, 2A and 3A. Status values follow that document.

| ID | Original severity | Disposition | Evidence |
|---|---|---|---|
| S-1 | High | **Partly fixed, partly blocked.** Actor identifier and decision time are required; the label must be printable; decisions are immutable and verified; the instance used is the verified one. **Authenticated authorisation is blocked by Foundation identity** | `selection/operator.py`; R2-N-1 tests; remediation §3 |
| S-2 | Medium | **Fixed.** Decisions are a tuple; duplicates are refused at verification | remediation §2 |
| S-3 | High | **Fixed.** Fingerprint covers the whole serialised analysis | remediation §2 |
| S-4 | Low | **Open.** Explicit project check at `run_investigation` not added. Engine-fixable; deferred | remediation §3A |
| S-5 | High | **Fixed, with the in-process residual.** Scoped search, copies, authorised-set re-query. Agent code in the same process can still reach objects through closures | remediation §2, §2A, §3 (F2) |
| S-6 | Medium | **Fixed** in AI-5.1 | remediation §2 |
| S-7 | Medium | **Open.** Not addressed in AI-5.1 or R2. The mock lookup refuses non-synthetic records, but the wrapper does not check evidence kind for a custom lookup | Engine-fixable; deferred (not in R2 scope) |
| S-8 | Medium | **Open, blocked by Foundation.** Classification and boundary are not in the binding | remediation §3A |
| S-11 | Low | **Blocked by Foundation.** Archived status is still caller-supplied | remediation §3 |
| R2-P0-1 | P0 (second re-review) | **Reproduced and fixed.** Task-extension exploit fails on current code; fails on pre-fix copy | remediation §2A |
| R2-P0-2 | P0 (second re-review) | **Reproduced and fixed.** Requirement mutation cannot change the analysis or selection; fails on pre-fix copy | remediation §2A |
| R2-P1-3 | P1 (second re-review) | **Reproduced and fixed.** `conflict_group_of` answers only for records served to the run | remediation §2A |
| R2-N-1 | Note (second re-review) | **Reproduced and fixed.** Invisible characters refused in operator identity | remediation §2A |

**Verdict unchanged.** Continued isolated development remains conditional. Foundation integration and production remain not ready. No independent re-review of the R2 fixes has happened yet.
