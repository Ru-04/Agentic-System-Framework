# AI-S10 Reproducibility and Environment Report

Status: Stage 1. Commands below were run on the development worktree during this stage.

## 1. Environment

| Item | Value |
|---|---|
| OS | Windows 11 Pro 10.0.26200 |
| Python | 3.12.10 (`ai_engine/.venv`) |
| pytest | 8.3.3 |
| ruff | 0.6.9 |
| mypy | 1.11.2 (compiled) |
| Base commit | `3e79d01` on `integration/ai-s01-s02-s03` |
| Working tree | Base plus the AI-S10 files listed in the implementation record |

Shell note: the commands use `.venv/Scripts/...` (Git Bash). In PowerShell use `.venv\Scripts\...`.
Set `PYTHONPATH` to `src;tests` (semicolon on Windows).

## 2. Fixture and file identifiers

Fixtures are synthetic and come from the accepted AI-S06 to AI-S09 test helpers:
projects `PRJ-SYN-0001` and `PRJ-SYN-0002`, requirements `REQ-SYN-000n`, evidence `EVD-SYN-000n`,
operator `OPR-SYN-1`, run `RUN-SYN-0001`.

First 16 hex characters of the SHA-256 of each AI-S10 file (recompute with `sha256sum`; full digests are
the authoritative identifiers):

| File | SHA-256 (prefix) |
|---|---|
| `tests/evaluation/catalog.py` | `91745c1546e212af` |
| `tests/evaluation/runner.py` | `207394b835aaaed6` |
| `tests/evaluation/scenarios.py` | `f34348524d33ce20` |
| `tests/test_ai_s10_evaluation.py` | `3d2a7e1f2b8d5d72` |

These hashes describe the working tree at the time of the gate run. Any later edit changes them.

## 3. Commands

```bash
cd ai_engine
PYTHONPATH="src;tests" .venv/Scripts/python.exe -m pytest tests/test_ai_s10_evaluation.py -q
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
.venv/Scripts/mypy.exe --strict src tests
PYTHONPATH="src;tests" .venv/Scripts/python.exe -m evaluation.report ../docs/sprints "<label>"
```

## 4. Metric definitions

Written after the first catalogue run, not before. The spec (section 5) asks for them before the first
run; this is a disclosed deviation.

- **Outcome** per scenario: `pass`, `fail`, `blocked`, `delegated`, `open_limitation`.
- **Counts** are reported per classification. A cross-class percentage is not computed.
- **Synthetic executed** means classification A scenarios with status `executed`.
- **Thresholds: none set.** Every numerical release threshold is **PENDING WDS Technical Lead**
  (spec section 7). No threshold is treated as approved.

## 5. Gate results (development worktree)

| Gate | Result |
|---|---|
| `test_ai_s10_evaluation.py` | 16 passed |
| Full suite | 1728 passed, 3 skipped (the 3 Foundation skips, lines 357, 362, 367 of `test_ai_s02_s04_acceptance_distinctions.py`) |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 151 files formatted |
| `mypy --strict src tests` | No issues in 151 source files |
| Catalogue run | 91 scenarios; 74 synthetic executed; 74 pass; 0 fail |

The 64 passing tests of the untracked Foundation files are counted in the full suite but are not in the
committed tree. The 3 skipped tests are not run and are not passed.

## 6. Clean-export reproducibility

Procedure: export the checkpoint commit to a clean directory with `git archive`, then run the gates in
section 3 there.

Expected for the committed tree: the full suite without the 64 untracked Foundation passes, so 1664 passed
and 0 skipped. The result of the clean export is reported in the Stage 1 hand-off message. It is not
written into this file, because this file is part of the commit it would describe.

## 7. Reproducibility limits

- Windows-specific: `PYTHONPATH` separator and the `.venv` layout. Other platforms need the usual
  adaptations.
- The catalogue results depend on the engine code at the commit. Changing the engine changes the
  outcomes and must be followed by a regeneration.
- The three Foundation skips are environmental, not a defect of AI-S10.
