# AI-S03 QA and Evaluation Plan

Scope: isolated, non-production retrieval infrastructure. Synthetic data only. No live vendor research, no real client
documents, no real provider, no production Foundation.

## 1. Required QA cases (WDS brief) and where they are tested

| WDS case | Test(s) |
|---|---|
| Deterministic retrieval fixtures | `fixtures/rag/synthetic_rag_corpus.json` (fixed content and computed hashes); `test_ai_s03_evaluation.py::test_retrieval_quality_on_the_fixed_query_set` |
| Unauthorised collection access | `test_ai_s03_security.py`: no grant (index never searched), granted collection without approval, one denied collection not leaking its neighbour, another actor, per-collection access check; `test_ai_s03_ingestion_access.py`: default deny |
| Cross-project evidence leakage | `test_ai_s03_security.py`: project A never returns project B documents, cross-project approval refused, a leaking index refused, project B actor cannot read A; `test_ai_s03_specialist.py::test_lookup_never_returns_another_projects_records`; grant matrix in `test_ai_s03_evaluation.py` |
| Stale and missing citations | `test_ai_s03_retrieval.py`: superseded version flagged, stale document against policy, hit for an unstored document (missing citation), hit whose text does not match the stored span (malformed) |
| Contradictory evidence | `test_ai_s03_retrieval.py::test_successful_retrieval...` and `test_ai_s03_evaluation.py::test_contradictions...`: explicit conflict group reported; members stay unverified |
| Unavailable documents and retrieval failures | `test_ai_s03_retrieval.py`: unavailable document, index exception (classified, message not echoed), empty query; `test_ai_s03_evaluation.py::test_unavailable_documents...` |
| Invalid metadata | `test_ai_s03_contracts.py` and `test_ai_s03_ingestion_access.py`: wrong hash, verified status, external URL, self-supersession, bad identifiers, invalid collection scope; refusal reasons do not echo text |
| Malformed retrieval results | `test_ai_s03_retrieval.py`: non-hit objects, forged span, malformed mixed with good hits (good hits still returned) |
| No synthetic evidence automatically verified | `test_ai_s03_security.py::test_every_retrieved_reference_is_unverified_across_the_corpus`, `test_synthetic_reference_cannot_be_built_as_verified`; `test_ai_s03_evaluation.py::test_no_synthetic_reference_is_ever_verified` |

## 2. Test inventory

| File | Tests | Level |
|---|---|---|
| `test_ai_s03_contracts.py` | 19 | Contract |
| `test_ai_s03_ingestion_access.py` | 19 | Unit and contract |
| `test_ai_s03_index.py` | 18 | Unit (chunking, embedder, hybrid scoring, SQL contract) |
| `test_ai_s03_retrieval.py` | 21 | Integration over the synthetic corpus |
| `test_ai_s03_security.py` | 20 | Security regression |
| `test_ai_s03_specialist.py` | 17 | Integration, including the AI-1 Shopify specialist (its agent and the execution wrapper were changed for project scoping under the Y-1 exception) |
| `test_ai_s03_evaluation.py` | 6 | Evaluation and matrix |
| `test_ai_s03_review_fixes.py` | 102 | Regression for the independent reviews and remediations |
| **Total** | **222** | |

## 3. Evaluation

### 3.1 Retrieval quality on the fixed query set

The fixed set has six cases. The table below is printed by the evaluation test on each run.

| Query | Expected status | Actual status | Documents returned |
|---|---|---|---|
| warehouse stock levels inventory | ok | ok | 2 (both inventory documents, a contradiction pair) |
| legacy checkout single page payment | ok | ok | 2 (superseded v1 and current v2) |
| gift cards sold online | ok | ok | 1 (stale against a 365-day policy) |
| wishlist registered customers | failed (source unavailable) | failed | 0 |
| quantum zebra lattice | no match | no match | 0 |
| (empty) | failed (empty query) | failed | 0 |

All six reach their expected status. Every expected document is returned.

### 3.2 Citation integrity

Every citation in the fixed set is a character-exact span (Python code-point offsets) of its stored version. The count is over all accepted evidence
in the fixed set; it is non-zero and the check is total.

### 3.3 Contradiction and staleness

The inventory query yields one contradiction group, `cg-inventory`, with two members. The gift-card query yields one item
flagged `stale`. The superseded checkout version is flagged `superseded`.

### 3.4 Security metrics

