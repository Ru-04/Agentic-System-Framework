# Foundation Phases 2–7 integration record

Branch: `feature/foundation-integration-p2-p7`, created from `feature/foundation-phase-7` at `09d1bdb` (Phases 5 and 6
are ancestors of that commit). Authoritative scope: `docs/INCREMENT_3_HARDENING_PLAN.md`, the phase records named
below, and the integration requests in chat. Nothing was pushed, deployed or merged into another branch. This record
is engineering evidence. It is not QA and not WDS acceptance.

## Inputs and recorded status

Two rounds. Round 1 merged the tips first given; round 2 merged the tips recorded at 07:59:53 UTC on 2 November 2026.
The status column holds only what the phase documents in this repository say. Phases 2, 3, 4 and 6 have no recorded
WDS acceptance.

| Phase | Round 1 | Round 2 | Recorded status (source) |
| --- | --- | --- | --- |
| 2 | `518ab67` | unchanged | "PHASE 2 ENGINEERING INCOMPLETE — SPECIFIC BLOCKERS REMAIN" (Blocker A unresolved; F-09 record missing; independent QA not run on the final SHA). No WDS acceptance (`docs/PHASE2_RECONCILIATION_AND_CLOSURE.md` §7) |
| 3 | `6e8f574` | `c6c5325` (`3065361` F-A and F-5; `c6c5325` docs) | QA PASSED on `4829386`, not on later commits; final WDS acceptance not given (`docs/PHASE3_GOVERNANCE_RECORD.md`) |
| 4 | `178a419` | `ee4d3b9` (QA remediation `ba710ee`, `6c53aa8`, `c42b9d7`, `ee4d3b9`) | Engineering evidence; relayed non-production decisions H-DEC-3 to H-DEC-6 with incomplete provenance; no formal WDS acceptance (`docs/PHASE4_CLOSURE_EVIDENCE.md`, `docs/GOVERNANCE_DECISION_REGISTER.md`) |
| 5 | ancestor of `09d1bdb` | unchanged | WDS acceptance granted for the standalone X7 scope at `f001b9d` (`docs/PHASE5_X7_QA_CLOSURE.md`) |
| 6 | ancestor of `09d1bdb` | unchanged | QA PASSED on `9a9e8d3`; WDS formal acceptance PENDING (`docs/PHASE6_X8_ENGINEERING.md`) |
| 7 | `09d1bdb` | `f189b41` (docs: post-QA delta review of `89d6ef2`) | WDS acceptance granted for `ae032a2`; F-1 test `89d6ef2` (`docs/PHASE7_ENGINEERING.md`) |

Branches that moved after the round-2 SHAs were recorded (not integrated):

| Branch | Newer tip | Content |
| --- | --- | --- |
| `feature/foundation-phase-3` | `50f3e40` (13:34 +0530) | Documentation: independent technical QA pass for `3065361` |
| `feature/foundation-phase-4` | `b604e7b` (13:30 +0530), then `d91513c` (13:52 +0530) | Lint and strict typing for the remediation (fixes the ruff and mypy findings below); remediation record |

## WDS rulings applied

Rulings given by WDS in chat on 2 November 2026, as relayed by the coordinator. No approver identity, signature or other
timestamp is recorded here.

| Ruling | Subject | Applied in |
| --- | --- | --- |
| "Ignore comments in test" | Comment-only differences in function definitions are acceptable | `478606a`: the Phase 2 catalog test compares function definitions without `--` and `/* */` comments; everything else exactly. No migration edited |
| "Treat as attachment" | H-64: a part with a Content-Type `name=` parameter is an attachment, never the body | `9628f4d`: Phase 4 EML parser |
| "Keep approval_refused" | A losing create approval keeps 409 `approval_refused`; no behaviour change | `baa0b49` unchanged; `fc53073` pins the lost-race outcome of `reject_create` and `cancel_change` |

## Merge commits and conflict resolutions

Each phase tip was merged with `git merge --no-ff`, one commit per phase per round. Full resolutions are in each commit
message.

