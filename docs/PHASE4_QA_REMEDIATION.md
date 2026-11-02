# Phase 4 QA remediation (2026-10-28)

This records the remediation of the independent QA assessment against the committed baseline `05dbdca`. The
remediation commit is `8d5b039`. The docs commit that adds this file follows it. This is engineering remediation evidence.
It is not formal WDS acceptance, and it does not replace the independent QA re-test.

## 1. Disposition of the QA findings

| ID | Severity | Finding | Disposition | Evidence |
|---|---|---|---|---|
| QA-01 | BLOCKER | Zero-text image-only PDF returned `partial` (spec requires `unsupported`) | **Fixed.** Zero segments is `unsupported` | `test_parse_defects.py::test_d1_an_image_only_pdf_with_no_text_is_unsupported…`; committed `test_a_committed_image_only_document_is_unsupported…` |
| QA-02 | BLOCKER (governance) | Zero-segment `partial` conflicted with the approved `partial` definition | **Fixed per WDS ruling.** `partial` requires a committed segment and a flagged region. Regions for zero-segment results are `unsupported` metadata | `test_partial_needs_at_least_one_committed_segment…`; `test_persisted_outcome_detail…`; committed D1 and image-only tests. Ruling recorded as `WDS-QA02-RULING-2026-10-28` (approver identity open) |
| QA-03 | MAJOR | EML (and TXT) offset keys differed from the schema names | **Fixed.** `start_offset` and `end_offset` on `eml_part` and `txt_line_range` | `test_eml_locators_use_the_schema_names…`; `test_eml_offsets_are_relative_to_the_nfc_normalized_part_text`; `test_eml_zero_length_parts…` |
| QA-04 | MAJOR | Parser input limit 25 MiB against the 20 MiB upload contract | **Fixed.** Parser limit is `storage.MAX_BYTES` (20 MiB). Upload and parser share one unit and boundary | `test_the_parser_input_limit_is_the_approved_upload_maximum…`; `test_upload_admits_exactly_the_maximum…`; committed `test_an_input_exactly_at_the_upload_maximum…`, `test_the_database_refuses…`, `test_an_upload_one_byte_above…` |
| QA-05 | MAJOR (suspected) | Object streams expand before limits apply | **Reproduced; mitigated, not fully contained.** Decoded size is bounded before any reader opens the file. Windows memory is not capped (H-DEC-4) | `test_d4_an_object_stream_that_expands…`; `test_d4_a_cross_reference_stream…`; probe evidence in §4 |
| QA-06 | MINOR | Text in nested form XObjects is not followed and not flagged | **Open, documented residual.** Not fixed in this remediation | `_direct_forms` does not recurse. Flagged as a known gap in §5 |
| QA-07 | MINOR | 120 s lease cited from Phase 3 material not on this branch | **Documentation corrected.** Ordering is unverified. Integration test required | `limits.py` docstring; `PHASE4_DEPENDENCY_REGISTER.md`; §6 |
| QA-08 | INFORMATIONAL | Plan status overstated approval | **Corrected.** Plan status line and register wording state the relayed, incomplete provenance | `docs/INCREMENT_3_HARDENING_PLAN.md` line 3; register amendments |
| D1 | (re-test FAIL) | Lost flag and over-applied partial | **Fixed** (see QA-01 and QA-02) | as above |
| D2 | (re-test PASS) | Declared sizes trusted | **Unchanged, passing.** Actual bytes counted. Declared mismatch refused | `test_d2_*` |
| D3 | (re-test PASS with QA-02 caveat) | Nested tables | **Unchanged.** Flagged; zero-text nested-only result is now `unsupported` | `test_d3_*` |
| D4 | (re-test PARTIAL) | PDF expansion bounded per page only; form text unflagged | **Partially fixed.** File-level expansion bound added; form text flags its page; nested forms open (QA-06); Windows memory not contained | `test_d4_*` |

Omitted finding IDs from the full report: QA-06 (nested form XObjects) and QA-07 are listed above. No other IDs were
given in the report.

## 2. Parser state transitions (committed behaviour)

