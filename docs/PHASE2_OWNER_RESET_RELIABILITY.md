# Owner-reset reliability (QA D1 and the historical intermittent failure)

## 1. Defect D1 (confirmed, fixed in commit `a7d9460`)

The reset handler `_reset_request` in `src/webdesk/authority/server.py` caught only `SQLAlchemyError` and
`TransportUnavailable`. Any other exception from `_run_reset` or from the transport escaped the handler. The
client then received no HTTP reply instead of the approved neutral `200 {"accepted": true}`.

Fix: the handler catches `Exception` at the request boundary. It logs only the exception class and the SQLSTATE
(from `exc.orig.sqlstate`, when present), never the message. It then sends the same neutral reply. `BaseException`
subclasses (process exit, interrupts) still propagate. `_run_reset` already rolls back on any `BaseException` and
closes the connection, so no partial reset state survives and no second delivery is attempted.

Negative control: the fault-injection module was run against the old narrow handler. 4 of 5 cases failed: the helper
exception, transport exception, failure-after-work and session-cleanup cases. The missing-transport case passed on both
versions, as expected, because it has no exception path. Against the fixed handler, all 5 pass.

## 2. Fault-injection coverage (`tests/committed/test_owner_reset_fault_injection.py`)

| Case | Injected failure | Asserted |
|---|---|---|
| Unexpected helper exception | `request_owner_reset` raises `RuntimeError` | Neutral reply; no delivery; no token; class logged; message not logged |
| Unexpected transport exception | transport `send` raises `RuntimeError` | Neutral reply; one attempt; no token; class logged; message not logged |
| Failure after transactional work | real reset runs (token issued and delivered), then `RuntimeError` | Neutral reply; token rolled back; at most one delivery; class logged |
| Missing transport | `reset_transport=None` | Neutral reply; no token; `reset.request.undeliverable` audited |
| Session cleanup after failure | helper exception | No client session left attached to the test database |

Redacted logging is asserted in the first three cases: the log contains the exception class and not the injected
message.

## 3. Repeated module runs (dedicated cluster, code `ad28ac0`)

- `tests/integration/test_owner_reset.py` and the fault-injection module, run ten times in sequence, each on its own
  namespace: 10 of 10 passed each time (about 10.4 to 11.4 s per run), exit 0.
- Full suite, three sequential passes (`fix-gate-1` to `fix-gate-3`): 688 passed, 1 warning, exit 0 each, no leftover
  databases, no attached sessions.

## 4. The historical intermittent failure (not proven)

The earlier failure (`test_a_second_owner_reset_supersedes_the_first_token`, "capture transport received no message")
logged this line on the authority's stderr: `delivery or database refusal; reply unchanged`. That line is written only
by the branch that catches `SQLAlchemyError` or `TransportUnavailable`. An unhandled exception (D1) would not produce it.
So the historical request reached the handled database branch.

At that time the same suite run also produced `password authentication failed for user "webdesk_authority_login"`
from the authority. That failure comes from a shared, cluster-wide role password that another session rotated. A failed
connection in `_run_reset` is an `OperationalError`, which is a `SQLAlchemyError`, so it takes the handled branch.

This is consistent with cross-session contamination, but it is not proven. The original line did not record the
exception class or SQLSTATE; the diagnostic that does was added afterwards. No run since has produced the failure,
and no run since has been contaminated.

## 5. Residual risk and acceptance impact

| Risk | Classification | Acceptance impact |
|---|---|---|
| Historical cause not proven (cross-session password rotation is the best explanation) | LOW for the code path (no reproduction on a clean cluster in 10 module runs and 3 full runs) | Not blocking on its own. QA should note that the root cause is a hypothesis. |
| Unhandled reset-path exception (D1) | Fixed and tested; a regression would now break only the test that injects it | Closed by the fix and the tests above. |
| Shared authority login role password (cluster-wide) | Test-environment risk, not a production behaviour | Must not be used for production or shared clusters; each phase must use its own cluster (see `docs/PHASE2_DEDICATED_TEST_CLUSTER.md`). |
