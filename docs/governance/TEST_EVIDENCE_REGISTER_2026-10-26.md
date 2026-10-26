# Test evidence register (26 October 2026)

Status key: **PASSED** = run and passed, with the commit shown. **NOT EXECUTED — ENVIRONMENT BLOCKED** = not run because Windows Application Control error 4551 blocked the tool. Blocked checks are never recorded as passed.

## ai_engine (integration branch `integration/ai-s01-s02-s03`)
| Check | Commit | Result | Status |
|---|---|---|---|
| pytest | `2f16db0` (AI-S01 + AI-S02 + AI-S03 integration) | 1190 passed | PASSED |
| ruff check, ruff format --check | `2f16db0` | clean | PASSED |
| mypy --strict src tests | `2f16db0` | clean (99 files) | PASSED |
| Clean-room pytest (full tree export) | tree of `16607e6` | 1190 passed | PASSED |
| Clean-room ruff check | tree of `16607e6` | clean | PASSED |
| Clean-room mypy --strict | tree of `16607e6` | DLL path-length error in the clean-room location | NOT EXECUTED — ENVIRONMENT (path length). In-place mypy is recorded above |
| pytest, ruff, mypy at current head | `ac1ef7e` (adds AI-S04 WooCommerce and BigCommerce, 30 tests, by `toarushiS`, not run by this session before) | pytest 1220 passed; ruff clean; ruff format clean (107 files); mypy --strict clean (107 files) | PASSED |

## webdesk (branch `claude/webdesk-specialist-baseline-v1-3b21b1`)
| Check | Commit | Result | Status |
|---|---|---|---|
| pytest tests/unit (last verified run) | `e3ba3b7` code state | 536 passed | PASSED (preserved from the last verified run, original commit reference) |
| mypy --strict src/webdesk (last verified run) | `e3ba3b7` code state | clean (82 files) | PASSED (preserved from the last verified run) |
| pytest tests/unit (current head `0d97ea1`) | `0d97ea1` | — | NOT EXECUTED — ENVIRONMENT BLOCKED (error 4551), retried 26 Oct 2026 |
| mypy src/webdesk (current head) | `0d97ea1` | — | NOT EXECUTED — ENVIRONMENT BLOCKED (error 4551), retried 26 Oct 2026 |
| ruff check src tests migrations | `0d97ea1` | clean | PASSED |
| ruff format --check src tests | `0d97ea1` | clean (155 files) | PASSED |
| Integration and committed tests (223) | `c54a868`-era code | 223 passed on a scratch database, dropped after the run | PASSED (preserved from the last verified run). Not re-run at current head |
| Hardening tests | — | Require CI roles | NOT EXECUTED locally; run only in CI |

## Not claimed
- No final QA acceptance is claimed. Mandatory checks blocked at the current head (webdesk pytest and mypy) must be rerun in an authorized environment before any acceptance.
- Automated runs are not human QA.

## Rerun when available
- webdesk: `pytest tests/unit` and `mypy src/webdesk`, at the head then current.
- webdesk: integration and committed tests on a scratch database.
- CI for each pushed commit once push is authorized.

## Update 26 October 2026 (later)
- ai_engine at `2988913` (clean-room full-tree export of HEAD): pytest **1253 passed**; ruff check and ruff format --check clean (115 files). Strict mypy not run in the clean-room copy.
- Webdesk pytest and mypy: NOT EXECUTED — APPLICATION CONTROL ERROR 4551. Per the WDS decision, the blocked executables were not retried in this environment. No authorized alternative environment is available to this session. The first authorized route is the GitHub `specialist-ci` run on a pushed commit, which waits for the deferred push.
- Integration worktree has 9 uncommitted modified files (not from this session). Not committed, not tested.

## Current-head results at 36eb0e6 + uncommitted adapter v0.2 work (26 October 2026)
Note: the Application Control block on webdesk pytest and mypy did not apply in this session when re-attempted (no restriction was changed or bypassed). Results below are from this session and are current-head evidence only for the uncommitted working tree described.
- pytest tests/unit: **572 passed** (536 prior + 36 new adapter v0.2 tests), 1 warning.
- mypy --strict src/webdesk: **clean**, 84 source files.
- ruff check src tests migrations: **clean**. ruff format --check src tests: **clean** (158 files).
- pytest tests/integration tests/committed (scratch database created and dropped): **223 passed**.
- Hardening tests (tests/hardening): NOT EXECUTED locally; require CI-provisioned roles.
- Not claimed: final QA acceptance. Adapter code is uncommitted; this run does not establish a commit as passing.
