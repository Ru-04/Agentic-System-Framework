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

- QA-06: text in nested form XObjects is not followed and not flagged.
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
