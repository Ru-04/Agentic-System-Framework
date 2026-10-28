# AI-S10 Next-Phase Handoff (Stage 3)

Status: the Stage 3 remediation is ready for the Stage 2 re-review. Nothing was pushed, merged or deployed.

## 1. Where the work is

- Branch: `integration/ai-s01-s02-s03` in the `integration-baseline` worktree. Base commit: `211d308`.
- Remediation commit: the full SHA is recorded in the Stage 4 acceptance packet (a commit cannot name its own SHA).
- Candidate source digest (engine source and AI-S10 test package):
  `a1bc6fc2d08287a6b974d074ddeabb4147cc1690ee1a4db575c2e3f0ebaa4fb9`.
- Engine source (`ai_engine/src`): unchanged from `211d308`.
- The session checkout `webdesk-ai-s02` (`feature/ai-s02`) does **not** contain AI-S06 to AI-S09 code. Do not run
  the AI-S10 gates there.

## 2. How to verify

From `ai_engine` in the `integration-baseline` worktree (see the reproducibility report, sections 4 and 8):

- AI-S10 files: `tests/test_ai_s10_evaluation.py`, `_evaluator_rules.py`, `_mutations.py`, `_consistency.py` (32 tests).
- Full suite: 1817 passed, 3 skipped in the development worktree; the committed tree is smaller by the 64
  untracked Foundation passes.
- `ruff check .`, `ruff format --check .`, `mypy --strict src tests`.
- Regenerate: `PYTHONPATH="src;tests" .venv/Scripts/python.exe -m evaluation.report ../docs/sprints`.
  The consistency test fails if the committed documents are stale.

## 3. Stage 2 re-review must check

1. QA-1 to QA-6 and every minor disposition in `AI_S10_QA_FINDINGS_REGISTER.md`.
2. The enforcement-point assertions (`enforced_by`) for each refusal scenario.
3. The replay mutation evidence: `consume` removed, and the always-refuse verification mutation.
4. Stale-input behaviour and classification: `STL-04` (rejection) against `STL-01`..`STL-03`, `STL-06` (exclusion), and `STL-05` (executed under the approved policy).
5. REC-03 and C-15 reporting: it must stay `open_limitation` and must never count as a pass.
6. Test-count reproducibility: the committed-tree clean export against the expected 1752 passed, 0 skipped.
7. Specification provenance: the sprint spec and master plan are untracked and cited as such.
8. AI-S01 coverage, requirement extraction, cross-project isolation and pipeline traceability.
9. `UD-01` (B-1): the SOW fingerprint comparison, its positive control, and its regression and mutation tests.
10. Readiness classifications and every number in the documents against the regenerated output.

## 4. Decisions WDS must make (not made here)

- **`STL-05`:** resolved by the WDS stale-input policy decision of 2026-10-28. No open decision remains on this item.
- **C-15:** envelope semantics for `succeeded` with `evidence_unavailable` (`REC-03`).
- **`UD-01`:** corrected under the WDS B-1 authorisation; no further decision is pending on it.
- **R-1 and R-2:** the gate bypass and the unsigned confirmations, before any Foundation integration.
- The governance decisions in `AI_S10_GOVERNANCE_POLICY_DECISION_REGISTER.md`.
- Numerical release thresholds (WDS Technical Lead).
- Approvals for real-provider evaluation, vendor-documentation retrieval, platform sandbox, Foundation integration,
  human UAT and production review.

## 5. Actions for the user (not taken by the author)

- Delete the stray duplicate package at `webdesk-ai-s02\ai_engine\ai_engine`. A safety check refused its removal.
- Decide whether `integration/ai-s01-s02-s03` is the branch of record for AI-S10. Nothing has been pushed.
- Decide whether the untracked sprint spec and master plan should be committed. They were not.

## 6. Not done

- No Stage 2 re-review verdict yet. No WDS acceptance. No real-provider, real-platform, Foundation, human or
  production check. These are reported as blocked, never as passed.
