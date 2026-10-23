# AI-S03 QA Findings Register

Scope: AI-S03 RAG and evidence retrieval, isolated and non-production. Every finding from every independent review
is recorded here with its disposition. Status values: **Fixed** (regression test added), **Decided** (WDS decision
recorded), **Documented limit** (accepted prototype limit, stated in the contracts document), **Open** (not closed).

## Independent review 1 (FAIL, nine findings)

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| F1 | High | A chunk relabelled to an allowed collection surfaced a stored document from an unallowed collection | Fixed | `test_relabelled_chunk_cannot_surface_a_document_from_an_unallowed_collection` |
| F2 | Medium | Empty-query enumeration skipped unavailable documents without a record | Fixed | `test_enumeration_classifies_an_unavailable_document` |
| F3 | Medium | A non-sequence index result raised instead of being classified | Fixed | `test_malformed_index_container_is_classified_and_audited` |
| F4 | Medium | Base model stripped edge whitespace silently; chunk spans could end in spaces | Fixed | Whitespace tests in `test_ai_s03_review_fixes.py` |
| F5 | Low | Cross-project approval gave a distinct refusal (existence oracle) | Fixed | `test_other_project_approval_is_indistinguishable_from_no_approval` |
| F6 | Low | "Byte-exact" wording for citations | Fixed | `test_citation_offsets_are_character_offsets_not_bytes` |
| F7 | Low | Same root as F4 | Fixed with F4 | As F4 |
| F8 | Low | Lookup raised on an invalid request | Fixed | `test_lookup_refuses_an_overlong_query_without_raising_or_searching` |
| F9 | Low | Stored document kind could mismatch its collection scope | Fixed | `test_stored_document_with_a_scope_that_does_not_match_its_kind_is_refused` |

## Independent review 2 (FAIL, blocking defects and minor items)

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| R2-1 | Blocking | Unavailable and unauthorised candidates consumed the `top_k` budget before validation | Fixed (window of 500 retained by WDS decision D-S03-01) | `test_withdrawn_chunks_do_not_consume_the_top_k_budget` |
| R2-2 | Blocking | Non-iterable `allowed_collections` raised `TypeError` out of the lookup | Fixed | `test_lookup_refuses_a_non_iterable_collections_value_without_raising` |
| R2-3 | Low | Evidence was not capped at `top_k` | Fixed | `test_evidence_is_capped_at_top_k` |
| R2-4 | Low | Empty-query audit labelled requested collections as denied | Fixed (D-S03-05: `not_evaluated_collections`) | `test_empty_query_audit_reports_collections_as_not_evaluated_not_denied` |
| R2-5 | Low | `RetrievalRequest.query` silently stripped | Fixed (D-S03-04: refused) | `test_query_with_edge_whitespace_is_refused_not_repaired` |
| R2-6 | Info | Audit comment claimed the cross-project distinction is kept | Fixed (comment corrected) | Contracts document; audit lists both as denied |

## Final independent re-review (FAIL, claims 1 to 8)

