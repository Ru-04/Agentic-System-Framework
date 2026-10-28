# QA F-02: teardown root cause

Scope: the `webdesk_app_login` backend that stayed attached to a disposable hardening database
(`wdst_<run>_hardening`) at teardown, which made the run exit 1 with `LeakedSessionError`.

## Diagnosis

The teardown check (`tests/support/db_cleanup.py`) reports every backend still attached to the database
when the run drops it. The report named one backend: user `webdesk_app_login`, on the run's hardening
database, with no application name. The owner had to be a process-level object that the owner-side
tests did not close.

Reproduction: `tests/hardening` alone, on its own run namespace, failed at `pytest_unconfigure` with the
same single `webdesk_app_login` backend. The suite reported `210 passed` and exited 1 only because of the
teardown check.

Owner: `tests/hardening/test_source_read_authorization.py`, function `_app()`.

- `_app()` is memoised with `@functools.cache` and returns `create_engine(WEBDESK_HARDENING_APP_URL)`.
- It used SQLAlchemy's default pool (`QueuePool`).
- Nothing ever calls `dispose()` on it. The fixture pattern that disposes engines covers only the
  function-scoped `engine` fixture, not this cached helper.
- Each `connect()` returns its connection to the pool. The pool keeps that connection open for the life
  of the Python process. Pytest's `pytest_unconfigure` runs in the same process, so the backend is still
  attached when the run drops its databases. The backend disappears only when the process exits, which
  is why earlier reports looked intermittent and resolved after the fact.

Why the earlier diagnosis missed it: the teardown report had no application name on the backend, and the
owner-side engines (`world`, `conn`, `make_active_user`) were all context-managed and returned correctly.
The leak was in the one place that kept an engine alive without a disposal path.

## Fix (at source)

`_app()` now uses `poolclass=NullPool`. Each use opens and closes its own connection. No pooled session
can outlive the test that used it. The docstring records the reason.

The bounded wait in `drop_when_detached` is unchanged. It still raises `LeakedSessionError` with the
backend list after 5 seconds, so a persistent session still fails the run. The wait only tolerates a
backend that is already exiting.

No `FORCE` drop and no termination of any session was used.

## Verification

- `tests/hardening` on run namespace `probe-hard1` (before the fix): 210 passed, exit 1, teardown reported
  `webdesk_app_login` on `wdst_probe_hard1_hardening`.
- `tests/hardening` on run namespace `probe-hard2` (after the fix): 210 passed, exit 0, no teardown report.
- Full suite runs on fresh namespaces: see `docs/PHASE2_EVIDENCE.md`, section "QA remediation, final sprint".

## Residual

- The session-scoped `app_engine` in `tests/hardening/conftest.py` uses a pool, but it is disposed by its
  fixture finaliser, which runs before `pytest_unconfigure`. It is not the leak. If a future test caches
  another engine without a disposal path, the teardown check will name it again.
- The teardown report still shows an empty application name for hardening backends. Setting
  `application_name` on test engines would make future reports self-identifying. Not done in this sprint.

## Verification on the dedicated cluster

- Three full sequential runs on `127.0.0.1:55442` (`p2-final3-1` to `p2-final3-3`, code `3ffdbbc`): each 681 passed, exit 0, `leftover_dbs=[]`, `attached_sessions=0` after teardown. See `docs/PHASE2_FINAL_GATE_EVIDENCE.md` section 8.
- The bounded wait in `drop_when_detached` was not changed; a persistent session still fails the run. No run in this verification needed the wait to succeed.
