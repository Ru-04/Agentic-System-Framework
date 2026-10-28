# Phase 4 closure evidence (2026-10-28, partial)

Branch `feature/foundation-phase-4`. Baseline `a3f39d6`. This record supersedes the status in
`docs/PHASE4_INDEPENDENT_QA_HANDOFF.md` where they differ. It is not formal WDS acceptance.

## Governance basis

- Decisions P-0, H-DEC-3 to H-DEC-6 and the EML offset semantics are recorded in
  `docs/GOVERNANCE_DECISION_REGISTER.md`, entry `P4-GOV-2026-10-28`.
- Provenance is incomplete: the approval was relayed in chat on 2026-10-28. The approver's identity, WDS's approval
  date and channel, and exact wording are not recorded. Those are the open provenance items.

## Defects (investigated 2026-10-28, reproduced on the baseline before the fix)

| ID | Finding on `a3f39d6` | Fix | Regression test |
|---|---|---|---|
| D1 | HTML-only EML with no subject returned `unsupported` and its flag was dropped | `_status`: any flagged region makes the result `partial`, with or without segments | `tests/unit/test_parse_defects.py::test_d1_*` |
| D2 | `_check_archive` trusted declared sizes; a header declaring 10 bytes over 5 MB of content passed | Every member is read in full, counted, and compared with its declared size; mismatch is `corrupt_structure` | `test_d2_*` (3 tests) |
| D3 | A table nested in a DOCX cell was dropped silently | Reported as `docx_nested_table:T.R.C.N`, status `partial`; nested text is not invented | `test_d3_*` |
| D4 | Page content was fully decompressed before the 10 MiB check (probe: 60 MiB peak for a 60 MiB stream); a form XObject's text was not extracted and not flagged | Bounded FlateDecode decode with `budget + 1`; unbounded filters flag the page; direct form XObjects are bounded, and text in them flags the page | `test_d4_*` (6 tests) |

The probes are in the session scratchpad, outside the repository.

## Approved EML offsets (P4-GOV-2026-10-28)

`eml_part` locators carry `char_start = 0` and `char_end = len(normalized part text)`. Normalization is NFC
followed by stripping surrounding whitespace. Unit tests: `test_eml_offsets_*`, `test_eml_body_offsets_*`,
and the updated `test_eml_yields_subject_and_body_*`.

## Verification run on 2026-10-28 (worktree, venv `D:\WDS\Agentic System FrameWork\.venv`)

| Check | Command | Result | Exit |
|---|---|---|---|
| Unit suite, before changes | `pytest tests/unit -q -p no:cacheprovider` | 194 passed | 0 |
| Unit suite, after changes | same | **210 passed**, 1 warning (includes 16 new defect tests) | 0 |
| Lint | `ruff check src tests migrations` | All checks passed | 0 |
| Format | `ruff format --check src tests migrations` | 6 files: the 4 frozen migrations and 2 untouched tests in `RUFF_FORMAT_EXCEPTIONS.md` | 1 (documented) |
| Strict types | `mypy --strict src/webdesk` | Success, 60 source files | 0 |

Subprocess crash and timeout tests and the isolated-equals-in-process corpus test run inside the unit suite
(`tests/unit/test_parse_isolation.py`). They passed on this run.

## Not run on 2026-10-28 (blocked)

- Full regression, committed-row PostgreSQL tests (`tests/committed/test_parse_outcomes.py` was written and
  collected, but skipped, because `WEBDESK_TEST_DATABASE_URL` is unset), PostgreSQL concurrency, privilege audit,
  AI Read v1 compatibility, migration and catalog checks, corpus manifest test, and the end-to-end demonstration.
- Blocker: the credentials in the local env files were rejected on `localhost:5432` (password authentication failed
  for `webdesk_integration_owner`, `webdesk_test_owner` and `webdesk_app_login`). `localhost:5433`, the Docker port
  named in the env file, was not reachable. No credentials were guessed or changed.

## Migration and privilege status

- No Phase 4 migration. The locator CHECK in migration `0007` requires only the keys for each locator type and
  admits the extra keys (`table_index`, `row`, `cell`, `message_id`, `char_start`, `char_end`). This was verified by
  reading the migration; the catalog check itself is not yet run.
- No privilege grant was changed. The parser child has no database role. Restricted-login evidence is pending the
  database run above.

## Open items

- Provenance of the WDS approval (see Governance basis).
- Full gate and committed-row tests (blocked by database access).
- Phase 3 lease reconciliation before merge.
