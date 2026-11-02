# Phase 2 dedicated PostgreSQL test cluster

Purpose: a PostgreSQL cluster used only by Phase 2 verification. No other worktree or phase connects to it.

## Topology

| Item | Value |
|---|---|
| Compose project | `webdesk-p2-test` |
| Container | `webdesk-p2-postgres` (image `postgres:16.4`) |
| Volume | `webdesk-p2-test_webdesk_p2_test_pgdata` (independent of every other volume) |
| Host endpoint | `127.0.0.1:55442` (published to the container's 5432) |
| Server identity (system identifier) | `7701671162267615270` (recorded at every run) |
| Shared clusters not used | `5433` (main checkout and others), `5434`, `5435`, `5436`, `5440`, `55434` (Phase 4) |

Port 55432 was not used: a stopped `homeserve` container publishes it.

## Roles

Created on this cluster only. Passwords are generated per cluster and kept in the git-ignored file `.env.phase2-test.local`. No password is recorded here.

| Role | Attributes | Purpose |
|---|---|---|
| `webdesk_owner` | cluster superuser (image default) | Provisioning only |
| `webdesk_integration_owner` | LOGIN, CREATEDB, CREATEROLE | Migrations and namespace creation; member of `webdesk_app`, `webdesk_ceremony`, `webdesk_authority`, `webdesk_guard_owner`, `webdesk_worker`, `webdesk_outbox` with SET and INHERIT |
| `webdesk_test_owner` | LOGIN, NOSUPERUSER | Hardening owner; member of `webdesk_ceremony` |
| `webdesk_app_login` | LOGIN, NOSUPERUSER | Restricted application login; member of `webdesk_app` |
| `webdesk_intake_worker_login` | LOGIN, NOSUPERUSER | Restricted worker login; created by the test code as the integration owner, member of `webdesk_worker` |
| `webdesk_authority_login` | created by migration 0023 | Authority login; password set per run by the test code |

Group roles (`webdesk_app`, `webdesk_ceremony`, `webdesk_authority`, `webdesk_guard_owner`, `webdesk_worker`, `webdesk_outbox`) are created by migrations.

## Provisioning order

1. `docker compose -p webdesk-p2-test -f <compose file> up -d` with the password variable set from the local file. The compose file binds `127.0.0.1:55442:5432`.
2. As `webdesk_owner`, create `webdesk_integration_owner`, `webdesk_test_owner` and `webdesk_app_login`. Set the database owner to `webdesk_integration_owner`.
3. Migrate the base database to head as `webdesk_integration_owner`.
4. As `webdesk_owner`, grant `webdesk_app` to `webdesk_app_login` and `webdesk_ceremony` to `webdesk_test_owner`. As `webdesk_owner`, grant the group roles to `webdesk_integration_owner` `WITH INHERIT TRUE, SET TRUE`. The initial grants lacked SET, which made `SET ROLE` fail.
5. After the base database is at head (migration 0046 creates the group role `webdesk_test_clock`), grant it to the integration owner as the cluster superuser: `GRANT webdesk_test_clock TO webdesk_integration_owner WITH INHERIT TRUE, SET TRUE;`. Only a test cluster grants this role. Production never does, so the contact-change window can only be shortened by a test session (QA D2).
6. Let the worker-login test create `webdesk_intake_worker_login` as the integration owner. Do not pre-create it as superuser: `ALTER ROLE` in the test then fails, because the integration owner has no ADMIN option on it.

## Isolation verification

- `run_p2.py` (scratch tooling, not committed) builds every URL from the local file, refuses any URL whose port is not 55442, and refuses to start while any session is attached to a namespace database on this cluster.
- It removes every inherited `WEBDESK_*` variable and sets only the four variables that the tests read.
- It queries `inet_server_port()` and `pg_control_system().system_identifier` before each run. The in-container port is 5432; the host mapping is 55442.
- Every run reports leftover namespace databases and attached sessions after teardown. All three final runs reported `leftover_dbs=[]` and `attached_sessions=0`.
- No source or test file hard-codes port 5433 or any other cluster.

## Known limits

- The worker login and the authority login are created or re-keyed by test code. Their grants depend on test order inside one run. A new cluster must follow the provisioning order above.
- The integration owner holds membership in every group role. This is inherited from the earlier Phase 2 cluster and is how the tests are written; it is recorded as a test-only grant.
