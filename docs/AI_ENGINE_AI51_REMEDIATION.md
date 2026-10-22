# AI-5.1 Security Remediation and Contract Preparation

- **Baseline:** `c159fac` (AI-4.1). Working-tree changes are **uncommitted and unpushed**.
- **Branch:** `feature/ai-engine` (no remote-tracking ref; not pushed).
- **Inputs:** `docs/AI_ENGINE_INDEPENDENT_REVIEW.md` (AI-5), `docs/AI_ENGINE_INDEPENDENT_AUDIT.md` (pre AI-5.1), and the independent AI-5.1 re-review of the P0 fixes.
- **Authoritative v2.0 scope:** **not found in the repository.** A search for "v2.0" returned no scope document. The seven-specialist list used here comes from the v0.3.10 draft (GOVERNANCE 5.3, AGENT_REGISTRY). Reconciliation against v2.0 is blocked until that document is supplied.
- **Scope limits:** no production LLM, RAG, automatic specialist execution, new Foundation persistence, or approval-dependent behaviour was started.

## 1. Verification

| Check | Result |
|---|---|
| `pytest` | 385 passed (326 at `c159fac`, plus 49 AI-5.1 P0 tests, plus 10 second-review tests) |
| `ruff check src tests`, `ruff format --check src tests` | clean |
| `mypy` (strict, `src/ai_engine`) | clean, 38 files |
| First independent re-review | Completed (read-only). Findings F1 to F10 below, each addressed or recorded as a limitation |
| Second independent re-review (R2) | Defects reproduced and fixed in section 2A. **Independent re-review of these fixes is pending; this document does not claim it.** |

## 2. Fixed P0 defects

| Audit ID | Defect | Fix | Location | Regression tests |
|---|---|---|---|---|
| N-4 | Outputs built with `model_construct` or mutated after construction were trusted | Wrapper re-validates agent output from its serialised form; selections re-validated in verification | `specialists/execution.py` (`run_specialist`, `model_validate(output.model_dump())`); `selection/operator.py` (`verify_selection`) | `test_ai51_p0_regressions.py` (model-constructed claim, candidate, question; mutated claims list; copied selections) |
| S-5 | Agent chose the evidence collection and project | Agent receives `_AgentEvidenceView`; scoped search refuses other projects and unallowlisted collections; wrapper re-queries the authorised set independently and accepts only records in it | `specialists/execution.py` (`_AgentEvidenceView`, `scoped_search`, `authorised`) | scope denial tests; `test_injected_fabricated_evidence_is_refused_by_the_authorised_set` |
| S-3 | Fingerprint covered a hand-picked subset of the analysis | Fingerprint hashes the whole serialised analysis | `selection/operator.py` (`analysis_fingerprint`) | `test_any_reviewed_content_change_makes_the_selection_stale` (six changes) |
| S-1 (partial), S-2, N-3 | Selections had no actor or time; decisions were mutable; enum comparison by identity | `actor_id` and timezone-aware `decided_at` required; `decisions` is a tuple; comparisons use equality; blank actor or label refused even with no decisions | `selection/operator.py` (`OperatorSelection`, `build_operator_selection`) | authority-field, immutability, string-decision and blank-actor tests |
| F1 (re-review) | Caller's selection object used after verification | `verify_selection` returns the checked instance; the workflow uses only that instance | `selection/operator.py`; `demo/workflow.py` (`run_investigation`) | `test_verified_selection_instance_is_the_only_one_used` |
| C-1 | Candidate solutions could claim verified status | AI output may not carry verified status on candidates, risks, claims, or evidence records | `contracts/specialist.py` (`_check_ai_output_rules`) | candidate, risk and evidence tests |
| C-2 | Specialist questions could carry Foundation IDs or non-open status | Refused in AI output | `contracts/specialist.py` (`_check_ai_output_rules`) | question tests, including a model-constructed question |
| C-3 | AI output could set claim materiality | Materiality must be unassessed in AI output | `contracts/specialist.py` (`_check_ai_output_rules`) | `test_ai_output_cannot_set_claim_materiality` |
| N-1, N-2, F6, F7 | Sentences matching no rule were dropped; short, letterless and over-length sentences were filtered or unrecorded | Every non-empty sentence is considered; unmatched and over-length sentences are recorded as `unclassified` statements with a source reference | `requirement_analysis/agent.py` (`split_sentences`, `_unclassified_statement`); `contracts/analysis.py` (`StatementKind.UNCLASSIFIED`) | `test_unmatched_source_sentence_is_recorded_not_dropped`, `test_short_and_letterless_sentences_are_recorded` |
| S-6, F5 | Self-reported failure, or no evidence source, reported as success | Self-reported `failed_validation` maps to failed; a run whose output is `evidence_unavailable` reports `specialist_not_completed` | `specialists/execution.py`; `demo/workflow.py` (`_status`) | `test_self_reported_failed_validation_is_never_reported_as_success`, `test_evidence_unavailable_is_never_a_completed_investigation` |
| F3 | Verified evidence records accepted in output | Refused by the output contract | `contracts/specialist.py` (`_check_ai_output_rules`) | `test_ai_output_cannot_carry_verified_evidence_records` |
| F4 | Foreign or non-requirement claim subjects accepted | Subjects must be task requirements or solutions proposed in the same result; other types refused | `specialists/validation.py` | `test_foreign_scope_item_subject_is_refused`, `test_foreign_candidate_subject_is_refused` |
| F8 | Blank actor replaced with a placeholder | Refused always | `selection/operator.py` | `test_blank_actor_is_refused_even_without_decisions` |
| F9 | Non-result return crashed the wrapper | Mapped to `failed_validation` | `specialists/execution.py` | `test_non_result_return_is_a_validation_failure_not_a_crash` |
| F10 | Context requirements dictionary mutable by agent | Agent receives a read-only mapping | `specialists/execution.py` (`MappingProxyType`) | covered by the view tests |

