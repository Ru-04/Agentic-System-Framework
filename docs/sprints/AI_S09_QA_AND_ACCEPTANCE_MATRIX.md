# AI-S09 QA and Acceptance Matrix

Status: engineering checkpoint. Not formal acceptance. Independent QA of the complete implementation is pending.

Test file: `ai_engine/tests/test_ai_s09_sow.py` (56 tests). Synthetic inputs; estimates produced by the real AI-S08 engine.

## 1. Mandatory test coverage (brief section 8)

| # | Area | Tests |
|---|---|---|
| 1 | Single requirement SOW | `test_a_single_requirement_sow_is_complete_and_draft` |
| 2 | Multi-requirement SOW | `test_every_in_scope_requirement_has_traceability_when_covered` |
| 3 | Multiple specialist domains | `test_findings_from_two_specialist_domains_are_listed_in_the_manifest`; `test_a_finding_citing_an_unknown_specialist_is_refused` |
| 4 | Missing specialist findings | `test_an_in_scope_requirement_without_a_finding_is_reported_as_an_evidence_gap` |
| 5 | Evidence gaps | `test_an_in_scope_requirement_without_a_finding_is_reported_as_an_evidence_gap`; `test_an_unverified_hypothesis_is_shown_as_provisional_not_as_established` |
| 6 | Governance blockers | `test_a_blocking_governance_finding_stays_visible_and_is_not_suppressed` |
| 7 | Unverified hypotheses | `test_an_unverified_hypothesis_is_shown_as_provisional_not_as_established` |
| 8 | Provisional estimates | `test_an_unverified_hypothesis_is_shown_as_provisional_not_as_established` (deliverable readiness); `test_resource_values_are_presented_by_discipline_with_completeness` |
| 9 | needs_inputs with missing hours | `test_a_line_without_hours_is_never_converted_into_a_number` |
| 10 | complete=False project totals | `test_a_partial_project_total_is_disclosed_and_not_presented_as_complete` |
| 11 | Resource-wise Low/Likely/High presentation | `test_resource_values_are_presented_by_discipline_with_completeness`; `test_a_complete_estimate_is_presented_as_complete` |
| 12 | Missing or contradictory assumptions | `test_contradictory_assumptions_for_one_key_are_reported`; `test_an_unconfirmed_assumption_keeps_its_status_label` |
| 13 | In-scope and out-of-scope consistency | `test_a_proposed_exclusion_that_a_deliverable_covers_is_a_contradiction`; `test_a_proposed_exclusion_appears_in_out_of_scope_as_a_proposal_needing_confirmation`; `test_an_exclusion_without_a_rationale_is_refused` |
| 14 | Requirement-to-deliverable coverage | `test_an_in_scope_requirement_with_no_deliverable_is_unrepresented_and_reported`; `test_every_in_scope_requirement_has_traceability_when_covered` |
| 15 | Duplicate work or deliverables | `test_duplicate_deliverables_are_reported`; `test_a_duplicate_deliverable_identifier_is_refused`; `test_a_deliverable_without_requirement_support_is_refused` |
| 16 | Stale requirement revisions | `test_a_stale_requirement_revision_is_reported` |
| 17 | Missing estimate references | `test_a_missing_estimate_reference_presents_no_effort`; `test_a_deliverable_citing_an_estimate_task_that_does_not_exist_is_reported` |
| 18 | Cross-project and collection isolation | `test_a_requirement_from_another_project_is_refused`; `test_governance_from_another_project_is_refused`; `test_an_estimate_from_another_project_is_refused` |
| 19 | Malformed or unexpected client content | `test_unknown_fields_in_client_content_are_refused`; `test_malformed_identifiers_are_refused` (four variants); `test_error_messages_do_not_echo_sentinel_values`; `test_a_deliverable_naming_an_unknown_workstream_is_refused` |
| 20 | Injection attempts in requirement text | `test_instruction_like_requirement_text_is_data_and_is_flagged`; `test_injection_in_a_deliverable_description_cannot_set_an_approval` |
| 21 | Draft-only lifecycle | `test_the_output_never_carries_an_approved_state_or_approver` |
| 22 | Unauthorized approval attempts | `test_an_approval_field_in_the_request_is_refused` (four fields) |
| 23 | No invented pricing or commitments | `test_the_output_model_has_no_price_rate_or_signature_fields`; `test_a_pricing_field_in_the_request_is_refused` |
| 24 | Deterministic output ordering | `test_the_same_input_produces_identical_output`; `test_reordering_inputs_does_not_change_the_output` |
| 25 | Version traceability | `test_a_new_version_records_its_previous_version`; `test_version_comparison_reports_added_and_revised_items` |
| 26 | Compatibility with AI-S01 to AI-S08 | `test_the_offline_pipeline_runs_orchestration_review_estimate_then_sow`; the regression subsets in the gate |

Additional tests: unrepresented-requirement and milestone checks (`test_milestones_carry_an_elapsed_duration_caveat_and_no_calendar_date`, `test_a_milestone_dependency_cycle_is_refused`, `test_a_milestone_naming_an_unknown_deliverable_is_refused`); overview and technical sections (`test_an_overview_that_was_not_supplied_is_marked_not_supported`, `test_technical_topics_without_input_are_marked_not_supported`, `test_a_technical_note_linked_to_an_unresolved_requirement_is_not_established`); governance and isolation of the engine (`test_a_missing_governance_review_is_refused`, `test_the_sow_engine_imports_no_network_foundation_or_provider_module`, `test_the_sow_engine_does_not_mutate_its_input`).

## 2. Gate results (at this checkpoint)

- Full suite (development worktree): 1696 passed, 3 skipped. The three skips are the Foundation tests at lines 357, 362 and 367 of `test_ai_s02_s04_acceptance_distinctions.py`, not run offline.
- Committed tree, clean export: to be recorded after commit (see the implementation record). The development worktree adds 67 collected tests from three untracked Foundation files (64 pass, 3 skip).
- AI-S09 focused: 56 passed.
- Regression subset (AI-S02 guard and contracts, AI-S05, AI-S06, AI-S07, AI-S08, AI-S09): 458 passed.
- Ruff check and format check: clean. Strict mypy: clean (144 files).
- AI-S01 to AI-S08 contract, orchestration, applications, governance and estimation paths: unchanged against HEAD before this sprint's commit.

## 3. Acceptance criteria (sprint specification section 9 and brief stage 4)

| Criterion | Status |
|---|---|
| Full approved draft SOW functionality (sections A-K as a structured model) | Implemented; subject to independent QA |
| Independent QA PASS | Pending |
| Requirement-to-SOW traceability works | Implemented and tested (`traceability`, coverage checks) |
| Estimate incompleteness visible | Implemented and tested |
| Governance warnings visible | Implemented and tested |
| Draft-only status enforced | Implemented and tested |
| No binding commercial commitments | Implemented and tested (schema has no commitment, price or signature fields) |
| Documentation matches implementation | Pending QA |
| Final candidate and commit identified | Pending commit |
| WDS formal acceptance | Pending |
