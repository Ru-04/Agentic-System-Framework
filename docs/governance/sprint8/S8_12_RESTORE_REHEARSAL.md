# S8-12 backup and restore rehearsal record

**Requirement:** S8-12 (RED in the dependency matrix). **This record covers preparation and a rehearsal on the current head only.**
**Not covered:** the final-schema rehearsal. It is BLOCKED on OPEN-18 (final migration list). No recovery claim is made for the final schema.

## 1. Procedure (as tested)
1. Create a committed source database with installed Administrators (`tests/conftest.py` fixtures).
2. Take a logical dump of the source with `pg_dump` (plain SQL, owners and grants kept), run inside the dedicated container.
3. Restore the dump into a fresh database with `psql -v ON_ERROR_STOP=1`.
4. Compare source and restored: alembic revision; schema DDL digest (comment lines and connect lines removed, owners and grants kept); row counts of every public table; table privileges granted to `webdesk*` roles.
5. Drop the restored database.

Test: `tests/recovery/test_s8_12_restore_rehearsal.py`. Run on request with `S8_RECOVERY=1 S8_DOCKER_CONTAINER=<container>`.

## 2. Results (dedicated cluster, PostgreSQL 16.4)

| Run | Dump (s) | Restore (s) | Tables compared | Rows | Alembic revision | Result |
|---|---|---|---|---|---|---|
| 1 | 0.358 | 1.868 | 32 | 62 | `0059_int_mark_inputs_fence` | passed |
| 2 | 0.350 | 2.013 | 32 | 62 | `0059_int_mark_inputs_fence` | passed |
| 3 | 0.363 | 1.857 | 32 | 62 | `0059_int_mark_inputs_fence` | passed |

Dump size: about 314 kB. Row count is small because the source holds only the installed fixtures.

## 3. What these numbers are, and are not
- They are **measured times for this rehearsal**, on one scratch cluster, with a small dataset. They are not an accepted RPO or RTO.
- RPO is not measured here. A logical dump is a point-in-time snapshot. Its RPO equals the interval between dumps, which no schedule defines.
- The rehearsal does not test a corrupted or partial dump, a restore onto a different server version, point-in-time recovery, or restore under load.
- Role verification is limited to privileges on tables. Cluster-level role memberships are not part of a database dump and were not restored by this test. They are provisioned by the deployment.
- The restored database was never used by an application. Its consistency was checked only by the comparisons in §1.

## 4. Remaining for S8-12
- Final-schema rehearsal after OPEN-18 is resolved.
- An approved RPO and RTO, which WDS must set. No threshold is set here.
- A backup schedule and retention policy, which the production boundary treats as open.
