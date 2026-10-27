# AI-S08 Implementation Record: Resource-Wise Low / Likely / High Estimation

Status: engineering checkpoint, isolated scope, offline, draft outputs only. Not formal acceptance. Baseline: AI-S07 `cbec19a1a97051f36a929c97ebea3530f813e229` (formally accepted for isolated engineering by WDS).

Companion documents: `AI_S08_ESTIMATION_CONTRACT.md` (contract, taxonomy, calculation rules, open decisions), `AI_S08_QA_AND_ACCEPTANCE_MATRIX.md`, `AI_S09_HANDOFF_FROM_AI_S08.md`.

## 1. What was implemented

Package `ai_engine/src/ai_engine/estimation/`:
- `contracts.py`: the input and output models, the seven disciplines, the work categories, basis kinds, the draft status enumeration (no `approved`), readiness, the three-point and ordering rules, and the sanitised error type.
- `engine.py`: `estimate(request)` and `build_request(raw)`. Validation, requirement and governance integrity, per-task issue detection, implementation-key merging, conflict detection, readiness, totals by discipline, requirement, work category and project, outstanding issues, and calculation provenance.
- `bridge.py`: read-only summaries from an AI-S07 `ReviewReport` (`governance_summary`) and an AI-S06 `OrchestrationResult` (`specialist_result_refs`).

## 2. Capabilities against the brief

| Brief item | Where | Notes |
|---|---|---|
| Requirement-to-task decomposition with traceability | `TaskInput`, `EstimateLine.task_ids`, `requirement_ids`, `supporting_refs` | Decomposition is supplied by the caller; the engine preserves and checks it |
| Resource-wise estimates per task-resource combination | `ResourceAllocation`, `EstimateLine` | Low, likely, high, assumptions, dependencies, uncertainty, supporting references, status |
| Three-point integrity | `ThreePoint`, `_task_issues`, `_conflicts` | Finite, non-negative, ordered; no coercion of text; missing and conflicting values surfaced |
| Evidence-aware estimation | `_requirement_readiness`, `GovernanceSummary` | Evidence-backed, provisional, unresolved and blocked states; governance does not approve |
| Estimation references with authorisation | `EstimateBasis`, `authorised_reference_projects`, `current_reference_versions` | Cross-project and stale references give no numbers |
| Dependencies and uncertainty | `TaskInput.dependencies`, `external_dependencies`, `client_inputs`, `access_requirements`, `uncertainty` | Carried to lines; unknown task dependencies refused |
| Aggregation | `_totals`, `by_discipline`, `by_requirement`, `by_work_category`, `project` | Per line once; complete flag; excluded line IDs listed |
| Duplicate-counting prevention | `_group_key`, `EstimateLine.task_ids` | Shared implementation counted once in project totals |
| Versioned draft | `estimate_version`, `requirement_revisions`, `governance_fingerprint`, `specialist_result_refs`, `draft_status` | No approval or actor fields |
| AI-S07 integration | `bridge.governance_summary`; integration test | Governance fingerprint and findings carried through; conflicts and blockers affect readiness |
| Offline AI-S06 integration | `bridge.specialist_result_refs`; integration test | Pipeline: orchestration, review, estimation |

## 3. Calculation rules (summary)

Hours are the stated low, likely and high of each estimated line. Totals are sums of those hours in line-ID order, using built-in float addition. No weighting, expected value, contingency, confidence score, duration or rate is applied, and none is approved. The full rules are in the contract, section 7.

Built-in float addition was chosen because the AI-S02 import guard permits only a short list of standard modules, and `math`, `decimal` and `statistics` are not on it. The guard was not changed. Sums are deterministic for a given input order and are compared with tolerances in tests.

## 4. Test results

Final candidate, after the completion pass:
- `pytest -q`: 1640 passed, 3 skipped. The three skips are the Foundation integration tests at `test_ai_s02_s04_acceptance_distinctions.py` lines 357, 362 and 367, visibly skipped and not run offline.
- AI-S08 focused: 65 tests in `test_ai_s08_estimation.py`, all passing.
- AI-S05, AI-S06 and AI-S07 focused: 254 passed. AI-S01 to AI-S04 focused subset: 239 passed.
- `ruff check .`: clean. `ruff format --check .`: clean. `mypy --strict src tests`: no issues in 141 files.

