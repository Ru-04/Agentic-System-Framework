# Phase 4 dependency register

Branch `feature/foundation-phase-4`. Base `46e0e14`. These items are not Phase 4 work. Each either blocks an
acceptance step or must be reconciled before merge.

| ID | Dependency | State on this branch | Needed for | Action owner | Action |
|---|---|---|---|---|---|
| D-P2 | Phase 2 remediation (uncommitted in its worktree): migrations `0044_grant_revocation_lock`, `0045_change_expiry_on_demand` | Not on this branch. Phase 4 does not use them. | Phase 2 acceptance, and any merge that touches the migration chain | Phase 2 owner | Commit in its worktree, then reconcile per `docs/PHASE3_MIGRATION_RECONCILIATION.md` |
| D-P3 | Phase 3 durable execution (committed `e9d888a` on `feature/foundation-phase-3`; migration `0050_durable_execution`) | Not merged. Phase 4 has no code dependency on it. | Phase 3 acceptance; the intake job's lease and reaper | Phase 3 owner | Merge only after WDS review. Its `down_revision` must move to the Phase 2 head when Phase 2 commits. |
| D-P4 | Isolated parse uses the job lease for its time bound | `PARSER_TIMEOUT_SECONDS` (30 s) is below the 120 s lease. The lease is the Phase 3 mechanism, not present here. | Crash recovery of a job whose parser was killed | Phase 3 owner | Confirm the lease ordering when D-P3 merges |
| D-H3 | H-DEC-3 numeric limits | Proposed values in `limits.py` | Acceptance of H-31 | WDS | Approve or replace each value (see `PHASE4_H_DEC_LIMITS_REGISTER.md`) |
| D-H4 | H-DEC-4 Windows memory cap | Not enforced on Windows. The timeout and the input size pre-check are the bounds. | Acceptance of H-32 on Windows | WDS | Choose: job object, or the current bounds |
| D-H5 | H-DEC-5 DOCX table locator fields | Proposed default in use: extension of `docx_paragraph` | Acceptance of H-33 | WDS | Confirm or replace |
| D-H6 | H-DEC-6 HTML-only email | Proposed default in use: reported as unextractable, `partial` | Acceptance of H-33 | WDS | Confirm or replace |
| D-H7 | EML character offsets: offsets into what | Not implemented | Acceptance of H-33 | WDS | Define the offset basis |
| D-H8 | Migration `0013` (plan) versus this branch | `0013` does not exist here; no migration was added | Acceptance of H-33 | WDS, Phase 4 owner | Confirm that the locator CHECK needs no change for the agreed fields |
| D-H9 | Numbering of Phase 4 migrations | None added | Avoiding collision with Phase 2 `0044`/`0045` and Phase 3 `0050` | Phase 4 owner | None while no migration is added |
| D-H10 | F-3 DOCX text boxes and headers/footers (default: text boxes extracted with `{paragraph_index, textbox_index}`; headers and footers flagged, not extracted) | In code on the QA remediation commits | Acceptance of H-33 | WDS | Confirm or replace the default (`PHASE4_PDF_CONTAINMENT.md` section 10) |
| D-H11 | F-4 replacement-only text (default: no segment; page flagged) | In code | Acceptance of D3 | WDS | Confirm or replace the default |
| D-H12 | F-5 admission per-page bound (default: refuse at admission with `pdf_stream_limit`) and the page-count limit, which admission still does not apply | In code for the per-page bound; page count not applied at admission | Acceptance of QA-05 and D4 | WDS | Confirm the per-page default; rule on the page-count limit |
| D-H13 | Images on pages with text: neither flagged nor OCRed | Not changed | Acceptance of H-33 | WDS | Rule whether such a page must be flagged |
| D-H14 | F-2 upload request bound `MAX_UPLOAD_REQUEST_BYTES` (21 MiB) and its reliance on Starlette 0.41.3 `Request.receive` and `Request.form()` | In code; the bound is counted in the route's receive wrapper | Acceptance of D5 | WDS for the value; the Phase 4 owner for the Starlette pin | Confirm the value. Re-test the bound on any Starlette or FastAPI upgrade (`pyproject.toml` pins fastapi 0.115.4). |

## Mechanisms that rely on library internals

- **Starlette 0.41.3 (via FastAPI 0.115.4).** `api/routes.py` `_bounded_form` wraps `request.receive` and builds a new
  `Request` from the same scope to parse the form. This relies on `Request.receive`, `Request.stream()` and
  `Request.form()` behaving as they do in 0.41.3. Its tests (`tests/unit/test_upload_body_bound.py`,
  `tests/committed/test_http_intake.py`) fail if the behaviour changes.

## Out of scope for this branch

- AI result writes: not implemented, as the sprint requires.
- Phase 5: not started.
- Merges, pushes and deployments: none performed.
