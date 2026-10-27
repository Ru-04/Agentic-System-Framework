# Phase 4 requirements gap matrix (parse robustness)

Base: `46e0e14` (committed Phase 2 state). Branch: `feature/foundation-phase-4`. Approved basis:
`docs/INCREMENT_3_HARDENING_PLAN.md`, Phase 4 section (H-30 to H-35) and its decision register (H-DEC-3 to H-DEC-6).

Status values: **done** (implemented and tested), **partial** (implemented with a stated gap), **open** (not
implemented), **decision** (blocked on a WDS decision), **dependency** (needs Phase 2 or Phase 3).

## Approved items

| ID | Requirement | Committed baseline | Phase 4 change | Test evidence | Status |
|---|---|---|---|---|---|
| H-30 | Catch every per-version failure; the version fails alone, the run continues | Parser exceptions caught; segment-write only caught `SQLAlchemyError` | Segment write catches every exception; all failures go through `_fail` (stable class, audit) | `test_a_segment_write_failure_of_any_kind_fails_only_that_version`; existing `test_a_parser_exception...` | done |
| H-31 | Resource limits: archive ratio and size, PDF pages, DOCX counts, segments per version, characters per segment; each breach a `failed` version with a stable class | None | `intake/limits.py` (proposed values, H-DEC-3); input size checked before parse; DOCX archive size and ratio; PDF page count; segment count and length before any write | `test_an_oversized_input...`; `test_a_segment_count_breach...`; `test_a_segment_length_breach...`; `test_a_docx_whose_uncompressed...`; `test_a_pdf_with_more_pages...` | partial: the DOCX paragraph and table-cell count and the per-page PDF stream size are not limited (no test). Values await H-DEC-3. |
| H-32 | Parse isolation: child process, wall-clock timeout shorter than the lease, memory cap; a timeout or child crash fails the version | None; parsers run in the worker process | None | none | open: process isolation not implemented. H-DEC-4 default (process timeout plus file-size pre-check) is not built. |
| H-33 | Complete locators: EML Message-ID in provenance and offsets; TXT offsets; DOCX table cells; PDF image-only page is `partial`; HTML-only email per H-DEC-6 | TXT lines as `txt_line_range` with line numbers; EML parts; PDF pages flagged on error | None beyond limits | existing intake tests | open for EML offsets, DOCX table cells (needs H-DEC-5 locator fields) and HTML-only handling (H-DEC-6). `partial` on PDF extraction error is implemented. |
| H-34 | `parse_error` holds `{"class": "partial", "flagged_regions": [...]}` for `partial` results | `parse_error` only for failures | Partial results persist their flagged regions | `test_a_partial_extraction_records_the_regions_it_could_not_extract` | done |
| H-35 | Atomicity tests for each partial and failed path on committed rows with the real file | Partial coverage in intake tests | New real-file tests for limits, partial and write failure | `tests/integration/test_parse_hardening.py` (7 tests, rolled back, real PostgreSQL) | partial: the committed-row (cross-connection) variant is not added |

## Sprint areas

| Area | Status | Note |
|---|---|---|
| A. Supported and unsupported formats, file identification, empty and malformed input | partial | Unsupported MIME is refused (existing). Corrupt structure is classified. Empty and corrupt-document corpus is not built. |
| B. Source-version correctness, immutable versions, stale parse results | existing; not re-verified in this sprint | Parse refuses non-pending versions (`not_pending`) and quarantined versions (existing test). |
| C. Reparse correctness (proofs, duplicates, concurrency, rollback) | not started in this sprint | `intake/reparse.py` exists in the base; the concurrency and idempotency tests are not written. |
| D. Security and classification | existing; not re-verified | Quarantine and restricted rules remain as in the base. No scanner is invented. External transmission is not enabled. |
| E. Workflow integration with Phase 3 | dependency | The intake worker in the base runs the parser through the existing job path. Phase 3 durable execution is not merged into this branch. |
| Corpus of versioned synthetic fixtures | open | Not built. |
| Synthetic demonstration | open | Not built. |

## Dependencies

- Phase 3 (`feature/foundation-phase-3`, committed `e9d888a`): durable execution. Not merged here. Phase 4 does not
  depend on its code. Its reconciliation needs the migration head (see `PHASE4_DEPENDENCY_REGISTER.md`).
- Phase 2 remediation (uncommitted in its worktree): migrations `0044` and `0045`. Not used here.
- WDS decisions: H-DEC-3 (numeric limits), H-DEC-4 (Windows memory cap), H-DEC-5 (DOCX locator fields), H-DEC-6
  (HTML-only email).