- Unavailable documents returned: **0**.
- Synthetic references verified: **0**.
- Evidence leaked outside the grant matrix (actor × project × collection, 12 combinations: 2 actors × 2 projects × 3 collections): **0**. Two combinations are
  granted, and both serve evidence.

### 3.5 What these numbers do not show

- They measure this implementation on a 10-document synthetic corpus with a test-only embedder. They say nothing
  about real embedders, real documents, scale, or latency.
- They are not a retrieval-quality claim for any production model. No provider is approved, and none was called.
- Recall and precision on real WDS documents are not measured. That needs collection-level approval first.

## 4. Gate

Run from `ai_engine/` in `feature/ai-s03`:

| Check | Result |
|---|---|
| `pytest` (commit 097ba44; AI-S02 tests are not in this commit) | 617 passed: 388 AI-1 and AI-S01; 229 AI-S03 and Y-1 (`tests/test_ai1_y1_conflict_scope.py`) |
| `ruff check src tests` | Clean |
| `ruff format --check src tests` | Clean (74 files, commit 097ba44) |
| `mypy` (project configuration, `src`) | Clean (45 files, commit 097ba44) |
| `mypy --strict src tests` | Clean (74 files, commit 097ba44) |

Recorded with `.venv` of the AI-S02 worktree. The AI-S03 worktree's own `mypy.exe` is blocked by the workstation's
Application Control policy (os error 4551), so the same pinned mypy 1.11.2 binary was used. Nothing else was changed.

## 5. Independent review

Requested: a fresh review agent, given the worktree and the approved scope, with no conclusions from the author. It was
asked to try to break the source-access restrictions, citation integrity, verification status, leakage, failure
classification and contract drift, and to report PASS or FAIL with reproductions.

Verdict: recorded in section 6 when received. AI-S03 is not accepted until that verdict is read and every finding is
either fixed with a regression test or classified.

## 6. Review outcome

Verdict received: **FAIL**, nine findings. Each finding has a regression test in
`ai_engine/tests/test_ai_s03_review_fixes.py` (21 tests). Two existing security tests were changed as
the F5 disposition requires. No finding is closed by reclassification.

| # | Severity | Finding | Disposition | Where |
|---|---|---|---|---|
| F1 | High | A hit whose stored document sat in a collection outside the allowed set was returned as evidence when the chunk claimed an allowed collection | Fixed. The stored document decides its collection. A document outside the allowed set, or a chunk that disagrees with its document, is refused as malformed | `retrieval.py` `_validate_hit`; `test_relabelled_chunk_cannot_surface...` |
| F2 | Medium | The empty-query enumeration path skipped unavailable documents without a record | Fixed. Recorded as `source_unavailable` with the document identifier | `retrieval.py` `enumerate_authorised`; `test_enumeration_classifies_an_unavailable_document` |
| F3 | Medium | A non-sequence index result raised instead of being classified | Fixed. Classified `malformed_result` and audited | `retrieval.py` `retrieve`; `test_malformed_index_container_is_classified_and_audited` (4 cases) |
| F4 | Medium | The base model stripped edge whitespace silently, and chunk spans could end in spaces and fail validation | Fixed. Text fields refuse edge whitespace (refuse, never repair). Chunking moves span bounds inward past edge whitespace and drops whitespace-only spans. Chunk identifiers are bounded digests | `contracts.py` (`_EXACT_TEXT`, `refuse_edge_whitespace`); `index.py` `build_chunks`, `_chunk_id`; 6 tests |
| F5 | Low | An approval for another project produced a distinct refusal, which revealed that the collection exists elsewhere | Fixed. One refusal for unapproved and cross-project collections. The audit record keeps the denied list. Two security tests now assert the single refusal | `retrieval.py` `_collection_failures`; `test_other_project_approval_is_indistinguishable...`; `test_ai_s03_security.py` (two tests) |
| F6 | Low | "Byte-exact" wording for citations | Fixed. Wording corrected in code, the contracts document and this plan. The code was already character-exact (code-point offsets); the defect was the wording. A multibyte test pins the behaviour | `contracts.py`, `retrieval.py` docstrings; both documents; `test_citation_offsets_are_character_offsets_not_bytes` |
| F7 | Low | Base-model whitespace stripping (same root as F4) | Closed with F4 | as F4 |
| F8 | Low | The lookup raised on an invalid request (overlong query, invalid project) | Fixed. An invalid request fails closed to an empty result, and the index is not called | `specialist.py` `search`; two tests |
| F9 | Low | A document added directly to the store could carry a kind that did not match its collection scope | Fixed. The retriever checks kind against scope and refuses `invalid_metadata` | `retrieval.py` `_validate_hit`; `test_stored_document_with_a_scope_that_does_not_match...` |

