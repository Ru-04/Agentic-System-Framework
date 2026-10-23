# Sprint 2 — closure evidence for QA4-06, QA4-08 and QA4-15

**Status:** engineering evidence only. **Not an independent QA sign-off.** AS's review is required.

## QA4-06 — candidate quarantine ordering (S2-D18)

- **Fix:** quarantine and eligibility run inside `InMemoryRetriever.search`, before ranking and the candidate limit, through `RetrievalQuery.admit` (`webdesk/evidence/retrieval.py`). The specialist supplies `make_admission` (`webdesk/evidence/untrusted.py`).
- **Evidence:** `tests/unit/test_s2_remediation.py::test_quarantined_high_overlap_passages_do_not_displace_an_eligible_one`; negative control `test_without_eligibility_quarantined_passages_would_take_the_slots`; boundary `test_eligible_passages_fill_exactly_the_limit_at_the_boundary`; identity and citation `test_source_identity_and_citation_span_survive_the_predicate`; empty eligible set `test_no_eligible_passage_is_missing_evidence_not_a_hit`; failure `test_a_failing_predicate_is_not_swallowed`.
- **Limit:** the reported exclusion count comes from the predicate. The count is shown without naming the excluded records.

## QA4-08 — plural normalization (S2-D19)

- **Fix:** sibilant `-es` endings only, on words of five or more letters (`processes`→`process`, `matches`→`match`, `boxes`→`box`, `classes`→`class`, `indexes`→`index`, `accesses`→`access`, `sizes`→`size`). One canonical form per word.
- **Defect found while testing:** a first version gave one word two forms, so one query word could satisfy the two-term floor. A regression test caught it, and the fix keeps one form per word.
- **Evidence:** `test_appropriate_plurals_match_their_singular`; false-match controls `test_unrelated_or_technical_forms_do_not_merge` (`https`/`http`, `axes`/`axe`, `process`/`proces`, `access`/`acces`, `address`/`addre`, `uses`/`use`); `test_one_word_cannot_satisfy_the_two_term_floor`; frozen floor `test_frozen_retrieval_threshold_is_unchanged_by_plural_folding`.
- **Recorded limits:** `caches` does not match `cache` (`test_known_limit_caches_does_not_match_cache`); `APIs` is not folded to `api` (`test_known_limit_plural_apis_is_not_folded`).

## QA4-15 — workspace isolation before ranking and limiting (S2-D20)

- **Fix:** the retriever filters by workspace before any scoring. An unauthorized passage never reaches ranking or the limit.
- **Evidence:** `test_unauthorized_high_overlap_evidence_does_not_displace_authorized_evidence`; unauthorized workspace `test_unauthorized_workspace_gets_no_evidence`; mixed candidates `test_mixed_candidates_return_only_authorized_passages`; citation leakage `test_specialist_output_never_names_or_cites_another_workspace`; empty authorized set `test_empty_authorized_result_set_is_incomplete_with_no_findings`; candidate-limit boundary `test_candidate_limit_boundary_with_authorized_evidence`.
- **Limit:** only `InMemoryRetriever` exists in this repository. A production retriever must meet the same contract before any production use, and that is not yet built.

## Effect on the 17-requirement evaluation (frozen thresholds, not tuned)

- Passage grades: **0 DIRECT, 5 PARTIAL, 111 IRRELEVANT** (before: 0, 5, 107). The retrieved total rose by four because the plural rule admits real matches.
- Requirements with a cited finding: **0**. Coverage was not increased artificially.
