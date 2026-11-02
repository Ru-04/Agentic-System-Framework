# Foundation Phases 2–7 integration record

Branch: `feature/foundation-integration-p2-p7`, created from `feature/foundation-phase-7` at `09d1bdb` (Phases 5 and 6
are ancestors of that commit). Authoritative scope: `docs/INCREMENT_3_HARDENING_PLAN.md`, the phase records named
below, and the integration requests in chat. Nothing was pushed, deployed or merged into another branch. This record
is engineering evidence. It is not QA and not WDS acceptance.

## Inputs and recorded status

Three rounds. Every tip from round 2 onward was merged by SHA, after checking that the branch still pointed at it. The
status column holds only what the phase documents in this repository say. Phases 2, 3, 4 and 6 have no recorded WDS
acceptance.

| Phase | Round 1 | Round 2 | Round 3 (final input) | Recorded status (source) |
| --- | --- | --- | --- | --- |
| 2 | `518ab67` | — | `518ab67` | "PHASE 2 ENGINEERING INCOMPLETE — SPECIFIC BLOCKERS REMAIN" (Blocker A unresolved; F-09 record missing; independent QA not run on the final SHA). No WDS acceptance (`docs/PHASE2_RECONCILIATION_AND_CLOSURE.md` §7) |
| 3 | `6e8f574` | `c6c5325` (`3065361` F-A and F-5) | `50f3e40` (docs: independent technical QA pass for `3065361`) | QA PASSED on `4829386`; the QA pass for `3065361` is recorded at `50f3e40`; final WDS acceptance not given (`docs/PHASE3_GOVERNANCE_RECORD.md`) |
| 4 | `178a419` | `ee4d3b9` (QA remediation) | `d91513c` (`b604e7b` lint and typing; remediation record) | Engineering evidence; relayed non-production decisions H-DEC-3 to H-DEC-6 with incomplete provenance; no formal WDS acceptance (`docs/PHASE4_CLOSURE_EVIDENCE.md`, `docs/PHASE4_QA_REMEDIATION.md`, `docs/GOVERNANCE_DECISION_REGISTER.md`) |
| 5 | ancestor of `09d1bdb` | — | ancestor | WDS acceptance granted for the standalone X7 scope at `f001b9d` (`docs/PHASE5_X7_QA_CLOSURE.md`) |
| 6 | ancestor of `09d1bdb` | — | ancestor | QA PASSED on `9a9e8d3`; WDS formal acceptance PENDING (`docs/PHASE6_X8_ENGINEERING.md`) |
| 7 | `09d1bdb` | `f189b41` (docs) | `f189b41` | WDS acceptance granted for `ae032a2`; F-1 test `89d6ef2`; post-QA delta verified (`docs/PHASE7_ENGINEERING.md`) |

At 08:53 UTC on 2 November 2026 each branch still pointed at its round-3 SHA. No newer tip was seen.

## WDS rulings applied

Rulings given by WDS in chat on 2 November 2026, as relayed by the coordinator. No approver identity, signature or other
timestamp is recorded here.

| # | Ruling | Subject | Applied in |
| --- | --- | --- | --- |
| 1 | "Ignore comments in test" | Comment-only differences in function definitions are acceptable | `478606a`: the Phase 2 catalog test compares function definitions without `--` and `/* */` comments; everything else exactly. No migration edited |
| 2 | "Treat as attachment" | H-64: a part with a Content-Type `name=` parameter is an attachment, never the body | `9628f4d`: Phase 4 EML parser |
| 3 | "Keep approval_refused" | A losing create approval keeps 409 `approval_refused`; no behaviour change | `baa0b49` unchanged; `fc53073` pins the lost-race outcome of `reject_create` and `cancel_change` |
| 4 | "Rollback stops at merge" | Supported rollback runs from head down to the integration merge revisions; downgrading a single phase branch below them is unsupported | `db7d6f1`: the Phase 3 cycle test covers only the supported range. See "Integrated rollback boundary" |
| 5 | "Report as attachment" | QA F-1: a multipart part carrying a Content-Type `name=` (nested, or the message itself) is one unprocessed attachment and its children are not walked | `5cfba55`, `25e22d3` (typing), `6c458c8` (top-level case; size rule limited to named multipart parts). Independent delta reviews: 25e22d3 DELTA FAILED (D-F1, D-F2); 6c458c8 DELTA VERIFIED |

## Integrated rollback boundary (ruling 4)