Regression evidence. The first reproduction run, against the unfixed code with an earlier draft of the
file, failed 12 of 21 tests. The failures covered F1, F2, F3, F4, F5, F8 and F9. That draft was then revised,
and the revised file was not re-run against the unfixed code. Some tests are guard tests that also pass
before a fix, because they protect behaviour that was already correct. The F6 test's own length assertion
was wrong in the first draft and was corrected.

Known limit, documented and not fixed: `enumerate_authorised()` has no `top_k` cap. It is a linear scan of
the store, suitable for the synthetic corpus only.

Gate after the fixes: pytest 1112 passed; `ruff check` and `ruff format --check` clean; `mypy src` clean
(55 files, working tree at that time) and `mypy --strict src tests` clean (98 files, working tree at that time), both with the pinned mypy 1.11.2 binary.

Status: re-review requested on the fixed tree.

### 6.1 Second independent review (FAIL, then addressed)

The re-review of the fixed tree returned FAIL, with these items. The source-access boundary held: no path from
an unapproved collection, another project, or an unavailable document to evidence was found.

- **Blocking, fixed.** Unavailable and unauthorised hits consumed the `top_k` budget before validation, so
  valid evidence could be hidden (`retrieval.py` `retrieve`). The index is now asked for up to 500 candidates
  (`_CANDIDATE_LIMIT`), validation runs over them, and the result is capped at `top_k`. This is a bound for the
  synthetic-scale index, not a guarantee for larger corpora. Test: `test_withdrawn_chunks_do_not_consume_the_top_k_budget`.
- **Blocking, fixed (F8 not fully closed).** A non-iterable `allowed_collections` raised `TypeError` in the lookup.
  The lookup now fails closed on `TypeError` as well (`specialist.py` `search`). Test:
  `test_lookup_refuses_a_non_iterable_collections_value_without_raising`.
- **Fixed.** Evidence is capped at `top_k` (`test_evidence_is_capped_at_top_k`). The audit comment that claimed
  the cross-project distinction is kept was wrong; the audit lists both as denied, and the comment now says so.
- **Open, for a WDS decision.** `RetrievalRequest.query` is stripped of edge whitespace, which conflicts with
  "refuse, never repair" for text fields. A query is not evidence text, so it was left unchanged rather than
  altered without a decision. Changing it would refuse requests with edge whitespace.
- **Open, documented.** An empty-query audit lists every requested collection as denied, although none were
  evaluated.
- **Info.** `CROSS_PROJECT_REFUSED` on a document subject is reachable only if an index returns another
  project's chunks; `HybridIndex` filters them, so it is a theoretical existence oracle.

Status after 6.1: the blocking items are fixed with tests and the gate is green. A further re-review is needed
before any closure. AI-S03 is **not accepted**.
 AI-S03 is **not accepted** until the re-review verdict is read
and every finding is confirmed closed.


### 6.2 Final remediation under WDS authorisation (re-review, decisions)

WDS authorised the final remediation and independent re-review. The confirmed decisions and their
implementation:

1. **Query validation.** `RetrievalRequest.query` keeps its exact characters. A query with leading or trailing
   whitespace is refused at construction (`ValidationError`), never repaired. The specialist lookup fails closed
   on such a query and does not call the index. Tests: `test_query_with_edge_whitespace_is_refused_not_repaired`,
   `test_query_with_edge_whitespace_never_reaches_the_index`.
2. **Empty-query audit.** An empty query is not searched, so no collection was evaluated. The audit now reports the
   requested collections as `not_evaluated_collections`, and does not report them as denied. Real queries still
   report denied collections as denied. Tests: `test_empty_query_audit_reports_collections_as_not_evaluated_not_denied`,
   `test_denied_collections_are_still_reported_as_denied_on_a_real_query`.
3. **500-candidate bound (retained).** The index is asked for up to 500 candidates so that unavailable or
   unauthorised candidates cannot displace valid evidence, and the result is capped at `top_k`. This is a bound
   for the isolated prototype and the synthetic corpus. It does **not** guarantee complete retrieval on larger
   datasets. A real dataset needs its own bound, measured retrieval, and approval.
4. **Cross-project isolation and metadata disclosure.** Verified by tests and by the independent re-review (see the
   re-review record below).

Gate: pytest 1132 passed (961 earlier, 171 AI-S03); ruff check and format clean; mypy `src` (55 files, working tree at that time) and
`--strict src tests` (98 files, working tree at that time) clean, pinned mypy 1.11.2.


