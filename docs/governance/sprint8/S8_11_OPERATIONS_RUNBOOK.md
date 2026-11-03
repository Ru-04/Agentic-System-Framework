# S8-11 operations runbook (draft for non-production use)

**Scope:** the Foundation as it exists at `866b314`: the application, the authentication authority, the intake and run worker, the outbox worker, and the operator CLIs. It covers detection, triage and recovery for those components only.
**Status:** DRAFT. Not production. The production boundary (`docs/PRODUCTION_BOUNDARY.md` §5 and §7) still lists the worker supervision, alerting and rehearsed recovery as open. Each procedure below states whether it is tested or only described.
**Not covered:** Sprint 6 specialists, Sprint 7 review and reporting, and the workspace entity (OPEN-11). None is in this repository.

## 1. Detection

| Signal | Source | How to read it | Evidence |
|---|---|---|---|
| Stuck worker jobs | `python -m webdesk.worker --report-stuck --stale-seconds 300` | Prints one JSON line per stuck job (`event: job.stuck`). Exit 0 when nothing is stuck, 1 when a job is stuck longer than the threshold, 2 on configuration error. It changes nothing. | `src/webdesk/worker/__main__.py`; `tests/committed/test_durable_execution.py` (stuck report cases) |
| Outbox delivery failure | Audit event `outbox.delivery.failed` (reason code only); `ops.alert.delivery_failed` at dead letter | Repeated failures for one notice mean the transport is refusing it. The alert row is unique per notice. | `src/webdesk/outbox/worker.py`; `tests/integration/test_outbox_worker.py` |
| Refused authority proofs | Audit event `authority.proof.refused` with a reason code | A spike means repeated misuse or a broken client. | `tests/hardening/test_eval_f11j.py`; `tests/hardening/test_proof_rollback.py`; `docs/PRODUCTION_BOUNDARY.md` §7 |
| Database refused or unavailable | CLI exit 2 (insufficient privilege) or 3 (database unavailable) | Exit 2 means a role or grant must be fixed. Exit 3 means the database is not reachable. | `src/webdesk/cli/diagnostics.py`; `tests/unit/test_phase6_cli.py` |

No alerting system is wired to these signals. Monitoring is therefore manual until the production monitoring blocker (`PRODUCTION_BOUNDARY.md` §7) is closed.

## 2. Triage

1. Run the stuck report. If exit is 0, no job is stuck. Stop.
2. If a job is stuck, note its correlation ID from the report. The correlation key appears in the audit row (migration `0052_audit_correlation.py`).
3. For an outbox notice, query its status and attempt count in `outbox_notices` through an operator role. Do not print the sealed address.
4. Decide between retry (the cause is transient), dead letter (the cause is permanent), and escalation (the cause is a broken component). The decision belongs to the operator, and the audit trail must record it.

## 3. Recovery procedures

### 3.1 Restart a worker after a crash
- The worker needs `WEBDESK_WORKER_DATABASE_URL` (the worker login) and `WEBDESK_STORAGE_ROOT` (the content-store root). Without them it exits with status 2.
- Start the worker again with `python -m webdesk.worker --once --owner <name>` for a single pass, or without `--once` for the loop. Use a new `--owner` for each start.
- Expired leases are reclaimed by the next claim. A job with attempts left is retried. A job with no attempts left is failed by the reaper.
- **Tested:** lease reclaim after a killed worker and attempt exhaustion (`tests/committed/test_durable_execution.py`, cases for killed and exhausted workers).
- **Not rehearsed:** the worker under a real process supervisor. No supervisor exists in this repository.

### 3.2 Run the outbox worker once
- `python -m webdesk.cli.outbox --limit 10`
- The worker needs `WEBDESK_OUTBOX_ENCRYPTION_KEY` and `WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD`. Without them it refuses to start (`ConfigurationError`).
- **Tested:** `tests/integration/test_outbox_worker.py` (threshold and key refusal; back-off; dead letter).

### 3.3 Run the expiry sweep
- `python -m webdesk.cli.sweep` runs one pass in its own transaction. A scheduler runs it repeatedly. This repository adds no scheduler.
- **Tested:** `tests/committed/test_durable_execution.py` (maintenance orchestration cases).

### 3.4 Install or recover the system with the owner's authorization
- `python -m webdesk.cli.install --authorization <file> --operator <id> --verifier <id>` (installation).
- `python -m webdesk.cli.recover --authorization <file> --operator <id>` (recovery ceremony).
- The package defines no console scripts (`pyproject.toml`), so these commands run as modules.
- The authorization file is a signed artifact. Its signature is verified by the ceremony code before any write (`src/webdesk/ceremony/install.py`, Ed25519).
- **Tested:** `tests/unit/test_install_authorization.py`, `tests/integration/test_install_ceremony.py`.
- **Not rehearsed:** the owner's signing ceremony with production key custody (`PRODUCTION_BOUNDARY.md` §2).

### 3.5 Database restore
- See `docs/governance/sprint8/S8_12_RESTORE_REHEARSAL.md`. The rehearsal covers the current head only. The restore procedure is **not** approved for the final schema, because OPEN-18 is open.

## 4. Things that are not procedures
- Do not reset a password, role or grant by direct SQL. Use the governed flows, or record the exception.
- Do not print the contents of `.env` files, the sealed contact address, or any token. The CLIs print counts or reason codes only.
- Do not run any command on a shared or production database from this document. Every procedure here was exercised only on dedicated scratch clusters.

## 5. Evidence and limits
- Correlation keys, reason codes and redaction are tested as described above.
- No runbook drill has been timed. No paging, on-call or escalation path exists.
- This draft is for engineering and the WDS operator. It is not an accepted operations procedure.
