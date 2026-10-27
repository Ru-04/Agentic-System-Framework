# Phase 3 dependency register

Phase 3 engineering is developed on `feature/foundation-phase-3`, based on the committed Phase 2 state `46e0e14`.
Merge and acceptance of Phase 3 stay blocked until the prerequisites below are satisfied. None of them is accepted by
this document.

## Base and prerequisites

| ID | Dependency | State at Phase 3 start | Effect on Phase 3 | Blocks |
|---|---|---|---|---|
| D-1a | Phase 2 QA remediation (findings F-01 to F-13) | Implemented in the Phase 2 worktree, **not committed**, with three regression runs in progress at the time of this sprint start | Not in this branch. Phase 3 does not depend on its code, but the migration chain must be joined when it is committed (see D-1c). | Phase 3 merge |
| D-1b | Phase 2 independent QA re-test and acceptance | Not performed | Phase 2 is not accepted. Phase 3 engineering uses only the committed Phase 2 interfaces (H-10 to H-14 as at `46e0e14`). | Phase 3 acceptance |
| D-1c | Migration chain join | Phase 2 remediation uses revisions `0044_grant_revocation_lock` and `0045_change_expiry_on_demand` on its own branch. This branch's chain ends at `0043_phase2_review_fixes`. Phase 3 adds `0050_durable_execution` on top of `0043`. | Once Phase 2 remediation is committed, `0050`'s `down_revision` must be set to the Phase 2 head (`0045`) so there is one head. Required before any merge. | Phase 3 merge |
| D-1d | Test-isolation namespaces, `TEMP` mirror for clones, and the migration catalog test | Implemented in the Phase 2 worktree, not committed | This branch uses fixed Phase 3 database names (`webdesk_p3_integration`, `webdesk_p3_hardening`) and random per-test names. The namespace mechanism is a required integration (see `docs/TEST_DATABASE_ISOLATION.md` in the Phase 2 branch). | Phase 3 merge (test reliability) |
| D-1e | Phase 1 independent acceptance | Not recorded | Phase 1 security invariants are preserved by the implementation; formal acceptance is a separate gate. | Phase 3 acceptance |

## Open items inside Phase 3 scope

| ID | Item | Owner | Blocks |
|---|---|---|---|
| D-2 | Outbox worker and expiry sweep are not run by `python -m webdesk.worker`. The outbox needs a transport. The sweep needs the ceremony role. | Phase 3 follow-up or the notification and outbox phase (H-50, H-52) | Phase 3 acceptance (H-26 is partial) |
| D-3 | H-21 asks for ceremony deadlines to use the database clock. The approved test-clock rule (P-INC3-TEST-CLOCK-05) allows an injected window. These must be reconciled by a WDS decision: keep the injected clock for tests and use the database clock for the deadline, or another rule. | WDS decision | Phase 3 acceptance (H-21 is partial) |
| D-4 | Production worker login provisioning (a secret per environment) | Deployment | Production only |
| D-5 | Process manager for the worker (H-26 requires one in production) | Deployment checklist | Production only |

## Non-goals (not in Phase 3)

- No AI result-write interface, no AI Engine change, no Specialist Agent change.
- No notification infrastructure, no production email transport.
- No Phase 4 work.
- No merge, push or deployment.