### 6.3 Final independent re-review: FAIL, dispositions, and decisions needed

A fresh, read-only reviewer with no implementation context reviewed the whole AI-S03 diff. **Verdict: FAIL.**
Gates it observed: pytest 1112 passed; ruff and format clean; strict mypy clean (pinned 1.11.2).

| Claim | Result | Disposition |
|---|---|---|
| 1. Valid evidence not displaced by unavailable or unauthorised candidates | NOT CONFIRMED at the bound | **WDS decision: option (a), accepted 2026-10-23.** The bound is kept and documented with its threshold (below). Unauthorised candidates cannot reach the index. |
| 2. Malformed `allowed_collections` fails closed | CONFIRMED, with exceptions | Fixed. The lookup accepts only a list or tuple. A generator, set, dict or string is refused and never iterated. |
| 3. Returned evidence never exceeds `top_k` | Retrieve path confirmed. Enumerate path not capped | Retrieve is capped. The lookup's empty-query path returns the full authorised snapshot, which AI-1 requires (section 6.1). **WDS decision required** on whether the snapshot should be capped, since that needs an AI-1 change. |
| 4. Query validation and bypasses | CONFIRMED | Fixed. `retrieve` and `enumerate_authorised` re-validate the request, so `model_copy` and `model_construct` cannot bypass query checks. A request that fails validation raises `ValidationError`; the specialist lookup never produces one. |
| 5. Audit classifications | CONFIRMED | No change. Empty query: `not_evaluated_collections`. Real query: denied. Audit holds identifiers and a digest, never text. |
| 6. Citations, versions and failure states | Superseded via the lookup: NOT CONFIRMED. Enumerate and retrieve classified an unavailable-only corpus differently: NOT CONFIRMED | Fixed. The lookup withholds superseded versions, since it cannot expose the freshness flag. Enumerate now reports the same FAILED state as retrieve. |
| 7. Cross-project isolation | CONFIRMED | No change. Other-project and unknown collections give the same refusal. The document-subject cross-project branch is reachable only from a faulty index. |
| 8. Metadata disclosure | CONFIRMED | No change. Refusal and failure details are fixed strings. |

Other findings:
- **All-denied returns FAILED, partly-denied with no hit returns NO_MATCH.** This is deliberate: when no collection
  can be searched, nothing ran, so the search fails. The authorisation-notice rule in the contracts document is
  narrowed to say so. **WDS to confirm.**
- Dict input was accepted as its keys. It is now refused.
- Info: the audit log and lookup group map grow in memory without bound, and query digests are unsalted SHA-256.
  Both are prototype limits.

**WDS decision (2026-10-23): option (a) accepted.** The 500-candidate bound is kept as documented.

**Displacement threshold (the bound as documented).** The index scores every chunk in the request's project and allowed collections that matches the query, and returns the 500 highest-ranked. Unavailable chunks count toward those 500. So an available, authorised, valid chunk is returned only if at most 499 matching chunks outrank it. A valid chunk ranked 501st or lower is not retrieved, even though it is valid. Among the valid chunks inside the window, the top `top_k` are returned. Pinned by `test_valid_chunk_ranked_within_the_candidate_bound_is_returned` (499 unavailable chunks outrank it: returned) and `test_valid_chunk_ranked_beyond_the_candidate_bound_is_not_returned` (500 outrank it: not returned). The enumerate path (the AI-1 snapshot) is not bounded this way; see section 6.3.

**Options considered for the bound (claim 1):**
(a) Accept the 500-candidate bound as documented, with the displacement threshold stated (500 or more higher-ranked
unavailable candidates).
(b) Filter unavailable documents in the index, before scoring, as the design already does for project and
collection. This removes the displacement. It changes the path that reports unavailable documents, so the
retrieval-failure classification for an all-unavailable query would need to be reported separately.

Status: **AI-S03 is not accepted.** The re-review FAIL stands until WDS decides claim 1 and the enumerate cap,
and an independent re-review confirms the fixes.

### 6.4 Completion cycle (WDS final execution directive)

Decisions applied, as confirmed by WDS:

- **D-S03-01 (candidate window).** The 500-candidate maximum is kept. Pinned by two tests: 499 higher-ranked
  unavailable candidates return the valid evidence; 500 do not. Accepted as a prototype limitation, not a guarantee
  of complete retrieval.