| Input | Result | Persisted detail | Test |
|---|---|---|---|
| PDF, all pages readable text | `succeeded` | none | `test_a_fully_valid_extraction…` |
| PDF, text page and image-only page | `partial` (1 segment, flag `pdf_page:2`) | `{"class":"partial","flagged_regions":[…]}` | `test_partial_needs…`; committed partial test |
| PDF, all pages image-only | `unsupported` (0 segments) | `{"class":"unsupported","unextractable_regions":["pdf_page:1"]}` | committed image-only test |
| HTML-only EML with a subject | `partial` (subject segment, flag) | partial detail | `test_an_html_only_email_with_a_subject…` |
| HTML-only EML with no subject | `unsupported` (0 segments) | unsupported detail | `test_d1_an_html_only_email_without_subject…`; committed D1 test |
| DOCX, text plus nested table | `partial` | partial detail | `test_d3_a_nested_table…` |
| DOCX, nested table only | `unsupported` | unsupported detail | `test_d3_a_nested_table_with_no_other_text…` |
| TXT, valid | `succeeded` | none | committed success test |
| TXT, one 20 MiB line | `failed` `segment_length_limit`, 0 segments | error class | committed boundary test |
| PDF, corrupt | `failed` `corrupt_structure` | error class | `test_a_corrupt_file…` |
| PDF, encrypted | upload refused (422) | — | corpus `restricted-pdf-encrypted` |
| PDF, LZW stream | `failed` `pdf_filter_unsupported` (file-level) | error class | `test_d4_an_lzw_stream…` |
| PDF, object or cross-reference stream expanding to 60 MiB | `failed` `archive_ratio_limit` | error class | `test_d4_an_object_stream…`; `test_d4_a_cross_reference_stream…` |
| Upload of 20 MiB + 1 byte | refused at admission, 413 | none | `test_an_upload_one_byte_above…`; `test_upload_admits…` |
| Version above 20 MiB reaching the database | refused, 409 `database_refused` | none | `test_the_database_refuses…` |

Reparse rule (EVAL-F14): only a `failed` version can be reparsed. A `partial` or `unsupported` version is refused
with `not_failed`. Tested by `test_a_committed_image_only_document_is_unsupported…` (committed) and
`test_a_committed_partial_version_cannot_be_parsed_again` (committed).

## 3. EML offsets

- `eml_part` locators carry `start_offset` and `end_offset`. Offsets are zero-based and end-exclusive, in code points,
  relative to the normalized part text (NFC, surrounding whitespace removed).
- Subject and body each carry the `message_id` when present. Zero-length parts produce no segment, so no zero-length
  locator is ever written.
- Database locator CHECK (migration 0007) requires the `eml_part` key and admits the offset keys.
- Read compatibility: no product code outside the parser reads the offset keys (the demonstration test does, by SQL). The AI read
  contract (v1) reads segments through their stored locators and passed unchanged (28 tests).

## 4. Resource-limit evidence (QA-04 and QA-05)

Synthetic probes, run on the baseline `05dbdca` and then on `8d5b039`. Each file is generated in memory. Peaks are
`tracemalloc` peaks in the parsing process, not total process memory.

| Probe | File size | Baseline result | After remediation |
|---|---|---|---|
| Object stream expanding to 60 MiB | 61 611 bytes | expanded fully, peak 137.4 MiB, 7.56 s, then `unsupported` | `archive_ratio_limit`, peak 11.9 MiB, 0.01 s |
| Cross-reference stream expanding to 60 MiB | 61 577 bytes | expanded fully, peak 137.4 MiB, 0.18 s, then `unsupported` | `archive_ratio_limit` (test) |
| Page content of 12 MiB spaces | about 12 KB | fully decoded before the 10 MiB check | `archive_ratio_limit` before decoding |
| Page content of 11 MiB incompressible bytes | about 11 MiB | refused at per-page limit | `pdf_stream_limit` (unchanged) |

Limits in force: input 20 MiB (`limits.MAX_INPUT_BYTES`, the upload maximum); PDF decoded expansion 100 MiB total with
ratio 100 to file size; per-page content and direct form stream 10 MiB; child timeout 30 s; child output 32 MiB.

