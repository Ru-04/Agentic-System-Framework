# Sprint 6 Foundation read evidence (3 November 2026)

**Branch:** `sprint6-foundation-read`, cut from `feature/foundation-integration-p2-p7` at `5974d59`.
**Scope:** the five `ai-read/v1` GET endpoints (contract `docs/AI_FOUNDATION_READ_CONTRACT_v1.md`, sections 4 to 10), and the OPEN-02 route move for the two AI-principal human routes (`SPRINT6_OPEN_DECISION_REGISTER_2026-11-03.md`, OPEN-02; `SPRINT6_END_TO_END_CONTRACT_v1.1_2026-11-03.md`, section 6.2).
**Status:** static checks recorded below. **PostgreSQL integration tests are NOT yet run** (section 3). This record does not claim they pass.

## 1. What changed

| Item | Change | Source |
|---|---|---|
| AI-principal issue route | `POST /runs/{run_id}/ai-principal` moved to `POST /v1/runs/{run_id}/ai-principal` | OPEN-02, v1.1 section 6.2 |
| AI-principal revoke route | `POST /runs/{run_id}/ai-principal/revoke` moved to `POST /v1/runs/{run_id}/ai-principal/revoke` | OPEN-02 |
| Method refusal on AI routes | A 405 on any `/v1/ai/` path returns `{"contract":"ai-read/v1","error":"method_not_allowed"}` (was Starlette's plain-text 405). Other HTTP errors keep FastAPI's default | ai-read/v1 section 9 |
| Tests | `tests/committed/test_ai_read_v1.py`: paths updated; five tests added (old paths return 404 and create or revoke nothing; read routes refuse every non-GET method with the contract error; every refusal has the contract shape; identifiers agree across routes; refused requests never record the token or its hash) | ai-read/v1 sections 6, 7, 9, 10 |
| Docs | `docs/AI_FOUNDATION_READ_HANDOFF.md`: route paths corrected to `/v1/runs/...` | OPEN-02 |

The five read endpoints already existed on `5974d59` in `src/webdesk/api/ai.py` (`GET /v1/ai/runs/{run_id}`, `/project`, `/source-versions`, `/source-versions/{id}/segments`, `/source-versions/{id}/content`). They were checked against the contract and not reimplemented. No migration was added. No write endpoint was added. No workspace table or isolation was implemented (OPEN-11 blocked, see section 4).

## 2. Static checks (exact output)

Captured in the session with `uv sync --extra dev --frozen` (ruff 0.6.9, mypy 1.11.2).

```
$ uv run ruff check src/webdesk/api/ai.py src/webdesk/api/app.py tests/committed/test_ai_read_v1.py
All checks passed!
exit=0

$ uv run ruff format --check src/webdesk/api/ai.py src/webdesk/api/app.py tests/committed/test_ai_read_v1.py
3 files already formatted
exit=0

$ uv run mypy --strict src/webdesk
Success: no issues found in 71 source files
exit=0

$ uv run pytest tests/unit -q
312 passed in 21.27s

$ uv run pytest --collect-only -q tests/committed/test_ai_read_v1.py
33 tests collected in 0.95s
```

`ruff check .` over the whole repository was also run and passed (`All checks passed!`).

## 3. PostgreSQL integration tests: NOT RUN

Required target: scratch cluster `127.0.0.1:56544` only (never `55432`), using the roles and URL pattern of `SPRINT6_G0_EVIDENCE_2026-11-03.md` sections 1 and 2 (branch `claude/sprint5-specialist-evaluations`).

Blocker: sections 1 and 2 of that record name the roles (`webdesk_integration_owner`, `webdesk_test_owner`, `webdesk_app_login`) and the port, but they do not record a password, and no scratch credential was supplied in this session. The git-ignored `.env.integration.local` points at a different port (5433) and was not used. No credential was guessed.

Command to run once a scratch URL is supplied (the owner URL needs `CREATEDB`, per `tests/conftest.py`):

```bash
WEBDESK_TEST_DATABASE_URL='postgresql+psycopg://<integration_owner_role>:<scratch password>@127.0.0.1:56544/<db>' uv run pytest tests/committed/test_ai_read_v1.py -ra -q
```

Result: **pending**. The output will be appended here verbatim, with any skip and its reason, when the run is made. Expected count: 33 tests in `test_ai_read_v1.py`.

Full-suite and migration gates (`alembic heads`, upgrade and downgrade) were not run in this session for the same reason.

## 4. Gaps not closed here

- **Workspace isolation (OPEN-11, D-DEP-1):** no workspace entity exists on `5974d59`. Authorization in this change is project-level only (the bound human's membership or grant, and the principal's single project and run). No `workspace_id` is accepted or checked.
- **Migrations (OPEN-18, OPEN-06):** no new revision. The list in v1.1 section 11.3 is unconfirmed.
- **Worker adapter, confirmation, results persistence (D-DEP-2, D-DEP-3, D-DEP-4):** not in scope.
- **Production activation:** not authorized and not claimed.
- **Independent QA:** not performed. This is a development-team record.
