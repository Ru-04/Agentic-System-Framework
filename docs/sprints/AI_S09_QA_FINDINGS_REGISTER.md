# AI-S09 QA Findings Register

Status: the consolidated independent QA of commit 70d5906 returned FAIL on documentation and code-quality items (recorded below). Its remediation was verified by a targeted independent review; the verdict and the two documentation corrections it required are recorded below. This register is not a PASS record for the complete candidate.

## Defects found during construction (implementer)

| ID | Severity (implementer's assessment) | Finding | Disposition | Test |
|---|---|---|---|---|
| B-1 | Major | The SOW took readiness from the estimate, so a blocker in the SOW's own governance review did not show when the estimate was built without it. | Fixed: stricter of governance and estimate readiness (`_combined_readiness`). | `test_a_blocking_governance_finding_stays_visible_and_is_not_suppressed` |
| B-2 | Major | A deliverable whose only task had no hours showed `0.0` with `complete=False`, which reads as an estimate. | Fixed: no value is presented when no line is estimated. | `test_a_line_without_hours_is_never_converted_into_a_number` |
| B-3 | Minor | The index helper used `getattr` with a computed attribute name, which the AI-S02 import guard rejects. | Fixed: key-extraction functions. Guard unchanged. | Existing guard test `test_no_provider_or_unlisted_module_is_reachable_under_src` in `test_ai_s02_guard.py` |
| B-4 | Minor | The error sanitiser echoed mapping keys. | Fixed: whitelist of known field names; other keys as placeholders. | `test_error_messages_do_not_echo_sentinel_values` |
| B-5 | Minor | An early test checked the word "approved" as a substring of `draft_not_approved`. | Fixed in the test: the check now reads the approval state. | `test_injection_in_a_deliverable_description_cannot_set_an_approval` |

## Independent consolidated QA of commit 70d5906ca762222a5c7b6cc19a11c99e3f6c4e9

Verdict: FAIL (eight major, four minor, documentation). The green gate reproduced (committed tree 1632 passed, 0 skipped; AI-S09 56 passed). No defect changed the approval state. The reviewer's mutation sweep caught M2 to M11 and missed M1.

| ID | Severity | Finding | Disposition | Regression test |
|---|---|---|---|---|
| MAJOR-1 | Major | An unestimated discipline bucket rendered zeros | Fixed: no value is shown for a bucket with no numeric line (`_resources`) | `test_an_unestimated_discipline_bucket_is_not_presented_as_zero_hours` |
| MAJOR-2 | Major | A workstream reported complete while a deliverable was unestimated | Fixed: complete only when every deliverable in it is complete | `test_a_workstream_is_incomplete_while_any_of_its_deliverables_is_unestimated` |
| MAJOR-3 | Major | Estimate effort for requirements outside the SOW was counted silently | Fixed: reported as an integrity issue; the project total is marked partial | `test_estimate_effort_for_a_requirement_outside_the_sow_is_disclosed` |
| MAJOR-4 | Major | A workstream holding only proposed exclusions was unflagged | Fixed: reported as contradictory workstream scope | `test_a_workstream_holding_only_excluded_requirements_is_flagged` |
| MAJOR-5 | Major | An unknown finding category was accepted when no estimate was supplied | Fixed: categories are checked against the request's specialist references, always | `test_a_finding_with_an_unknown_category_is_refused_without_an_estimate` |
| MAJOR-6 | Major | The injection screen covered only some free-text fields | Fixed: every free-text field is screened; the contract lists them | `test_injection_in_each_free_text_field_is_flagged_and_changes_nothing` (six cases) |
| MAJOR-7 | Major | In-scope requirement statements and finding summaries were not rendered | Fixed: both are rendered as data in their sections | `test_requirement_statements_and_finding_summaries_are_rendered_as_data` |
| MAJOR-8 | Major | No test covered the estimate being stricter than governance | Fixed: test added; the readiness rule itself was already correct | `test_the_estimate_readiness_can_be_stricter_than_governance_in_the_sow` |
| MINOR-1 | Minor | Some section states were hard-coded to supported | Fixed: the in-scope section is not supported when no workstream is supplied | Covered by the in-scope and missing-input tests |
| MINOR-2 | Minor | A dependency-only milestone was not flagged | Fixed | `test_a_milestone_with_dependencies_but_no_deliverable_is_flagged` |
| MINOR-3 | Minor | Acceptance criteria order changed the output | Fixed: criteria are sorted | `test_reordering_acceptance_criteria_does_not_change_the_output` |
| MINOR-4 | Minor | The revised-requirement path had no assertion | Fixed | `test_a_revised_requirement_is_reported_between_versions` |
| DOC | Documentation | Stated claims were false: needs_inputs display (contract), injection scope (contract and record), refusal of unknown categories (contract), identical output for reordered inputs, committed count recorded as pending, headline count from the development worktree, critical-type findings | Corrected in the contract, record, matrix and dependency register | Documentation |

Reviewer's mutation sweep: M2 to M11 caught; M1 (readiness combination) survived and is now covered by `test_the_estimate_readiness_can_be_stricter_than_governance_in_the_sow`.

Status: remediation is complete and the gate is green (development worktree 1712 passed, 3 skipped; SOW 72 tests). An independent verification of this remediation has not yet been recorded, so no PASS is claimed for the corrected candidate.