**Classification of QA-05:**
- *Reproduced defect:* yes, on the baseline.
- *Corrected in scope:* decoded size is bounded before any PDF reader opens the file.
- *Residual, not contained:* on Windows the parser child has no memory cap (H-DEC-4). The bound above limits decoded
  size, not process memory. Production use needs a separate containment decision.
- *Residual, not contained:* streams that pypdf decodes and that are not zlib-coded are refused by name only for LZW and
  RunLength. Other non-zlib filters on object streams are not bounded by this pass.

## 5. Known open residuals

- QA-06: text in nested form XObjects is flagged, not extracted (Option B). An image in a nested form flags an image-only
  page (F-1, section 11). Images on pages that have text are not flagged (section 11).
- QA-05 (Windows): no memory cap in the child on Windows (H-DEC-4, production blocker).
- TXT and EML offset values are per the approved schema. Any dispute on offset basis belongs to WDS.

## 6. Phase 2/3 integration dependencies (not completed)

- Phase 3 lease: the 120 s figure is not on this branch. The 30 s parser timeout must be confirmed below the lease when
  Phase 3 merges. Integration test: a parse that approaches the timeout while a job lease is held.
- Migrations: Phase 2 `0044`/`0045` and Phase 3 `0050`/`0051` are not on this branch. Head here is `0043`. A merge needs
  down-revision reconciliation.
- Reparse under Phase 3 durable execution is untested here.

## 7. Governance (see `docs/GOVERNANCE_DECISION_REGISTER.md`)

- `WDS-QA02-RULING-2026-10-28`: recorded from the relayed ruling. Approver identity and approval date as WDS records them
  are **not recorded**.
- `P4-GOV-2026-10-28`: amended for the offset names, the 20 MiB input limit, the PDF expansion application of H-31, and
  the H-DEC-6 consequence.
- Plan status corrected (QA-08).

## 8. Verification (dedicated Phase 4 cluster, `webdesk-p4-postgres`, `127.0.0.1:55434`, PostgreSQL 16.4)

Code commit tested: `8d5b039`. A docstring-only change to `src/webdesk/intake/limits.py` (lease wording, QA-07) was made
after the run started and is included in the docs commit. It changes no behaviour.

| # | Step | Result | Exit |
|---|---|---|---|
| 01 | Focused H-30 to H-35 (defects, intake, isolation, hardening, reparse, intake DB) | 118 passed | 0 |
| 02 | Committed-row outcomes (success, partial, unsupported, failed, neighbour, rollback, stale, reparse, boundary) | 13 passed | 0 |
| 03 | Concurrency and reparse | 3 passed | 0 |
| 04 | Crash, hang, output cap (subprocess) | 3 passed, 23 deselected | 0 |
| 05 | Corpus manifest (CORPUS_VERSION 2) | 2 passed | 0 |
| 06 | Full Foundation regression | **759 passed**, 1 warning | 0 |
| 07 | AI Read v1 compatibility | 28 passed | 0 |
| 08 | Restricted-login privilege audit | 34 passed | 0 |
| 09 | Migration and catalog (upgrade head, downgrade -1, upgrade head; locator CHECK) | head `0043_phase2_review_fixes`; ok | 0 |
| 10 | Synthetic demonstration | 1 passed | 0 |
| 11 | Ruff lint | All checks passed | 0 |
| 12 | Ruff format policy | six documented files only | 1 (by design) |
| 13 | Strict mypy | Success, 60 files | 0 |

Timestamps (+05:30) are in the gate summary, run started 18:11:44. Logs are in the session scratchpad
(`gate/summary.txt`). The format exceptions are `migrations/versions/0017, 0019, 0020, 0040` and
`tests/hardening/test_privilege_hardening.py`, `tests/integration/test_reassessment.py`, listed in
`docs/RUFF_FORMAT_EXCEPTIONS.md`.

During remediation I formatted six exception files by accident with an over-broad `ruff format` run. I reverted them
with `git checkout` before any commit, so no formatting drift is in the history.

## 9. Independent QA re-test handoff

- Reviewed commit: `8d5b039` (plus the docs commit that adds this file).
- Please re-test QA-01 to QA-08, D1 to D4, and the resource probes in §4.
- Known open: QA-06 and the Windows memory residual.
- Governance: approver identity and approval date as WDS records them are not in the repository.
- No WDS acceptance is implied. Production readiness is not claimed.

