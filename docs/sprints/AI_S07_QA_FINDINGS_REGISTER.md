# AI-S07 QA Findings Register

Scope: independent QA and verification of the AI-S07 Runtime Governance Reviewer candidate. All reviewers were read-only and did not implement the candidate. Each row records the finding, its severity, its disposition and the test that discriminates it.

## Review rounds

| Round | Reviewer | Verdict | Blocking? |
|---|---|---|---|
| 1 | Independent QA | FAIL (three MAJOR gaps) | No BLOCKER |
| 2 | Independent re-review | PASS WITH FINDINGS (two MAJOR, one MINOR) | No BLOCKER |
| 3 | Consolidated independent QA | FAIL (two MAJOR served-copy gaps; one fail-open window; two documentation MINORs) | No BLOCKER |
| 4 | Final independent verifier | FAIL (one MAJOR fail-open parameter default; one MAJOR documentation; minors) | No BLOCKER |
| 5 | Final independent verifier, after round-4 remediation | FAIL (two MINOR defects, one documentation nit, one test gap); round-4 MAJOR fixes held | No BLOCKER |
| 6 | Final independent verifier, after round-5 remediation | FAIL (one MINOR documentation defect); backing logic and provenance re-check verified | No BLOCKER |
| 7 | Gate and documentation re-check after round-6 wording fix (no independent re-verification run) | Gate green; wording corrected | |

## Findings and dispositions

| ID | Round | Severity | Finding | Disposition | Discriminating test |
|---|---|---|---|---|---|
| R1-1 | 1 | MAJOR | Verified claim citing an unverified approved record gave no finding | Fixed: record status required (`_is_verifiable`) | `test_a_verified_claim_citing_an_unverified_record_is_a_blocker` |
| R1-2 | 1 | MAJOR | Same-category feasibility disagreement silently accepted | Fixed: divergence checked across all claims | `test_disagreeing_claims_within_one_category_are_a_divergence` |
| R1-3 | 1 | MAJOR | Unverified claim citing synthetic mock gave EVIDENCE_BACKED | Fixed: backing requires verifiable, verified records | `test_unverified_claims_citing_synthetic_evidence_are_not_evidence_backed` |
| R1-4 | 1 | MINOR | Feasibility CONFLICTING without conflict entry unreported | Fixed | `test_feasibility_conflicting_without_a_conflict_entry_is_unreported` |
| R1-5 | 1 | MINOR | Naive `as_of` raised TypeError | Fixed: refused at input | `test_a_naive_as_of_is_refused` |
| R1-6 | 1 | MINOR | Duplicate admitted evidence IDs overwritten | Fixed: refused in adapter | `test_duplicate_admitted_evidence_ids_are_refused` |
| R2-1 | 2 | MAJOR | EVIDENCE_BACKED ignored claim status | Superseded by the authority model: claim status is not proof; backing is decided on admitted records | `test_a_claim_with_relevant_verified_evidence_is_evidence_backed` (positive gated outcome) and `test_a_verified_record_without_recorded_provenance_is_not_backed` (negative gate) |
| R2-2 | 2 | MAJOR | Served copy not reconciled with admitted record | Fixed: `SERVED_RECORD_MISMATCH`; backing requires identical copy | `test_a_served_copy_whose_content_differs_from_the_admitted_record_is_a_mismatch` |
| R2-3 | 2 | MINOR | Naive `checked_at` on admitted record raised TypeError | Fixed: refused at input | `test_a_naive_checked_at_on_an_admitted_record_is_refused` |
| R3-1 | 3 | MAJOR | A duplicated served ID could hide a mismatch, depending on order | Fixed: duplicates are a mismatch in any order and never back | `test_duplicate_served_copies_are_a_mismatch_in_either_order` |
| R3-2 | 3 | MAJOR | An uncited served copy escaped mismatch checks | Fixed: every served copy is checked; an unadmitted served record is a blocker | `test_an_uncited_mismatched_served_copy_is_reported`, `test_an_uncited_served_record_that_is_not_admitted_is_reported` |
| R3-3 | 3 | MINOR | Staleness window without `as_of` silently ignored (fail-open) | Fixed: refused at input | `test_a_staleness_window_without_as_of_is_refused` |
| R3-4 | 3 | MINOR | Fingerprint docstring overclaimed | Fixed: docstring states the coverage; parameters now hashed | `test_the_fingerprint_covers_the_review_parameters` |
| R3-5 | 3 | MINOR | Module docstring called all checks policy-independent | Fixed | Documentation (reviewed in round 4) |
| R4-1 | 4 | MAJOR | With no collection set or no window, a record with no collection mapping still backed | Fixed: backing requires `as_of`, `stale_after` and an authorised set; otherwise nothing backs and `MISSING_REVIEW_PARAMETER` is reported | `test_evidence_is_not_backed_without_a_window_or_a_collection_set`, `test_evidence_with_an_unknown_collection_fails_closed` |
| R4-2 | 4 | MAJOR | Record cited QA, matrix and handoff documents that did not exist | Fixed: this register, `AI_S07_ACCEPTANCE_MATRIX.md` and `AI_S08_HANDOFF_FROM_AI_S07.md` now exist | Documentation (reviewed in round 5) |
| R4-3 | 4 | MINOR | Module docstring still said "policy-independent" before its caveat; collection wording had no caveat | Fixed | Documentation (reviewed in round 5) |
| R4-4 | 4 | MINOR | Contract stated one provenance rule for all verified evidence; vendor documentation has different required fields | Fixed: provenance rule now per kind | Documentation (reviewed in round 5) |
| R4-5 | 4 | MINOR | Record misstated when the zero-evidence MAJOR finding fires | Fixed | Documentation (reviewed in round 5) |
| R4-6 | 4 | MINOR | Adapter-only orchestration import rule had no test | Fixed | `test_only_the_adapter_imports_orchestration` |
| R5-1 | 5 | MINOR | `governance/__init__.py` said "policy-independent checks" without the caller-supplied caveat | Fixed | Documentation (reviewed in round 6) |
| R5-2 | 5 | MINOR | Reviewer trusted a verified record's status without re-checking provenance; an unvalidated copy with stripped provenance backed | Fixed: `_has_provenance` re-checked in `_is_verifiable` | `test_a_verified_record_without_recorded_provenance_is_not_backed` |
| R5-3 | 5 | nit | Served-status wording said "forced to be unverified" but an equal status is also accepted | Fixed | Documentation (reviewed in round 6) |
| R5-4 | 5 | test gap | The adapter-only AST test did not inspect plain `import` statements | Fixed | `test_only_the_adapter_imports_orchestration` |
| R6-1 | 6 | MINOR | `_same_record` docstring (and the contract and record) said a stronger served status is a mismatch; the code treats any status other than unverified or equal to the admitted one as a mismatch | Fixed: wording corrected to match the code, which is the stricter rule | Documentation; the behaviour is covered by the served-status tests |

## Governance decision carried forward

D-EVB-1 (served-status interpretation) is not a QA defect. WDS approved it for isolated engineering in the final directive. See `AI_S07_GOVERNANCE_REVIEWER_CONTRACT.md` section 5 and `AI_S07_D06_D09_RECONCILIATION.md`.

## Final status

Round 6 verdict: FAIL on one MINOR documentation defect, which is corrected (round 7). The backing logic, provenance re-check, gating, and unchanged AI-S01 to AI-S06 paths were verified. Round 6 did not re-run after the wording fix; the change is documentation-only and the gate is green (1575 passed, 3 skipped). No independent PASS verdict on the final text is recorded, so acceptance criterion 20 in the acceptance matrix stays open.
