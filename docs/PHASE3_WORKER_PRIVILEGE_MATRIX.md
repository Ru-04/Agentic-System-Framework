# Worker privilege matrix (Phase 3)

Role model (migrations `0031` and `0050`). The intake worker logs in as a login role that is a member of
`webdesk_worker` and of nothing else. The test login is `webdesk_intake_worker_login`; deployment provisions the real
login with a secret (see `tests/committed/test_worker_login.py`).

## Table privileges of `webdesk_worker`

| Object | Privilege | Reason |
|---|---|---|
| `workflow_runs` | SELECT | run state and revision reads |
| `run_input_snapshots` | SELECT | the versions a run will parse |
| `source_versions` | SELECT | version status and scan status reads |

The worker holds no INSERT, UPDATE or DELETE on any table. Every write goes through a guard function.

## Guard functions executable by `webdesk_worker`

| Function | Purpose | Lease rule |
|---|---|---|
| `fn_worker_claim_job` | claim the next eligible job with a lease and an attempt | claims queued jobs, and expired leases with attempts left (`clock_timestamp()`) |
| `fn_worker_renew_lease` | renew the caller's lease | refused unless the lease is owned by the caller and unexpired (`0050`) |
| `fn_worker_hold_lease` (`0051`) | confirm the caller's live lease and hold a `FOR KEY SHARE` lock on the job for the step's transaction | refused unless owned and unexpired; the lock blocks reclaim and does not block the heartbeat (H-22) |
| `fn_worker_lock_run` | lock a run row for a state change | none |
| `fn_worker_transition_run` | guarded run state change (expected state must hold) | none; legality is checked in worker code (`ALLOWED_TRANSITIONS`) |
| `fn_worker_set_run_status` | set a run's status (queued after requeue) | none |
| `fn_worker_mark_inputs_changed` | mark a run's inputs as changed | none |
| `fn_worker_finish_job` | complete or fail the caller's leased job | refused unless owned and unexpired (`0050`) |
| `fn_worker_requeue_job` | requeue the caller's job with backoff | refused unless owned and unexpired (`0050`) |
| `fn_worker_begin_parse` | move a version to parsing | none |
| `fn_worker_mark_version` | record a version's parse status | none |
| `fn_worker_insert_segment` | write a parsed segment | none |
| `fn_worker_insert_checkpoint` | write a checkpoint (identifiers and flags only; the trigger enforces the key set) | none (written only after a successful renewal in the same transaction) |
| `fn_worker_record_audit` | write one system audit event | none |
| `fn_worker_reap_expired` (`0050`) | fail expired jobs with exhausted attempts, and their runs | locks job then run; expired leases only; attempts exhausted only |
| `fn_worker_stuck_jobs` (`0051`) | read-only report of expired leases not reclaimed and queued jobs not claimed (G-8) | none; changes nothing |

`tests/hardening/test_privilege_audit.py` pins this exact set for `webdesk_worker`. A new function must be added to the
pin deliberately (the reaper was added in Phase 3).

## Owner and definer

Each function above is `SECURITY DEFINER`, owned by `webdesk_guard_owner`, with `search_path = pg_catalog, public`.
`PUBLIC` has no EXECUTE on any guard or authority function (privilege audit).

## What the worker login cannot do

Covered by existing tests (`tests/committed/test_worker_login.py`): it cannot write intake or run tables, cannot call a
human wrapper, and cannot reach another role.
