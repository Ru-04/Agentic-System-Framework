# Phase 4 closure evidence (2026-10-28)

> Superseded in part on 2026-10-28 by `docs/PHASE4_QA_REMEDIATION.md` (commit `8d5b039`). Partial status, offset names, input limit and expansion checks are updated there. Earlier text below is kept for history.

Branch `feature/foundation-phase-4`. Baseline `a3f39d6`. Defect and offset commit `cb93047`. Committed-row tests and
`.gitignore` commit `69aa9e8`. This document is engineering evidence. It is not formal WDS acceptance and not a
production-readiness claim.

## 1. Database environment and recovery

- **Shared cluster (not used by Phase 4 tests):** container `agenticsystemframework-postgres-1`, PostgreSQL 16.4,
  published `5433`. It was found running and was only read (catalog and `pg_stat_activity` checks). The hardening suite
  rotates the shared `webdesk_authority_login` password (`provision_login_password`), and another workstream's session was
  active on that cluster. Running Phase 4 hardening tests there would have broken them, so Phase 4 used its own cluster.
- **Phase 4 cluster:** container `webdesk-p4-postgres`, image `postgres:16.4` (same version), published
  `127.0.0.1:55434`, volume `webdesk_p4_pgdata`. Created on 2026-10-28. It holds only Phase 4 roles and databases.
- **Namespaces:** `webdesk_p4_integration` (migrated, base for committed-row fixtures), `webdesk_p4_hardening` (migrated,
  hardening database), and per-test `webdesk_test_*` and `webdesk_template_*` databases created and dropped by the
  fixtures. A scratch database `webdesk_p4_migcheck` was created and dropped by the catalog check.
- **Port isolation:** no source or test file hard-codes port 5432 or 5433. Every connection URL comes from the environment
  exports, which target `127.0.0.1:55434`. Nothing targets 5433.
- **Credentials:** generated locally into the git-ignored `.env.phase4.local`. They were never printed or committed.

### Deviations from the documented shared-cluster shape (recorded)

The isolated cluster was provisioned to match `docs/PRIVILEGE_AUDIT_2026-10-23.txt`, with these exceptions:

1. The hardening database owner is `webdesk_integration_owner`, not `webdesk_test_owner`. The documented owner cannot
   migrate, because migrations grant `webdesk_guard_owner`, which it has no admin option on.
2. `webdesk_integration_owner` holds `ADMIN OPTION` on the `webdesk_intake_worker_login` role, so the provisioning test can
   `ALTER` it. The role was created by the superuser.
3. Memberships were applied with `SET` enabled for the integration owner. Without it, `SET ROLE webdesk_ceremony` is refused.

All three are test-topology choices in the isolated cluster. They do not change product code or migrations.

## 2. Defects D1 to D4 (commit `cb93047`)

| ID | Finding on `a3f39d6` | Fix | Tests |
|---|---|---|---|
| D1 | An HTML-only email with no subject returned `unsupported`, dropping its flag | Any flagged region makes the result `partial` | `test_parse_defects.py::test_d1_*`; committed `test_d1_a_committed_html_only_email_*` |
| D2 | ZIP checks trusted declared sizes (a 10-byte declaration over 5 MB content passed) | Members are read and counted; a size mismatch is `corrupt_structure` | `test_d2_*` (3 tests, including an honest archive over the limit) |
| D3 | A table nested in a DOCX cell was dropped | Reported as `docx_nested_table:T.R.C.N`; status `partial` | `test_d3_*` |
| D4 | Page content was fully decompressed before its 10 MiB check (60 MiB peak measured); form XObject text was missed without a flag | Bounded FlateDecode with an output limit; unbounded filters flag the page; direct form streams are bounded, and text in them flags the page | `test_d4_*` (6 tests, including a 60 MiB expansion) |

Adversarial inputs covered: a forged archive size, an honest archive over the uncompressed limit, a compressed expansion
past the stream budget, a page whose decoded content exceeds the limit, a form with hidden text, and an unbounded filter
(LZW) that flags its page without failing the file.

## 3. EML character offsets (approved, P4-GOV-2026-10-28)

`eml_part` locators carry `char_start = 0` and `char_end = len(normalized part text)`. Normalization is NFC followed by
stripping surrounding whitespace. Tests: `test_eml_offsets_are_relative_to_the_nfc_normalized_part_text`,
`test_eml_body_offsets_follow_the_stripped_text`, and the updated `test_eml_yields_subject_and_body_*`.

## 4. Verification gate (13 steps, sequential, dedicated cluster)

Each row is one step of the final gate run on 2026-10-28, taken from the run's `summary.txt`. Python was the project venv
(`D:\WDS\Agentic System FrameWork\.venv\Scripts\python.exe`), run with the Phase 4 environment exports and `PYTHONPATH`
set to this worktree's `src`.