| Commit | Merge | Conflicts and resolution |
| --- | --- | --- |
| `74236f8` | Phase 2 `518ab67` | `projects/service.py`: both imports. `tests/conftest.py`: Phase 2 run namespaces; `_drop_when_detached` is an alias of the guard in `tests/support/db_cleanup.py`, which counts client backends only (Phase 6 `538ac10`). `test_source_read_authorization.py`: Phase 2 setup engine. `RUFF_FORMAT_EXCEPTIONS.md`: four frozen migrations |
| `c5ce98c` | Phase 3 `6e8f574` | `runs/jobs.py`: Phase 3 lease hold, per-step intake, `LeaseLost`, correlation, with Phase 7 `project_id` on every run audit; `job.requeued` written once. `audit/service.py`: `project_id` and `correlation_id`. Ceremony and install CLI: Phase 3 database clock (no `Clock`) with Phase 7 H-74 and Phase 6 H-50. Clock-free API adaptations in Phase 6 and Phase 2 tests and the Phase 7 replay test |
| `ad3f4b6` | Phase 4 `178a419` | `.gitignore`: both secrets files. Ruff doc: integrated list |
| `7760b75` | Phase 3 `c6c5325` | No textual conflict. `runs/jobs.py` calls the fenced `fn_worker_mark_inputs_changed(job, owner)` and raises `LeaseLost` on refusal. SQL overlap with Phase 7 `0049` reconciled by `0059` |
| `6987406` | Phase 4 `ee4d3b9` | `api/routes.py`: Phase 4 streaming `_bounded_form(request, limit)` (F-2) replaces Phase 7's buffering version; one limit `MAX_UPLOAD_REQUEST_BYTES = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES` (20 MiB + 1 MiB, the same value on both sides); Phase 7 H-61 allowlist and H-66 refusal kept. Merged by the recorded SHA. A first attempt merged the branch name after it had moved to `b604e7b`; that local, unpushed merge was reset away and redone at `ee4d3b9` |
| `a18e355` | Phase 7 `f189b41` | Documentation only |

No test was removed from either side. `uv.lock` and `pyproject.toml` did not differ between the branches; the venv was
built with `uv sync --frozen --all-extras` (exit 0).

## Migration graph

Heads before round 1: `0046_fixed_contact_change_window`, `0049_p7_run_audit_project_id`,
`0054_contact_change_reject_clock`. After round 1: `0057_int_expire_change_clock`. After the round-2 Phase 3 merge:
`0055_approval_worker_fence` and `0057_int_expire_change_clock`. Now: one head, `0059_int_mark_inputs_fence`.

```
0041_ai_read_v1
├── 0042_phase2_identity_controls → 0043_phase2_review_fixes
│   ├── 0044_grant_revocation_lock → 0045 → 0046_fixed_contact_change_window ───────────┐
│   └── 0050_durable_execution → … → 0054_contact_change_reject_clock ──────────────────┤
│                                     └── 0055_approval_worker_fence ───────────────┐   │
└── 0042_x7_staleness_archive → … → 0049_p7_run_audit_project_id ───────────────────┼───┤
                          0055_int_merge_p2_p3_p7 ◄─────────────────────────────────┼───┘
                          → 0056_int_corr_audit_project → 0057_int_expire_change_clock
                          → 0058_int_merge_p3_fence ◄───────────────────────────────┘
                          → 0059_int_mark_inputs_fence
```

No revision 0001–0054 and no `0055_approval_worker_fence` was edited, renamed or renumbered; each is byte-identical to
its branch version. `0055_approval_worker_fence` and `0055_int_merge_p2_p3_p7` share the 0055 prefix with different
revision IDs. Alembic applies this history with the Phase 5–7 line before `0055_approval_worker_fence`, both on a fresh
database and from `0057`.

| Revision | Down revision | Change | Downgrade |
| --- | --- | --- | --- |
| `0055_int_merge_p2_p3_p7` | 0046, 0049, 0054 | None (merge point) | None |
| `0056_int_corr_audit_project` | 0055_int | `fn_worker_record_audit_correlated` gains `p_project_id uuid DEFAULT NULL` (written to `audit_events.project_id`); 0052 checks unchanged; EXECUTE to `webdesk_worker` only | Restores the 0052 text and grants |
| `0057_int_expire_change_clock` | 0056 | Phase 2 `fn_expire_stale_change_for_email` on `clock_timestamp()` (PH3-FC-01); grants kept (EXECUTE to `webdesk_app`) | Restores the 0045 text |
| `0058_int_merge_p3_fence` | `0055_approval_worker_fence`, 0057 | None (merge point) | None |
| `0059_int_mark_inputs_fence` | 0058 | `fn_worker_mark_inputs_changed(job, owner)` with both safeguards: the Phase 3 lease and owner fence (job KEY SHARE before the run) and the Phase 5 first mark audited as `run.stale_marked` with the run's project (Phase 7 H-70); `DROP FUNCTION IF EXISTS` of a one-argument overload. Grants of the replaced function: EXECUTE to `webdesk_worker` only | Restores the `0055_approval_worker_fence` text and grants |