Supported rollback in the integrated history runs from head (`0059_int_mark_inputs_fence`) down to the integration
merge revisions, `0058_int_merge_p3_fence` and `0055_int_merge_p2_p3_p7`, through the revisions between them (`0057`,
`0056`). At `0055_int_merge_p2_p3_p7` the database holds two version rows, `0055_int_merge_p2_p3_p7` and
`0055_approval_worker_fence`. Every supported state is catalog-identical to a fresh database migrated to the same
revisions, and the re-upgrade is catalog-identical to head (cycle test and migration gate below).

Downgrading any single phase branch below these revisions is unsupported. Known reasons: the frozen
`0055_approval_worker_fence` downgrade restores the one-argument `fn_worker_mark_inputs_changed` with its Phase 3 branch
text while the Phase 5–7 line stays at `0049`, which expects the audited text; and the `0046` downgrade drops the
cluster-wide role `webdesk_test_clock`.

## Merge commits and conflict resolutions

Each phase tip was merged with `git merge --no-ff`, one commit per phase per round. Full resolutions are in each commit
message.

| Commit | Merge | Conflicts and resolution |
| --- | --- | --- |
| `74236f8` | Phase 2 `518ab67` | `projects/service.py`: both imports. `tests/conftest.py`: Phase 2 run namespaces; `_drop_when_detached` is an alias of the guard in `tests/support/db_cleanup.py`, which counts client backends only (Phase 6 `538ac10`). `test_source_read_authorization.py`: Phase 2 setup engine. `RUFF_FORMAT_EXCEPTIONS.md`: four frozen migrations |
| `c5ce98c` | Phase 3 `6e8f574` | `runs/jobs.py`: Phase 3 lease hold, per-step intake, `LeaseLost`, correlation, with Phase 7 `project_id` on every run audit; `job.requeued` written once. `audit/service.py`: `project_id` and `correlation_id`. Ceremony and install CLI: Phase 3 database clock (no `Clock`) with Phase 7 H-74 and Phase 6 H-50. Clock-free API adaptations in Phase 6 and Phase 2 tests and the Phase 7 replay test |
| `ad3f4b6` | Phase 4 `178a419` | `.gitignore`: both secrets files. Ruff doc: integrated list |
| `7760b75` | Phase 3 `c6c5325` | No textual conflict. `runs/jobs.py` calls the fenced `fn_worker_mark_inputs_changed(job, owner)` and raises `LeaseLost` on refusal. SQL overlap with Phase 7 `0049` reconciled by `0059` |
| `6987406` | Phase 4 `ee4d3b9` | `api/routes.py`: Phase 4 streaming `_bounded_form(request, limit)` (F-2) replaces Phase 7's buffering version; one limit `MAX_UPLOAD_REQUEST_BYTES = MAX_UPLOAD_BYTES + MULTIPART_OVERHEAD_BYTES` (20 MiB + 1 MiB, the same value on both sides); Phase 7 H-61 allowlist and H-66 refusal kept. A first attempt merged the branch name after it had moved to `b604e7b`; that local, unpushed merge was reset away and redone by SHA |
| `a18e355` | Phase 7 `f189b41` | Documentation only |
| `e410949` | Phase 4 `d91513c` | `api/routes.py`: `b604e7b` only rewrapped the comment of Phase 4's limit definition, which the integrated file replaces; integrated text kept. `intake/parsers.py` auto-merged with the H-64 change |
| `c850ee9` | Phase 3 `50f3e40` | Documentation only |

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
| `0055_int_merge_p2_p3_p7` | 0046, 0049, 0054 | None (merge point) | None. Lowest supported rollback target |
| `0056_int_corr_audit_project` | 0055_int | `fn_worker_record_audit_correlated` gains `p_project_id uuid DEFAULT NULL` (written to `audit_events.project_id`); 0052 checks unchanged; EXECUTE to `webdesk_worker` only | Restores the 0052 text and grants |
| `0057_int_expire_change_clock` | 0056 | Phase 2 `fn_expire_stale_change_for_email` on `clock_timestamp()` (PH3-FC-01); grants kept (EXECUTE to `webdesk_app`) | Restores the 0045 text |
| `0058_int_merge_p3_fence` | `0055_approval_worker_fence`, 0057 | None (merge point) | None. Supported rollback target |
| `0059_int_mark_inputs_fence` | 0058 | `fn_worker_mark_inputs_changed(job, owner)` with both safeguards: the Phase 3 lease and owner fence (job KEY SHARE before the run) and the Phase 5 first mark audited as `run.stale_marked` with the run's project (Phase 7 H-70); `DROP FUNCTION IF EXISTS` of a one-argument overload. Grants of the replaced function: EXECUTE to `webdesk_worker` only | Restores the `0055_approval_worker_fence` text and grants |

All new functions are SECURITY DEFINER, owned by `webdesk_guard_owner`, with `search_path = pg_catalog, public` and no
PUBLIC EXECUTE.

