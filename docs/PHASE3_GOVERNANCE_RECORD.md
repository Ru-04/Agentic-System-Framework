# Phase 3 final correction: governance record

This record documents the WDS authorization communicated in the user conversation on 29 October 2026, and the
engineering decisions that implement it. It separates **implementation authorization** from **final WDS acceptance**.
Implementation authorization does not accept Phase 3. Final acceptance remains a WDS decision.

## Authorization as communicated

- Title: "Foundation Phase 3 final closure. Formal WDS Authorization, 29 October 2026."
- Scope: complete the final engineering correction, governance documentation, complete verification and independent QA
  handoff in one sprint, without reopening completed architecture.
- Stated limits: it does not waive security, independent QA, migration governance or formal acceptance evidence.
- Rulings in the authorization:
  1. H-76's authoritative database-time requirement applies to contact-approval liveness in `identity/contacts.py`.
     Correct the affected predicates to `clock_timestamp()`. Preserve the lock order and the denial audit, and do not
     widen privilege. Use a new additive migration after `0052` if a deployed routine changes. (Finding F-2.)
  2. Heartbeat scheduling: the worker may schedule renewal attempts at a nominal 30-second interval using a monotonic
     elapsed-time clock. PostgreSQL is authoritative for lease expiry, ownership, renewal timestamps, stale-worker
     fencing and reclaim eligibility.
  3. F-3: accept that the renewal/fencing race test alone does not detect fence removal, because another dedicated test
     does. Retain the mutation test. Improve coverage if it can be done without changing production behaviour.
  4. F-4: accept that a hard-killed test process may leave its per-process worker login behind. Document a safe cleanup
     procedure. Normal completion must still clean up.

## Decision records

The identifiers below are **engineering record labels assigned in this repository**. They are not WDS-issued decision
identifiers. WDS must assign or confirm its own identifiers.

| Label | Subject | Decision text (as communicated) | Applicable requirements |
|---|---|---|---|
| PH3-FC-01 | Contact-approval liveness on the database clock | H-76 applies to contact-approval liveness. Use `clock_timestamp()` in the affected predicates (migration `0053`). | H-21, H-76, finding F-2 |
| PH3-FC-02 | Heartbeat scheduling | Nominal 30-second scheduling on a monotonic clock; PostgreSQL authoritative for expiry, ownership, renewal timestamps, fencing and reclaim. | H-22 |
| PH3-FC-03 | Fence-removal coverage | Accepted limitation of the race test; a dedicated deterministic test is added; the mutation test is retained. | Finding F-3 |
| PH3-FC-04 | Test-login cleanup | Accepted limitation for hard-killed test processes; a documented, ownership-aware purge procedure is provided. | Finding F-4 |

## Baseline and resulting implementation

- Reviewed baseline (independently reviewed by a fresh QA agent; the run is dated 2026-10-28 by the machine clock,
  verdict "QA PASSED, eligible for WDS acceptance"): `4829386`. That QA verdict does not cover later changes.
- Implementation commits on top of the baseline:
  - `e3c2929`: PH3-FC-01. Migration `0053_contact_approval_clock` and the Python predicates in `identity/contacts.py`
    and `tokens/service.py`, with the nine-test F-2 suite.
  - `60f6cc5`: PH3-FC-02 wording, PH3-FC-03 deterministic fence test and delayed-renewal test, PH3-FC-04 cleanup
    procedure and tests, and the real restricted-login G-7 tests.
  - `969f610`: migration `0054` (contact change rejection routine, missed by 0053).
  - `db844ed`: correction of the `0053` downgrade text to the live pre-0053 catalog (branch-local; unaccepted, unpushed).
  - The documentation commit that follows (this record, the matrix, the handoff).
- Specification version: v0.3.10 with amendments A1 and A2, as cited by the Phase 1 and Phase 3 handoffs. The authorization
  rulings are not part of the v0.3.10 text; they are recorded here as the WDS authorization of 29 October 2026.

## Artifact hash

- `migrations/versions/0053_contact_approval_clock.py`, SHA-256
  `cab2f6dccf29ae90a187a5476dcda62e21c1ce7474567d27ad24386e668510b7` (as committed in `e3c2929`).

## Verification evidence

See `docs/PHASE3_DECISION_EVIDENCE.md` (sections 8 to 10) and `docs/PHASE3_ENGINEERING_EVIDENCE.md` for the test commands,
totals, exit codes, timestamps and teardown results. The QA re-test package is `docs/PHASE3_QA_RETEST_DELTA.md`.

## Fields that require administrative attestation

These fields are not available to the implementing agent. They are not filled in and must not be inferred.

