# Phase 4 engineering evidence

Branch `feature/foundation-phase-4`. Base `46e0e14`. Sprint start commit `85315a1`. This document records
what was built and how it was checked. It is not an acceptance. Acceptance belongs to independent QA.

## 1. Parser isolation (H-32)

**Design.** A parse runs in a child process, `python -s -m webdesk.intake.parser_child <mime>`, with the file on
stdin and one JSON object on stdout. The child imports the parsers only. It does not import the database, storage
or authority layers.

**Bounds, enforced by the parent (`src/webdesk/intake/isolation.py`).**

- Wall-clock timeout of 30 s (`PARSER_TIMEOUT_SECONDS`). Below the 120 s job lease. On timeout,
  `subprocess.run` kills the child and waits for it before the exception returns. Class `parser_timeout`.
- Output cap of 32 MiB (`PARSER_OUTPUT_BYTES`). Class `parser_output_limit`.
- Non-zero exit, a signal, or unreadable output: class `parser_crash`.
- POSIX: address-space cap of 1 GiB through `RLIMIT_AS` in the child. Windows: not enforced (H-DEC-4).
- Windows: `CREATE_NO_WINDOW`, so the child opens no console window.

**Privilege.** The child environment is an allowlist: `SYSTEMROOT`, `TEMP`, `TMP`, `PATH`, `WEBDESK_ENV` and
`PYTHONPATH` (set to this source tree). The database URLs and storage and key settings are never passed. The
fault switch `WEBDESK_PARSER_FAULT` is forwarded only when `WEBDESK_ENV=test`.

**Source tree.** The child runs with `-s` and not `-I`, because `-I` ignores `PYTHONPATH`. The venv's editable
install points at the main checkout, so the child sets `cwd` and `PYTHONPATH` to this worktree's `src`. A
failure to do this would load the wrong code silently. This is recorded because it is easy to miss.

**Parent survival.** Every child fault maps to a stable class and a `failed` version. The worker process is not
affected. `test_a_crashing_child_fails_with_parser_crash_and_the_parent_survives` runs three crashes in a row,
then a healthy parse.

**Tests.** `tests/unit/test_parse_isolation.py`: 26 tests. They cover the environment allowlist, the fault switch,
the memory-cap platform fact, equality of isolated and in-process results for every parseable corpus case, crash,
hang (killed at a 2 s test timeout, returning in under 20 s), output cap and unknown MIME. The demonstration
(`tests/committed/test_parse_demonstration.py`) runs a crash on real persistence.

**Known limits.**

- Windows has no memory cap. The timeout and input-size pre-check bound the parse. H-DEC-4 is open.
- The parse holds the version row lock (`FOR UPDATE` in `fn_worker_begin_parse`) for its duration, up to the
  timeout. The lock is released by commit or rollback, so no other path is blocked beyond that window.

## 2. Locators and provenance (H-33)

| Format | Locator | Provenance | Verified by |
|---|---|---|---|
| TXT | `txt_line_range`: `line_start`, `line_end`, `char_start`, `char_end` | Code-point offsets into the decoded UTF-8 text. `text[char_start:char_end]` equals the segment text. Split on `\n` only. | `test_txt_offsets_recover_each_segment_exactly...` |
| PDF | `pdf_page`: `page_number` | Image-only pages are flagged `pdf_page:N`, not read as blank. | `test_an_image_only_pdf_page_is_partial...` |
| DOCX | `docx_paragraph`: `paragraph_index`; for table cells also `table_index`, `row`, `cell` (H-DEC-5 proposed) | Merged cells are read once | `test_docx_table_cells_are_segments...`; `test_a_docx_table_cell_is_persisted...` |
| EML | `eml_part`: `eml_part`, plus `message_id` (provenance, not text) | Message-ID is in the locator, not the segment text | `test_eml_segments_carry_the_message_id...` |
| HTML-only EML | flagged `eml_part:body_html_only`, status `partial` (H-DEC-6 proposed) | The body is reported, not dropped | `test_an_html_only_eml_body...` |

