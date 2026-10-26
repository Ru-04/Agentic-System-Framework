# Final Sprint 3 review package for PG (26 October 2026)

**Purpose:** evidence index and test commands for PG's independent QA review. **This package is not QA.** It records what exists and where. It does not contain any finding, sign-off or declaration.

## 1. PG's first step (personal, before any review)
PG completes the declaration personally: `docs/governance/PG_INDEPENDENCE_DECLARATION_TEMPLATE_2026-10-26.md`. The assistant has not completed or signed it. PG's independence is PENDING until PG completes it. If PG authored or materially contributed to the reviewed work, PG must say so and must not review it.

## 2. Reviewed commits
- **Adapter v0.2 and synthetic vertical slice:** `3969a8f` (branch `claude/webdesk-specialist-baseline-v1-3b21b1`, local). Remote push deferred; the remote branch is at `abf13a9`.
- **Platform foundations:** `e3ba3b7` and the governance commits after it (see `git log`).
- **Documentation commit:** the commit that adds this package and the Sprint 3 closure reconciliation. Its SHA is the latest commit on this branch that adds this file (see git log).

PG must confirm the SHA with `git rev-parse HEAD` in the worktree and record it.

## 3. Test commands (run in an authorized environment)
From the worktree, at the commit under review:
```bash
git rev-parse HEAD
uv sync --extra dev
uv run --extra dev pytest tests/unit -q
uv run --extra dev mypy --strict src/webdesk
uv run --extra dev ruff check src tests migrations
uv run --extra dev ruff format --check src tests
```
Integration and committed tests, on a scratch database that the operator creates and drops:
```bash
uv run --extra dev pytest tests/integration tests/committed -q -p no:warnings
```
Hardening tests (CI-provisioned roles only): `uv run --extra dev pytest tests/hardening -q`.

Record the SHA, the environment, the command output and the date for each run.

## 4. Evidence index
- Specialist contract, harness, authority, workspace: `src/webdesk/specialists/` (contract.py, harness.py, authority.py, workspace.py, errors.py, catalog.py).
- Platform foundations: `src/webdesk/specialists/platforms/generic.py` and the six platform modules.
- Adapter v0.2: `src/webdesk/specialists/adapter_v02.py`; slice: `src/webdesk/specialists/synthetic_slice.py`; fixture: `docs/governance/fixtures/synthetic_vertical_slice_fixture.json`.
- Tests: `tests/unit/test_m2_s3_platforms.py`, `tests/unit/test_adapter_v02.py`, `tests/unit/test_specialist_*.py`, `tests/unit/test_s2_*.py`, integration tests in `tests/integration/`.
- Records: `docs/governance/M2_S3_COMPLETION_REPORT.md`, `SPRINT3_CLOSURE_RECONCILIATION_2026-10-26.md`, `TEST_EVIDENCE_REGISTER_2026-10-26.md`, `ARCHITECTURE_COMPATIBILITY_ASSESSMENT_2026-10-26.md`, `ADAPTER_CONTRACT_PROPOSAL_2026-10-26.md`, `ARCHITECTURE_DECISION_RECORD_2026-10-26.md`, `SPECIALIST_IMPLEMENTATION_MATRIX_2026-10-26.md`.

## 5. Results to re-check (not results of this package)
- Last recorded at the adapter commit's working tree (26 Oct 2026): unit 572 passed, strict mypy clean (84 files), ruff clean, integration and committed 223 passed.
- PG must re-run these at the reviewed SHA. Earlier results do not transfer to other commits.

## 6. What PG reviews
1. Contract compatibility of the seven categories (1.0.0 WebDesk contract and v0.2 adapter).
2. Workspace isolation, evidence admission, origin rules, instruction screening.
3. Authority boundary: forbidden and unknown actions refused; operator confirmation required.
4. Error handling and provider-failure mapping (no provider text echoed).
5. The synthetic slice: test-only, not platform evidence.
6. Security regressions, and whether any adapter path bypasses WebDesk controls.

## 7. Outstanding items PG must not be asked to accept
- Source approval for every platform (none approved).
- Production integration (blocked; QA-07).
- Hardening tests (CI-only).
- Shift4Shop owner verification (`developer.3dcart.com` not confirmed as the owner's official documentation).

## 8. Declaration and sign-off
PG records findings and makes the PASS, PASS WITH CONDITIONS or FAIL decision personally. The assistant does not fill in any field, finding, decision or signature.