## 10. Sprint 2026-10-28 (QA-05 and QA-06 blockers)

Starting baseline `8040f9e`. Code commits, in order:

- `d5dc287`: meter every PDF decode at the reader boundary; detect hidden text in nested graphs. Replaces the pre-scan.
- `17c825b`: committed-row tests for nested-form text and admission refusal of an expanding PDF.
- `f03698d`: serialize the process-wide decoder patch; concurrency regression test.

Design and guarantees: `docs/PHASE4_PDF_CONTAINMENT.md`. Provenance: `docs/PHASE4_GOVERNANCE_PROVENANCE_MATRIX.md`.

### 10.1 Findings and disposition

| ID | Disposition | Evidence |
|---|---|---|
| QA-05 bypass A (CR-only stream line) | **Fixed.** Metered at the decoder, so the delimiter does not matter | `test_qa05_bypass_a_cr_only_line_ending_after_stream_is_metered_like_any_other`; `test_qa05_bypass_a_crlf_line_ending_is_metered` |
| QA-05 bypass B (hidden `endstream` in deflate data) | **Fixed** | `test_qa05_bypass_b_a_hidden_endstream_in_compressed_data_is_metered` |
| QA-05 root cause (pre-scan disagrees with reader) | **Fixed.** The boundary moved to the decoder the reader calls | `PHASE4_PDF_CONTAINMENT.md` section 2 |
| QA-05 cross-reference streams, indirect or wrong `/Length`, aggregate expansion, incremental update | **Fixed** and tested | `test_qa05_a_cross_reference_stream_bomb_is_metered`; `test_qa05_an_indirect_or_wrong_length_does_not_change_the_charge`; `test_qa05_aggregate_expansion_across_two_streams_is_refused_by_the_cumulative_budget` |
| QA-05 admission (upload opened PDFs unmetered in the API process) | **Found in this sprint, fixed.** Admission uses the same meter | `test_qa05_a_committed_expanding_pdf_is_refused_at_admission_before_any_parse` (422) |
| QA-05 concurrent admission and parsing (process-wide patch) | **Found in this sprint, fixed** with a lock | `test_qa05_concurrent_admission_and_parsing_never_leak_the_patch` |
| QA-05 child-process containment | **Verified.** The bomb returns a classified refusal from the child; the parent survives | `test_qa05_the_child_process_refuses_the_bomb_and_the_parent_survives` |
| QA-05 Windows process memory | **Not contained.** Stated as a residual, not claimed | `PHASE4_PDF_CONTAINMENT.md` section 6 |
| QA-06 text two levels inside forms | **Fixed (Option B).** Page flagged; zero segments give `unsupported` with metadata | `test_qa06_text_two_levels_inside_forms_is_flagged_not_silently_dropped`; committed `test_qa06_a_committed_nested_form_text_is_unsupported_with_its_region_as_metadata` |
| QA-06 mixed ordinary and nested text | **Fixed.** Partial with the segment and the flag | `test_qa06_mixed_ordinary_text_and_nested_form_text_is_partial_with_the_flag`; committed `test_qa06_a_committed_mixed_page_is_partial…` |
| QA-06 repeated, cyclic, excessive depth, sibling forms | **Fixed.** Visited set, depth 8, 512-object bound; unbounded walks flag the page | `test_qa06_*` (repeated, cyclic, depth, siblings) |
| QA-06 annotations, patterns, Type 3 glyphs (same silent-omission class) | **Fixed** under the same walk | `test_qa06_text_in_an_annotation…`; `test_qa06_text_in_a_type3…`; `test_qa06_a_pattern_stream…` |
| QA-06 negative control (vector-only form) | **Verified not flagged** | `test_qa06_a_vector_only_form_is_not_flagged` |

### 10.2 Preserved previous fixes