## 2A. Second re-review (R2) defects

**Pre-fix method.** The pre-fix behaviour was reproduced in a scratch copy outside the repository. That copy had the `specialists/execution.py` fix reversed to its prior text and the post-run selection re-check removed from `demo/workflow.py`. It kept the other AI-5.1 changes. Probes ran against that copy and against the working tree. Scratch scripts are not part of the repository.

| ID | Defect | Pre-fix reproduction | Fix | Location | Regression tests | Status |
|---|---|---|---|---|---|---|
| R2-P0-1 | The agent could extend the task it was given. An unconfirmed requirement could be cited and the run reported `succeeded` | Caller's task gained `REQ-FOREIGN-0001`. `run_demo(confirm=["CAND-005"])` with an extending agent reported `execution=succeeded` and `completed_with_unresolved_items` | The agent receives a validated copy of the task. Validation and routing use the caller's task | `specialists/execution.py` (`run_specialist`) | `test_agent_cannot_extend_the_task_it_was_given`; `test_demo_run_does_not_report_unconfirmed_requirements_as_investigated`. Both fail on the pre-fix copy | **Reproduced and fixed** |
| R2-P0-2 | An agent edit to `specialist_category_ids` changed the analysis under a recorded decision. The run still reported success | Exact mutation through `run_demo`: `execution=succeeded`; the mutation appears in the reported analysis; `selection.analysis_fingerprint` no longer matches the report | Requirements and project are passed as copies. `run_investigation` re-runs `verify_selection` after the agent returns | `specialists/execution.py`; `demo/workflow.py` (`run_investigation`) | `test_agent_cannot_change_the_requirements_it_was_given`; `test_demo_selection_still_matches_the_analysis_after_an_agent_run`. Both fail on the pre-fix copy | **Reproduced and fixed** |
| R2-P1-3 | `conflict_group_of` disclosed a contradiction group for another project's record (existence and metadata oracle) | Foreign record's group `foreign-secret-group` returned to the agent. Unknown identifiers returned `None` | Lookup answers only for records served to this run. Foreign, unknown and allowed-but-unserved records all return `None` | `specialists/execution.py` (`served_group_of`) | `test_conflict_group_is_not_disclosed_for_unserved_or_foreign_evidence`. Fails on the pre-fix copy | **Reproduced and fixed** |
| R2-N-1 | Zero-width and other invisible characters accepted as operator label or actor identifier. The CLI exited 0 with `--operator` set to U+200B | Observed in the working tree before this fix | Printability check on label and actor; surrounding whitespace is still trimmed | `selection/operator.py` (`OperatorSelection._check_unique`) | `test_invisible_or_control_characters_are_refused_as_operator_identity`; `test_printable_operator_identity_is_still_accepted` | **Reproduced and fixed** |
| R2-V-1 | Nested mutable fields of the project, requirements, task and returned evidence reachable from the agent | Generic probe that mutates every reachable list, dict and set: on the pre-fix copy the caller's task, project and requirements were changed and the wrapper then rejected the run. Store records were not changed on either version | Copies for task, project and requirements; returned evidence records are deep copies; the wrapper's served records are the lookup's own | `specialists/execution.py` | Probe only (see section 12A). No pre-fix change to the store was observed | **Fixed for the wrapper boundary. Store-level pre-fix reproduction unavailable** |

