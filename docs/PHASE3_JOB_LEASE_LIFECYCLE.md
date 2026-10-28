# Job and lease lifecycle (Phase 3)

Scope: the intake job (`workflow_jobs`) and the run it belongs to (`workflow_runs`). The states are the existing
Foundation vocabulary (migration `0007`). Phase 3 adds no state.

## Job states (`workflow_jobs.job_status`)

| State | Meaning | Lease | Who moves it |
|---|---|---|---|
| `queued` | eligible when `available_at <= clock_timestamp()` | none | created with the run; back to here after a retryable failure (with backoff) |
| `leased` | claimed by one worker, attempt counted | `lease_owner` and `lease_expires_at` set | claim (`fn_worker_claim_job`) |
| `waiting_human` | parked for a human decision | none (the schema forbids a lease) | a human path; never a worker claim |
| `completed` | intake finished for this run | cleared | the owner, at finish (`fn_worker_finish_job`) |
| `failed` | attempts exhausted or a permanent refusal | cleared | the owner (permanent or exhausted), or the reaper (`fn_worker_reap_expired`) |
| `cancelled` | the run was cancelled | cleared | run cancellation (`fn_cancel_run_with_proof`) |

## Run states used by intake

`created → intake_pending → parsing → intake_complete → blocked_pending_decision` on success.
`intake_pending` or `parsing` → `failed` (`failure_class = system_failure`) on exhaustion or a permanent refusal.
`failed → intake_pending` only by an Administrator retry (`fn_retry_run_with_proof`). Legal transitions are the
`ALLOWED_TRANSITIONS` table in `runs/service.py`; a guard checks the expected state under a row lock.

## Lease rules

- **Claim.** A job is claimable when it is `queued` and due, or `leased` with an expired lease and attempts remaining.
  Each claim increments `attempts`. The claim transaction commits before any execution (H-20).
- **Lease length.** 120 seconds in production. A test profile may shorten it (`WEBDESK_TEST_LEASE_SECONDS`, refused
  outside `WEBDESK_ENV=test`).
- **Heartbeat (H-22).** While a worker holds a job, a background thread renews the lease every 30 seconds
  (`runs/heartbeat.py`). The renewal stamps `clock_timestamp()`. It renews only the caller's own unexpired lease on a
  job that is still `leased`, so it is refused after a reclaim, a cancellation or a finish. A renewal error is reported
  by class and retried at the next tick. The heartbeat interval is capped at a quarter of the lease, so a short test
  lease still renews safely.
- **Step fence (H-22).** Each step first calls `fn_worker_hold_lease` (migration `0051`). That proves the lease is live
  and holds a `FOR KEY SHARE` lock on the job until the step's transaction ends. The lock does not block the heartbeat's
  update, but it blocks reclaim (`FOR UPDATE SKIP LOCKED`), so no other worker can take the job during a step.
- **Stall.** A single step running longer than the step limit (600 seconds) stops the heartbeat. The worker reports
  `heartbeat.stalled` and the process ends with exit code 70, which releases the step's transaction and lets the lease
  expire. A stall is not left to renew forever.
- **Expiry.** Lease times use `clock_timestamp()` in the database (H-21). A worker cannot renew, finish or requeue a
  lease that has expired, even before another worker reclaims it.
- **Stale worker.** A worker whose lease is lost or expired gets `lease_lost` from its next step, or from the
  heartbeat, and writes nothing further.
- **Reaper (H-24).** A leased job whose lease expired with `attempts >= 3` moves to `failed`. Its run moves to
  `failed` with `system_failure` when the run is in `intake_pending` or `parsing`. The run then leaves the active
  statuses, which releases its slot. The reaper locks the job, then the run (H-25 order). Each reap is audited
  (`job.reaped`, `run.failed`).

## Failure classes

| Outcome | Condition | Result |
|---|---|---|
| Retryable | an unexpected exception (`system_error`) while attempts remain | `queued` with `available_at = now + 2**attempts` seconds (outbox backoff schedule), run back to `queued` |
| Exhausted | a retryable failure on the third attempt | job and run `failed` (`system_failure`) |
| Permanent | a `RunError` (an authorization or schema refusal) | job and run `failed` at once, attempt not retried |
| Lost lease | the lease is no longer owned by the caller | `lease_lost`, nothing written |
| Reaped | expired lease and no attempts left (no worker is running) | job and run `failed` by the reaper |

## Transaction boundaries

One transaction per step, each committed on success:

1. claim (commits the attempt and the lease)
2. begin: the run moves to `parsing` (renews the lease)
3. one per version: renew, then parse
4. finish: renew, transition to `intake_complete` then `blocked_pending_decision` (parked), checkpoint, complete the job,
   audit `run.parked`

Each step begins with the fence (`hold`), so a stale worker is refused before it writes. A failure in any step rolls
back that step only. The failure is recorded in a fresh transaction. An uncommitted step is never a committed result.

## Checkpoints

`workflow_checkpoints` rows are written by the finish step, after its fence, in the same transaction. A stale worker is
refused by the fence before it reaches the insert, so it cannot overwrite a successor's checkpoint.

## Cancellation

`fn_cancel_run_with_proof` locks the run's jobs first, then the run (H-25 order, the same as claim and reap). It moves
queued, leased and waiting jobs to `cancelled` and clears their leases. A worker holding a cancelled job gets
`lease_lost` from its next step. A cancelled run is not resumable: resume applies only to a `waiting_human` run.

## Concurrency guarantees and their tests

| Guarantee | Test |
|---|---|
| Two workers do not claim the same job | `test_two_workers_racing_for_one_queued_job_get_exactly_one_claim` |
| Cancellation waits for a claim, no deadlock | `test_a_cancellation_waits_for_a_claim_without_a_deadlock` |
| Stale worker cannot renew or complete after expiry | `test_a_stale_worker_cannot_renew_or_complete...` |
| A reclaimed job cannot be finished by its former owner | `test_a_worker_that_lost_its_claim_to_a_reclaim_writes_nothing` |
| A stale worker cannot overwrite a successor's checkpoint | `test_a_stale_worker_cannot_overwrite_the_checkpoint_of_its_successor` |
| A killed worker's claim is recovered after expiry | `test_a_killed_worker_is_recovered_after_lease_expiry_and_attempts_are_counted` |
| Three crashes exhaust the attempts; the reaper releases the slot | `test_three_crashes_exhaust_the_attempts_and_the_reaper_releases_the_slot` |
| Retries back off, then end in a terminal failure | `test_retryable_failures_requeue_with_backoff_then_end_in_a_terminal_failure` |
| A permanent refusal fails at once | `test_a_permanent_refusal_fails_at_once_without_a_retry` |
| A waiting-for-human job is not claimed | `test_a_job_waiting_for_a_human_is_not_claimable_by_a_worker` |
| A cancelled run's worker cannot complete; a cancelled run cannot resume | `test_a_worker_whose_run_was_cancelled_cannot_complete_the_job`; `test_a_cancelled_run_cannot_be_resumed` |
| Graceful stop finishes the loop with exit code 0 | `test_the_worker_process_stops_gracefully_when_asked_to_stop` |