- QA-01, QA-02, QA-03, QA-04: unchanged; their tests run in gate steps 01, 02 and 06.
- D1 to D4: unchanged; `test_parse_defects.py` updated only where the boundary moved (the per-stream refusal test now
  asserts the meter's ratio refusal; the LZW page is flagged, not refused as a whole file, because it is never decoded).
- H-30 and H-35: committed outcome and concurrency tests (gate steps 02 and 03) pass.

### 10.3 Gate on the final committed implementation (`f03698d`, dedicated developer cluster, system identifier
`7701663525754380326`, PostgreSQL 16.4)

Run alone; a first attempt overlapped a stopped run on the same namespaces and was discarded. Log directory is the session
scratchpad `gate/` (`summary.txt` and one log per step). Timestamps are +05:30.

| # | Step | Result | Exit | Window |
|---|---|---|---|---|
| 01 | Focused H-30 to H-35 | 118 passed | 0 | 21:38:38 to 21:39:09 |
| 02 | Committed-row outcomes | 16 passed | 0 | 21:39:09 to 21:39:28 |
| 03 | Concurrency and reparse | 3 passed | 0 | 21:39:28 to 21:39:35 |
| 04 | Crash, hang, output cap | 3 passed, 23 deselected | 0 | 21:39:35 to 21:39:41 |
| 05 | Corpus manifest | 2 passed (manifest unchanged; CORPUS_VERSION 2) | 0 | 21:39:41 to 21:39:43 |
| 06 | Full Foundation regression | **787 passed**, 1 warning | 0 | 21:39:43 to 21:46:35 |
| 07 | AI Read v1 | 28 passed | 0 | 21:46:35 to 21:48:25 |
| 08 | Restricted-role privilege audit | 34 passed | 0 | 21:48:25 to 21:48:29 |
| 09 | Migration and catalog | head `0043_phase2_review_fixes`; upgrade, downgrade -1, upgrade; locator CHECK admits offset keys | 0 | 21:48:29 to 21:48:30 |
| 10 | Synthetic demonstration | 1 passed | 0 | 21:48:31 to 21:48:36 |
| 11 | Ruff lint | clean | 0 | 21:48:36 |
| 12 | Ruff format policy | 6 files would reformat: `migrations/versions/0017, 0019, 0020, 0040`, `tests/hardening/test_privilege_hardening.py`, `tests/integration/test_reassessment.py`; these are the documented exceptions | 1 (documented) | 21:48:36 |
| 13 | Strict mypy | clean, 60 files | 0 | 21:48:36 to 21:48:37 |

Teardown state: the developer cluster `webdesk-p4-postgres` (127.0.0.1:55434) is still running and was not modified beyond
the test databases the fixtures create and drop. The QA cluster `webdesk-qa-postgres` (127.0.0.1:55435) from the earlier
independent re-test is still running. Neither was deleted.

### 10.4 Residual limitations

- Windows process memory: not contained (H-DEC-4). Production containment needs a separate decision.
- Admission time: the upload-time open is bounded by the decode budget, not by time. The API process has no separate
  timeout for it.
- Corrupt flate streams are refused, which is stricter than pypdf.
- QA-06 is Option B: nested-form text is flagged, not extracted.
- Governance provenance: see `PHASE4_GOVERNANCE_PROVENANCE_MATRIX.md`. Engineering completion does not resolve it.

### 10.5 Verdict

PHASE 4 ENGINEERING REMEDIATION COMPLETE — READY FOR INDEPENDENT QA. This is engineering authorization only. It is not
independent QA and not WDS acceptance. The author of these changes also wrote the probes and this record; an independent
reviewer must re-test QA-05 and QA-06 from `PHASE4_PDF_CONTAINMENT.md` and `tests/unit/test_pdf_containment.py`.

### 10.6 Final-review remediation (commit f416716, 2026-10-29)

| Finding | Disposition |
|---|---|
| D1 ASCII85 not metered | Fixed: worst-case reservation before decode |
| D2 filter refusal swallowed by reader rebuild | Fixed: file fails with `pdf_filter_unsupported` |
| D3 replacement characters without flag | Fixed: page flagged, segment kept. *Corrected by F-4 (section 11): a segment of only U+FFFD is not committed.* |
| D4 admission in API process, no time bound | Fixed for the enforced bound: admission runs in the timed child. Reviewer's specific xref-loop repro not reproduced by a synthetic fixture |
| D5 upload read unbounded before size check | Partly fixed: read capped at max+1. Framework multipart buffering remains a residual. *Corrected by F-2 (section 11): the source upload's body is bounded before it is buffered.* |

