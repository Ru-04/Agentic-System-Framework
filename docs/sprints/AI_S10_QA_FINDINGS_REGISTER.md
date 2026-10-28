# AI-S10 QA Findings Register

Status: the Stage 2 independent QA of baseline `211d308` returned **FAIL**. Stage 3 remediated every
finding below. The Stage 2 **re-review of the remediation commit is pending** and is the only verdict that can
move this register to PASS. The author's self-checks are not an independent verdict.

## 1. Stage 2 findings (baseline `211d308`) and dispositions

| ID | Severity | Finding (as reported) | Disposition | Evidence |
|---|---|---|---|---|
| QA-1 | Blocking | Replay test refused by workflow state before the ledger; removing `consume` left the suite green. | **Resolved.** Replay executors reach the ledger boundary (`consume`); refusals are checked at the enforcement point; mutation fails the replay tests. | `RPL-01`..`RPL-07`, `SEC-06`; `test_ledger_consume_removed_is_detected`. |
| QA-2 | Blocking | Spec section 8 required stale-input rejection; the engine flags it. | **Resolved by WDS policy decision (2026-10-28).** Stale inputs are flagged, excluded from authoritative use and carried as findings (`STL-05`, `STL-01`..`STL-03`, `STL-06`). Stale or replayed operator authorisations are rejected (`STL-04`, `SEC-06`..`SEC-08`, `RPL-*`). | `STL-*`; `test_stale_input_policy_is_flag_and_exclude_with_operator_rejection`. |
| QA-3 | Major | REC-03 expectation rewritten to fit the observed behaviour (C-15). | **Resolved.** Expectation restored and frozen. Classified `OPEN_LIMITATION`, linked to C-15, excluded from PASS. Producer unchanged. | `REC-03`; `test_frozen_expectation_for_rec03_*`. |
| QA-4 | Major | Negative tests passed under an always-refuse mutation (SEC-05, SEC-07, SEC-08, SPEC-08). | **Resolved.** Exact reasons and enforcement points asserted; positive controls added; always-refuse mutation detected. | `SEC-05`, `SEC-07`, `SEC-08`, `SPEC-08`; `test_always_refuse_verification_is_detected`. |
| QA-5 | Major | Results not anchored to one candidate; 1728 cited against 1664 committed; untracked provenance unclear. | **Resolved.** Candidate source digest; consistency test; separate test-count table; provenance stated per source; documents reconciled. | `report.candidate_digest()`; `test_committed_results_match_the_regenerated_output`; reproducibility report section 5. |
| QA-6 | Major | Coverage gaps: AI-S01 (zero), requirement extraction (delegated), cross-project (narrow), pipeline traceability (none). | **Resolved for the offline scope.** AI-S01 (seven scenarios, S01-01..S01-07, plus the stale-operator rejection STL-04); extraction (8 deterministic and 3 LLM-backed, offline); cross-project (6 + `SEC-01`); traceability (`TRC-01`); the integrated adapter gap is blocked (`TRC-02`). | catalogue sections on AI-S01, REQ, LLM, XP, TRC. |
| Minor (EVID-15) | Minor | Expected text named estimate and SOW; executor checked the estimate only. | **Resolved.** Executor checks the estimate readiness and the SOW deliverable and risk text. | `evid_blocker_not_erased`. |
| Minor (SOW-12) | Minor | Expected "several fields"; executor tested one. | **Resolved.** Five positions tested; each must be flagged; approval unchanged. | `sow_injection_data`. |
| Minor (SOW-09) | Minor | Expected "durations"; regex covered dates only. | **Resolved.** Dates and schedule durations checked. Effort hours (AI-S08 estimate values) excluded deliberately, stated in the executor. | `sow_no_dates`. |
| Minor (SEC-09) | Minor | Name-based detection of a gate parameter. | **Resolved.** Behavioural: a direct call with no confirmation, actor or proposal returns an execution. Limitation still present. | `sec_r1_present`; `SEC-09` (open limitation). |
| Minor (REC-01) | Minor | Only the initial failure was reported; no recovery tested. | **Resolved.** `REC-04`: transient first attempt, successful retry, eight calls. | `rec_recovery_after_transient`. |
| Minor (REC-02) | Minor | One permanent variant. | **Resolved.** Three permanent statuses covered; `REC-05` covers an exception that is not retried. | `rec_permanent_no_retry`, `rec_exception_not_retried`. |

## 2. Reviewer observations (Stage 2 report) and dispositions

| ID | Observation | Disposition |
|---|---|---|
| QA-7 | SEC-12 is refused by the `Claim` constructor, not the output validator; SPEC-13 is genuine. | **Resolved.** Enforcement recorded as `Claim` for SEC-12 and `SpecialistInvestigationResult` for SPEC-13; SEC-12 expected text narrowed to the Claim contract. |
| QA-8 | SEC-09 accepted any name-based signature check. | Resolved (see the minor above). |
| QA-9 | REC-01 proved bounded retry only; REC-02 covered one variant. | Resolved (see the minors above). |
| QA-10 | Three executors corrected after the first run; a misplaced duplicate evaluation package exists in the session worktree. | The corrections are recorded in the implementation record. **The duplicate remains and must be deleted by the user** (`webdesk-ai-s02\ai_engine\ai_engine`); the removal was refused by a safety check. |
| — | EVID-16 would still report open if the lexical screen were removed entirely. | Accepted as stated: EVID-16 is an open limitation whose check passes only while the limitation is present. Semantic adequacy remains untested. |

## 3. New finding recorded by Stage 3 (upstream, not fixed)

| ID | Class | Finding | Disposition |
|---|---|---|---|
| UD-01 | Upstream defect (AI-S09), open limitation | The SOW does not compare the estimate's governance fingerprint with the governance review's. A mismatched estimate is accepted with no integrity issue. | **Recorded.** Outside AI-S10 scope; fixing it changes accepted AI-S09 output and needs the permitted upstream change and renewed verification. Test asserts the defect is still present. |

## 4. Known limits that remain (not hidden)

- Mutation coverage is two controls (ledger `consume`; verification gate). The inline stale-revision check and
  the upstream fingerprint gap are not mutation-tested.
- `STL-05` is executed under the stale-input policy ratified by WDS on 2026-10-28; no open decision remains on it.
- `REC-03` / `C-15` remain unresolved policy.
- AI-S01 wrapper denials are status-based; their enforcement point is recorded as none.
- AI-S05 has 130 accepted tests and 2 catalogue scenarios; its breadth is in its test file.
- `PIPE-04`, `PIPE-05`, `SPEC-14` remain delegated (sprint test files), as recorded.

## 5. Stage 2 re-review

Pending. The full re-review of the remediation commit is to be performed by an independent reviewer that has
not seen the Stage 3 reasoning, and is required before any PASS is claimed.