All new functions are SECURITY DEFINER, owned by `webdesk_guard_owner`, with `search_path = pg_catalog, public` and no
PUBLIC EXECUTE.

## Reconciliation changes (separate commits, each with a test)

| Commit | Defect | Fix | Test |
| --- | --- | --- | --- |
| `021f75c` | Phase 3 tests predated H-74 artifacts and the branched history | Test adaptations (operator and verifier signed; downgrade to 0043 leaves `{0043, 0049}`) | the two tests |
| `d055337` | H-70: Phase 3 correlated audits had no `project_id` | 0056; service and reaper pass the project | `test_integration_p2_p7.py` (5 of 6 fail without) |
| `a8c64a3` | PH3-FC-01 / H-76: Phase 2 on-demand change expiry used `now()` | 0057 | fails without 0057 |
| `baa0b49` | A losing create approval escaped as an unaudited `ProofRefused` | maps to the earlier audited 409 `approval_refused` | fails without the fix |
| `020090b` | Authority test login leaked after namespaced databases were dropped | cleanup through the `postgres` database | fails without the fix |
| `607b292` | Phase 3 `0055` dropped Phase 7's audited stale mark; the H-70 parked-run test lost `run.stale_marked` | 0059 | holder/non-holder and signature tests; without 0059 the holder test and the Phase 7 H-70 test fail |
| `478606a` | Ruling "Ignore comments in test" | catalog test strips SQL comments | bite check: changing `'queued'` to `'blocked'` (or adding one space) in the body restored by the 0042_x7 downgrade fails the test; reverted |
| `9628f4d` | Ruling "Treat as attachment" (H-64) | named parts are attachments, never the body | `tests/unit/test_eml_named_parts.py` (6); 4 fail with the `name=` check disabled |
| `fc53073` | Ruling "Keep approval_refused" | none (behaviour pinned) | real two-connection races (Phase 2 `_race` helper): `reject_create` and `cancel_change` losers raise `ProofRefused("approval_not_pending")` with one committed `authority.proof.refused` audit |

## H-68, H-76, H-64 and Finding 5 on the merged code

| Item | Status | Evidence |
| --- | --- | --- |
| H-68 (lock order per H-25; H-DEC-1 cancel rule unchanged) | **Satisfied** | Claim, cancel (0050), reaper and worker steps lock job then run; `runs/service.cancel_run` takes no lock first; 0059 keeps job KEY SHARE before the run. `test_a_cancellation_waits_for_a_claim_without_a_deadlock` passes. A parked run is still cancellable (H-DEC-1) |
| H-76 (one time source, H-21; PH3-FC-01) | **Satisfied for the H-21 files and PH3-FC-01** | Leases, renewal, hold, finish, requeue, reaper, stuck report and the 0059 fence use `clock_timestamp()`; ceremonies use `database_now`; no `Clock` in `src`; 0057 for the Phase 2 expiry; Phase 3 `0055` moves the user and role trigger predicates to `clock_timestamp()` (F-A). Outbox leases still use `now()` (gap) |
| H-64 (EML HTML bodies and `name=` parts) | **Satisfied** | HTML-only bodies per the amended H-DEC-6 (Phase 4 tests). `name=` parts per the WDS ruling "Treat as attachment" (`9628f4d`, `tests/unit/test_eml_named_parts.py`) |
| Phase 5 Finding 5 / Phase 3 F-5 (`fn_worker_mark_inputs_changed` fence) | **Closed in the candidate** | Only the fenced `(job, owner)` signature exists at head; a worker that does not hold the lease gets false and nothing changes; the one-argument call is refused (`test_a_worker_cannot_mark_a_run_it_has_not_claimed`, `test_the_claim_holder_marks_its_run_and_a_stale_holder_cannot`, 0059 tests). The H-70 audit is kept |

## Test cluster

Container `webdesk-int-postgres`, `127.0.0.1:5486`, PostgreSQL 16.4, system identifier `7703463813966012454`.
Bootstrap `C:/Users/baps/.webdesk-int/bootstrap_int.sh` (outside the repository), adapted from the Phase 7 QA template:
database names, port and container guard, CRLF-safe secrets reading, and the Phase 2 grant of `webdesk_test_clock` to
the integration owner (QA D2). No application role is a superuser or object owner. Every downgrade test that crosses
`0046` drops and recreates `webdesk_test_clock` cluster-wide, so the grant is re-applied before each run.

## Engineering gate

Code HEAD `fc53073`. This record is the only later commit.

