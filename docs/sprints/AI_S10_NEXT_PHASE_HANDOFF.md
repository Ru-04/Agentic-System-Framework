# AI-S10 Next-Phase Handoff

Status: Stage 1 checkpoint handed to Stage 2 independent QA and to WDS. Nothing was pushed, merged or
deployed.

## 1. Where the work is

- Branch: `integration/ai-s01-s02-s03` in the `integration-baseline` worktree (base `3e79d01`).
- Checkpoint commit: the SHA is reported in the Stage 1 hand-off message, not here, because a commit cannot
  name its own SHA.
- Session checkout `webdesk-ai-s02` (`feature/ai-s02`, `c43cda0`) does **not** contain AI-S06 to AI-S09
  code. Do not run the AI-S10 gates there.

## 2. How to verify

Run from `ai_engine` in the `integration-baseline` worktree (see the reproducibility report, section 3):

- `tests/test_ai_s10_evaluation.py`: 16 tests.
- Full suite: 1728 passed, 3 skipped in the development worktree; the committed tree is smaller by the
  64 untracked Foundation passes.
- `ruff check .`, `ruff format --check .`, `mypy --strict src tests`.
- Regenerate outputs: `python -m evaluation.report ../docs/sprints "<label>"`.

## 3. Stage 2 must check

1. The catalogue expectations (OBS-6). The author wrote them.
2. REC-03 and C-15 (OBS-1). Decide whether `succeeded` with `evidence_unavailable` is acceptable.
3. Coverage gaps: AI-S01, AI-S02, AI-S05, requirement extraction (OBS-2, OBS-3, OBS-5).
4. "Stale input rejected" (OBS-4).
5. That no "pass" in any document claims more than the executor proves.
6. The clean-export reproducibility of the checkpoint.

## 4. Decisions WDS must make (not made here)

- Governance: A-4, C-15, GP-1, D-05, D-06, D-07, D-10, D-04/C-08, D-14, R-1, R-2, D-12, D-13, DEC-09, D-02.
- Numerical release thresholds (WDS Technical Lead).
- Approvals for any of: real-provider evaluation, vendor-documentation retrieval, platform sandbox, Foundation
  integration, human UAT, production review.

## 5. Actions for the user (not taken by the author)

- Delete the stray copy at `webdesk-ai-s02\ai_engine\ai_engine` (removal refused by a safety check).
- Decide whether `integration/ai-s01-s02-s03` is the branch of record for AI-S10. Nothing has been pushed.
- Decide whether the untracked sprint spec and master plan should be committed. They were not.

## 6. Not done

- No independent QA. No WDS acceptance. No real-provider, real-platform, Foundation, human or production
  check. These are reported as blocked, never as passed.