**Operational limitations (migration notes):**

- Rollback stops at the integration merge revisions (ruling 4). Do not run `alembic downgrade` to a revision below
  `0055_int_merge_p2_p3_p7`, or below `0055_approval_worker_fence`, on an integrated database. Below that point the
  `0055_approval_worker_fence` downgrade removes the Phase 7 H-70 stale-mark audit while the Phase 5–7 line stays at
  `0049`, and the `0046` downgrade drops the cluster-wide role `webdesk_test_clock`.
- Upgrade in Alembic's order (`alembic upgrade head`). A database upgraded to `0055_approval_worker_fence` first and then
  to `0049` briefly holds an unfenced, PUBLIC-executable one-argument mark function until it reaches `0059`, which drops
  it.
- The Phase 2 catalog test still downgrades a scratch database to `0041` (a full rollback of every line, used only to
  test the downgrade texts). It recreates `webdesk_test_clock` on re-upgrade with an ADMIN-only membership for the
  integration owner; the test-only grant with INHERIT and SET is re-applied before a run.

## Reconciliation changes (separate commits, each with a test)

| Commit | Defect or ruling | Fix | Test |
| --- | --- | --- | --- |
| `021f75c` | Phase 3 tests predated H-74 artifacts and the branched history | Test adaptations | the two tests |
| `d055337` | H-70: Phase 3 correlated audits had no `project_id` | 0056; service and reaper pass the project | `test_integration_p2_p7.py` (5 of 6 fail without) |
| `a8c64a3` | PH3-FC-01 / H-76: Phase 2 on-demand change expiry used `now()` | 0057 | fails without 0057 |
| `baa0b49` | A losing create approval escaped as an unaudited `ProofRefused` | maps to the earlier audited 409 `approval_refused` | fails without the fix |
| `020090b` | Authority test login leaked after namespaced databases were dropped | cleanup through the `postgres` database | fails without the fix |
| `607b292` | Phase 3 `0055` dropped Phase 7's audited stale mark | 0059 | without 0059 the holder test and the Phase 7 H-70 test fail |
| `478606a` | Ruling 1 | catalog test strips SQL comments | bite check: `'queued'` → `'blocked'` (or one extra space) in a restored body fails the test; reverted |
| `9628f4d` | Ruling 2 (H-64) | named parts are attachments, never the body | `tests/unit/test_eml_named_parts.py` (6); 4 fail with the `name=` check disabled |
| `fc53073` | Ruling 3 | none (behaviour pinned) | real two-connection races: `reject_create` and `cancel_change` losers raise `ProofRefused("approval_not_pending")` with one committed `authority.proof.refused` audit |
| `db7d6f1` | Ruling 4; cycle-test knock-on on `webdesk_test_clock` | cycle test steps 0058 → 0057 → 0056 → 0055_int, exact catalog per step against fresh databases, then head; it never crosses `0046`, and asserts the role and its memberships are unchanged | bite check: `RETURN false` → `RETURN true` in the 0059 downgrade text fails at 0058; reverted |

## H-68, H-76, H-64 and Finding 5 on the merged code

| Item | Status | Evidence |
| --- | --- | --- |
| H-68 (lock order per H-25; H-DEC-1 cancel rule unchanged) | **Satisfied** | Claim, cancel (0050), reaper and worker steps lock job then run; `runs/service.cancel_run` takes no lock first; 0059 keeps job KEY SHARE before the run. `test_a_cancellation_waits_for_a_claim_without_a_deadlock` passes. A parked run is still cancellable (H-DEC-1) |
| H-76 (one time source, H-21; PH3-FC-01) | **Satisfied for the H-21 files and PH3-FC-01** | Leases, renewal, hold, finish, requeue, reaper, stuck report and the 0059 fence use `clock_timestamp()`; ceremonies use `database_now`; no `Clock` in `src`; 0057 for the Phase 2 expiry; Phase 3 `0055` moves the user and role trigger predicates to `clock_timestamp()` (F-A). Outbox leases still use `now()` (gap) |
| H-64 (EML HTML bodies and `name=` parts) | **Satisfied** | HTML-only bodies per the amended H-DEC-6 (Phase 4 tests). `name=` parts per ruling 2 (`9628f4d`, `tests/unit/test_eml_named_parts.py`) |
| Phase 5 Finding 5 / Phase 3 F-5 (`fn_worker_mark_inputs_changed` fence) | **Closed in the candidate** | Only the fenced `(job, owner)` signature exists at head; a worker that does not hold the lease gets false and nothing changes; the one-argument call is refused (Phase 3 tests and 0059 tests). The H-70 audit is kept |

## Test cluster