| ID | Claim | Result | Disposition | Test or record |
|---|---|---|---|---|
| FR-1 | Valid evidence not displaced by unavailable or unauthorised candidates | Not confirmed at the window | Documented limit (D-S03-01). Threshold stated in the contracts document, section 4 | `test_valid_chunk_ranked_within_the_candidate_bound_is_returned`; `test_valid_chunk_ranked_beyond_the_candidate_bound_is_not_returned` |
| FR-2 | Malformed `allowed_collections` fails closed | Confirmed, with exceptions | Fixed. Only list or tuple accepted; generators, sets, dicts and strings refused | `test_lookup_refuses_a_collections_value_that_is_not_a_list_or_tuple` |
| FR-3 | Returned evidence never exceeds `top_k` | Retrieve confirmed. Enumeration uncapped | Ranked path capped. Enumeration uncapped by design (D-S03-02) | `test_evidence_is_capped_at_top_k`; contracts section 12 |
| FR-4 | Query validation cannot be bypassed | Bypassed via `model_copy` and `model_construct` | Fixed. Request re-validated on entry to `retrieve` and `enumerate_authorised` | `test_retrieve_revalidates_a_request_altered_after_construction` |
| FR-5 | Audit classifications correct | Confirmed | No change | Audit tests in `test_ai_s03_retrieval.py` and `test_ai_s03_security.py` |
| FR-6a | Superseded version not served as current via the lookup | Confirmed | Fixed. The lookup withholds superseded versions | `test_lookup_withholds_a_superseded_version_as_current_evidence` |
| FR-6b | Unavailable-only corpus classified differently by enumerate and retrieve | Confirmed | Fixed. Both return `failed` | `test_enumerate_and_retrieve_agree_on_an_unavailable_only_corpus` |
| FR-7 | Cross-project isolation | Confirmed | No change. Document-subject cross-project branch reachable only from a faulty index | Security tests |
| FR-8 | Metadata disclosure | Confirmed | No change. Failure details are fixed strings; subjects are identifiers | Security tests |
| FR-9 | Dict input accepted as its keys | Confirmed | Fixed (refused with the list or tuple rule) | `test_lookup_refuses_a_collections_value_that_is_not_a_list_or_tuple` |
| FR-10 | All-denied returns FAILED while partly denied returns NO_MATCH | Inconsistent with the authorisation rule as worded | Decided (D-S03-03). All-denied is `failed` with one `access_denied` reason | `test_all_denied_retrieval_is_failed_with_one_sanitized_reason`; `test_all_denied_enumeration_is_failed_with_one_sanitized_reason` |
| FR-11 | Audit log and lookup group map grow without bound | Info | Documented limit (prototype, in-memory) | Implementation report |
| FR-12 | Query digests are unsalted SHA-256 | Info | Documented limit. Digests identify a query, they do not hide it | Implementation report |

## Directive verification items (WDS final execution directive)

| # | Item | Result | Evidence |
|---|---|---|---|
| 1 | Previously blocking defects | Fixed | R2-1, R2-2, FR-6a, FR-6b |
| 2 | Empty-query complete-snapshot boundary | Verified | `test_empty_query_snapshot_contains_only_authorised_project_and_collection_records`; `test_empty_query_lookup_without_authorisation_returns_nothing` |
| 3 | Query validation | Verified | R2-5, FR-4 |
| 4 | 500-candidate boundary tests | Verified | FR-1 |
| 5 | No displacement by preventable post-filtering defects | Verified after review 3. Unauthorised and other-project chunks are excluded before scoring. Superseded hits displaced current evidence in the lookup (B1), now fixed | QA plan, section 6.4, item 5 and section 6.5 |
| 6 | Malformed `allowed_collections` fails closed | Verified | FR-2, FR-9 |
| 7 | Ranked results never exceed `top_k` | Verified | R2-3 |
| 8 | Citation integrity, source versions, availability, provenance | Verified | Existing citation and security tests |
| 9 | Retrieval-failure and unavailable states distinct | Verified | FR-6b; all-denied test; `failed` vs `no_match` |
| 10 | Documentation consistent with behaviour | Corrected after review 3 (QA plan, section 6.5). Re-verified at the next freeze | Contracts section 12 |

## Independent review 3 (FAIL, then fixed)

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| B1 | Blocking | Superseded hits displaced current evidence in the lookup after the cap | Fixed | `test_superseded_hits_do_not_displace_current_evidence_in_the_lookup` |
| M1 | Medium | Two unflagged versions of one document both served as current | Fixed (rule qualified in the contract to one project and collection) | `test_two_unflagged_versions_of_one_document_are_withheld_from_the_lookup` |
| L1 | Low | Access-port exception unclassified | Fixed | `test_access_port_error_is_classified_and_nothing_is_searched` |
| L2 | Low | Unavailable-only non-matching query: `no_match` vs `failed` | Documented | Contracts section 12 |
| L3 | Info | Relevance summary can be one character short | Documented | QA plan, section 6.5 |
| INFO | Info | Global document identifiers; silent `[]` for over-long lookup queries; `model_copy` edge-whitespace raises | Documented | Contracts section 12 |

## Remediation (WDS formal authorisation)

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| A-1 | Medium | Access fail-open on a non-bool port response | Fixed (strict `is True`) | `test_faulty_access_response_denies_the_collection_in_ranked_retrieval` and related |
| S-1 | Low | Withdrawn sibling invalidated an eligible version | Fixed (eligible siblings only); documented | `test_withdrawn_sibling_does_not_invalidate_an_eligible_version` and related |
| W-1 | Info | Whitespace-only query behaviour differs between direct APIs and the lookup | Documented as intentional; behaviour kept | `test_whitespace_only_query_raises_a_controlled_error_on_direct_retrieval` and related |