**Not proven by this work.** These fixes protect the wrapper boundary against code that uses the public interfaces. They do not stop in-process Python code from reaching objects through closures, `gc` or `object.__setattr__`. That limit is an architectural decision, recorded in section 3.

## 2B. Independent review of commit 39199d2 (AI-S01 baseline)

An independent reviewer exported `39199d2` to a scratch directory and reran the suite (385 passed; ruff, format and strict mypy clean) and the adversarial files (59 passed). The reviewer then probed the public interfaces. Findings and dispositions:

| ID | Finding | Disposition |
|---|---|---|
| R3-P0-1 | Allowlist check-then-use: a caller iterable that yields different collections on each pass passed the check and then searched a foreign collection, returning its record to the agent | **Reproduced and fixed.** The allowlist is snapshotted once and the same list is checked and searched (`specialists/execution.py`). Regression test `test_collection_allowlist_is_read_once_so_a_foreign_collection_cannot_be_searched`. Pre-fix reproduction: the probe returned the foreign record; post-fix it returns only the eight allowed records |
| R3-P1-2 | A decision survived a project revision change | **Fixed.** `run_investigation` raises `StaleSelectionError` when the analysis revision differs from the project revision. Test `test_decision_against_an_earlier_project_revision_is_stale` |
| R3-P1-4 | An empty rationale raised a raw `ValidationError` and a CLI traceback | **Fixed.** Refused as `SelectionError`. Test `test_empty_rationale_is_a_selection_error_not_a_traceback` |
| R3-P1-1 | With a non-empty allowlist that matches no collection, the Shopify agent returns no evidence and the run reports `completed_with_unresolved_items`, not `specialist_not_completed` | **Open.** The agent reports `EVIDENCE_UNAVAILABLE` only for an empty allowlist. Changing this is an agent-policy decision (what counts as an evidence source). Deferred to WDS |
| R3-P1-3 | `decided_at` in the demo is a constant (`DEMO_TIMESTAMP`), so the decision time is not the real decision time | **Open, by design for the demo.** A real decision time needs the Foundation clock and actor authority (S-1 residual) |

Architectural (not counted, documented): closure access to the original context (`view._search.__closure__`), as in section 3.

## 3. Remaining issues (not fixed, with reasons)

| ID | Issue | Why not fixed | Required to close |
|---|---|---|---|
| S-1 (residual) | Operator identity is attributed, not authenticated | Authorisation of an actor is a Foundation identity and governance function | Foundation operator identity port; GOVERNANCE 11 |
| S-11 | Archived status is caller-supplied | Foundation is the source of project status; the engine has no store to re-read | Foundation project read port, re-read at execution |
| F2 (residual) | An in-process agent can still introspect closures and reach the lookup object | Python provides no sandbox for code in the same process. The authorised-set re-query in the wrapper makes fabricated evidence unrecoverable, but the agent is still trusted code | Process isolation for untrusted or third-party specialists; an architecture decision |
| F10 (residual) | Object-level tampering through `object.__setattr__` is invisible to the fingerprint | The fingerprint covers serialised fields only. No code reads the tampered attributes | Same as F2; process isolation |
| C-4 | Blocked versus needs-clarification | Specifications are drafts; a WDS ruling is required | A-4 ruling |
| EVIDENCE_UNAVAILABLE envelope | The envelope still reports `succeeded`; the demo treats it as not completed | Changing the envelope enum is a contract change | Decide whether to add a status (C-15) |
| S-4 | Project comparison at the `run_investigation` entry point | Low; partially covered by the task builder | Add an explicit check in a later increment |
| S-8 | Snapshot excludes classification, boundary and platforms | Foundation-owned fields; no authoritative source yet | Foundation project read port |

