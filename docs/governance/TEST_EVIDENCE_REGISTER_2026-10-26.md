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
