# AI-S10 QA Findings Register

Status: **Stage 1 self-check only. Independent QA (Stage 2) has not been performed.** The author cannot
be the independent reviewer. Stage 2 adds its own findings to this register.

## 1. Stage 1 self-check findings (author)

| ID | Finding | Disposition | Status |
|---|---|---|---|
| SF-1 | The evaluation package was first created in the wrong checkout (`ai_engine/ai_engine/tests/evaluation` in the session's checkout, from a relative path). A copy exists there. | Work moved to `integration-baseline`. The stray copy could not be deleted (a safety check refused the removal). | **Open. User to delete** `webdesk-ai-s02\ai_engine\ai_engine` |
| SF-2 | Three executors gave wrong results on first run (EST-10, PIPE-02, SOW-02) because the executor inputs were wrong. | Inputs corrected to the engine's contract. The engine was not changed. | Closed |
| SF-3 | REC-03 was first written to expect refusal with no attempt. The engine runs the category with no evidence and reports `succeeded`. | Expectation corrected to the observed contract. Recorded as observation OBS-1. | Closed by correction; QA to confirm |
| SF-4 | 138 lint findings in new files before fixes (E501, F401, I001, S105). | Autofix plus manual wrapping. S105 on `PASS` suppressed with a comment. Sentinel renamed. `__all__` workaround removed. | Closed |
| SF-5 | Metric definitions were written after the first run. | Disclosed in the reproducibility report, section 4. | Disclosed |
| SF-6 | The author's first coverage count showed no AI-S01 or AI-S02 references. The output had been cut by `tail`, which hid the AI-S01 and AI-S02 rows. | Recounted. AI-S02 has two blocked references. The traceability matrix corrected. | Closed |
| SF-7 | The traceability matrix attributed the AI-S07 open limitation to EXT-08. It is EVID-16. | Corrected. | Closed |
| SF-8 | Traceability row for AI-S06 named EXT-06 as its blocked scenario. It is SEC-18. | Corrected. | Closed |
| SF-9 | The spec requires failure and recovery scenarios, including partial authorisation with no fallback and stale input rejected. | REC-01 to REC-03 added. "Stale input rejected" is implemented as flagged and not backed (SEC-04, EVID-07, EST-07), not rejected. See OBS-4. | Closed for REC-01 to REC-03; OBS-4 open |

## 2. Observations for Stage 2

| ID | Observation | Why it matters |
|---|---|---|
| OBS-1 | REC-03: a category without its collection still runs, reports `succeeded`, and its specialist reports `evidence_unavailable`. No other collection is substituted. | Matches C-15. Consumers may read success as completeness. Decision required (governance register). |
| OBS-2 | AI-S01 has no catalogue reference. AI-S02 has two blocked references only. | The matrix shows no executed coverage for these sprints. Add scenarios or accept the gap. |
| OBS-3 | AI-S05 has 130 tests and 2 catalogue scenarios. | Breadth is in the test file, not the catalogue. |
| OBS-4 | The spec says "stale input rejected". The implementation flags and does not back stale input, and marks the estimate line `needs_inputs`. It does not reject the request. | QA to decide whether flagging satisfies the spec or whether rejection is required. |
| OBS-5 | Requirement extraction has one delegated scenario (PIPE-04) and no sprint reference. | Spec section 2 lists it as in scope. |
| OBS-6 | The 16 AI-S10 tests check the runner, including mutations. They do not check the catalogue's expectations against an independent oracle. | Expectations were written by the author. Stage 2 should review them. |
| OBS-7 | All adversarial cases are fixed and hand-written, one or two per class. No generated or property-based cases. | Absence of failures is not proof of absence of defects. |
| OBS-8 | Two of the three open limitations (R-1, EVID-16) are real defects in the sense that the control is absent. They are shown as present, not fixed. | Correct per the spec; QA should confirm they are not marked as passes anywhere. |
| OBS-9 | The sprint spec and master plan are untracked in the worktree. The spec was read in full; the master plan was read by search only. | Authority files not fully reviewed are named as such in this record. |

## 3. Stage 2 (independent QA)

Not started. Stage 2 should check: the catalogue expectations; the REC-03 decision; OBS-2 and OBS-5 coverage;
the reproducibility of the clean export; and the wording of every "pass" against what it proves.