### 3A. Classification after R2

| Class | Items | Note |
|---|---|---|
| Open P0 in engine code | **None confirmed** after R2 fixes | Conditional on the architectural limit below being accepted for the current in-repo specialist |
| Open P1 in engine code | **None confirmed** | S-8, S-11 and S-1 residual are P1 in intent but cannot be closed in the engine (see blocked) |
| Open, engine-fixable, low | S-4 (project comparison at `run_investigation`) | Not in this work; a single explicit check, deferred to avoid scope creep |
| Blocked by Foundation | S-1 residual (operator authentication); S-8 (classification and boundary in the binding); S-11 (archived status re-read) | Need the trusted actor and project read ports in section 9 |
| Blocked by governance | C-15 (envelope status for evidence-unavailable runs); C-4 / A-4 (blocked versus needs-clarification) | Need WDS rulings in section 11 |
| Architectural limitation | F2 and F10 residuals: in-process agents can reach objects through closures, `gc` or `object.__setattr__`; wrapper copies stop cooperative and public-interface mutation only | Not fixable inside Python. Required before any untrusted or third-party specialist: process isolation (section 11, item 5) |

**Not claimed.** Authenticated operator authorisation does not exist. The selection record names an actor and a time; it does not prove who the actor is or that they are allowed to decide. Foundation must provide that trusted actor and session authority. In-process Python agents are not security-isolated.

## 4. Contract changes (AI-5.1)

| Change | Kind | Consumers affected | Action |
|---|---|---|---|
| `OperatorSelection.actor_id` and `decided_at` (required) | **Breaking** for constructors | operator tests, demo workflow | Foundation to supply actor identity |
| `OperatorSelection.decisions` is a tuple | **Breaking** for code that mutated the list | none in repo | Documented |
| `verify_selection` returns `OperatorSelection` | **Breaking** signature change (previously `None`) | demo workflow | Callers must use the return value |
| `_AgentEvidenceView` replaces the evidence object given to agents | **Breaking** for agents that read internal attributes | none in repo | Documented; agents must use `search` and `conflict_group_of` |
| `StatementKind.UNCLASSIFIED` | Additive enum value | analysis consumers | Compatible |
| AI output authority rules (no verified status, materiality, question IDs, non-open questions, verified evidence records) | **Tightening**; governance position | any caller constructing such output | Requires WDS confirmation; see section 6 |
| `requires actor_id` on the demo CLI path | None; the demo passes the operator label as actor | demo | Demonstration only |

## 5. Contract alignment proposals for the seven specialists

Status of each row is taken from the v0.3.10 draft registry and SERVICE_CATALOG. Every row is a **proposal** for WDS review. None is approved.