## 5. Defects found while building, and independent QA remediation

Independent QA of commit `0a7bfee` returned FAIL (0 blocker, 3 major, 2 minor). Each finding was reproduced and fixed with a regression test. See `AI_S08_QA_FINDINGS_REGISTER.md`.

- MAJOR-1: an empty estimate reported `complete=True`. Fixed: an empty estimate and any requirement with no task are incomplete. Tests: `test_an_empty_estimate_is_never_complete`, `test_a_requirement_with_no_task_makes_the_project_needs_inputs`.
- MAJOR-2: a blocking finding that named no requirement did not affect readiness. Fixed: `has_blocker` makes project readiness `blocked`. Test: `test_a_blocker_without_requirement_ids_blocks_readiness`.
- MAJOR-3: error messages echoed mapping keys and extra field names. Fixed: sanitisation shows positions, known field names and `<key>`. Test: `test_error_messages_do_not_echo_mapping_keys_extra_fields_or_identifiers`.
- MINOR-1: error messages named requirement and task identifiers. Fixed: messages give counts or no identifiers. Test: `test_a_missing_governance_assessment_names_a_count_not_identifiers`.
- Second verification round (FAIL, two residual defects, both fixed): an estimate with no requirements at all still reported complete, now incomplete and needs inputs (test `test_an_estimate_with_no_requirements_is_incomplete_and_needs_inputs`); integer mapping keys still leaked their value, now shown as `<index>` or `<key>` (test `test_an_integer_mapping_key_does_not_leak_its_value`).
- MINOR-2: lines with no hours were absent from by-discipline totals. Fixed: an `unassigned` bucket. Test: `test_tasks_without_hours_appear_in_the_unassigned_bucket`.

Defects found while building, fixed before QA:

- Shared-task conflict check compared hours across all disciplines of a task, so a task with two roles conflicted with itself. Fixed: the check is discipline-scoped. Test: `test_a_task_with_two_roles_yields_one_line_per_role_and_discipline_totals`.
- Integer hours: strict floats accept integers, so the test asserts the stored float. Text is still refused. Test: `test_an_integer_hour_value_is_stored_as_a_float_and_text_is_refused`.
- A requirement with no task left project readiness unaffected. Fixed: it is an outstanding issue and sets project readiness to `needs_inputs`. Test: `test_a_requirement_with_no_task_makes_the_project_needs_inputs`.
- `math.fsum` was rejected by the AI-S02 import guard. Fixed: built-in summation, no change to the guard.

## 6. Limitations accepted for this checkpoint

- No numeric estimate is authoritative. Numbers come from caller-supplied bases. The WDS reference dataset and authorised historical data are not provided (C-08, D-04).
- A human estimator basis is accepted on the caller's record; the engine cannot verify the estimator.
- The engine does not map work categories to disciplines; the caller names each discipline.
- By-requirement subtotals include shared lines and do not add to the project total.
- Built-in float summation; no compensated arithmetic.
- No persistence, approval workflow, roles or audit. Those are Foundation services.
- Work categories and disciplines follow the brief and REQUIREMENT_SCHEMA 9.2; the brief's architecture category has no discipline of its own, so the caller must assign one.

## 7. Foundation and governance dependencies

Authoritative requirement revisions and approval status; authorised historical and reference data with verified version and provenance; authority over human estimators; draft persistence and approval; project and collection authorisation for cross-project references; and the blocking effect of governance findings on approval (`ReviewReport.has_blocker` and `EstimateDraft.readiness` are the signals).

## 8. Checkpoint

Stage 1 engineering checkpoint commit: see the commit SHA reported with this record. It is not formal acceptance. Next: independent QA of the full AI-S08 implementation, then consolidated remediation, then WDS acceptance.