- **D-S03-02 (empty-query lookup).** The complete authorised snapshot is preserved and not capped. Verified: only
  authorised project and collection records are returned; malformed collections fail closed; unauthorised records
  are never included. The difference from ranked retrieval is in contracts section 12.
- **D-S03-03 (all-denied).** When every requested collection is denied: `failed`, one sanitized `access_denied` reason
  with no collection identifier, no evidence, and an accurate audit (`denied_collections` lists them;
  `not_evaluated_collections` is empty). Distinguished from: empty queries (`not_evaluated`), authorised searches with no
  match (`no_match`), index errors and unavailable evidence (`failed` with their own classes), and partial authorisation
  (permitted collections are still searched; the denied ones are listed individually).
- **D-S03-04 (query validation).** A query with leading or trailing whitespace is refused, not trimmed. The lookup
  fails closed on it without calling the index.
- **D-S03-05 (audit).** A collection not evaluated is never labelled denied. Empty queries report
  `not_evaluated_collections`.

Verification items:

| # | Item | Evidence |
|---|---|---|
| 1 | Previously blocking retrieval defects | Withdrawn-chunk displacement and `TypeError` tests (review round 2); superseded lookup and enumerate classification (final re-review) |
| 2 | Empty-query complete-snapshot boundary | `test_empty_query_snapshot_contains_only_authorised_project_and_collection_records`; `test_empty_query_lookup_without_authorisation_returns_nothing` |
| 3 | Approved query validation | `test_query_with_edge_whitespace_is_refused_not_repaired` (parametrised); `test_query_with_edge_whitespace_never_reaches_the_index`; `test_retrieve_revalidates_a_request_altered_after_construction` |
| 4 | 500-candidate boundary | `test_valid_chunk_ranked_within_the_candidate_bound_is_returned`; `test_valid_chunk_ranked_beyond_the_candidate_bound_is_not_returned` |
| 5 | No displacement by post-filtering defects | Unauthorised and other-project chunks are excluded before scoring by the index. Superseded hits displaced current evidence in the lookup after the cap (review 3, B1); fixed by withholding them before the cap. The window still counts unavailable and superseded candidates (item 4) |
| 6 | Malformed `allowed_collections` fails closed | `test_lookup_refuses_a_collections_value_that_is_not_a_list_or_tuple` (4 cases); `test_empty_query_lookup_refuses_a_malformed_collections_value` |
| 7 | Ranked results never exceed `top_k` | `test_evidence_is_capped_at_top_k`. The enumeration path is uncapped by design (item 2) |
| 8 | Citation integrity, source versions, availability, provenance | Existing citation, contract and security tests; `citation_is_intact` on every hit |
| 9 | Retrieval-failure and unavailable states distinct | `test_enumerate_and_retrieve_agree_on_an_unavailable_only_corpus`; `test_all_denied_*`; `failed` vs `no_match` per the contracts document |
| 10 | Documentation consistent with behaviour | Corrected for the review-3 findings (section 6.5); re-verified at the next freeze |

Gate: pytest 1132 passed (AI-1 and AI-S01 388; AI-S02 573; AI-S03 171, working tree at that time); ruff check and format clean; mypy `src` (55 files)
and `--strict src tests` (98 files) clean with the pinned binary.

### 6.5 Independent review 3 (FAIL, then fixed)

Reviewer: a fresh read-only agent. Frozen candidate verified against a SHA-256 manifest (25 files).
Baseline: pytest 1127 passed; ruff check and format clean; strict mypy clean (pinned 1.11.2). The reviewer found no
unauthorised, cross-project, or metadata leak.

| ID | Severity | Finding | Disposition | Test |
|---|---|---|---|---|
| B1 | Blocking | The lookup took its `top_k` ten slots from superseded hits, then dropped them. Current evidence was lost | Fixed. `retrieve(..., current_only=True)` withholds superseded versions before the cap | `test_superseded_hits_do_not_displace_current_evidence_in_the_lookup`; `test_nine_superseded_hits_leave_the_current_evidence_in_the_lookup`; `test_direct_retrieval_still_returns_a_superseded_version_flagged` |
| M1 | Medium | Two versions of one document, neither naming a supersession, were both served as current | Fixed. Refused with `invalid_metadata` ("more than one current version is stored"; qualified by the contract to one project and collection) | `test_two_unflagged_versions_of_one_document_are_withheld_from_the_lookup` |
| L1 | Low | An access-port exception propagated unclassified | Fixed. `access_check_failed`; nothing searched; collections reported as not evaluated | `test_access_port_error_is_classified_and_nothing_is_searched` |
| L2 | Low | Unavailable-only, non-matching query: `no_match` from retrieve, `failed` from enumerate | Documented (contracts section 12). Matching queries agree | Contracts section 12 |
| L3 | Info | The lookup's relevance summary can be 499 characters, because the base model strips the last character's trailing space | Documented; citation unaffected | This section |
| INFO | Info | Document identifiers are unique per project; a duplicate within one project is refused at ingestion, and the same identifier in another project is independent. A query over 500 characters returns `[]` silently from the lookup. A `model_copy` with edge whitespace raises `ValidationError` out of `retrieve` | Documented. The refusal is deliberate and fails closed | Contracts section 12; query validation tests |