Container `webdesk-int-postgres`, `127.0.0.1:5486`, PostgreSQL 16.4, system identifier `7703463813966012454`.
Bootstrap `C:/Users/baps/.webdesk-int/bootstrap_int.sh` (outside the repository), adapted from the Phase 7 QA template:
database names, port and container guard, CRLF-safe secrets reading, and the Phase 2 grant of `webdesk_test_clock` to
the integration owner (QA D2). No application role is a superuser or object owner.

## Engineering gate

Code HEAD `db7d6f1`. This record is the only later commit.

| Check | Command | Result | Exit |
| --- | --- | --- | --- |
| Full suite | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | **1026 passed, 0 failed, 0 skipped**, 1 warning (Starlette/anyio deprecation), 11 min 19 s | 0 |
| Lint | `ruff check src tests migrations` (0.6.9) | all checks passed | 0 |
| Format | `ruff format --check src tests migrations` | only the four frozen migrations in `docs/RUFF_FORMAT_EXCEPTIONS.md` | 1 (documented exceptions only) |
| Types | `mypy --strict src/webdesk` (1.11.2) | no issues in 71 files | 0 |
| Migrations, fresh scratch databases | empty → head; −1 → head; down to `0057` + `0055_approval_worker_fence` → head; down to `0055_int_merge_p2_p3_p7` + `0055_approval_worker_fence` → head | single head `0059`; each step ok; each downgraded state identical to a fresh upgrade to the same revisions; each re-upgrade identical to head and to a second fresh head; 88 `webdesk_guard` functions, none with PUBLIC EXECUTE. Informational, outside the supported range: down to `0046`/`0049`/`0055_approval_worker_fence` also matched; an out-of-order upgrade shows the transient one-argument function that 0059 removes | 0 |
| Privilege audit | `pytest tests/hardening/test_privilege_audit.py` | 17 passed | 0 |

## Remaining gaps and open questions

- The rollback boundary of ruling 4 is enforced by documentation and tests, not by the migrations: nothing stops an
  operator from downgrading below the merge revisions.
- Test-cluster hygiene: the Phase 2 catalog test's full downgrade drops and recreates `webdesk_test_clock`; the test-only
  grant with INHERIT and SET is re-applied before a run (the suite passes either way).
- H-76: the outbox lease functions (`fn_outbox_claim`, `fn_outbox_renew`, `fn_outbox_retry`, `fn_outbox_mark_sent`)
  still use `now()`. Not in this scope.
- Phase 4 D-P4: the 30 s parser timeout is below the 120 s lease and the Phase 3 heartbeat renews during a parse step;
  not separately tested.
- Phase 7 F-2 to F-8, Phase 6 informational items and Phase 2 Blocker A are unchanged.
- Independent QA of this candidate and any acceptance are outstanding.

## Independent QA and status (recorded after QA)

- Frozen integration candidate: **32c98f6** (code commit db7d6f1). Reviewer: a separate agent in a detached checkout
  `D:/WDS/qa-int-32c98f6`, QA cluster `webdesk-int-qa-postgres`, port 5487, system identifier 7703463818934988838.
- Reviewer results: full suite 1026 passed, 0 failed, 0 skipped, exit 0; ruff clean; format only the four documented
  frozen migrations; `mypy --strict` clean; single head 0059; supported rollback range verified on 16 scratch
  databases; no PUBLIC EXECUTE on any of 88 guard functions. Report: `docs/FOUNDATION_INTEGRATION_QA_REPORT_32c98f6.md`.
- Verdict: **QA PASSED — INTEGRATION CANDIDATE TECHNICALLY VERIFIED** (technical assessment, not acceptance).
- QA F-1 (Medium) closed under ruling 5 ("Report as attachment", WDS in chat, 2 November 2026). Delta reviews by the
  same reviewer: 25e22d3 DELTA FAILED (D-F1 top-level case, D-F2 size change too broad); remediated in 6c458c8,
  **DELTA VERIFIED — 6c458c8 TECHNICALLY VERIFIED** (full suite 1031 passed, exit 0, on the QA cluster).
- Current integration code HEAD: 6c458c8. Open: D-F3 (Low), a named `message/rfc822` part reports its serialized size
  (Python `is_multipart()` is true for it); size metadata only, read by nothing in `src`. D-I1 (Informational), a Phase 3
  test-harness reader-thread race warning. F-2 to F-9 Low or Informational.
- Promotion of this candidate requires recorded WDS acceptance of Phases 2, 3, 4 and 6 (not recorded in the
  repository). Production readiness: **NOT VERIFIED**; see `docs/FOUNDATION_PRODUCTION_READINESS_ASSESSMENT.md`.