| # | Registry capability | Specialist category | Platform identifier (proposed) | Registry status | Notes and alignment proposal | Open decisions |
|---|---|---|---|---|---|---|
| 1 | `CAP-ECOMMERCE` | `shopify_specialist` | `shopify` | proposed | Implemented as a synthetic prototype (AI-3). Align the platform version field: versions must be supplied before any platform claim can be verified | D-02/C-06, D-12, S5 (version) |
| 2 | `CAP-3D-CART-SHIFT-SHOPIFY` (legacy identifier) | `three_d_cart_shift_shopify_specialist` | `3dcart_shift4shop` (SERVICE_CATALOG) | proposed_canonical_name_and_alias_pending | D-01: an independent platform, not a 3D tool or a migration. Keep the legacy identifier as an alias only. Shift4Shop naming and category name require D-15 alias mapping. Registry says version identification is required before platform claims | D-15 canonical names; D-01 naming cleanup |
| 3 | `CAP-WORDPRESS-WOOCOMMERCE` | `wordpress_woocommerce_specialist` | `wordpress_woocommerce` | proposed | One combined category (GOVERNANCE 5.3); must not route to two specialists. Internal CMS and commerce concerns may be separated as facets | Facet model |
| 4 | `CAP-BIGCOMMERCE` | `bigcommerce_specialist` | `bigcommerce` | proposed | Same contract as the Shopify specialist; no BigCommerce-specific fields are defined yet | Evidence allowlist |
| 5 | `CAP-MAGENTO-ADOBE-COMMERCE` | `magento_adobe_commerce_specialist` | `magento_adobe_commerce` | proposed | Same contract; module-level claims need version context | Evidence allowlist |
| 6 | `CAP-STANDALONE-APPLICATIONS` | `standalone_applications_specialist` | none (platform-agnostic) | proposed | Must be analysable without any commerce specialist (GOVERNANCE 5.3). Platform context is "none", not "unknown" | Platform-agnostic task contract |
| 7 | `CAP-MIDDLEWARE-APPLICATIONS` | `middleware_applications_specialist` | none (platform-agnostic) | proposed | Technology selection is evidence-driven; Node.js is an option, not mandatory (GOVERNANCE 5.3) | Technology evidence source |

Shared alignment points for all seven:
- Every specialist uses the AI-2 `SpecialistTask` and `SpecialistInvestigationResult` contracts unchanged.
- Platform context for standalone and middleware is a distinct value, not an unknown platform. This needs a contract amendment (proposal A-5) because the current `PlatformContext` requires a platform identifier.
- Claim types and approach types may need per-specialist subsets. Proposed: no change until a specialist is in build.
- Evidence collections are per specialist and per WDS allowlist (D-02/C-06).

Also noted: `CAP-INTEGRATION-SOFTWARE` (legacy compatibility alias) and `CAP-AI-AUTOMATION` exist in the registry. They are outside the seven and are not proposed for implementation.

## 6. Decisions taken in AI-5.1 that need confirmation

1. **AI output may not assert verified evidence status**, on claims, candidates, risks, or evidence records. This follows the audit recommendation and the plan's statement that the retrieval layer sets evidence status. It is a governance position, not a spec quote; WDS must confirm it.
2. **Operator attribution is required, not authorisation.** The record names an actor and time. Who may act is not defined by the engine.
3. **An unclassified sentence is recorded as a statement with a reference to the source segment**, not with its full text. The statement says the full text is in the referenced segment.
4. **A run with no evidence source is reported as `specialist_not_completed`**, although its envelope is `succeeded` (C-15).

## 7. Shared dependencies

| Dependency | Where specified | Current state | Needed for |
|---|---|---|---|
| Specialist tools | AGENT_REGISTRY `services_and_tools`: `TOOL-DB-APPLICATION`, `TOOL-SCHEMA-VALIDATOR`, `TOOL-FILE-PARSER`, `TOOL-APPROVED-RETRIEVAL-READ`, `TOOL-APPROVED-WEB-READ`, `TOOL-INTERNAL-KNOWLEDGE-READ`, `SVC-EVIDENCE-RETRIEVAL` | Proposed; no implementation beyond the evidence lookup port and schema validator | All seven specialists |
| LLM | `MODEL-DEFAULT-STRUCTURED`, `MODEL-DEFAULT-REASONING`, `MODEL-REVIEW` (environment-configured) | D-12 undecided: provider, model, budget, data policy | Any live specialist reasoning |
| RAG | D-02: internal RAG first, then approved live sources | Not built; allowlist OPEN and default-deny | Evidence grounding for all seven |
| LangGraph | ARCHITECTURE (lines 30, 46, 66, 116): LangGraph for orchestration | **Specification inconsistency:** the registry defines `AG-ORCHESTRATOR` as a deterministic service, not LangGraph. Not a dependency of the current code | Multi-specialist orchestration |
| Multi-specialist routing | AGENT_REGISTRY `ROUTE-CROSS-PLATFORM-001` (union of relevant categories; disabled) | C-05 undecided | Multi-specialist collaboration |
| Python libraries | `pydantic`, `pyyaml` (pinned) | In use | All |

