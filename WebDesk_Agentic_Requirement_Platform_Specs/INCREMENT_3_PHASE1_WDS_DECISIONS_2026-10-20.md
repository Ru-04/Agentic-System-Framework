# WDS-confirmed Phase 1 decisions — implementation handoff

These decisions are authoritative **post-baseline amendment A1** to the approved limited Foundation v0.3.10 package, not a blanket authorization to modify the older frozen baseline in place. The register, Governance, Schema and Evaluation Plan contain the normative amendments.

## Decision 1: P-INC3-LAST-ADMIN-04

- Reject and audit in-app Administrator self-disable and self-role-revoke.
- Reject and audit disabling/revoking the last active Administrator; enforce atomically at both service and database boundaries, and under concurrency.
- External total loss of Administrator access is not an ordinary disable/revoke test setup. The confirmed zero-admin remedy is only owner-authorized, audited **offline** restore or reinstallation, without in-app privilege bypass.

## Decision 2: P-INC3-TEST-CLOCK-05

- Use a consistent test-only clock in a disposable DB to cover 24-hour appointment and activation deadlines; follow real signed installation, activation, role-grant and recovery workflows.
- No direct approved-row date manipulation, production-exposed clock setting, or login-role session-flag bypass.
- Keep all eight xfailed security/governance scenarios in acceptance scope; rebuild them or escalate a concrete irreconcilable spec contradiction.

## Required Phase 1 next actions for Claude Code

1. Read this amendment and the approved v0.3.10 baseline; append the decision identifiers to the repository decision register. Do not rewrite unrelated approved content.
2. Build a reusable isolated test fixture with one consistent test-effective time observed by ceremony services and DB authorization checks, while keeping real-clock fail-closed production behavior. Do not fake expired approved fields via direct UPDATE.
3. Reconstruct the four recovery appointment tests, zero-admin test (missed first contact), expiry sweep tests, and reserved-contact installation test; where a precise prerequisite is impossible under the normative rules, describe the inconsistency and propose a spec-safe replacement rather than waiving it.
4. Re-run the restricted-role negative tests, full regression suite, Ruff, strict mypy and migrations against fresh databases. Fix implementation bugs in Phase 1 only.
5. Update INCREMENT_3_EVIDENCE.md with per-case expected/actual, DB role, fixture/clock configuration and status. Commit only after verified results, and stop before Phase 2; no push/merge without instruction.

## Important availability boundary

The active source repository, PostgreSQL test server and local Claude Code environment were not available in the packaging session. This package records the WDS decision and updates the specification copy, **not** the repository's tests, source code, Git history or live test results.
