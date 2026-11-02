# M2 Sprint 5: independent QA package for PG (2 November 2026)

**Status: READY — DELIVERY PENDING.** The package is prepared. It has not been delivered: the PG delivery channel is not confirmed, and PG's independence for this work is not established. **No PG review, signature, independence declaration or finding exists in this repository, and none is given here.** Claude's own testing is not independent QA.

## 1. Engineering SHA under review

- Final engineering SHA: **[to be filled from the push result]**
- Branch: `claude/sprint5-specialist-evaluations`
- Predecessors: `46e3418` (dataset v3), `f175812` (matching fix). Both are ancestors of the final SHA.

## 2. Scope to review

| Area | Files |
|---|---|
| Redirect and out-of-catalog rules | `src/webdesk/investigation/specialists.py` (`PROHIBITED_OPERATIONS`, `UNAPPROVED_CAPABILITIES`, `stated_version`, `decide`) |
| Runner | `src/webdesk/evaluation/runner.py` |
| Scorecard | `src/webdesk/evaluation/scorecard.py` |
| Datasets and manifests | `src/webdesk/evaluation/data/sprint5_scenarios_v4.json` and `.manifest.json` (v1 to v3 unchanged in expectation) |
| Tests | `tests/unit/test_sprint5_harness.py`, `tests/unit/test_sprint5_scorecard.py` |
| Governance records | `SPRINT5_REQUIREMENT_TEST_MATRIX_2026-11-02.md`, `SPRINT5_REAL_EVIDENCE_RECORD_2026-11-02.md`, `SPRINT5_SCORECARD_2026-11-02.json`, `SPRINT5_THRESHOLD_PROPOSAL_2026-11-02.md`, `SHOPIFY_55_LABELLING_HANDOFF_2026-11-02.md` |

## 3. Questions for the reviewer

1. Does `PROHIBITED_OPERATIONS` refuse only redirect requests, and not legitimate requests that merely mention redirects? Is the keyword rule acceptable?
2. Does `UNAPPROVED_CAPABILITIES` distinguish a named unapproved capability (UNSUPPORTED_SOURCE) from a request that names none (CLARIFY)?
3. Is the BigCommerce citation (an endpoint path as the passage) acceptable for the narrow claim it supports?
4. Is the S5-011 expectation (UNSUPPORTED_SOURCE against the specification's CLARIFY example) a finding?
5. Does the scorecard overstate anything? In particular, do "evaluated" dimension statuses claim more than requirement-level routing?

## 4. Evidence the reviewer can rerun

```bash
.venv/Scripts/python.exe -m pytest tests/unit/test_sprint5_harness.py tests/unit/test_sprint5_scorecard.py
.venv/Scripts/python.exe -m ruff check src tests
.venv/Scripts/python.exe -m mypy --strict src/webdesk/evaluation src/webdesk/investigation
```

Not runnable here: PostgreSQL and hardening tests (no database configured). CI must run them.

## 5. Known gaps the reviewer should weigh

- Requirement-level results are not evidence of vendor accuracy.
- Five of seven specialists have no active source.
- Shopify relevance: 0 of 55 labelled.
- The 28 October BigCommerce pilot digest no longer matches the live page.

## 6. Reviewer record (to be completed only by PG, personally)

| Field | Entry |
|---|---|
| Independence declaration | _Not provided_ |
| Reviewed SHA | _Not provided_ |
| Review scope and methods | _Not provided_ |
| Findings | _Not provided_ |
| QA decision | _Not provided_ |
| Personal attestation | _Not provided_ |

If PG has not reviewed this work through an authorized channel, the handoff status stays READY — DELIVERY PENDING. Remediation (Stage 3) is not started, because there are no independent findings.
