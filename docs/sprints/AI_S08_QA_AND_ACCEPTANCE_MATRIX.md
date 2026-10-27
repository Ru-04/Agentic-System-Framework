# AI-S08 QA and Acceptance Matrix

Status: engineering checkpoint. Not formal acceptance. Independent QA of the full implementation is pending (see `AI_S08_QA_FINDINGS_REGISTER.md` once issued).

Test file: `ai_engine/tests/test_ai_s08_estimation.py`. Every calculation is checked against a hand-computed value or a stated input. Synthetic fixtures only.

## 1. Mandatory test matrix (brief section 6)

| # | Item | Tests |
|---|---|---|
| 1 | Single requirement | `test_a_single_task_reports_its_stated_hours_and_totals` |
| 2 | Multiple requirements | `test_totals_sum_across_requirements_and_by_requirement_subtotals_are_separate` |
| 3 | Multiple resource roles | `test_a_task_with_two_roles_yields_one_line_per_role_and_discipline_totals`; `test_a_task_may_name_each_discipline_once` |
| 4 | Low / Likely / High validation | `test_invalid_three_point_hours_are_refused`; `test_equal_and_zero_three_point_values_are_accepted`; `test_an_integer_hour_value_is_stored_as_a_float_and_text_is_refused` |
| 5 | Correct totals and subtotals | `test_fractional_totals_are_exact_sums_of_the_stated_hours`; `test_a_task_with_two_roles...`; `test_totals_sum_across...` |
| 6 | Duplicate work-item handling | `test_shared_implementation_counts_once_in_project_totals`; `test_shared_implementation_with_conflicting_hours_is_not_estimated`; `test_shared_implementation_with_conflicting_work_category_is_not_estimated` |
| 7 | Missing technical detail | `test_a_task_without_a_numeric_basis_gives_no_numbers`; `test_a_task_without_hours_is_reported_not_silently_dropped` |
| 8 | Missing evidence | `test_an_unverified_hypothesis_keeps_numbers_but_is_provisional`; `test_an_unsupported_requirement_is_unresolved_not_established` |
| 9 | Conflicting specialist findings | `test_a_conflicted_requirement_blocks_readiness_of_its_lines`; `test_a_blocking_finding_blocks_even_when_status_reads_backed` |
| 10 | Unverified hypotheses | `test_an_unverified_hypothesis_keeps_numbers_but_is_provisional` |
| 11 | Stale source references | `test_a_stale_reference_version_gives_no_numbers`; `test_an_unconfirmed_reference_version_gives_no_numbers`; `test_a_historical_reference_needs_a_confirmed_current_version` |
| 12 | Unsupported resource categories | `test_an_unsupported_discipline_is_refused_with_a_sanitised_message` |
| 13 | Negative, invalid and nonfinite hours | `test_invalid_three_point_hours_are_refused` (negative, NaN, infinity, unordered, bool); `test_malformed_hour_values_are_refused_and_not_echoed` (NaN, infinity, negative, text, null at raw input) |
| 14 | Estimate version consistency | `test_the_draft_carries_the_version_revisions_and_governance_fingerprint` |
| 15 | Requirement revision changes | `test_a_task_built_on_an_older_revision_is_stale_until_it_is_rebuilt` |
| 16 | Cross-project isolation | `test_a_requirement_snapshot_from_another_project_is_refused`; `test_governance_for_another_project_is_refused`; `test_a_cross_project_basis_gives_no_numbers_unless_authorised`; `test_the_estimator_package_imports_no_network_or_foundation_modules` |
| 17 | Historical reference authorisation | `test_a_cross_project_basis_gives_no_numbers_unless_authorised`; `test_a_historical_reference_needs_a_confirmed_current_version`; `test_a_synthetic_fixture_is_refused_unless_the_request_allows_it`; `test_a_synthetic_basis_must_say_it_is_synthetic` |
| 18 | Partial estimation outputs | `test_a_partial_estimate_reports_exact_excluded_lines_and_incomplete_totals`; `test_a_requirement_with_no_task_makes_the_project_needs_inputs` |
| 19 | Governance findings influencing readiness | `test_a_conflicted_requirement_blocks_readiness_of_its_lines`; `test_a_blocking_finding_blocks_even_when_status_reads_backed`; `test_escalations_are_listed_for_human_review` |
| 20 | No automatic estimate approval | `test_no_output_can_carry_an_approved_status`; `test_the_estimator_package_never_writes_an_approval` |
| 21 | Compatibility with AI-S01 to AI-S07 | `test_the_offline_pipeline_runs_orchestration_review_then_estimation`; the AI-S01–S07 suites run in the gate |
| 22 | Offline AI-S09 handoff suitability | `test_the_draft_serialises_to_json_and_is_deterministic` |