Corrections made to this plan and the register: item 5 and item 10 above, and the register rows for directive items 5 and 10.
The claim that unavailable-only queries "both return failed" (section 6.3, claim 6) holds for matching queries only; see L2.

Gate after review-3 fixes: pytest 1132 passed (AI-1 and AI-S01 388; AI-S02 573; AI-S03 171); ruff check and format clean;
mypy `src` and `--strict src tests` clean.

### 6.6 Remediation under WDS formal authorisation (access, sibling versions, whitespace-only query)

WDS confirmed that AI-S03 remains in approved scope and lifted the implementation hold for these fixes only. The
findings are from the focused review of section 6.5 (Medium, Low, Informational).

| ID | Severity | Finding | Remediation | Tests |
|---|---|---|---|---|
| A-1 | Medium | Access fail-open: the port result was tested for truthiness, so a non-bool response granted access | Strict `is True` check (`access.py`). Every other response is denied | `test_faulty_access_response_denies_the_collection_in_ranked_retrieval` (10 responses); `..._in_enumeration`; `..._yields_no_specialist_evidence`; `test_a_true_access_response_still_grants_access` (positive control); `test_access_port_exception_is_not_echoed_in_the_outcome` |
| S-1 | Low | A withdrawn sibling version invalidated an eligible version (over-refusal) | Duplicate-current check counts only available, unsuperseded siblings (`retrieval.py`). Contracts section 12 describes it | `test_withdrawn_sibling_does_not_invalidate_an_eligible_version`; `test_withdrawn_version_does_not_block_an_eligible_current_version`; `test_superseded_sibling_does_not_invalidate_the_eligible_current_version`; `test_two_eligible_unsuperseded_versions_are_still_refused`; `test_withdrawn_sibling_with_a_current_version_is_served_through_the_lookup` |
| W-1 | Info | Whitespace-only query: direct APIs raised out of retrieval, and the lookup behaviour was undocumented | Behaviour kept (reject, never repair). Direct APIs raise `ValidationError` and never call the index; the lookup returns `[]`. The difference is documented in contracts section 12 | `test_whitespace_only_query_raises_a_controlled_error_on_direct_retrieval` (3 cases); `..._on_enumeration` (2); `test_whitespace_only_query_returns_nothing_from_the_lookup_without_searching` |

Confirmed unchanged: superseded handling in the lookup, the cap before withholding, the 500-candidate window and its
threshold tests, all-denied `access_denied`, partial authorisation, malformed `allowed_collections` (fail closed),
`top_k` on the ranked path, citation integrity, and the audit (no text, `not_evaluated` never denied).

Gate: pytest 1177 passed (AI-1 and AI-S01 388; AI-S02 573; AI-S03 216). Ruff check and format clean. Strict mypy clean
over `src` (55 files) and `src tests` (98 files), working tree at that time.

### 6.7 Final QA of the remediation (FAIL, then fixed)

The focused reviewer (fresh, read-only, with the frozen manifest verified) confirmed the three remediations: the strict
`is True` access check (item A-1), the eligible-sibling rule (S-1, mechanics), and the whitespace-only query (W-1). It also
confirmed the regression list. It found one new defect:

| ID | Severity | Finding | Disposition | Test |
|---|---|---|---|---|
| X-1 | Medium | The duplicate-current check looked at every stored version of a document id, across projects and collections. A second project's document could make this project's evidence refused, and the reply revealed a cross-project document id | Fixed. The sibling check is scoped to the same project and collection (`retrieval.py` `_has_other_current_version`) | `test_sibling_stored_for_another_project_does_not_invalidate_this_project_evidence`; `test_sibling_stored_in_another_collection_does_not_invalidate_this_collection_evidence` |

