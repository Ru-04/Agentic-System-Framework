# Gate-closure checklist and authorized CI strategy (27 October 2026)

Management approval and independent review evidence are kept apart. Nothing below is closed without the evidence named in its row.

## 1. Sprint 4 configuration review (uncommitted, preserved)

| Item | Result |
|---|---|
| `src/webdesk/evidence/approved_boundaries.py` (uncommitted) | Matches the approved decisions exactly: ADOBE-01 (four URLs: `commerce/php/` shared, `webapi/rest/`, `webapi/graphql/`, `extensibility/events/`); MAGENTO-01 (one release-notes URL on `experienceleague.adobe.com`); WooCommerce and BigCommerce entries unchanged. Each Adobe-only and Magento URL sits under its own edition key. No directory tree is approved. |
| `tests/unit/test_sprint4_exact_pages.py` (uncommitted, untracked) | Covers exact-page acceptance, child/sibling/parent refusal, query and encoding refusal, `frontend-core` exclusion, contributor-guide refusal, devdocs redirect refusal, edition separation, and WooCommerce/BigCommerce compatibility. **NOT EXECUTED.** |
| Static checks | `ruff check src tests migrations`: passed. `ruff format --check src tests`: passed (162 files). |
| Security static review | Reviewed by reading. No new host or path beyond the approved list. No credential, no network call, no retrieval code added. |

**Commit decision:** the configuration and tests are **not committed**. The tests have not run, and a commit should contain only verified changes. The change is preserved in the working tree.

## 2. Test results at the current state

| Check | Commit / tree | Result |
|---|---|---|
| `pytest tests/unit` | `40b6746` (code identical to later docs-only commits) | 600 passed (last executed) |
| `mypy --strict src/webdesk` | same | clean (last executed) |
| `pytest tests/unit` including the uncommitted tests | working tree | **NOT EXECUTED — APPLICATION CONTROL ERROR 4551** |
| `mypy --strict` including the uncommitted config | working tree | **NOT EXECUTED — APPLICATION CONTROL ERROR 4551** |
| `pytest tests/integration tests/committed` | `40b6746`-era code | 223 passed (last executed on a scratch database) |
| `pytest tests/hardening` | — | **NOT EXECUTED** (needs CI-provisioned roles) |

Nothing is described as passing unless it executed.

## 3. Gate-closure checklist

| # | Gate | Status | Evidence required to close | Owner |
|---|---|---|---|---|
| G1 | WDS management acceptance of Sprint 3 | **APPROVED** (27 Oct 2026, chat) | Recorded (`35b0ae6`) | WDS Authorized Approver |
| G2 | PG QA completion | **REPORTED BY MANAGEMENT** (PASS, no defects) | Management statement only | WDS management |
| G3 | PG personally completed independence declaration | **PENDING VERIFICATION** | PG's own signed declaration, naming the reviewed commits | PG (personally) |
| G4 | PG signed independent QA record | **PENDING VERIFICATION** | PG's own review, findings, and personal PASS / PASS WITH CONDITIONS / FAIL decision, signed by PG | PG (personally) |
| G5 | Shopify 55 genuine human relevance labels | **OPEN** (0 of 55) | 55 labels from a qualified independent reviewer, imported and evaluated | Independent reviewer named by WDS |
| G6 | CI run on the reviewed commits | **OPEN** | A passing `specialist-ci` run on a pushed commit | Engineering, after push approval |
| G7 | Hardening tests (`tests/hardening`) | **OPEN** | A passing run in CI with CI-provisioned roles | Engineering, CI |
| G8 | Current-head unit, mypy and integration tests with the uncommitted changes | **OPEN** | Execution in an authorized environment | Engineering, once a runner is available |
| G9 | Milestone 1 controls (Sprint 1 and 2 human QA; specification approval; independent Milestone 1 testing; final CI) | **OPEN** | As listed in `MILESTONE1_ACCEPTANCE_TRACKER_2026-10-23.md` | WDS and independent reviewers |

Management approval (G1, G2) is recorded separately from independent review evidence (G3, G4, G5). G2 does not close G4.

## 4. Authorized CI strategy (proposal only; nothing pushed)

**Source branch:** `claude/webdesk-specialist-baseline-v1-3b21b1`.
**Commit to test:** the commit that includes the approved configuration and its tests, created only after a local run succeeds (or after an authorized runner executes them).
**Workflow:** `.github/workflows/specialist-ci.yml`, as configured in the repository. No change to authentication or workflow settings is proposed.

Checks that CI would run:
1. `ruff format --check src tests` and `ruff check src tests migrations`.
2. `mypy --strict src/webdesk`.
3. `pytest tests/unit`.
4. Postgres job: `alembic upgrade head`, provisioning of hardening roles, then `pytest tests/integration tests/committed tests/hardening`.

Pushing needs your formal approval (see section 5). The earlier push attempts returned HTTP 403 for the identity `toarushiS`. Access must be restored before any push. I have not changed credentials and will not.

## 5. Remaining formal gate items
1. PG's personal declaration and signed review (G3, G4).
2. The 55 labels (G5).
3. A CI run on a pushed commit (G6) and hardening in CI (G7).
4. Execution of the uncommitted tests in an authorized environment, then a verified local commit (G8).
5. Milestone 1 controls (G9).