## 8. Specialist work packages (not started)

Each package is independent, synthetic-only, and gated. None may start live functionality without WDS approval.

| Package | Scope | Inputs | Deliverables | Gating decisions | Dependencies |
|---|---|---|---|---|---|
| WP-S1 Shift4Shop | Platform investigation on synthetic evidence | Synthetic fixtures; alias mapping | Specialist, fixtures, scenario tests | D-15, D-01 naming | Shared contract tests |
| WP-S2 WordPress/WooCommerce | Combined category; facet model | Synthetic fixtures | Specialist, facet tests | Facet model; evidence allowlist | Shared tools |
| WP-S3 BigCommerce | Platform investigation on synthetic evidence | Synthetic fixtures | Specialist, scenario tests | Evidence allowlist | Shared tools |
| WP-S4 Magento/Adobe Commerce | Platform investigation on synthetic evidence | Synthetic fixtures | Specialist, scenario tests | Evidence allowlist | Shared tools |
| WP-S5 Standalone applications | Platform-agnostic analysis | Synthetic fixtures | Specialist without commerce dependency | Platform-agnostic contract (A-5) | Contract amendment A-5 |
| WP-S6 Middleware applications | Evidence-driven technology options | Synthetic fixtures | Specialist, option tests | Technology evidence source | Contract amendment A-5 |
| WP-X Multi-specialist collaboration | Combine categories for one requirement | Outputs of WP-S1 to S6 | Collaboration contract and tests | C-05; handoff rules | All of WP-S1 to S6 |
| WP-E Estimation | Hour estimates by discipline | None authorised | Not started | D-04: reference dataset not provided | Authorised reference data |
| WP-D Draft SOW | DOCX and PDF draft | None authorised | Not started | D-10: template not approved | Approved template |

WP-E and WP-D are listed because the brief requires them. They cannot start: D-04 and D-10 are open and no reference data or template exists in the repository.

## 9. Foundation integration: versioned interface proposal

**Status: proposal only. No Foundation integration owner has been contacted. This increment cannot coordinate with them; the handoff has to be made by WDS.**

| Port (proposed) | Version | Direction | Purpose | Notes |
|---|---|---|---|---|
| `ProjectReadPort` | v1 | Foundation to AI | Project status, classification, boundary, platforms, revision | Re-read at execution; status is not caller-supplied |
| `SourceSegmentReadPort` | v1 | Foundation to AI | Authorised source segments | Already modelled by `FoundationReadPort` |
| `OperatorIdentityPort` | v1 | Foundation to AI | Authoritative actor for a decision | Needed to close S-1 |
| `EvidenceLookupPort` | v1 | Foundation to AI | Authorised, scoped evidence | Scope enforced by the wrapper; empty allowlist is deny-all |
| `IdAllocationPort` | v1 | Foundation to AI | Foundation requirement and question IDs | Replaces mock IDs |
| `CandidateWritePort` | future | AI to Foundation | Persisted candidate records | Not requested; blocked by D-PERS and G9 |

Version rules: each port carries a major version; the AI engine declares the contract version it was built against (`0.1.0` today). Breaking changes require a new major version and a compatibility test suite.

## 10. AI-5.1 acceptance criteria

| # | Criterion | Status |
|---|---|---|
| 1 | Reproductions from the audit are refused | Met (regression tests) |
| 2 | Boundary re-validation for outputs and selections | Met |
| 3 | Fingerprint covers every reviewed field | Met (six probed changes) |
| 4 | Out-of-scope evidence cannot be read or cited | Met for the public interface; residual for in-process code (F2) |
| 5 | Unrecorded sentences are not silently dropped | Met |
| 6 | AI output cannot assert verified, materiality, or authoritative question state | Met |
| 7 | Operator selections are attributed, immutable, and duplicate-free | Met for attribution; authorisation residual (S-1) |
| 8 | Register and gap entries match the state of the work | Met for C-4, D-OP and G9; A-4 remains open |
| 9 | Suite, ruff, format check and strict mypy pass | Met (385 tests) |
| 10 | No Foundation model or persistence changed | Met |
| 11 | R2-P0-1, R2-P0-2 and R2-P1-3 reproduced on the pre-fix copy, with failing tests, then fixed | Met (section 2A) |
| 12 | Independent re-review of the R2 fixes | **Not met.** Pending; handoff in section 12A |
| 13 | AI-S01 closure | **Not met.** Requires criterion 12, the blocked items in section 3A, and WDS acceptance |