## Final QA of the remediation

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| X-1 | Medium | Duplicate-current check spanned projects and collections (cross-project interference) | Fixed (scoped to project and collection) | `test_sibling_stored_for_another_project_does_not_invalidate_this_project_evidence` and related |
| R-1 | Info | Empty-query lookup unbounded; `[]` ambiguous between refused and no match; enumeration scans the store | Documented residual risks | QA plan, section 6.7 |

## Second focused QA

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| X-2 | High | Document store keyed without project: cross-project collision on identifier and version | Fixed (store keyed by project, document, version) | `test_same_document_id_and_version_in_another_project_does_not_collide` and related |
| W-2 | Low | Whitespace-only query raises on direct retrieval | Not changed: approved W-1 behaviour | QA plan, section 6.8; contracts section 12 |

## Third focused QA

| ID | Severity | Finding | Disposition | Test or record |
|---|---|---|---|---|
| X-3 | High | Chunk identity omitted the project; the index mixed two projects' chunks | Fixed | `test_same_document_id_and_version_in_two_projects_do_not_affect_each_other_in_the_index`; `test_hybrid_index_refuses_duplicate_chunk_identifiers` |
| X-4 | Medium | Evidence identifiers omitted the project | Fixed | `test_evidence_identifiers_differ_between_projects_for_the_same_document` |
| X-5 | Low | DocumentStore.add performs no approval check | Documented residual risk; production path is ingest() | QA plan, section 6.9 |

## Fourth focused QA

| ID | Severity | Finding | Disposition | Record |
|---|---|---|---|---|
| Y-1 | Medium | AI-1 mock lookup keys conflict groups by evidence id; two projects in one mock overwrite each other | Not changed (AI-1 code, outside AI-S03). WDS decision required. [Superseded by the Y-1 entry below: fixed under the WDS-approved exception.] | QA plan, section 6.10 |
| Y-2 | Medium | Superseded withholding holds only within the 500-candidate window | Accepted limit; wording corrected | Contracts sections 4 and 12 |
| Y-3 | Low | Empty-query lookup uncapped | By design (D-S03-02) | QA plan, section 6.10 |

## WDS final decision: Y-1, Y-2, Y-3

| ID | Severity | Finding | Disposition | Record |
|---|---|---|---|---|
| Y-1 | Medium | AI-1 mock lookup keyed conflict groups by evidence identifier alone; two projects overwrote each other | Fixed under the WDS-approved AI-1 exception: groups keyed by project and identifier; execution and the Shopify agent pass the authoritative project | QA plan, section 6.11; `tests/test_ai1_y1_conflict_scope.py` |
| Y-2 | Medium | Superseded candidates competing within the 500-candidate window can displace valid current evidence on direct retrieval; unavailable candidates consume positions within the window but do not consume final `top_k` output slots | Accepted prototype limitation (WDS). Results report `no_match` or `failed`; no evidence invented; no disclosure | Contracts sections 4 and 12; QA plan, section 6.11 |
| Y-3 | Low | Empty-query lookup is uncapped | Accepted by design (D-S03-02) | QA plan, section 6.11 |

## Open Medium for WDS decision

| ID | Severity | Finding | Status | Record |
|---|---|---|---|---|
| CH-1 | Medium | A chain whose last version is withdrawn could leave an earlier unsuperseded version served as current. Reasoned from the code, not executed: the withdrawn last version does not count as a sibling, so the earlier version is the only eligible one | Open, WDS decision required. Not fixed | QA plan, section 6.7, line 310. **Contract reference MISSING:** no contract section states the withdrawn-last-version chain case. The nearest text, the version-eligibility paragraph in contracts section 12, covers withdrawn siblings only |

## Open items

| ID | Item | Owner |
|---|---|---|
| OPEN-1 | Independent QA PASS on the frozen candidate | Independent reviewer, then WDS |
| OPEN-2 | Foundation operator identity, trusted project status, permission service, persistence | Foundation |
| OPEN-3 | Real collection approvals (synthetic approvals only today) | WDS governance |
| OPEN-4 | Governance rulings A-4, C-15 and governance position 1 | WDS governance |
| OPEN-5 | Measured retrieval bound for any real dataset | WDS, before any real corpus |
| OPEN-6 | Whether the specialist empty-query snapshot is capped | Out of AI-S03 scope; requires an AI-1 change |