| Check | Command | Result | Exit |
| --- | --- | --- | --- |
| Full suite | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | **1024 passed, 2 failed, 0 skipped** (1026 collected), 12 min 50 s | 1 |
| Lint | `ruff check src tests migrations` (0.6.9) | 7 findings, all in Phase 4 files as merged at `ee4d3b9`: `intake/isolation.py` S101, `intake/parsers.py` S112 and E501 (Phase 4 lines, not the H-64 change), `tests/unit/test_parse_defects.py` I001 and 3 E501. Each file has the same findings at `ee4d3b9` and none at `b604e7b` | 1 |
| Format | `ruff format --check src tests migrations` | The four frozen migrations in `docs/RUFF_FORMAT_EXCEPTIONS.md`, and `tests/unit/test_parse_defects.py` (Phase 4, `ee4d3b9`) | 1 |
| Types | `mypy --strict src/webdesk` (1.11.2) | 1 error: `intake/isolation.py:106` `IO[Any]` has no `read1` (Phase 4, `ee4d3b9`; addressed in `b604e7b`) | 1 |
| Migrations, fresh scratch databases | empty → head; −1 → head; down to the two heads before 0058 → head; down to `0046`, `0049`, `0055_approval_worker_fence` → head; out-of-order upgrade | Single head `0059`; each step ok; each downgraded state identical to a fresh upgrade to the same heads (in Alembic's order), each re-upgrade identical to head and to a second fresh head; 88 `webdesk_guard` functions, none with PUBLIC EXECUTE. Upgrading `0055_approval_worker_fence` before `0049` leaves an unfenced one-argument function with PUBLIC EXECUTE until head; 0059 removes it | 0 |
| Privilege audit | `pytest tests/hardening/test_privilege_audit.py` | 17 passed | 0 |

The Phase 2 catalog test (`test_migration_catalog`) now passes in the full suite under the comment ruling. The two
failures:

1. `tests/committed/test_migration_cycle.py::test_the_0050_downgrade_to_0043_and_reupgrade_reproduce_the_head_catalog`
   (Phase 3). New in round 2, caused by the Phase 3 tip together with Phase 7, not by an integration revision. A
   downgrade to 0043 runs the `0055_approval_worker_fence` downgrade, which restores the one-argument
   `fn_worker_mark_inputs_changed` with its Phase 3 branch text (`WHERE run_id = p_run`, no first-mark condition, no
   audit). The Phase 5–7 line stays at `0049`, whose text is the audited one, so the downgraded catalog differs from a
   fresh 0043 + 0049 in that one function. Shown on scratch databases: head → down to 0043 gives the Phase 3 text; a
   fresh 0043 + 0049 gives the 0049 text. The 0059 downgrade restores the 0055 text exactly; the difference comes from
   the frozen `0055` downgrade. Not fixable without editing `0055_approval_worker_fence`.
2. `tests/hardening/test_contact_change_window.py::test_the_application_login_cannot_shorten_the_change_window`: a
   knock-on of (1). The cycle test stops after the `0046` downgrade has dropped `webdesk_test_clock` and before
   re-upgrading, so this test sees SQLSTATE 42704. Run after the role is restored, it passes (with
   `test_migration_catalog`, 3 passed).

## Remaining gaps and open questions

- **Open (WDS or Phase 3 owner):** the `0055_approval_worker_fence` downgrade text in the merged history (gate failure 1).
  Options: a governance exception to change that downgrade, or a ruling for the Phase 3 cycle test. The cycle test was
  not relaxed.
- **Open (Phase 4 tip):** the ruff and mypy findings of `ee4d3b9` are fixed on `b604e7b`, which moved after the SHA was
  recorded; `d91513c` followed. Not integrated, as instructed.
- **Not integrated:** Phase 3 `50f3e40` (documentation).
- An out-of-order upgrade (Phase 3 `0055` applied before `0049`) briefly creates an unfenced, PUBLIC-executable
  one-argument mark function; 0059 drops it. Alembic's order for this history does not do this.
- Test-cluster hygiene: downgrade tests drop `webdesk_test_clock` cluster-wide; the grant has to be re-applied.
- H-76: the outbox lease functions (`fn_outbox_claim`, `fn_outbox_renew`, `fn_outbox_retry`, `fn_outbox_mark_sent`)
  still use `now()`. Not in this scope.
- Phase 4 D-P4: the 30 s parser timeout is below the 120 s lease and the Phase 3 heartbeat renews during a parse step;
  not separately tested.
- Phase 7 F-2 to F-8, Phase 6 informational items and Phase 2 Blocker A are unchanged.
- Independent QA of this candidate and any acceptance are outstanding.
