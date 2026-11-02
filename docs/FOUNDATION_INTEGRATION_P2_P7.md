# Foundation Phases 2–7 integration record

Branch: `feature/foundation-integration-p2-p7`, created from `feature/foundation-phase-7` at `09d1bdb` (Phases 5 and 6
are ancestors of that commit). Authoritative scope: `docs/INCREMENT_3_HARDENING_PLAN.md`, the phase records named
below, and the integration request in chat. Nothing was pushed, deployed or merged into another branch. This record is
engineering evidence. It is not QA and not WDS acceptance.

## Inputs and recorded status

Only what the phase documents in this repository say. Phases 2, 3, 4 and 6 have no recorded WDS acceptance.

| Phase | Input | Recorded status (source) |
| --- | --- | --- |
| 2 | `feature/foundation-phase-2` at `518ab67` | "PHASE 2 ENGINEERING INCOMPLETE — SPECIFIC BLOCKERS REMAIN" (Blocker A, Windows authority-child start, unresolved; F-09 record missing; independent QA not run on the final SHA). No WDS acceptance (`docs/PHASE2_RECONCILIATION_AND_CLOSURE.md` §7) |
| 3 | `feature/foundation-phase-3` at `6e8f574` | Independent QA "QA PASSED, eligible for WDS acceptance" on `4829386`, not on later commits; final WDS acceptance not given (`docs/PHASE3_GOVERNANCE_RECORD.md`) |
| 4 | `feature/foundation-phase-4` at `178a419` | Engineering evidence only; relayed non-production decisions H-DEC-3 to H-DEC-6 with incomplete provenance; no formal WDS acceptance (`docs/PHASE4_CLOSURE_EVIDENCE.md`, `docs/GOVERNANCE_DECISION_REGISTER.md`) |
| 5 | ancestor of `09d1bdb` | WDS acceptance granted for the standalone X7 scope at `f001b9d` (`docs/PHASE5_X7_QA_CLOSURE.md`) |
| 6 | ancestor of `09d1bdb` | QA PASSED on `9a9e8d3`; WDS formal acceptance PENDING (`docs/PHASE6_X8_ENGINEERING.md`) |
| 7 | `09d1bdb` | WDS acceptance granted for `ae032a2`; F-1 test commit `89d6ef2` (`docs/PHASE7_ENGINEERING.md`) |

Branches that moved after the inputs were fixed (not integrated here): `feature/foundation-phase-3` now ends at
`3065361` (13:02 +0530, after the Phase 3 merge at 12:38), which adds `0055_approval_worker_fence`; and
`feature/foundation-phase-7` now ends at `f189b41` (documentation only). See Remaining gaps.

## Merge commits and conflict resolutions

Each phase was merged with `git merge --no-ff`, one commit per phase. Full resolutions are in each commit message.