QA remediation tests: `test_an_empty_estimate_is_never_complete`; `test_a_blocker_without_requirement_ids_blocks_readiness`; `test_tasks_without_hours_appear_in_the_unassigned_bucket`; `test_error_messages_do_not_echo_mapping_keys_extra_fields_or_identifiers`; `test_a_missing_governance_assessment_names_a_count_not_identifiers`; `test_an_estimate_with_no_requirements_is_incomplete_and_needs_inputs`; `test_an_integer_mapping_key_does_not_leak_its_value`.

## 2. Security and integrity tests (brief section 5)

| Control | Tests |
|---|---|
| Cross-project data isolation | Requirement, governance and basis project tests in item 16 |
| Authorised source references | Item 17 tests |
| Malformed requirement IDs | `test_malformed_requirement_ids_are_refused` (five variants) |
| Stale requirement snapshots | Item 15 test |
| Invalid resource allocations | Items 3 and 4 tests; `test_a_task_may_name_each_discipline_once` |
| Invalid hour ranges | Item 4 tests |
| Unauthorised historical reference | Item 17 tests |
| Input object mutation | `test_the_request_is_not_mutated_by_estimation` |
| Exception and error sanitisation | `test_an_unsupported_discipline...`; `test_malformed_hour_values...` (sentinel value never echoed) |
| Missing governance assessments | `test_a_missing_governance_review_is_refused`; `test_a_requirement_without_a_governance_assessment_is_refused` |
| Unsupported estimation parameters | `test_a_duplicate_task_is_refused`; `test_a_task_for_an_unknown_requirement_is_refused`; `test_a_task_citing_an_unknown_specialist_result_is_refused`; `test_an_unknown_task_dependency_is_refused` |
| No autonomous human approval | Item 20 tests |
| No direct Foundation database access | `test_the_estimator_package_imports_no_network_or_foundation_modules` |
| No real provider or external network calls | The same import test; the package imports no network module |
| Deterministic output | `test_the_draft_serialises_to_json_and_is_deterministic` |

## 3. Gate results (at this checkpoint)

- Full suite: 1640 passed, 3 skipped. Scope note: the counts include 64 tests in three untracked Foundation files (`ai_engine/tests/test_ai_s02_s04_acceptance_distinctions.py`, `test_ai_s02_s04_boundaries.py`, `test_ai_s02_s04_integration.py`), which are not committed. The committed tree alone collects 1576 tests. The 3 skips are in the untracked file. The skips are the Foundation tests at lines 357, 362 and 367 of `test_ai_s02_s04_acceptance_distinctions.py`, not run offline.
- AI-S08 focused: 65 tests, all passing (58 at checkpoint, plus 7 QA regression tests).
- AI-S05, AI-S06 and AI-S07 focused: 254 passed. AI-S01 to AI-S04 focused: 239 passed.
- Ruff check and format check: clean. Strict mypy across source and tests: clean.
- AI-S01 to AI-S07 contract, orchestration, applications and governance paths: unchanged against HEAD.

## 4. Acceptance criteria (sprint specification section 9, brief section 4)

| Criterion | Status |
|---|---|
| Complete approved isolated estimation functionality | Met at checkpoint; subject to QA |
| Valid resource-wise Low/Likely/High outputs | Met (items 3, 4, 5) |
| Correct aggregation and requirement traceability | Met (items 2, 5, 6); shared-line subtotal behaviour documented |
| Accurate handling of evidence gaps and uncertainty | Met (items 8, 9, 10, 19) |
| Governance review compatibility | Met (item 21; governance bridge tests) |
| No autonomous commercial approvals | Met (item 20) |
| Green complete test and static-analysis gates | Met at checkpoint |
| Independent QA PASS | Pending |
| WDS formal acceptance | Pending |

## 5. Known limitations

See `AI_S08_IMPLEMENTATION_RECORD.md` section 6 and `AI_S08_ESTIMATION_CONTRACT.md` section 8.
