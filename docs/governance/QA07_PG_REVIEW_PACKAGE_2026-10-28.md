# QA-07 independent review package for PG (28 October 2026)

**Delivery status: DELIVERY PENDING.** This package was prepared in the repository. It has not been delivered to PG. No delivery channel is available from this session, and no review has been requested or received.

**Review subject:** QA-07 runtime authorization enforcement (decision QA-07-MERGE-01) and the cumulative candidate for the first development integration merge.

## Exact SHAs

| Item | Value |
|---|---|
| QA-07 branch | `claude/qa07-validation` |
| Last CI-tested engineering commit | `8304d2ca536cd57bf4e9616205f293ebae66066e` (CI run #57, success) |
| CI on later commits | `d60e794` (run #58, success); `f4e0f96` (run #59, success); `bb06554` (run #60, success, management-reported PASS) |
| Current head for merge review | `bb06554dd3365df8d9f8b6b3fc13a463a34b1715` (asyncio scope fix; see the merge authorization request) |
| Target | `feature/increment-1-foundation` at `740b1695555303b29323a58df3e2345663d9821d` (ancestor of the candidate) |

The review must be bound to the final CI-passing commit. If `d60e794` passes CI, the reviewed commit is `d60e794`, which differs from `8304d2c` only in the traceability report.

## Documents to read first

1. `docs/governance/QA07_TRACEABILITY_2026-10-28.md`. Requirement-to-test traceability, known limits, and the final engineering record.
2. `docs/governance/QA07_CONTROL_MATRIX_2026-10-28.md`. Classes A, B and C.
3. Code: `src/webdesk/specialists/authorization.py`, `src/webdesk/specialists/harness.py`, `src/webdesk/specialists/adapter_v02.py`, `src/webdesk/investigation/pilot.py`, `src/webdesk/investigation/retrieval.py`, `src/webdesk/rbac/engine.py`.
4. Tests: `tests/unit/test_qa07_runtime_authority.py`, `tests/unit/test_qa07_rbac_wiring.py`, `tests/unit/test_pilot.py`, `tests/support/authority.py`.

## Areas PG must assess

1. Authoritative operator verification, and whether trusted authorization is established outside protected components.
2. Runtime permission enforcement through `rbac_permission_check` and `rbac.engine.authorize`.
3. Pilot authorization: whether `run_pilot` can create authority or enter the scope itself.
4. Run-start path: `src/webdesk/runs/service.py` `start_run`. Specialist execution is not reachable from it (no import of `webdesk.specialists` under `src/webdesk/runs` or `src/webdesk/api`).
5. Direct invocation and retrieval bypass protection.
6. Workspace isolation: workspace must be a project UUID for RBAC; synthetic identifiers are refused.
7. Revocation and expiry: revocation is an in-memory flag.
8. Security limitations, as listed in the traceability report, known limits 1 to 6.
9. CI evidence: runs #57 (`8304d2c`, success) and #58 (`d60e794`, status to be confirmed).
10. R4 exclusion: migrations 0020 to 0027 absent; no R4-named paths.

## Points PG should look at specifically

- **Audit assertion change.** `tests/unit/test_pilot.py` now expects one audit entry per pilot case. Confirm that this is the correct contract and that the test still detects missing or duplicate decisions.
- **Asynchronous paths.** A task created inside a verified scope copies the context. The scope is now a deactivatable object, so the copy is refused once the scope closes. Tests: `tests/unit/test_qa07_rbac_wiring.py` asyncio section. This fix was made after `8304d2c`, so it is covered only by the CI run on the final SHA.
- **In-process limit.** `harness_scope` is public. Code that imports it can enter the scope. The control refuses direct and accidental calls only.
- **Production wiring.** The RBAC check is not exercised against the SQL store in an integration test.
- **Six deleted lines** in `src/webdesk/intake/reassess.py` and two test files, from the earlier format-only commit `79c90bc`. The three files `src/webdesk/intake/reassess.py`, `tests/hardening/conftest.py` and `tests/integration/test_gate1_schema.py` were checked in the author's session: each is syntax-tree identical to the target, so the change is formatting only. PG should re-verify this independently.

## PG section (to be completed by PG personally)

Nothing below has been filled in. It must be completed by PG. It must not be completed on PG's behalf.

- **Independence declaration:** [PG to complete personally]
- **Findings:** [PG to record]
- **Review decision:** [PG to record]
- **Attestation:** [PG to sign personally]
- **Date:** [PG to record]

## Stage 3 status

No PG findings exist, so no remediation has been performed and none is recorded. "NOT REQUIRED" can be recorded only after PG's review confirms zero defects.
