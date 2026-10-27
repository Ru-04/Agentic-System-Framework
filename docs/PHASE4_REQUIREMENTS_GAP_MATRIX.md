# Phase 4 requirements gap matrix (parse robustness)

Base: `46e0e14` (committed Phase 2 state). Branch: `feature/foundation-phase-4`. Approved basis:
`docs/INCREMENT_3_HARDENING_PLAN.md`, Phase 4 section (H-30 to H-35) and its decision register (H-DEC-3 to
H-DEC-6). Starting commit of this sprint: `85315a1`.

Status values: **done** (implemented and tested), **partial** (implemented with a stated gap), **open**,
**decision** (blocked on a WDS decision; a proposed default is implemented and labelled), **dependency** (needs
Phase 2 or Phase 3). This matrix does not accept any item. Acceptance is for independent QA.

## Approved items

| ID | Requirement (plan text, summarised) | Implementation | Test evidence | Status |
|---|---|---|---|---|
| H-30 | One version's failure cannot corrupt or roll back another version; every failure is classified and audited | `parse_service.parse_version` catches every parser and write exception; each path goes through `_fail` (stable class, `source.parse.failed` audit). Isolation (H-32) adds a crash and timeout class per version. | `test_a_segment_write_failure_of_any_kind_fails_only_that_version`; `test_a_parser_exception_fails_only_that_version_and_writes_no_segments`; `test_a_crashing_child_fails_with_parser_crash_and_the_parent_survives` (unit); reparse demonstration (step 3, step 5) | done |
| H-31 | Limits on input size, PDF pages, PDF per-page stream size, DOCX and archive expansion, DOCX paragraph and table-cell count, segments per version, characters per segment, execution time, memory where the platform allows | `intake/limits.py` (proposed values, H-DEC-3). Input size before parse; ZIP size and ratio; PDF page count and stream size; DOCX element count; segment count and length before any write; wall-clock timeout (H-32); address-space cap on POSIX (H-32) | `test_an_oversized_input...`; `test_a_segment_count_breach...`; `test_a_segment_length_breach...`; `test_a_docx_whose_uncompressed...`; `test_a_pdf_with_more_pages...`; `test_a_docx_with_more_elements...`; `test_a_pdf_page_stream_over...`; corpus `oversized-*` cases | partial: numeric values await H-DEC-3. The memory cap is not enforced on Windows (H-DEC-4, see the limits register). |
| H-32 | Isolated parser execution: timeout shorter than the lease, crash containment, resource limits, child cleanup, Windows behaviour, controlled classification, parent survival, no unnecessary parser database privilege | `intake/isolation.py` (child process; allowlisted environment with no database URL; timeout; output cap; POSIX memory cap; `CREATE_NO_WINDOW` on Windows). `intake/parser_child.py` imports only the parsers. Default runner of `parse_version`. | `tests/unit/test_parse_isolation.py` (26 tests, including crash, hang, output cap, environment allowlist, fault switch gated by `WEBDESK_ENV=test`); `test_the_isolated_result_equals_the_in_process_result` for every parseable corpus case | done for the Windows timeout and crash path. partial: on Windows the memory cap is not enforced (H-DEC-4). Child cleanup relies on `subprocess.run` kill-and-wait; no grandchild process exists in any parser. |
| H-33 | Complete locators: EML Message-ID as provenance and offsets; TXT character offsets and `\n`-only splitting; DOCX table cells; PDF image-only page is `partial`; HTML-only email per H-DEC-6 | TXT: `txt_line_range` with `char_start`/`char_end`, split on `\n` only (U+2028 and U+0085 stay in the line). PDF: `_has_image` flags an image-only page as `pdf_page:N`. DOCX: table cells as `docx_paragraph` with `table_index`, `row`, `cell` (H-DEC-5 proposed default). EML: `message_id` on each `eml_part` locator. HTML-only body: flagged `eml_part:body_html_only` (H-DEC-6 proposed default). | `test_txt_offsets_recover_each_segment_exactly...`; `test_eml_segments_carry_the_message_id...`; `test_an_html_only_eml_body...`; `test_docx_table_cells_are_segments...`; `test_an_image_only_pdf_page...`; `test_a_docx_table_cell_is_persisted_with_its_table_locator` (real PostgreSQL); corpus `partial-*` cases | partial: EML character offsets are not implemented. The plan does not say offsets into what (raw message or extracted part); this is a question for WDS. Decision pending on H-DEC-5 and H-DEC-6 (proposed defaults in use). No migration was added: the locator CHECK in migration 0007 already admits these keys, and the plan's `0013` does not exist on this branch. |
| H-34 | `parse_error` holds `{"class": "partial", "flagged_regions": [...]}`; partial results retrieved consistently; partial never reported as complete; behaviour on failure, retry, reparse | `parse_service.parse_version` persists flagged regions for every `partial` result. A partial version is not reparseable (`not_failed`). | `test_a_partial_extraction_records_the_regions_it_could_not_extract`; `test_a_partial_version_cannot_be_reparsed_and_keeps_its_flagged_regions` (real PostgreSQL); demonstration step 4 | done |
| H-35 | Atomicity tests for each partial and failed path, on committed rows with the real file | Rolled-back integration tests (real file, real persistence) and committed-row concurrency tests | `tests/integration/test_parse_hardening.py`, `test_parse_reparse.py` (rolled back); `tests/committed/test_parse_concurrency.py` (committed, two connections) | partial: the committed-row variant covers the race and reparse paths, not every partial and failed path. Remaining paths are covered only in rolled-back form. |

