# H-DEC-3 proposed limits register (Phase 4)

Status: **proposed. Not approved by WDS.** The plan (H-DEC-3) asks WDS for numeric production values. None
has been chosen here. Each value below is a proposal in `src/webdesk/intake/limits.py`, kept as a constant so
any change is visible in review. Tests enforce each limit with deterministic synthetic cases. The tests set
small values through monkeypatching where a full-size fixture would be slow; the enforcement path is real.

| Limit | Constant | Proposed value | Breach class | Enforced at | Test |
|---|---|---|---|---|---|
| Input size | `MAX_INPUT_BYTES` | 25 MiB | `input_too_large` | before any parse | corpus `oversized-txt`, `oversized-pdf`; `test_an_oversized_input...` |
| PDF pages | `MAX_PDF_PAGES` | 500 | `pdf_page_limit` | parser, before extraction | `test_a_pdf_with_more_pages...` |
| PDF per-page content stream | `MAX_PDF_PAGE_STREAM_BYTES` | 10 MiB | `pdf_stream_limit` | parser, and upload admission before a version exists (F-5) | `test_a_pdf_page_stream_over...`; `test_f5_admission_refuses_an_oversized_page...` |
| ZIP uncompressed total (DOCX) | `MAX_ARCHIVE_UNCOMPRESSED_BYTES` | 100 MiB | `archive_size_limit` | parser | `test_a_docx_whose_uncompressed...` |
| ZIP inflate ratio (DOCX) | `MAX_ARCHIVE_RATIO` | 100 : 1 | `archive_ratio_limit` | parser | corpus `oversized-docx-archive` |
| DOCX paragraphs, table-cell and text-box paragraphs | `MAX_DOCX_ELEMENTS` | 20 000 | `docx_element_limit` | parser | `test_a_docx_with_more_elements...` |
| Source upload request body (new, F-2) | `MAX_UPLOAD_REQUEST_BYTES` | 21 MiB (the 20 MiB file maximum plus 1 MiB for fields and framing) | `too_large` (413) | upload route, as the body arrives, before it is buffered | `test_f2_a_body_over_the_limit...`; `test_f2_an_upload_over_the_request_bound...` |
| Segments per version | `MAX_SEGMENTS_PER_VERSION` | 5 000 | `segment_limit` | before any write | `test_a_segment_count_breach...` |
| Characters per segment | `MAX_CHARS_PER_SEGMENT` | 20 000 | `segment_length_limit` | before any write | `test_a_segment_length_breach...` |
| Parser wall-clock time | `PARSER_TIMEOUT_SECONDS` | 30 s | `parser_timeout` | child process kill | `test_a_hanging_child_is_killed_at_the_timeout` |
| Child output size | `PARSER_OUTPUT_BYTES` | 32 MiB | `parser_output_limit` | parent, while the child writes; the child is killed past the cap (F-6) | `test_an_oversized_child_output...`; `test_f6_an_endless_child_output...` |
| Child address space (POSIX) | `PARSER_MEMORY_BYTES` | 1 GiB | `parser_crash` (the child is terminated by the kernel) | child `RLIMIT_AS` | not exercised on this Windows host |

## Constraints the values must satisfy

- `PARSER_TIMEOUT_SECONDS` must stay below the job lease (120 s, see the Phase 3 lease note). It is 30 s, so a
  parser cannot outlive its claim. WDS must keep this ordering if the lease changes.
- `MEMORY_CAP_ENFORCED` is `True` on POSIX only. On Windows the memory bound is absent until H-DEC-4 is decided
  (a job object is the candidate). This is a recorded residual, not a silent gap.
- A breach never yields partial text. Each limit fails the whole version with its class.

## Decisions requested from WDS

1. Approve or replace each proposed value (H-DEC-3).
2. Decide the Windows memory cap (H-DEC-4): job object, or the process timeout plus the input-size pre-check
   already in place. The current build uses the second.
3. Confirm DOCX table locator fields (H-DEC-5, proposed: extension of `docx_paragraph`).
4. Confirm the HTML-only email treatment (H-DEC-6, proposed: report as unextractable, `partial`).
5. Confirm the proposed `MAX_UPLOAD_REQUEST_BYTES` value (F-2). It is a new limit, not in the approved register.
6. Confirm the independent-QA defaults in `docs/PHASE4_PDF_CONTAINMENT.md` section 10: admission applies the per-page
   bound (F-5); replacement-only text commits no segment (F-4); DOCX text boxes are extracted and headers and footers
   are flagged, not extracted (F-3). Also rule on the page-count limit at admission and on images on text pages.
