# Increment 2 Evidence Report (Phases A–E, gap closure)

**Status: Gate 1 is NOT yet complete.** Every release-blocking gap from the first evidence pass is
closed by tests. One item is BLOCKED by a decision (EVAL-DEPLOYMENT-GATE-001). Nothing here is an
independent review.

Branch `feature/increment-1-foundation`. Uncommitted, on top of commit `ce76b32`.

## 1. Verification run

| Check | Result |
|---|---|
| Full suite (`pytest`, PostgreSQL 16.4 `webdesk_test`; committed rows in a session database) | **383 passed, 0 failed** |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 89 files already formatted |
| `mypy` (strict, `src/webdesk`, 46 source files) | Success: no issues |
| Migrations | Head `0009_classification_reassessment` |

Dependencies added across Phases C–F, each pinned and at least two weeks old: `pypdf==5.1.0`,
`python-docx==1.1.2`, `rfc8785==0.1.4`, `python-multipart==0.0.12`. The HTTP layer depends on
`python-multipart` for form uploads.

Only one warning is reported: a deprecation from Starlette's test client, not from project code.

## 2. What closed each gap

| Gap from the first pass | Closed by | Tests |
|---|---|---|
| **F05 HTTP layer** | Authenticated routes for upload, content read, run start and controls, and reparse. Strict JSON bodies. Server-owned form fields refused with 422. Each request runs in one transaction, so denial audits survive. | `tests/committed/test_http_intake.py` (8): no session → 401; analyst upload and byte read-back; server field refused; stale revision → 409; unknown JSON field → 422; administrator cannot start a run (403); run controls and reparse follow role rules; no storage root → 503 |
| **F07 expected run revision** | Cancel, retry and resume require `expected_run_revision`. Mismatch → 409 before any change. | `test_run_controls_refuse_a_stale_run_revision`; HTTP control test |
| **F08 checkpoint** | An `intake_complete` checkpoint is written with run ID references and flags only. Resume is refused for parked runs in Gate 1. | `test_intake_writes_a_checkpoint_with_identifiers_and_flags_only`; `test_resume_is_refused_for_a_parked_run_in_gate_1` |
| **F09 transitions** | Unlisted transitions refused. Retry refused on an archived project. | `test_an_unlisted_transition_is_refused`; `test_an_archived_project_refuses_retry_of_a_failed_run` |
| **F11f appointment expiry** | Sweep expires unconsumed, past-deadline appointments. | `test_the_sweep_expires_an_unconsumed_appointment_past_its_deadline` |
| **F12 denial audits** | Cancel and reparse refusals each write one denial audit. | `test_refused_run_cancel_writes_a_denial_audit`; `test_refused_reparse_writes_a_denial_audit` |
| **F14 reparse refusals** | Quarantined, superseded and archived versions refused with stable reasons. | three `test_reparse_refuses_…` tests |
| **F14b / F04 reuse** | Re-parsing a version gives the same segment IDs, with no duplicates. | `test_a_repeated_parse_reuses_the_same_segment_identities_without_duplicates` |
| **F03 corrupt upload** | A corrupt DOCX is refused with 422, leaves no source row, and writes a refusal audit. | `test_a_corrupt_docx_is_refused_with_no_source_row_and_an_audit` |
| **F02 tombstones** | The tombstone table has exactly the specified columns and none for content. | `test_audit_tombstones_have_no_content_columns` |

## 3. EVAL-F status

Key: **COMPLETE** (every pass condition has a test), **PARTIAL** (a pass condition has no test or no
implementation), **BLOCKED** (waits on a decision), **OUT OF SCOPE** (spec-limited, cannot be tested
here).