| # | Step | Command (abridged) | Start → end (+05:30) | Result | Exit |
|---|---|---|---|---|---|
| 01 | Focused H-30 to H-35 | `pytest tests/unit/test_parse_defects.py tests/unit/test_intake_unit.py tests/unit/test_parse_isolation.py tests/integration/test_parse_hardening.py tests/integration/test_parse_reparse.py tests/integration/test_intake_db.py` | 16:24:58 → 16:25:35 | 102 passed | 0 |
| 02 | Committed-row outcomes | `pytest tests/committed/test_parse_outcomes.py` | 16:25:35 → 16:25:52 | 9 passed | 0 |
| 03 | Concurrency and reparse | `pytest tests/committed/test_parse_concurrency.py` | 16:25:52 → 16:26:03 | 3 passed | 0 |
| 04 | Crash, hang, output cap (subprocess) | `pytest tests/unit/test_parse_isolation.py -k "crash or hang or timeout or output"` | 16:26:03 → 16:26:10 | 3 passed, 23 deselected | 0 |
| 05 | Corpus manifest | `pytest tests/unit/test_parse_corpus_manifest.py` | 16:26:10 → 16:26:13 | 2 passed | 0 |
| 06 | Full Foundation regression | `pytest tests -q -p no:cacheprovider` | 16:26:13 → 16:34:39 | **739 passed**, 1 warning | 0 |
| 07 | AI Read v1 compatibility | `pytest tests/committed/test_ai_read_v1.py` | 16:34:39 → 16:36:42 | 28 passed, 1 warning | 0 |
| 08 | Restricted-login privilege audit | `pytest tests/hardening/test_privilege_audit.py tests/hardening/test_privilege_hardening.py` | 16:36:42 → 16:36:48 | 34 passed | 0 |
| 09 | Migration and catalog | `p4_catalog.py`: upgrade head, downgrade -1, upgrade head; locator CHECK printed | 16:36:48 → 16:36:49 | ok; head `0043_phase2_review_fixes` | 0 |
| 10 | Synthetic demonstration | `pytest tests/committed/test_parse_demonstration.py -s` | 16:36:50 → 16:36:58 | 1 passed | 0 |
| 11 | Ruff lint | `ruff check src tests migrations` | 16:36:58 | All checks passed | 0 |
| 12 | Ruff format policy | `ruff format --check src tests migrations` | 16:36:58 | 6 files would reformat: the 4 frozen migrations and 2 untouched tests listed in `RUFF_FORMAT_EXCEPTIONS.md`; no other file | 1 (documented) |
| 13 | Strict mypy | `mypy --strict src/webdesk` | 16:36:58 → 16:37:00 | Success, 60 files | 0 |

Step 12 exits 1 by design: only the six listed files may fail the format check, and they do.

### Earlier gate runs (for transparency)

- **Run 1** (15:53 to 16:12) failed in step 06 (88 failed, 112 errors, all in `tests/hardening`) and step 08 (23 failed,
  5 errors). The cause was provisioning gaps in the isolated cluster (§1). Ruff failed on line lengths in my new test file,
  since fixed.
- **Run 2** (16:14 to 16:24) passed steps 01 to 05, 07, 09, 10 and 13. Step 06 reported 738 passed and 1 failed in
  `test_worker_login`. A provisioning membership I had added twice produced a duplicate row. I removed the extra grant
  (isolated cluster only). Run 3 is the final record above.

## 5. Committed-row, concurrency and reparse results

- **Committed-row outcomes (9 passed):** successful parse; partial with a flagged region beside its segments; partial with
  no text segment (D1); parser failure (`segment_length_limit`, one 20 001-character line, nothing written); a failed version
  beside an untouched neighbour; a rolled-back parse leaving the version pending with no residue; a stale reparse refused
  with `revision_conflict` and the failed version unchanged; a failed version reparsed once to 2 segments, then `not_pending`
  on a second parse; a partial version not reparseable.
- **Concurrency (3 passed):** two parses of one pending version write its segments exactly once; a reparse racing a parse
  leaves one consistent state; a stale reparse loses the race. Each runs 4 rounds on fresh committed rows.
- **Upload admission note:** PDF admission refuses corrupt and encrypted files before parsing, so the committed parser-failure
  path uses a valid file that the parser refuses on a limit. The corpus remains the reference for corrupt and encrypted inputs.

## 6. Migration, catalog and privilege

- **Migrations:** no Phase 4 migration. Head is `0043_phase2_review_fixes`. The round trip (`upgrade head`, `downgrade -1`,
  `upgrade head`) passed on a scratch database.
