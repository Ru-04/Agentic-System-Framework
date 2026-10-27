# CI record: commit 1a12fee (27 October 2026)

**Verified against the repository and GitHub Actions:**
- Repository: `Ru-04/Agentic-System-Framework`
- Branch: `claude/webdesk-specialist-baseline-v1-3b21b1`
- Commit: `1a12fee` (remote head confirmed by `git ls-remote`)
- Workflow: `specialist-ci`, run #25, `https://github.com/Ru-04/Agentic-System-Framework/actions/runs/40513149053`
- Trigger: push. Status: **Success**. Duration 2m 54s.
- Jobs: `lint-type-unit` and `postgres-tests`, both listed on the run.

**Result: CI PASS for commit `1a12fee` only.**

## Which checks this run covered (from `.github/workflows/specialist-ci.yml`)
| Job | Step | Covers |
|---|---|---|
| lint-type-unit | Format check | `ruff format --check src tests` |
| lint-type-unit | Lint | `ruff check src tests migrations` |
| lint-type-unit | Type check | `mypy` (strict, `src/webdesk`) |
| lint-type-unit | Unit and specialist contract tests | `pytest tests/unit` (includes adapter v0.2, workspace, authority, allowlist security regression) |
| postgres-tests | Migrate integration database | `alembic upgrade head` |
| postgres-tests | Create and migrate hardening database | Role and database provisioning |
| postgres-tests | Integration, committed and hardening tests | `pytest tests/integration tests/committed tests/hardening` |

A job is marked successful only when all its steps succeed, and no step in this workflow is set to continue on error. So every step above passed.

## Limits of this record
- The per-test counts and per-step logs are not visible without signing in to GitHub ("Sign in to view logs"). This record does not state individual test counts.
- The hardening tests run inside the same step as the integration and committed tests. They are covered by that step's success. Their individual results are not separately verified here.

## Not covered by this CI record
- The uncommitted Sprint 4 configuration (`src/webdesk/evidence/approved_boundaries.py`) and its tests (`tests/unit/test_sprint4_exact_pages.py`). They are not in commit `1a12fee`, so CI did not run them. They are NOT verified.
- PG's independent QA, the 55-pair Shopify review, and the Milestone 1 controls. Unchanged by this record.

## Validation run for the Sprint 4 configuration (CI-01, throwaway branch)
- Branch: `claude/sprint4-config-validation` (not merged; throwaway).
- Tested commit: `8f7ba79` (base `1a12fee` plus only the two approved files).
- Workflow: `specialist-ci` run #26: https://github.com/Ru-04/Agentic-System-Framework/actions/runs/40515435697. Status: **Success**. Duration 2m 58s.
- Jobs: `lint-type-unit` and `postgres-tests`, both successful. Job success confirmed. Per-test counts are not visible in the public logs (sign-in required).
- File comparison: the two files in the development worktree match `8f7ba79` exactly, ignoring CRLF line endings.
- Promotion: committed locally to the development branch as `186fd3b` (the two files only). **Not pushed.**
- Source activation: none. All evidence sources remain inactive. No profile reads the configuration.

## Development-branch CI run #27 (commit 694b978)
- Branch: `claude/webdesk-specialist-baseline-v1-3b21b1`. Remote head confirmed as `694b978` after the approved normal push (fast-forward from `1a12fee`).
- Workflow: `specialist-ci` run #27, triggered by push. Status: **completed successfully**, duration 3m 0s, as shown on the Actions list.
- Job-level result is confirmed on the list. Per-job and per-test detail requires sign-in and is not recorded here.