Gate on `f416716` (developer cluster `webdesk-p4-postgres`, system identifier `7701663525754380326`), run after the
cluster was restarted without changing its data: focused 118 passed; committed outcomes 16 passed; concurrency 3 passed;
crash and timeout 3 passed (23 deselected); corpus 2 passed; full regression **793 passed**; AI Read v1 28 passed;
privilege audit 34 passed; migration and catalog ok; demonstration 1 passed; Ruff lint clean; Ruff format exit 1 with
the six documented exception files; strict mypy clean. Earlier invalid runs (cluster down, and an overlapping run) are
not counted.

## 11. Remediation of the independent QA of `178a419` (F-1 to F-6)

Independent QA verdict on `178a419`: FAILED, six confirmed defects (`C:/Users/baps/AppData/Local/Claude-Data/.../phase4-indep-qa-report.md`,
held outside the repository). This section records the engineering remediation. It is not independent QA and not WDS
acceptance. The independent reviewer re-tests the engineering SHA below.

Engineering commits on `feature/foundation-phase-4`, in order:

| Commit | Content |
|---|---|
| `ba710ee` | F-1, F-3, F-4: nested image-only pages, replacement-only text, DOCX text boxes, headers and footers |
| `6c53aa8` | F-2: source upload body bounded before buffering |
| `c42b9d7` | F-5: admission applies the per-page bound; F-6 is in the next commit |
| `ee4d3b9` | F-6: child stdout read with the output cap enforced while the child writes |
| `b604e7b` | Lint and strict typing for the remediation changes (no behaviour change). **Engineering SHA.** |

Each finding has a regression test that failed before its fix and passes after it. Red was observed by running the
new test against the unfixed code, except where noted.

| Finding | Fix | Test (red before fix) | Control (passed before and after) |
|---|---|---|---|
| F-1 (High, QA-06) | The image rule walks forms, patterns and Type 3 fonts, with the text walk's bounds | `test_qa06_an_image_only_form_inside_a_page_flags_the_page_not_a_silent_omission`; `test_qa06_an_image_two_forms_deep_is_flagged_as_well` | `test_qa06_a_vector_only_nested_form_is_still_not_flagged` |
| F-2 (High, D5) | `_bounded_form` in `api/routes.py`: declared length checked, then bytes counted as received; 413 `too_large` past `MAX_UPLOAD_REQUEST_BYTES` | `tests/unit/test_upload_body_bound.py::test_f2_a_body_over_the_limit_is_refused_before_the_rest_of_it_is_read`; `::test_f2_a_declared_length_over_the_limit_is_refused_without_reading_the_body`; `tests/committed/test_http_intake.py::test_f2_an_upload_over_the_request_bound_is_refused_and_no_source_is_created` (200 before, 413 after) | `::test_f2_a_body_within_the_limit_is_parsed_as_before` |
| F-3 (Medium-High, H-33) | `textbox_index` locator for text-box paragraphs; table in a text box flagged; header and footer parts with text flagged; VML fallback not read twice | `test_f3_a_text_box_paragraph_is_a_segment_with_a_textbox_locator`; `test_f3_a_text_box_in_a_table_cell_is_extracted_once`; `test_f3_a_text_box_offered_as_a_fallback_and_a_choice_is_extracted_once`; `test_f3_a_text_box_holding_a_table_is_flagged_not_dropped`; `test_f3_footer_text_is_flagged_as_an_unextracted_region_and_not_extracted`; `test_f3_header_text_is_flagged_as_an_unextracted_region` | `test_f3_an_empty_header_and_footer_are_not_flagged` |
| F-4 (Medium, D3) | A page whose text is only U+FFFD commits no segment; it stays flagged | `test_d3_a_page_whose_only_extracted_text_is_replacement_characters_commits_no_segment` (committed five U+FFFD) | Existing D3 test |
| F-5 (Low-Medium) | `open_pdf_structure` applies the per-page bound; filter refusals and other faults are still admitted | `test_f5_admission_refuses_an_oversized_page_before_any_version_exists` (did not raise before) | `test_f5_admission_does_not_refuse_a_page_the_parser_only_flags_for_its_filter` |
| F-5 (child path) | Same bound through `open_pdf_in_child` | `test_f5_the_admission_child_refuses_an_oversized_page_before_any_version_exists`. **Written after the fix; not observed red separately.** It goes through the same function as the red test above. | — |
| F-6 (Low) | `_run_child` reads stdout while the child runs, at most cap plus one byte, then kills the child | `test_f6_an_endless_child_output_is_stopped_at_the_cap_not_at_the_timeout` (timed out at 20 s before); `test_f6_the_child_is_reaped_when_its_output_is_refused` (timed out before) | `test_f6_output_within_the_cap_is_returned_whole_with_the_exit_code` (failed before only on the changed return type) |

