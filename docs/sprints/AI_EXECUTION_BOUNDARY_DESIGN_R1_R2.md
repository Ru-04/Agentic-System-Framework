# Execution-Boundary Design: R-1 and R-2 (Stage 1C)

Status: design and inventory. R-1 and R-2 remain **open**. No accepted AI-2 or AI-S06 code was changed.
Live execution using synthetic confirmation objects is not authorised and is not enabled.

## 1. Execution entry points (inventory on `integration/ai-s01-s02-s03`)

| # | Entry point | Calls | Protection today | Status |
|---|---|---|---|---|
| E1 | `specialists/execution.py: run_specialist` | agent `run` (`execution.py:208`) | none: no confirmation, actor, grant or proposal parameter | **Open (R-1)** |
| E2 | `orchestration/workflow.py: Orchestrator.execute` | `run_specialist` (`workflow.py:357`) | in-process confirmation (`gate.py: verify_confirmation`); replay ledger (in memory) | Gated; R-2 open |
| E3 | `demo/workflow.py: run_investigation` | `run_specialist` (`workflow.py:258`) | operator selection with revision check (`verify_selection`, `StaleSelectionError`) | Gated by an operator decision, not by Foundation authority |
| E4 | `demo/cli.py: run_demo` | `run_investigation` | none beyond E3 (command-line caller) | Demonstration only |
| E5 | `specialists/execution.py` agent `run` | none (leaf) | runs inside E1 | n/a |

E1 is reachable by any caller that imports `ai_engine.specialists.execution.run_specialist`. Scenario `SEC-09`
(`open_limitation`) demonstrates this: a direct call returns an execution status with no confirmation.

## 2. Required enforcement boundary (what R-1 and R-2 need)

Every route that executes a specialist must present an **execution grant** that is:

1. issued only by the authoritative confirmation boundary, from a Foundation-authenticated operator decision
   (R-2: principal, operator authority, session validity);
2. bound to the run, the project, the specialist category, and the requirement revisions it covers;
3. single-use (replay rejected) and time-limited (expiry rejected);
4. checked by `run_specialist` itself, so no caller can bypass it (R-1).

Required refusals (adversarial tests to be added when the boundary exists): unauthorised principal; stale grant;
replayed grant; grant bound to another run, project, category or revision; expired grant; mock or synthetic grant on
a live path.

## 3. Why the boundary cannot be completed in this checkpoint

- The authoritative source of operator identity is Foundation (`AI-Principal` and human sessions are on the
  Foundation branches, not on this branch; see `AI_INTEGRATION_READINESS_BASELINE.md`).
- The Foundation AI read contract (`ai-read/v1`) has **no** route for confirmations, grants or specialist
  selection (contract sections 6 and 8). Those routes are unavailable and must be coordinated with the Foundation owner.
- Making `run_specialist` require a grant changes an accepted AI-2 interface and its callers (E2, E3). That is an
  upstream change and needs a narrowly scoped WDS decision.

## 4. Consequence for acceptance

- R-1 remains open: `SEC-09` stays an open limitation. Engineering may not claim the gate protects E1.
- R-2 remains open: `EXT-06` stays blocked on Foundation-issued authorisation.
- No synthetic confirmation may be presented as an operator decision on a live path.

## 5. Proposed next steps (for WDS decision)

1. WDS decides whether the grant parameter is added to `run_specialist` (interface change) or E1 is removed from the
   public surface and exposed only through an internal module.
2. Foundation owner provides, or declines to provide, a confirmation and grant route under the AI contract.
3. Adversarial tests for E1 to E4 are added against the chosen boundary, each failing when its check is removed.