## 11. Items for WDS decision

1. Supply the authoritative v2.0 scope document, or confirm which seven specifications must be reconciled and approved.
2. Confirm governance position 1 in section 6 (no verified AI output).
3. Rule on A-4 and on proposal A-5 (platform-agnostic context).
4. Decide the envelope status for evidence-unavailable runs (C-15).
5. Decide whether specialists will run in a separate process (F2 residual), a prerequisite for third-party or untrusted specialists.
6. Authorise, or defer, the seven specialist work packages. Nothing in this increment starts them.
7. Hand the Foundation interface proposal (section 9) to the integration owner.

## 12A. Independent re-review handoff (R2 fixes)

**Subject:** the uncommitted working tree on `feature/ai-engine`, based on `c159fac`. Nothing is committed, pushed or merged. Do not treat this as a commit.

**Exact state.** Hashes of every changed or new file under `ai_engine/` are listed in `C:\Users\baps\AppData\Local\Temp\claude\D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-ai-engine-af7c07\5ca0e0fd-be1f-4f3a-baee-dd7ef59937cf\scratchpad\handoff_hashes.txt`. The SHA-256 of that list is `46bb0bf1af241cfffccf0b5a5ea445370459e86c24f5580afe0d475930407f8b`. Documentation under `docs/` is excluded from the hash.

**Files changed for R2:**
- `ai_engine/src/ai_engine/specialists/execution.py`: copies for the agent; served-only conflict lookup
- `ai_engine/src/ai_engine/demo/workflow.py`: post-run `verify_selection` in `run_investigation`
- `ai_engine/src/ai_engine/selection/operator.py`: printability check on label and actor
- `ai_engine/tests/test_ai51_review2_regressions.py`: new file, 10 tests

**Checks at hand-off:** `uv run pytest -q` 385 passed. `ruff check src tests` clean. `ruff format --check src tests` clean. `uv run mypy` clean, 38 files.

**Reproduction scripts** (scratch, outside the repository):
- `C:\Users\baps\AppData\Local\Temp\claude\D--WDS-Agentic-System-FrameWork--claude-worktrees-webdesk-ai-engine-af7c07\5ca0e0fd-be1f-4f3a-baee-dd7ef59937cf\scratchpad\revert_p0_1.py` builds the pre-fix copy in `scratchpad\prefix`
- `...\scratchpad\probe_p0_2.py` runs the exact R2-P0-2 mutation through `run_demo`
- `...\scratchpad\probe_isolation.py <tests_dir>` mutates every reachable mutable field and compares the originals

**Reviewer should attack:**
1. Any route by which an agent reaches the caller's task, project, requirement or evidence objects without a copy
2. Any route to a conflict group or other metadata for a record that was not served in the run
3. Whether the post-run `verify_selection` can be bypassed or made to pass against a changed analysis
4. Whether the printability check misses a class of character that can hide attribution

**Known limits the reviewer should not re-report as new:** in-process introspection through closures, `gc` or `object.__setattr__` (F2 and F10 residuals); operator authentication (blocked by Foundation); S-8 and S-11 (blocked by Foundation).

**Line endings:** several files, including the three edited in `src`, are CRLF in the working copy and LF in the index. `git diff` therefore shows whole-file changes. `git diff --ignore-cr-at-eol` shows the substantive change. This predates R2 and was not altered.

**Readiness:** the R2 fixes are ready for independent review. AI-S01 is not ready to close: criterion 12 in section 10 is open, the items in section 3A are unresolved, and WDS has not accepted it.

## 12. Not started and not authorised

Production LLM and RAG; automatic specialist execution; new Foundation persistence; approval-dependent behaviour; live vendor retrieval; estimation and draft SOW generation (blocked by D-04 and D-10). Nothing was committed, pushed or merged.