- **Locator CHECK (migration 0007):** requires only the keys named per locator type and admits the extra keys (`table_index`,
  `row`, `cell`, `message_id`, `char_start`, `char_end`). The catalog check printed the three CHECK constraints and the unique
  key on `(source_version_id, extraction_version, locator_type, locator_key)`. No new constraint is needed for the approved
  semantics.
- **Privilege:** the restricted-login suites pass on the isolated cluster (34 in step 08, plus the hardening tests in step 06),
  under the deviations in §1.

## 7. Requirements traceability, H-30 to H-35

| ID | Requirement (summary) | Evidence | Status |
|---|---|---|---|
| H-30 | Per-version failure isolated and audited | Unit `test_a_segment_write_failure…`, `test_a_parser_exception_fails_only…`; committed neighbour and rollback tests; isolation child tests | Closed (engineering) |
| H-31 | Resource limits | `limits.py` constants; hardening limit tests; D2 and D4 fixes and tests; values recorded under P4-GOV H-DEC-3; F-5 admission per-page bound and F-2 request bound (§11) | Closed for non-production, pending WDS confirmation of D-H12 and D-H14. Production values need a separate WDS decision. |
| H-32 | Isolated parser process, timeout, crash containment | `isolation.py`, `parser_child.py`; isolation tests; crash, hang and output-cap tests in steps 01 and 04; output cap enforced while the child writes (F-6, §11) | Closed for non-production, with the Windows memory residual recorded under H-DEC-4. Production containment needs a separate decision. |
| H-33 | TXT, PDF, DOCX and EML locators | TXT offsets; PDF image pages; nested image-only pages flagged (F-1); DOCX cells; DOCX text boxes extracted and headers and footers flagged (F-3); replacement-only text not committed (F-4); D3 nested tables flagged; EML message-id and approved offsets (§3); HTML-only flagged | Not closed by this document. The F-1, F-3 and F-4 fixes are in place. Acceptance needs WDS confirmation of D-H10, D-H11 and D-H13 (§11). |
| H-34 | Flagged regions and partial extraction | D1 fix; committed partial and HTML-only tests; partial not reparseable | Closed |
| H-35 | Committed-row atomicity and concurrency | Nine outcome tests and three concurrency tests on committed rows; rolled-back and stale-reparse paths | Closed for the paths listed in §5 |

## 8. Governance and provenance (not closed by this document)

- The decisions in `docs/GOVERNANCE_DECISION_REGISTER.md`, entry `P4-GOV-2026-10-28`, record the relayed approval. The approver's
  identity, WDS's own approval date and channel, and exact wording are **not recorded**. The register says so.
- H-DEC-3 numeric values remain provisional. Production values need WDS.
- H-DEC-4 covers non-production Windows testing only. Production containment needs a separate WDS decision.

## 9. Future merge dependencies (not completed integrations)

- **Migration ancestry:** `feature/foundation-phase-3` (`e9d888a`, migration `0050_durable_execution`) and the Phase 2 remediation
  migrations `0044` and `0045` are not in this branch. Their `down_revision` must be reconciled before merge.
- **Phase 3 lease:** the 120 s job lease is not in this branch. `PARSER_TIMEOUT_SECONDS = 30` must be confirmed below the lease
  when Phase 3 merges.
- **Phase 3 durable execution:** no code dependency in this branch, but the intake job lease and reaper are untested here.

## 10. Remaining items

- Provenance of the WDS approval (§8).
- Production containment and production limit values (§8).
- The merge dependencies in §9.
- Independent QA has not started. The remediation SHA in §11 is for the independent reviewer to re-test; it has not been
  tested by anyone outside the engineering session.
- WDS confirmation of the defaults and values in §11.

## 11. Remediation of the independent QA of `178a419`

Full record: `docs/PHASE4_QA_REMEDIATION.md` section 11. Engineering SHA for the independent reviewer to re-test:
`b604e7b` (code). Documentation for that code is in the commit that adds this section.

- Six findings fixed (F-1 to F-6). Each has a regression test that failed before its fix.
- Gate on `b604e7b`: full regression with hardening configured 814 passed, exit 0. Focused gate, committed-row,
  restricted-login and migration steps passed. Two rows are not clean: row 02 (no-hardening run, a harness KeyError in two
  hardening test files that index an unset variable) and row 12 (base downgrade, not run). See section 11.1 of that file.
- Decisions awaiting WDS confirmation: D-H10 (DOCX text boxes and header and footer flags), D-H11 (replacement-only
  text), D-H12 (admission per-page bound, and page-count limit not applied at admission), D-H13 (images on text pages),
  D-H14 (`MAX_UPLOAD_REQUEST_BYTES` value). Recorded in `docs/PHASE4_DEPENDENCY_REGISTER.md`.
- Not closed by this section: Windows process memory (H-DEC-4), production limits, formal acceptance, and the Phase 2 and
  Phase 3 integrations (§9).