| Test | Status | Remaining gap (if any) |
|---|---|---|
| EVAL-F01-MATRIX | COMPLETE (caveat) | The oracle is derived from the matrix, so the test checks consistency with it rather than an independent reading. |
| EVAL-F02-CLASS | COMPLETE | Reassessment is Administrator-only, needs a justification and the current source revision, cannot go below the project floor, and is audited with old and new classes (`test_reassessment.py`, 9 tests). Migration 0009 makes the database refuse any direct change to source or version classification (`test_the_database_refuses_a_direct_classification_change`). |
| EVAL-F03-UPLOAD | COMPLETE | — |
| EVAL-F04-LOCATOR | COMPLETE | — |
| EVAL-F05-DTO | COMPLETE (caveat) | Idempotent replay is tested at the service layer, not over HTTP. |
| EVAL-F06-JOBS | COMPLETE (caveat) | Job backoff timing is not asserted. |
| EVAL-F07-CONCURRENCY | COMPLETE | — |
| EVAL-F08-SOT | COMPLETE (scoped) | No resume path exists in Gate 1, so the "checkpoint cannot bypass authorization" rule is satisfied by absence. Revisit if resume is added. |
| EVAL-F09-TRANSITIONS | COMPLETE | — |
| EVAL-F10-STALE | COMPLETE (review item) | The pass condition says "reject altered order". The encoder sorts inputs, so reordering yields the same digest. This is the specified canonical behaviour, and the wording needs WDS confirmation. |
| EVAL-F11-SELFGRANT | COMPLETE | — |
| EVAL-F11b-SELFASSIGN | COMPLETE | — |
| EVAL-F11c-ACTIVATION | COMPLETE | — |
| EVAL-F11d-CONTACT-APPROVAL | COMPLETE (caveat) | The 24-hour expiry runs only when the sweep is invoked. No scheduler exists. |
| EVAL-F11e-TOKEN-RATELIMIT | COMPLETE | — |
| EVAL-F11f-CEREMONY-RECOVERY | COMPLETE (caveat) | The sweep's appointment expiry is tested; the scheduler caveat from F11d applies. |
| EVAL-F11g-CONTACT-OUTBOX | COMPLETE (caveat) | Single send relies on the capture sink honouring the idempotency key. A production provider must be verified to do the same. |
| EVAL-F11h-ADMIN-APPOINTMENT | COMPLETE | — |
| EVAL-F11i-ZERO-ADMIN-OFFLINE-POLICY | OUT OF SCOPE | In-app refusal is tested. The offline path is a specification and cannot be tested here. |
| EVAL-F12-AUDIT | COMPLETE (documented exception) | Every refusal in the services writes a denial audit, each with a test (`test_denial_branches.py`, `test_cli_audit.py`, plus the earlier per-service tests). Installation refusals are audited when a database is configured: the CLI opens the database first and commits `ceremony.install.denied` before exiting (`test_cli_audit.py`, 3 tests). **Documented exception:** with no database URL configured there is no audit log to write to, so that refusal goes to standard error only. |
| EVAL-F13-SNAPSHOT | COMPLETE (caveat) | The itemised failed sources are recorded in the `run.parked` audit payload, which no test reads. |
| EVAL-F14-SOURCE-REPARSE | COMPLETE | — |
| EVAL-F14b-PARSE-ATOMICITY | COMPLETE | — |
| F-CFG-01 (project-local) | COMPLETE | Not registered in the spec (C-6). |
| EVAL-DEPLOYMENT-GATE-001 | **BLOCKED** | Hosting decision D-16 is open. |
| EVAL-LEGACY / later-phase | OUT OF SCOPE | — |

## 4. Summary

| Status | Count |
|---|---|
| COMPLETE (including caveated) | 24 |
| PARTIAL | 0 |
| BLOCKED | 1 (EVAL-DEPLOYMENT-GATE-001) |
| OUT OF SCOPE (spec-limited or later phase) | 3 (F11i, EVAL-LEGACY items, F08 scoped note) |

Items that still stop Gate 1 from being claimed:

1. **EVAL-DEPLOYMENT-GATE-001**: the hosting and egress decision (D-16).

Also still open, although they do not change the status above:

- The 24-hour expiry sweep has no scheduler. It must be run by a job that is not built.
- The outbox key custody decision (C-9) and the password and session placeholders (C-8, confirmed as
  12 characters and 8 hours) are recorded in the deployment checklist, not decided in code.
- EVAL-F10: confirm whether the "reject altered order" wording means a non-sorting encoder must fail,
  which would be a spec change and needs your approval.

## 5. Deviations and decisions

- The owner role in local Docker is a superuser. Production must not use that (C-10).
- A Windows PostgreSQL service occupies port 5432, so Compose publishes on 5433.
- `WEBDESK_STORAGE_ROOT` must be an absolute path (D-7). Without it, intake returns 503.
- Restricted content is quarantined on upload and cannot be parsed, snapshotted or read. No scanner
  exists (D-2).
- Edges in `dependency_edges` are append-only, as the schema requires. Tests build new chains from
  fresh identifiers instead of editing existing edges.

## 6. Not done

- Nothing is committed. The spec baseline and all Increment 1 and 2 work are uncommitted apart from
  `ce76b32`.
- No independent review of any phase has been done.
- Out of scope and not started: LangGraph, specialist agents, LLM, RAG, estimation, SOW generation,
  production deployment.