The reviewer's residual risks are recorded and not changed: the empty-query lookup is unbounded by design (AI-1 snapshot);
a refused edge-whitespace query and no match both return `[]` to specialists; the enumeration path scans the whole store;
a chain whose last version is withdrawn could leave an earlier unsuperseded version served as current (reasoned from code,
not executed. Contract reference MISSING: no contract section states this case; see register CH-1). **Severity: Medium. Status: Open, WDS decision required. Register entry CH-1** ([AI_S03_QA_FINDINGS_REGISTER.md](AI_S03_QA_FINDINGS_REGISTER.md), section "Open Medium for WDS decision").

Gate after X-1 and X-2: pytest 1179 passed (AI-1 and AI-S01 388; AI-S02 573; AI-S03 218). Ruff and format clean. Strict mypy clean.

### 6.8 Second focused QA (FAIL on X-2, then fixed)

The second focused reviewer confirmed X-1 for the retrieval paths, the sibling rules within one project and collection,
the strict access check, and the regression list. It found one High defect and one Low item:

| ID | Severity | Finding | Disposition | Test |
|---|---|---|---|---|
| X-2 | High | The document store was keyed by (document, version) with no project. Another project's document with the same identifier and version refused this project's ingestion as a duplicate, and could remove this project's current version from its lookup | Fixed. The store is keyed by (project, document, version); `get` and `versions_of` take the project; the duplicate check and version selection are project-scoped | `test_same_document_id_and_version_in_another_project_does_not_collide`; `test_a_duplicate_version_within_one_project_is_still_refused` |
| W-2 | Low | A whitespace-only query raises `ValidationError` on direct retrieval instead of returning `EMPTY_QUERY` | Not changed. This is the approved W-1 behaviour: reject invalid input with a controlled error, never repair, and never call the index. The lookup returns `[]` | Section 12 of the contracts document; `test_whitespace_only_query_raises_a_controlled_error_on_direct_retrieval` |

Residual risks recorded by the reviewer and not changed: direct retrieval returns superseded versions flagged; withdrawn
or unavailable siblings produce `source_unavailable` notices alongside an `ok` status; the same identifier across two
collections of one project gives two current versions in a combined request (by design); and the 500-candidate window
can hide valid evidence on corpora above that size (documented limit).

Gate after X-2: pytest 1179 passed (AI-1 and AI-S01 388; AI-S02 573; AI-S03 218). Ruff and format clean. Strict mypy clean.

### 6.9 Third focused QA (FAIL on X-3, then fixed)

The third reviewer confirmed the project-keyed store (X-2) for ingestion and for citations, and the within-project rules.
It found a High defect that X-2 did not cover: chunk identifiers were derived from document id, version and position, with
no project. Two projects with the same document id and version therefore produced the same chunk ids, and the index maps
(tokens and vectors, keyed by chunk id) were overwritten. The results for each project then depended on the other
project's text and on ingestion order.

| ID | Severity | Finding | Disposition | Test |
|---|---|---|---|---|
| X-3 | High | Chunk identity omitted the project, so the index mixed two projects' chunks | Fixed. The chunk identifier includes the project (`index.py` `_chunk_id`). `HybridIndex` refuses duplicate chunk identifiers instead of overwriting | `test_same_document_id_and_version_in_two_projects_do_not_affect_each_other_in_the_index` (both ingestion orders); `test_hybrid_index_refuses_duplicate_chunk_identifiers` |
| X-4 | Medium | Evidence identifiers omitted the project, so one identifier could be issued for two projects | Fixed. The evidence identifier includes the project (`retrieval.py` `_evidence_id`) | `test_evidence_identifiers_differ_between_projects_for_the_same_document` |
| X-5 | Low | `DocumentStore.add` is public and performs no approval or scope check | Documented residual risk. Production ingestion goes through `ingest()`, which checks approval and scope. `add` is kept as a test seam; its only production caller is `ingest()` | QA plan, section 6.9 |

Gate after X-3 to X-5 (working tree at that time, with the AI-S02 files staged): pytest 1183 passed (AI-1 and AI-S01 388; AI-S02 573; AI-S03 222). Ruff and format clean. Strict mypy clean.

### 6.10 Fourth focused QA (FAIL) and disposition

