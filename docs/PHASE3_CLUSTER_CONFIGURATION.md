# Phase 3 cluster configuration evidence

No credential is recorded in this file or in any tracked file. Passwords live only in scratch env files outside the repository.

## Designated Phase 3 development cluster

- Address: `127.0.0.1:5440`, PostgreSQL 16.4 (Debian), in the Docker compose project `webdesk-phase3-closure`
  (container `webdesk-phase3-closure-postgres-1`, named volume `webdesk-phase3-closure_pgdata`).
- Verified system identifier: `7701670125748215847` (checked on 29 October 2026 after a Docker restart; identical to the
  identifier recorded at provisioning).
- Superuser: the bootstrap role of this cluster (its name is kept in the scratch env file, not here). Owner roles:
  `webdesk_integration_owner` (CREATEDB, CREATEROLE), `webdesk_test_owner` (NOSUPERUSER), `webdesk_app_login`
  (NOSUPERUSER). Databases: `webdesk_p3c_integration` (owner `webdesk_integration_owner`) and `webdesk_p3c_hardening`
  (migrated as the bootstrap superuser; objects handed to the integration owner, the state the test fixtures expect).
- Migration head of both databases: `0054_contact_change_reject_clock`.

## Why some files point to 5435

- `.env.hardening.local` and `.env.integration.local` are git-ignored, worktree-local files. They contain owner and
  app-login URLs for the historical cluster `127.0.0.1:5435`, database `webdesk_hardening` and `webdesk_integration`,
  which was created separately (under the shared test-cluster template, project `webdesk-phase3-test`). They were never
  changed to 5440, because their passwords belong to the 5435 roles, and the 5440 roles have different passwords.
- The reconciliation decision is to keep these two files unchanged: they describe the historical 5435 cluster, which is
  preserved. Phase 3 development verification on 5440 uses a scratch env file derived from the 5440 bootstrap (not in the
  repository, not printed, not committed).
- No tracked file references 5435, except the evidence report's historical note (`docs/PHASE3_ENGINEERING_EVIDENCE.md`,
  section "Dedicated test cluster"), which is kept as history.

## Other clusters (not touched by this work)

- `127.0.0.1:5433` (shared main cluster), `5434`, `5436` (other test clusters), `5435` (historical Phase 3 test cluster,
  preserved), `5450` (QA cluster of the previous author-led review), `5451` (fresh-cluster remediation), `5452` (independent
  QA cluster), `55442` (Phase 2 development), `55434` and `55435` (Phase 4). None was modified, stopped, or connected to
  by the verification runs in this sprint.

## Leftover test artifacts on 5440 (not removed; owner approval required)

Standing rule for this worktree: leftover databases are not deleted without the owner's approval. Found after the
interrupted full run and reported, not removed:

- One database named `webdesk_test_*` or `webdesk_template_*` (from the interrupted run).
- Two test login roles matching `webdesk_intake_test_<12 hex>` or `webdesk_authority_test_<12 hex>`, created by the
  interrupted run and not removed by normal exit. Each is a candidate for the documented purge (dry run first).

Exact names are listed in the verification report with their counts; they are not deleted by this sprint.

## Teardown at the end of the final verification (29 October 2026)

- Server identity re-verified: system identifier 7701670125748215847, port 5432 inside the container (5440 on the host).
- No open client sessions after the regression.
- Leftover resources, not removed (no established ownership and cleanup authorization for deletion):
  - one template database `webdesk_template_6b5f4ad4c3` (from a test run);
  - one login role `webdesk_authority_test_68ad6eeb8c02` (from a test run; no session attached).
  The owner may approve removal with the documented purge procedure (dry run first).
