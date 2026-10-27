# AI-S09 QA Findings Register

Status: the independent QA of the complete AI-S09 implementation has not yet run. This register records the defects found by the implementer during construction. It is not an independent QA record.

## Defects found during construction (implementer)

| ID | Severity (implementer's assessment) | Finding | Disposition | Test |
|---|---|---|---|---|
| B-1 | Major | The SOW took readiness from the estimate, so a blocker in the SOW's own governance review did not show when the estimate was built without it. | Fixed: stricter of governance and estimate readiness (`_combined_readiness`). | `test_a_blocking_governance_finding_stays_visible_and_is_not_suppressed` |
| B-2 | Major | A deliverable whose only task had no hours showed `0.0` with `complete=False`, which reads as an estimate. | Fixed: no value is presented when no line is estimated. | `test_a_line_without_hours_is_never_converted_into_a_number` |
| B-3 | Minor | The index helper used `getattr` with a computed attribute name, which the AI-S02 import guard rejects. | Fixed: key-extraction functions. Guard unchanged. | Existing guard test `test_no_provider_or_unlisted_module_is_reachable_under_src` in `test_ai_s02_guard.py` |
| B-4 | Minor | The error sanitiser echoed mapping keys. | Fixed: whitelist of known field names; other keys as placeholders. | `test_error_messages_do_not_echo_sentinel_values` |
| B-5 | Minor | An early test checked the word "approved" as a substring of `draft_not_approved`. | Fixed in the test: the check now reads the approval state. | `test_injection_in_a_deliverable_description_cannot_set_an_approval` |

## Independent QA

Pending. The consolidated QA will be recorded here with its verdict, the commit it inspected, and each finding with its disposition. No PASS is claimed until an independent reviewer issues one.
