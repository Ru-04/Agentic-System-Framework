# AI-S08 QA Findings Register

Scope: independent QA of the AI-S08 draft effort estimation engine. The reviewer was read-only and did not implement the engine.

## Consolidated QA of commit 0a7bfee6303bcf28e6401a554a3190389de8ea7b

Verdict: FAIL. 0 BLOCKER, 3 MAJOR, 2 MINOR.

Reviewer checks that passed: complete sprint functionality (R1); requirement-to-task traceability (R2); resource-wise estimate fields (R3); hour-range validation at both the model and raw-input boundaries (R4); arithmetic on a three-line and a fractional example (R5, sums); duplicate-counting in project totals (R6); governance adapter copying and no mutation (R8); missing-information handling as needs-inputs or outstanding issues (R9); version and revision handling (R10); project and data isolation, including the AST scan for network, filesystem, environment, clock and database access (R11); no approval status or actor field (R12); AI-S01 to AI-S07 protected paths unchanged (R14); test effectiveness, where the reviewer's mutation sweep (M1 to M12) was caught by the existing test file (R16); adversarial probes (a) to (d) and (f).

| ID | Severity | Finding | Contract or requirement | Disposition | Regression test |
|---|---|---|---|---|---|
| MAJOR-1 | MAJOR | An empty estimate, or one with a requirement that has no task, reported `complete=True` and `excluded=[]` | REQUIREMENT_SCHEMA 9.2; AI-S08 contract section 7.4 | Fixed: totals are incomplete for an empty estimate and for any uncovered requirement | `test_an_empty_estimate_is_never_complete`; `test_a_requirement_with_no_task_makes_the_project_needs_inputs` |
| MAJOR-2 | MAJOR | A governance blocker that named no requirement left readiness unaffected | Requirement R7; AI-S08 readiness rules; engine docstring | Fixed: `has_blocker` makes project readiness `blocked` | `test_a_blocker_without_requirement_ids_blocks_readiness` |
| MAJOR-3 | MAJOR | Error messages echoed mapping keys and extra field names (`<sentinel>` values reached `str(error)`) | Requirement R13; AI-S08 contract section 6 (false statement before the fix) | Fixed: sanitisation shows positions, known field names and `<key>` only | `test_error_messages_do_not_echo_mapping_keys_extra_fields_or_identifiers` |
| MINOR-1 | MINOR | Error messages named requirement and task identifiers | Requirement R13 | Fixed: messages give counts or no identifiers | `test_a_missing_governance_assessment_names_a_count_not_identifiers` |
| MINOR-2 | MINOR | Lines with no hours (discipline None) were absent from by-discipline totals | Requirement R9 | Fixed: an `unassigned` bucket | `test_tasks_without_hours_appear_in_the_unassigned_bucket` |

Non-blocking recommendations from the review, and their disposition:
- State in the contract that integers are stored as floats: already in contract section 6; the test asserts the conversion.
- The brief refers to `_sanitize`; the function is named `sanitized`. No code change.
- Add tests for an empty estimate's completeness and for blocker-only readiness: added (see above).

Review notes not treated as defects:
- Per-line discipline, and per-requirement subtotals that include shared lines, are documented behaviour (contract section 7.5).
- A human estimator basis is accepted on the caller's record; the engine cannot verify the estimator (contract section 4).

## Gate after remediation

- Full suite: 1640 passed, 3 skipped. The skips are the Foundation tests at lines 357, 362 and 367 of `test_ai_s02_s04_acceptance_distinctions.py`.
- AI-S08 focused: 65 tests, all passing.
- Ruff check and format check: clean. Strict mypy across source and tests: clean.
- AI-S01 to AI-S07 contract, orchestration, applications and governance paths: unchanged against HEAD.

## Independent verification of the remediation

First verification of the remediation (FAIL, two residual defects): D1 (MAJOR) an estimate with no requirements at all reported `complete=True`; D2 (MINOR) integer mapping keys still leaked their value through the sanitiser. Both fixed; regression tests `test_an_estimate_with_no_requirements_is_incomplete_and_needs_inputs` and `test_an_integer_mapping_key_does_not_leak_its_value`. Contract section 6 corrected (positions are `<index>`).

The same verifier passed F2, F4 and F5 outright and passed F1 and F3 except for the two residual cases above. It also passed the four adversarial probes, the gate, the unchanged protected paths and the non-weakened tests. Its documentation failures were the two statements corrected above.

Gate after the second remediation: full suite 1640 passed, 3 skipped (lines 357, 362, 367 of `test_ai_s02_s04_acceptance_distinctions.py`); AI-S08 65 tests; ruff and strict mypy clean.

A second independent verification of this final text has not been run. The verdict on the complete remediation is therefore not recorded here as PASS.