## Reparse and concurrency (sprint section)

| Item | Status | Evidence |
|---|---|---|
| Reparse authorization and operation proofs | done | `test_a_failed_version_is_reparsed_once...`; demonstration step 2 (analyst proof refused) |
| Duplicate reparse request handling | done | `test_a_second_reparse_of_the_same_version_is_refused_as_not_failed` (denial audited) |
| Idempotency: a repeated parse of a succeeded version adds nothing | done | `test_a_parse_of_a_version_that_is_not_pending_is_refused_and_adds_nothing` |
| Concurrent parse and parse of one version | done | `test_two_parses_of_one_pending_version_write_its_segments_exactly_once` (4 rounds, real PostgreSQL) |
| Concurrent parse and reparse | done | `test_a_reparse_racing_a_parse_leaves_one_consistent_state...` (4 rounds) |
| Stale result rejection (revision) | done | `test_a_reparse_with_a_stale_source_revision...`; `test_a_stale_reparse_loses_the_race...`; demonstration step 8 |
| Rollback and retry | done | `test_a_rolled_back_segment_write_leaves_no_residue_for_the_retry` |
| Version-specific segment correctness | done | `test_segments_belong_to_their_own_version...` |
| Durable denial and error audit | done | `source.reparse.denied` rows asserted (`not_failed`, `revision_conflict`); `source.parse.failed` in the demonstration trail |
| Replayed proof | done | `test_a_reparse_proof_is_spent_by_its_first_accepted_reparse` in `tests/integration/test_gap_closure.py`; demonstration step 8 |

## Sprint areas

| Area | Status | Note |
|---|---|---|
| A. Formats, identification, empty and malformed input | partial | Unsupported MIME refused; corrupt structures classified; empty and corrupt cases in the corpus |
| B. Source-version correctness, immutable versions, stale parses | done for the tests listed above | Parse refuses non-pending and quarantined versions |
| C. Reparse correctness, concurrency, rollback | done | See the table above |
| D. Security and classification | existing | Quarantine refused at the database (corpus `quarantined-*`, existing suite). No scanner is invented. |
| E. Workflow integration with Phase 3 | dependency | The intake job runs `parse_version`, which now uses the isolated runner. Phase 3 durable execution is not merged into this branch. |
| Synthetic corpus | done | `tests/support/parse_corpus.py`, pinned in `tests/support/parse_corpus_manifest.json`; inventory in `docs/PHASE4_SYNTHETIC_CORPUS.md` |
| Synthetic demonstration | done | `tests/committed/test_parse_demonstration.py`; output in `docs/PHASE4_DEMONSTRATION_OUTPUT.md` |

## Dependencies

- Phase 3 (`feature/foundation-phase-3`, committed `e9d888a`): durable execution. Not merged here. See
  `PHASE4_DEPENDENCY_REGISTER.md`.
- Phase 2 remediation (uncommitted in its worktree): migrations `0044` and `0045`. Not used here.
- WDS decisions: H-DEC-3 (numeric limits), H-DEC-4 (Windows memory cap), H-DEC-5 (DOCX locator fields), H-DEC-6
  (HTML-only email), and a new question on EML offsets (see H-33).
