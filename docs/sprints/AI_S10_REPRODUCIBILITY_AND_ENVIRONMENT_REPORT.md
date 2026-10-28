# AI-S10 Reproducibility and Environment Report (Stage 3)

Status: Stage 3 remediation. The commands and counts below were run on the development worktree after the
final source change. The committed-tree (clean export) counts are measured after the remediation commit and
recorded in the Stage 4 acceptance packet, because this file is part of that commit.

## 1. Candidate identity

- Remediation chain on branch `integration/ai-s01-s02-s03`: `211d308` (Stage 1 checkpoint), `e274cf4` (Stage 3 remediation), `7476ffa` (corrective), `7528c53` (WDS-authorised stale-input policy). Each commit's message states its own digest; the digest changed with later source edits, so only the candidate digest below is current.
- Base commit: `211d308` (`AI-S10: integrated evaluation checkpoint (synthetic, Stage 1)`), branch
  `integration/ai-s01-s02-s03`.
- Engine source (`ai_engine/src`): unchanged from the base commit.
- **Candidate source digest** (SHA-256 over the engine source and the AI-S10 test package, line endings
  normalised; computed by `evaluation.report.candidate_digest()`):

  `64c86e2603e606c055747520aa680fa638ad877776cd0ae6464f94919c91366f`

- The committed result documents state this digest. The consistency test regenerates the results from the
  source and fails if the committed documents differ. An export of the same commit must therefore produce
  the same digest.

## 2. Environment

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.12.10 (`ai_engine/.venv`) |
| pytest | 8.3.3 |
| ruff | 0.6.9 |
| mypy | 1.11.2 (compiled) |
| Test path | `PYTHONPATH="src;tests"` (semicolon on Windows); `pyproject.toml` `pythonpath = ["src"]` |

Shell note: the commands use `.venv/Scripts/...` (Git Bash). In PowerShell use `.venv\Scripts\...`.

## 3. Fixture and identifier conventions

All fixtures are synthetic: projects `PRJ-SYN-0001` and `PRJ-SYN-0002`, requirements `REQ-SYN-000n`,
evidence `EVD-SYN-000n`, the synthetic operator `OPR-SYN-1`, run `RUN-SYN-0001`. Confirmations built by the
AI-S10 executors are synthetic, human-shaped (`mock=False`) records. They are not Foundation operator
authority. The offline LLM is deterministic and scripted; no provider is called.

## 4. Commands

```bash
cd ai_engine
PYTHONPATH="src;tests" .venv/Scripts/python.exe -m pytest tests/test_ai_s10_evaluation.py tests/test_ai_s10_evaluator_rules.py tests/test_ai_s10_mutations.py tests/test_ai_s10_consistency.py -q
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/mypy.exe --strict src tests
PYTHONPATH="src;tests" .venv/Scripts/python.exe -m evaluation.report ../docs/sprints
```

## 5. Test-count separation

Counts are published separately. Committed and untracked tests are never added into one committed-baseline
number.

| Count | Value | Source |
|---|---|---|
| Development worktree: passed | 1816 | full suite on `integration-baseline` at the candidate commit (`9f1e2f5`) |
| Development worktree: skipped | 3 | the three Foundation tests (lines 357, 362, 367 of `test_ai_s02_s04_acceptance_distinctions.py`) |
| Development worktree: failed | 0 | |
| Untracked Foundation tests (collected) | 67 | `test_ai_s02_s04_acceptance_distinctions.py` (18), `_boundaries.py` (43), `_integration.py` (6) |
| Untracked Foundation tests: passed / skipped | 64 / 3 | same files |
| Committed tree: passed | 1752 | measured in a cold clean export of `9f1e2f5`; development passed (1816) minus the untracked Foundation passes (64); re-measure in clean export of the Stage 3 commit |
| Committed tree: expected skipped | 0 | the skipped tests are untracked |
| Collected but not run | 0 | no collected test is excluded from the run |
| External integration criteria not executed | 12 blocked catalogue rows | see the catalogue; blocked rows are never counted as passed |

The committed-tree figures are the expectation derived from the counts above. The measured clean-export
figures of the remediation commit are recorded in the Stage 4 acceptance packet.

## 6. Scenario catalogue counts (regenerated from source)

- Total: 136 scenarios.
- Class A (isolated synthetic): 116 pass, 0 fail, 5 open limitations, 3 delegated, 0 blocked.
- Class B to F (external): 12 blocked, none passed.
- Outcomes: pass 116, open_limitation 5, delegated 3, blocked 12, fail 0.
- No cross-class percentage is computed.

## 7. Metric definitions

Written after the first catalogue run (disclosed; the spec requires them before the first run).

- **Outcome** per scenario: `pass`, `fail`, `blocked`, `delegated`, `open_limitation`.
- **Enforcement check**: a scenario that declares an enforcement point passes only when its refusal was raised
  at that point.
- **Thresholds: none set.** Every numerical release threshold is **PENDING WDS Technical Lead** (spec section 7).

## 8. Clean-export reproducibility procedure

1. `git archive <remediation-commit> | tar -x -C <scratch>/clean`
2. From `<scratch>/clean/ai_engine`, with `PYTHONPATH=src;tests`, run the commands in section 4.
3. Confirm the digest in the regenerated output equals the one in section 1.
4. Confirm the regenerated result documents equal the committed ones (the consistency test does this).
5. Confirm the import path is the exported `src` (print `ai_engine.__file__`).

## 9. Reproducibility limits

- Windows-specific: the `PYTHONPATH` separator and the `.venv` layout.
- The results depend on the engine source at the commit; a source change changes the digest and requires
  regeneration.
- Line endings: the digest normalises CRLF to LF. Git warns about CRLF in the working copy; the stored content is LF.