| Commit | Phase | Conflicts and resolution |
| --- | --- | --- |
| `74236f8` | 2 (`518ab67`) | `projects/service.py`: both imports (`ProofRefused`, `wrapper_refusal`). `tests/conftest.py`: Phase 2 run namespaces kept; `_drop_when_detached` is an alias of the single guard in `tests/support/db_cleanup.py`, which now counts client backends only (Phase 6 `538ac10`) and says "sessions still attached". `test_source_read_authorization.py`: Phase 2 setup engine (the namespaced hardening database is owned by the integration owner). `RUFF_FORMAT_EXCEPTIONS.md`: only the four frozen migrations remain |
| `c5ce98c` | 3 (`6e8f574`) | `runs/jobs.py`: Phase 3 lease hold, per-step intake, `LeaseLost` and correlation keys, with Phase 7 `project_id` on every run audit; the `job.requeued` event both phases added is written once. `audit/service.py`: `record_worker_event` takes `project_id` and `correlation_id`. `ceremony/install.py`, `recovery.py`, `cli/install.py`: Phase 3 D-3/H-21 database clock (no injected `Clock`) with Phase 7 H-74 operator and verifier binding, `owner_key_invalid` and digest replay refusal, and Phase 6 H-50 pre-insert refusals. Test conftests, `test_projects.py`, `test_install_authorization.py` (Phase 3's D-3 assertion kept, through the H-74 helper). API adaptations: `cli/recover.py`, Phase 6 tests, the Phase 7 replay test and the Phase 2 recovery status test no longer pass a clock and name the now required verifier |
| `ad3f4b6` | 4 (`178a419`) | `.gitignore`: both secrets files. `RUFF_FORMAT_EXCEPTIONS.md`: integrated list kept. The predicted `tests/conftest.py` and `test_source_read_authorization.py` conflicts did not recur (same text after the Phase 2 merge). `api/routes.py` auto-merged: H-60 checks before authorization and the bounded read `MAX_BYTES + 1` |

No test was removed from either side, and no assertion was weakened. `uv.lock` and `pyproject.toml` did not differ
between the branches; the venv was built with `uv sync --frozen --all-extras` (exit 0).

## Migration graph

Heads before the merge revision: `0046_fixed_contact_change_window`, `0049_p7_run_audit_project_id`,
`0054_contact_change_reject_clock`. Heads after: one, `0057_int_expire_change_clock`.

```
0041_ai_read_v1
├── 0042_phase2_identity_controls → 0043_phase2_review_fixes
│   ├── 0044_grant_revocation_lock → 0045_change_expiry_on_demand → 0046_fixed_contact_change_window ─┐
│   └── 0050_durable_execution → … → 0054_contact_change_reject_clock ────────────────────────────────┤
└── 0042_x7_staleness_archive → … → 0049_p7_run_audit_project_id ─────────────────────────────────────┤
                                                       0055_int_merge_p2_p3_p7 ◄────────────────────────┘
                                                       → 0056_int_corr_audit_project → 0057_int_expire_change_clock
```

No revision 0001–0054 was edited, renamed or renumbered; every file is byte-identical to its branch version. In
particular, `0050` keeps `down_revision = 0043_phase2_review_fixes`, instead of the edit proposed in
`docs/PHASE3_MIGRATION_RECONCILIATION.md` and the "one linear chain" in the Phase 7 handoff. The lines redefine no common
function (checked by name across the three lines), so the order in which Alembic applies them does not matter.

| Revision | Down revision | Change | Downgrade |
| --- | --- | --- | --- |
| `0055_int_merge_p2_p3_p7` | the three heads | None (merge point) | None; leaves the three heads |
| `0056_int_corr_audit_project` | 0055 | Replaces the 0052 `fn_worker_record_audit_correlated` with the same eight arguments plus `p_project_id uuid DEFAULT NULL`, written to `audit_events.project_id`. 0052 checks unchanged. Owner `webdesk_guard_owner`, SECURITY DEFINER, `search_path = pg_catalog, public`, EXECUTE to `webdesk_worker` only | Drops it; restores the 0052 text and grants |
| `0057_int_expire_change_clock` | 0056 | Re-issues Phase 2's `fn_expire_stale_change_for_email` with `expires_at <= clock_timestamp()` (was `now()`); CREATE OR REPLACE keeps owner, definer, search path and grants (EXECUTE to `webdesk_app`) | Restores the exact 0045 text |

## Reconciliation changes (separate commits, each with a test)

| Commit | Defect found | Fix | Test |
| --- | --- | --- | --- |
| `021f75c` | Phase 3 tests predated the H-74 artifact fields and the branched history (TypeError; `MultipleResultsFound`) | `test_authorization_expiry.py` signs operator and verifier; `test_migration_cycle.py` expects `{0043, 0049}` after a downgrade to 0043 and migrates its reference to both | the two tests themselves |
| `d055337` | H-70: Phase 3 correlated audits (`run.parked`, `run.failed`, `job.requeued`, `job.reaped`) had no `project_id` | 0056; service passes the project; the reaper reads the run's project | `tests/committed/test_integration_p2_p7.py` (6 tests; 5 fail with the project argument removed) |
| `a8c64a3` | PH3-FC-01 / H-76: Phase 2's on-demand change expiry used transaction-start `now()` | 0057 | committed test with a 2-second window inside one transaction; fails without 0057 |
| `baa0b49` | Phase 2 made `approval_not_pending` a `ProofRefused`; a losing create approval escaped unaudited (Phase 3 race test failed) | `approve_create` maps it to the earlier audited 409 `approval_refused`; change paths keep 409 `not_pending` | deterministic loser test; fails without the fix |
| `020090b` | The per-process authority test login was not dropped at exit: its URL named the namespaced database, already dropped | `tests/support/authority.py` drops it through the `postgres` maintenance database, as the worker login already does | test fails without the fix |

## H-68, H-76 and H-64 on the merged code

| Item | Plan text | Status | Evidence |
| --- | --- | --- | --- |
| H-68 | "Lock order per H-25. The parked-run cancellation question is a governance decision (H-DEC-1). It is not changed here." H-25: "claim and cancel_run both lock job then run. A test with two connections confirms no deadlock." | **Satisfied** | `fn_worker_claim_job` locks the job (`FOR UPDATE SKIP LOCKED`) then updates the run; `fn_cancel_run_with_proof` (0050) locks the run's jobs then the run; the reaper and the worker steps (`fn_worker_hold_lease`, then `fn_worker_lock_run`) take the same order; `runs/service.cancel_run` takes no lock before the guard; no x7 migration redefines these functions. Two-connection test `test_a_cancellation_waits_for_a_claim_without_a_deadlock` passes. H-DEC-1: a parked (`blocked_pending_decision`) run is still cancellable, unchanged (`test_h70_a_parked_run_audits_…` cancels one) |
| H-76 | "One time source (see H-21)." H-21: lease times on `clock_timestamp()`; ceremony deadlines on the same source, not the injected clock (`runs/jobs.py`, `ceremony/install.py`, `ceremony/recovery.py`, `identity/sweep.py`). Relayed ruling PH3-FC-01 extends it to contact-approval liveness | **Satisfied for the H-21 files and PH3-FC-01, with 0057** | Job leases, renewal, hold, finish, requeue, reaper and stuck report use `clock_timestamp()`; install and recovery use `database_now`; no `Clock` remains in `src` (Phase 6 `cli/recover.py` and Phase 7 `prepare_*` were adapted in the Phase 3 merge); sweep uses `clock_timestamp()`. Phase 2's `fn_expire_stale_change_for_email` was the one contact-liveness predicate left on `now()`; 0057 fixes it. Not covered: the outbox lease functions (Remaining gaps) |
| H-64 | "EML HTML bodies and `name=` parts. Per H-DEC-6." | **Partly satisfied** | HTML-only body follows H-DEC-6 as amended (WDS-QA02-RULING, WDS-DECISIONS-2026-10-29): partial beside a subject segment, unsupported with `unextractable_regions` without one (`test_parse_defects.py`, `test_parse_isolation.py`, committed `test_d1_…`). `name=` parts: a part named only by `Content-Type; name=` is reported as an unprocessed attachment with that name (Python's `get_filename` falls back to `name=`), except that a `text/plain` part with `name=` and no `Content-Disposition` that is the first plain part is extracted as the body. No ruling or test defines `name=` handling. Needs a WDS rule before any change |

## Test cluster

Container `webdesk-int-postgres`, `127.0.0.1:5486`, PostgreSQL 16.4, system identifier `7703463813966012454`.
Bootstrap: `C:/Users/baps/.webdesk-int/bootstrap_int.sh` (outside the repository), adapted from the Phase 7 QA template:
database names, a port and container guard, CRLF-safe secrets reading, and the Phase 2 grant
`GRANT webdesk_test_clock TO webdesk_integration_owner WITH INHERIT TRUE, SET TRUE` (QA D2). No application role is a
superuser or object owner. The first attempt failed on the CRLF password file; the roles and databases it had created
were dropped and the fixed script was run once on the clean cluster (exit 0).

## Engineering gate

Code HEAD `020090b`. This record is the only later commit.

| Check | Command | Result | Exit |
| --- | --- | --- | --- |
| Full suite, first run (`ef55153`) | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 11 failed, 972 passed, 0 skipped; found the defects above | 1 |
| Full suite (`020090b`) | same | **990 passed, 2 failed, 0 skipped** (992 collected), 12 min 28 s | 1 |
| Lint | `ruff check src tests migrations` (0.6.9) | all checks passed | 0 |
| Format | `ruff format --check src tests migrations` | 4 files: the four frozen migrations in `docs/RUFF_FORMAT_EXCEPTIONS.md`; 240 formatted | 1 (exceptions only) |
| Types | `mypy --strict src/webdesk` (1.11.2) | no issues in 71 files | 0 |
| Migrations, fresh scratch databases | empty → head; −1 → head; down to the three heads → head | each step ok; one head `0057`; catalog after −1/+1 and after the three-head round trip identical to head; three-head state identical to a fresh upgrade to the three heads; 88 `webdesk_guard` functions, none with PUBLIC EXECUTE; scratch databases dropped | 0 |
| Privilege audit | `pytest tests/hardening/test_privilege_audit.py` | 17 passed | 0 |

The two failures have one cause:

1. `tests/committed/test_migration_catalog.py::test_a_multi_step_downgrade_to_0041_and_reupgrade_reproduce_the_head_catalog`
   (Phase 2): after a downgrade to 0041, `fn_start_run_with_proof` differs from a fresh 0041 by one SQL comment line. The
   `0042_x7_staleness_archive` downgrade restores the 0030 function without the comment
   `-- The latest non-superseded version per source, …`. Confirmed by a reverted local experiment: with only that line
   added to the 0042_x7 downgrade text, the test passes. No earlier line ran a downgrade below 0042_x7, so the defect was
   latent. It cannot be fixed without editing an accepted migration.
2. `tests/committed/test_migration_cycle.py::test_the_0050_downgrade_…` (Phase 3) fails only after (1): the 0046
   downgrade drops the cluster-wide role `webdesk_test_clock`, and (1) stops before re-upgrading, so the head catalog of
   (2) lacks the role. Run alone, (2) passes.

## Remaining gaps and open questions

- **Open (WDS):** the 0042_x7 downgrade comment (gate failure 1). Options: a governance exception to add the comment line
  to the frozen migration, or a ruling on whether comment-only differences count in the Phase 2 catalog test.
- **Not integrated:** Phase 3 `3065361` (QA F-A and F-5). Its `0055_approval_worker_fence` drops and recreates
  `fn_worker_mark_inputs_changed`, which Phase 7 `0049` also redefines (H-70 stale-mark audit), and it shares the `0055`
  prefix with the merge revision here (distinct IDs). Integrating it needs a new reconciliation. Phase 5 Finding 5 stays
  open in this candidate.
- Test-cluster hygiene: the 0046 downgrade drops `webdesk_test_clock` cluster-wide. Each downgrade test removes the
  bootstrap grant's INHERIT and SET options; the role is recreated with an ADMIN-only membership. Re-grant before a run.
- H-76: the outbox lease functions (`fn_outbox_claim`, `fn_outbox_renew`, `fn_outbox_retry`, `fn_outbox_mark_sent`)
  still use `now()`. Neither line changed them (Phase 6 assigned outbox lease semantics to Phase 3). Not in this scope.
- H-64 `name=` handling: no ruling (see above).
- P4 D-P4 (lease ordering): `PARSER_TIMEOUT_SECONDS` 30 s is below the 120 s lease, and the Phase 3 heartbeat renews the
  lease while a parse step runs. Not separately tested.
- The losing create approval returns 409 `approval_refused` (pre-Phase 2 behaviour). WDS may prefer Phase 2's
  `not_pending` wording. `reject_create` and `cancel_change` now raise `ProofRefused` on a lost race, where they raised a
  raw database error before; no test covers them.
- Phase 7 F-2 to F-8, Phase 6 informational items and Phase 2 Blocker A are unchanged.
- Independent QA of this candidate and any acceptance are outstanding.
