# AI-S10 Foundation Integration Blocker Register (Stage 3)

Status: every Foundation-integrated check is **blocked or skipped. None passed.** Nothing in this stage calls
Foundation, a real database, or a real service. Synthetic outcomes cannot establish live Foundation authority.

| ID | Scenario | Blocker | What is needed to unblock | Status | Owner |
|---|---|---|---|---|---|
| FND-1 | `EXT-05` | Authoritative requirement and evidence reads are not available to the engine | Foundation read API, contract and approval | Blocked | WDS and Foundation |
| FND-2 | `EXT-06` (R-2) | Operator confirmations are unsigned in-process records; Foundation-issued authorisation not implemented | Foundation-issued, verifiable authorisation; gate re-binding | Blocked | Engineering with WDS |
| FND-3 | `EXT-07` | Three Foundation integration tests skipped in the development worktree | Foundation test environment and approval | Skipped, not passed | WDS |
| FND-4 | `SEC-18` | No durable, tamper-evident audit of runs, confirmations and refusals | Foundation audit and run-state persistence | Blocked | Engineering with WDS |
| FND-5 | `TRC-02` | No integrated adapter path from a Foundation-fed requirement to a SOW; the offline pipeline uses synthetic fixtures | Foundation adapter implementation and approval | Blocked | Engineering with WDS |

## Replay enforcement note (R-2 boundary)

The replay ledger (`RPL-01`..`RPL-07`, `SEC-06`) is an **in-memory, offline** enforcement point. It proves the
ledger refuses reuse within one process. It does not prove replay protection across processes, restarts or
Foundation sessions, which is FND-2 and FND-4.

## Skipped tests (FND-3), exact reasons from the source

- `tests/test_ai_s02_s04_acceptance_distinctions.py:357`: "Needs Foundation test environment and approval; not run offline"
- `tests/test_ai_s02_s04_acceptance_distinctions.py:362`: "Needs Foundation test environment and approval; not run offline"
- `tests/test_ai_s02_s04_acceptance_distinctions.py:367`: "Needs approved requirement reads in Foundation; not implemented"

## Untracked Foundation files (not committed, not modified by AI-S10)

- `tests/test_ai_s02_s04_acceptance_distinctions.py` (18 collected), `tests/test_ai_s02_s04_boundaries.py` (43),
  `tests/test_ai_s02_s04_integration.py` (6): 67 collected. 64 pass and 3 skip in the development worktree. The
  64 passes are excluded from the committed tree's count.
- Untracked reference documents present in the worktree, **not reviewed in full in this stage**:
  `docs/AI_FOUNDATION_READ_CONTRACT_AND_READINESS_2026-10-26.md`,
  `docs/AI_S02_S04_FOUNDATION_ADAPTER_GAP_AND_DESIGN_PROPOSAL.md`.

## Rule applied

A Foundation skip is reported as skipped. It is not counted as a pass, and no synthetic pass is presented as
evidence of Foundation integration.