Default decisions that need WDS confirmation are recorded as D-H10 to D-H14 in `PHASE4_DEPENDENCY_REGISTER.md`, and in
section 10 of `PHASE4_PDF_CONTAINMENT.md`.

**Known harness issue, not changed by this remediation.** Two hardening test files read `WEBDESK_HARDENING_OWNER_URL` with
`os.environ[...]` and do not check it. When hardening is not configured they error instead of skipping. They are unchanged
since `178a419`. Step 02 of the gate below shows this.

### 11.1 Developer gate on `b604e7b`

Cluster `webdesk-p4-postgres` (`127.0.0.1:55434`). The container had stopped (exit 255) and was started with
`docker start`. Its volume was not changed. Databases: `webdesk_p4_integration`, `webdesk_p4_hardening`, and the scratch
`webdesk_p4_migcheck`, which was created and dropped by the gate. The gate's 16 rows follow the QA report's G1 to G16 list.
Row 12 (base downgrade) was not run. Full log and summary: the session scratchpad, `gate/summary.txt`.

| # | Step | Result | Exit |
|---|---|---|---|
| 01 | Unit suite | 277 passed, 1 warning | 0 |
| 02 | Full regression, hardening not configured | 605 passed, 6 failed, 203 skipped (harness KeyError, above) | 1 |
| 03 | Hardening suites as restricted login | 210 passed | 0 |
| 04 | Full regression, hardening configured | **814 passed**, 1 warning, 0 failed | 0 |
| 05 | Focused Phase 4 gate | 234 passed, 1 warning | 0 |
| 06 | Synthetic demonstration | 1 passed | 0 |
| 07 | Ruff lint (`src tests`) | All checks passed | 0 |
| 08 | Ruff format check | Two files only: the documented exceptions | 1 (by policy) |
| 09 | Strict mypy (`src/webdesk`) | No issues in 60 files | 0 |
| 10 | Alembic upgrade head, fresh database | `0043_phase2_review_fixes (head)` | 0 |
| 11 | Alembic upgrade head, downgrade -1, upgrade head | head `0043_phase2_review_fixes`. The first attempt was a runner error (its sequence started on an empty database); the re-run passed | 0 |
| 12 | Alembic downgrade base | **Not run.** QA saw DependentObjectsStillExist on a shared cluster | — |
| 13 | Restricted-login privilege audit | 17 passed | 0 |
| 14 | Corpus manifest | 2 passed | 0 |
| 15 | Crash, hang, output cap | 29 passed | 0 |
| 16 | Committed outcomes and concurrency | 19 passed | 0 |

Totals: 814 passed in the configured full regression, against 793 passed at `f416716` (the earlier gate on the same cluster).
Strict mypy is clean. Ruff lint is clean. Ruff format has only the two documented exceptions.

### 11.2 Open, not in this remediation

- Windows process memory (H-DEC-4) is not contained. Not touched.
- Base migration round trip (row 12) is not run.
- Page-count limit (500) is applied by the parser only, not at admission (D-H12).
- Images on pages that have text are not flagged (D-H13).
- Footnotes, endnotes and comments in DOCX are not read.
- The two hardening test files that index the owner URL directly (step 02).
- The QA-07 Phase 3 lease ordering is still unverified on this branch.