**Locator keys.** `locator_key` is the RFC 8785 canonical JSON of the locator, unchanged in form. The
`UNIQUE (source_version_id, extraction_version, locator_type, locator_key)` constraint is the same as before.
Segment identity is per version because the version is in the key.

**Schema.** The locator CHECK in migration 0007 requires specific keys per type and does not forbid others, so the
extended keys above are admitted without a migration. The plan says migration `0013` widens the CHECK. That file
does not exist on this branch, and no migration was added. The divergence is recorded for WDS.

**Open.** EML character offsets. The plan asks for "character offsets for subject and body" but does not say
offsets into what. This sprint does not invent an answer. Raise with WDS.

## 3. Partial results (H-34)

`parse_error` holds `{"class": "partial", "flagged_regions": [...]}` for every `partial` result. A partial version
is not reparseable (`not_failed`), so its flagged regions cannot be silently cleared by a retry.
`test_a_partial_version_cannot_be_reparsed_and_keeps_its_flagged_regions` checks this on real PostgreSQL.

## 4. Reparse, duplicates, idempotency and concurrency

| Scenario | Test | Result |
|---|---|---|
| Failed version reparsed once, retry writes one set of segments | `test_a_failed_version_is_reparsed_once...` | succeeded, segment count equals the line count |
| Second reparse of a reset version | `test_a_second_reparse_of_the_same_version_is_refused_as_not_failed` | 409 `not_failed`, denial audited |
| Stale source revision | `test_a_reparse_with_a_stale_source_revision...` | 409 `revision_conflict`, denial audited, version stays failed |
| Partial version reparse | `test_a_partial_version_cannot_be_reparsed...` | 409 `not_failed`, flagged regions kept |
| Rolled-back segment write then retry | `test_a_rolled_back_segment_write_leaves_no_residue...` | no residue, retry succeeds |
| Repeat parse of a succeeded version | `test_a_parse_of_a_version_that_is_not_pending...` | refused `not_pending`, no new rows |
| Quarantined version | `test_a_quarantined_version_is_refused_by_the_parser...` | refused `quarantined`, no rows |
| Cross-version isolation | `test_segments_belong_to_their_own_version...` | each version holds only its own lines |
| Two parses race on one version | `test_two_parses_of_one_pending_version...` (committed, 4 rounds) | exactly one `succeeded`, the other `not_pending` |
| Parse races reparse | `test_a_reparse_racing_a_parse...` (committed, 4 rounds) | one of two consistent states, never duplicates |
| Stale reparse after a newer revision | `test_a_stale_reparse_loses_the_race...` (committed) | `revision_conflict`, failed state kept |
| Replayed proof | `test_a_reparse_proof_is_spent_by_its_first_accepted_reparse` (existing) | `ProofRefused` |

Every race test asserts an invariant that holds in both orderings, and each runs several rounds on fresh rows.
Both threads hold their own connections and transactions and start on a barrier.

**Application read restriction.** `webdesk_app` can read segment locators and locator keys, but not
`text_content` (migration 0037). The tests verify ordering and identity through locators and assert text through
the unit tests. This is the designed boundary, not a test workaround.

## 5. Migration and privilege evidence

- **Migrations added in this sprint: none.** The chain head is unchanged from the base (`0043_phase2_review_fixes`).
  No committed migration was edited.
- **Privileges.** No new grant was issued. The parser child has no database role and no database URL. The
  reparse, parse and read paths run under their existing roles, as in the base.
- **Privilege audit.** `tests/hardening/` runs under the restricted login in the full regression. See the handoff
  for the exact result.

## 6. Verification commands

The environment file used for the sprint sets `WEBDESK_TEST_DATABASE_URL` to the `webdesk_p4_integration` database
and the hardening URLs to `webdesk_p4_hardening`. Runs are sequential. No destructive run overlaps another.

```bash
source <env file that sets the namespace URLs>
python -m pytest tests -q -p no:cacheprovider
python -m ruff check src tests
python -m mypy --strict src/webdesk
```

The exact totals and exit codes are recorded in `docs/PHASE4_INDEPENDENT_QA_HANDOFF.md`.