- **Approver legal name and account identifier**: requires administrative attestation.
- **Authenticated approval reference or approval-channel identifier**: requires administrative attestation.
- **Digital signature or approval link**: none exists in this record, and none has been created. Requires administrative
  attestation.
- **Time of day of the approval**: not stated in the directive. The machine clock is not used as evidence. The
  directive names the timezone as Asia/Kolkata and the date as 29 October 2026. Requires administrative attestation of the
  time of day.
- **Prior retroactive authorizations**: none is claimed.

## What this record does not decide

- Final WDS acceptance of Phase 3.
- The WDS-assigned decision identifiers (replacing the PH3-FC labels).
- The production transport, production credentials and deployment process configuration, which remain separately
  classified dependencies.

## Directive of 29 October 2026 (Asia/Kolkata): decisions as approved

- Source of the authorization: the user message in this conversation that opens "WDS, Foundation Phase 3 final completion
  directive", stating "WDS authorization: formally approved" and the timezone Asia/Kolkata. No signed document, approval
  link or external reference was supplied. The agent does not hold any authenticated approval channel.
- Approver identity: not stated in the directive. Requires administrative attestation.

| Decision | Exact wording as approved | Record label (engineering, not WDS-issued) |
|---|---|---|
| F-2 / H-76 | Contact-approval liveness must be based on PostgreSQL wall-clock time using `clock_timestamp()`, not transaction-start `now()`. | PH3-FC-01 (see `0053`, `0054`) |
| Heartbeat | The worker may use monotonic elapsed time to schedule nominal 30-second renewal attempts. PostgreSQL remains authoritative for lease ownership, expiry, renewal timestamps and stale-worker fencing. | PH3-FC-02 |
| F-3 | Accept the limited renewal/fencing race-test mutation coverage because another mandatory test detects removal of the step fence. Retain the detecting test. | PH3-FC-03 |
| F-4 | Accept the test-only hard-kill login-cleanup residual, subject to documented ownership-safe cleanup and normal-exit cleanup. | PH3-FC-04 |
| Production transport and credentials | Remain deployment or later-phase dependencies. | Classification (no decision identifier) |
| Cross-phase integration | Remains separately gated. No Phase 2 or Phase 4 merge is authorized by this directive. | Gate (no decision identifier) |

## Migration artifacts (SHA-256 of files as committed)

- `migrations/versions/0053_contact_approval_clock.py` at commit `db844ed` (downgrade corrected): `cab2f6dccf29ae90a187a5476dcda62e21c1ce7474567d27ad24386e668510b7`
- `migrations/versions/0054_contact_change_reject_clock.py` at commit `969f610`: `f8e0d3c3483f5d26683c682e161974fcd876f01581ddf71878f5334bf701977f`

## Status at closure of the final verification (29 October 2026)

- Implementation (tested): `db844ed`. Full regression on `db844ed`: 744 passed, 0 failed, 0 errors, 0 skipped
  (9 min 33 s, server 127.0.0.1:5440, system identifier 7701670125748215847, PostgreSQL 16.4). The background
  wrapper did not record the process exit code; the summary line has no failures or errors.
- Decisions PH3-FC-01 to PH3-FC-04 are recorded as communicated. They are implemented and verified as stated above.
- Still outstanding (requires administrative attestation; not available to the agent): the approver's identity and
  account identifier, any signature or approval link, the time of day of the approval (the timezone Asia/Kolkata is as
  stated in the directive), and WDS-assigned decision identifiers replacing the PH3-FC labels.
- Final WDS acceptance is not part of this record and has not been granted.

## Closure status (2 November 2026)

- Technical status: Phase 3 is complete on `feature/foundation-phase-3` at commit `3065361` (migration `0055_approval_worker_fence`,
  after `6e8f574`). Developer full regression on `3065361`: 747 passed, 0 failed, exit code 0, 9 min 24 s. Ruff check, the format
  check on the changed files, and strict mypy on `src/webdesk` pass.
- Findings closed in this remediation: F-A (approval triggers `webdesk_users_guard` and `webdesk_role_guard` on the database clock,
  under PH3-FC-01) and F-5 (`fn_worker_mark_inputs_changed` fenced by the caller's unexpired lease).
- Independent QA: the separate re-test of `3065361` was incomplete when this record was written. Its F-3 mutation rerun,
  its own full regression exit code, its ruff and mypy runs, and cluster teardown were pending. Its partial report is
  `phase3-indep-qa-report-3065361.md` in the shared notes folder. It is not a PASS verdict.
- A separate QA review was also carried out by the project owner, who reports no issues found. That review is recorded as
  reported. It is not an independent verdict and it does not replace the re-test above. The reviewer's identity and method are
  not recorded here, because they were not supplied.
- WDS formal acceptance: not granted. The attestation fields in "Fields that require administrative attestation" are still
  outstanding and are not filled in.