The fourth reviewer confirmed X-3, X-4, and the regression list on the RAG path. Its verdict is FAIL, on the items below.

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| Y-1 | Medium | [Superseded by the WDS-approved Y-1 exception; fixed, see section 6.11.] The AI-1 mock evidence lookup (`ai_engine/src/ai_engine/evidence/lookup.py`) keys conflict groups by evidence id alone, and the mock's synthetic ids are fixed strings. Two projects loaded into one mock overwrite each other's groups | Not changed in AI-S03. This file is AI-1 code, outside the AI-S03 change set, and AI-1 files are frozen. [Superseded by the WDS Y-1 exception: the three AI-1 files were corrected under it; see section 6.11.] The RAG path is not affected. **WDS decision required**: change the AI-1 mock, or confirm that it is used only single-project |
| Y-2 | Medium | Superseded versions are withheld only within the 500-candidate window; beyond it, superseded hits can hide current evidence, and beyond the window the result is silent (lookup path: `no_match` for superseded candidates; direct retrieval: superseded versions can displace current ones within `top_k`; `failed` with `source_unavailable` notices for unavailable candidates when no valid candidate is accepted) | Not a new defect: it is the accepted window limit (D-S03-01). The wording that said "before the cap" without qualification was wrong, and is corrected in code comments and in contracts sections 4 and 12 |
| Y-3 | Low | The empty-query lookup returns the full authorised set with no cap | By design (D-S03-02, AI-1 snapshot). Limited to the task's project and allowed collections |

Residual risks recorded by the reviewer: the evidence identifier is a 64-bit truncated SHA-256; conflict groups are
document-level slugs, safe only because RAG outcomes are single-project; the collection registry is keyed by collection id
alone, so a collection id cannot be approved for two projects; the lookup's group map grows without bound; the index is
in-memory and synthetic-scale.

Status: the commit condition (independent PASS with no outstanding blocking findings) is **not met**. Y-1 is outside the
AI-S03 change set and needs a WDS decision. No commit was made.

Gate: pytest 617 passed in commit 097ba44 (AI-1 and AI-S01 388; AI-S03 and Y-1 229; the AI-S02 tests are not in this commit). Ruff and format clean. Strict mypy clean.

### 6.11 Final decisions and the Y-1 correction (WDS final decision)

**Y-1 (approved for remediation, AI-1 exception).** The AI-1 mock evidence lookup (`ai_engine/src/ai_engine/evidence/lookup.py`)
keyed conflict groups by evidence identifier alone. Two projects with a record of the same identifier overwrote each
other's group. Changes:

- The mock stores groups by (project, evidence identifier). `conflict_group_of(evidence_id, *, project_id=None)`
  answers for the given project. Without a project it answers only when the identifier names exactly one record; an
  identifier shared by two projects gets no group rather than a guessed one. The protocol signature gained the keyword,
  which is optional, so existing single-project callers are unchanged.
- Execution passes the run's authoritative project (`specialists/execution.py`). The agent view ignores any project a
  caller supplies. The Shopify agent passes its task's project (`shopify/agent.py`).
- The RAG lookup scopes its groups the same way (`rag/specialist.py`).

Related project-scoping operations reviewed for the same pattern: the authorised map in `execution.py` is pinned to the
task's project; the served-evidence map in `specialists/validation.py` is per run; the RAG evidence identifier includes the
project (finding X-4). No other operation keyed by identifier alone was found.

Regression tests (`tests/test_ai1_y1_conflict_scope.py`, 7 tests): two projects with identical identifiers and different
groups keep their own groups in either ingestion order; a project with no group gets none from another; an identifier
shared by two projects gets no group without a project; an unknown project gets none; single-project behaviour is unchanged;
search still returns only the requested project's record.

**Y-2 (accepted prototype limitation).** The 500-candidate window is retained. Superseded candidates inside the window
are withheld before the cap; superseded candidates competing within the window can displace valid current evidence on direct retrieval. Unavailable candidates consume positions within the 500-candidate window but do not consume final `top_k` output slots. On the specialist lookup path (`current_only`), superseded candidates inside the window are withheld, and the result is `no_match` when nothing else is eligible. On direct retrieval, superseded versions are returned flagged `superseded` and can occupy `top_k` slots, so a current version can be displaced; a caller that needs only current evidence must use the lookup path or filter the flags. Unavailable candidates inside the window give `failed` with `source_unavailable` notices when no valid candidate is accepted; if a valid candidate is accepted, the result is `ok` with a `source_unavailable` notice. No evidence is invented on either path. No unauthorised
information is disclosed: the refusal reasons are fixed and name no collection. The displacement-boundary tests
(499 returned, 500 not) continue to pass. Documented in contracts sections 4 and 12.

**Y-3 (accepted by design).** The empty-query specialist lookup keeps the D-S03-02 complete-snapshot contract and is not
capped at 500. It returns only records in the authorised project and collections, and malformed input returns nothing.
