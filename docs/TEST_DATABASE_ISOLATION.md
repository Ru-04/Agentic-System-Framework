# Test database isolation

Owner: Foundation engineering. Remediation of QA findings F-02, F-03 and F-12 (Phase 2 QA).

## 1. Namespaces (F-03)

Every pytest session owns one **run namespace**:

- The run identifier comes from `WEBDESK_TEST_RUN_ID` (explicit) or is generated as `<worktree>-<8 hex>`. It must
  match `^[a-z0-9][a-z0-9-]{2,23}$`.
- Database names are `wdst_<run id with _>_<role>`, where the role is `tpl`, `integration`, `hardening`, or
  `c<10 hex>` for a committed-test database. Names are at most 63 characters.
- `pytest_configure` (tests/conftest.py) creates the run's **template** (empty), refuses if any database with the
  prefix exists, migrates the template to head, clones the **integration** and **hardening** databases from it,
  labels each one with a comment (`webdesk test run <id> worktree <path> pid <pid>`), and points these variables at
  them: `WEBDESK_TEST_DATABASE_URL`, `WEBDESK_INTEGRATION_OWNER_URL`, `WEBDESK_HARDENING_OWNER_URL`,
  `WEBDESK_HARDENING_APP_URL`. Users and hosts are unchanged.
- Committed-test databases are cloned from the run's template and named inside the run's namespace.
- `pytest_unconfigure` drops only the run's labelled databases, after checking that no other session is attached,
  and restores the environment.

Database privileges: migration 0020 revokes `TEMP` on the database it migrates (R1). `CREATE DATABASE ...
TEMPLATE` does not copy database privileges, so every clone (namespace and committed-test) re-applies that revocation
through `mirror_database_privileges`. Without it, the application role could create temporary objects in a clone,
which the R1 test (`test_n28`) refuses in a migrated database. The first full run caught exactly this, and the
migration catalog test now compares `TEMP` for PUBLIC, `webdesk_app` and `webdesk_ceremony`.

Nothing outside the namespace is read, altered or dropped.

### Refusal of an unsafe reuse

If a namespace prefix already has databases, the session stops with a usage error that names them and changes
nothing. Verified: a sentinel database named with the prefix of `qa-refuse-01` caused
`ERROR: namespace 'wdst_qa_refuse_01_' already has databases ['wdst_qa_refuse_01_tpl']; choose another
WEBDESK_TEST_RUN_ID. Nothing was changed.` The sentinel was removed afterwards.

### Module-level reads

A test or conftest module that reads a database variable at import time sees the value that existed when it was
imported. pytest imports the conftest files for the command-line paths before `pytest_configure` runs. The hardening
conftest therefore reads its URLs inside fixtures. Test modules collected later may read at import time.

Finding caught during this remediation: the hardening conftest read its URLs at import, so the hardening tests ran
against the shared Phase 2 database (at head 0043, without 0044 and 0045). The privilege audit passed against that
stale database. After the fix, the same audit ran against the run's own database and correctly reported the new
application-callable function, which is now pinned.

## 2. Concurrent runs

Verified with two sessions running at the same time, under `qa-alpha-01` and `qa-bravo-01`:

| Session | Modules | Result |
|---|---|---|
| alpha (`qa-alpha-01`) | `test_phase2_concurrency.py`, `test_change_expiry.py` | 8 passed |
| bravo (`qa-bravo-01`) | `test_recovery_status_codes.py` (run while alpha was active) | 3 passed |

After both finished, no `wdst_*` database remained, and the other `webdesk_*` databases were unchanged.

## 3. Teardown (F-02)

`tests/support/db_cleanup.py` drops a database only when no other session is attached.

- It waits up to 5 seconds (`DETACH_WAIT_SECONDS`) for backends to exit. A backend that is still exiting is
  tolerated. A connection the test still holds stays open for the whole wait.
- If a session is still attached, it raises `LeakedSessionError`. The message names the test
  (`PYTEST_CURRENT_TEST`), and lists each backend: process id, user, application name, state, backend type, start
  time and current query.
- `DROP ... WITH (FORCE)` is never used. It would hide a leak and would terminate sessions this run does not own.

The wait is a bounded safeguard, not a diagnosis. The cause of the earlier intermittent reports is not established;
see the Phase 2 remediation evidence, section 5.

## 4. Leftover databases (F-12)

Before this remediation, earlier runs left disposable databases behind. A cleanup was denied by the execution
environment, and this remediation does not bypass that denial. The leftovers are **not** attributed to this worktree.

What exists (as reported; re-check before any cleanup):

- about 25 `webdesk_test_*` databases,
- six `webdesk_template_*` databases,
- two `webdesk_probe*` databases.

Some of the `webdesk_test_*` names match teardown errors recorded in the QA evidence. Ownership cannot be proven from
names alone, so none is assumed to belong to this worktree.

### Authorised cleanup prerequisites

A database may be dropped only when all of these hold:

1. It is in the list above, or it is named by a documented run, and its name matches `webdesk_test_*`,
   `webdesk_template_*` or `webdesk_probe*`. Fixed Phase 2 names (`webdesk_p2_*`) and any database outside these
   prefixes are never dropped by cleanup.
2. It has no attached session when checked immediately before the drop (`pg_stat_activity`).
3. No pytest or migration process is running against the cluster.
4. The drop is `DROP DATABASE` without `FORCE`.
5. The names dropped are recorded with the evidence.

Labelled namespace databases are dropped by the run itself. Unlabelled leftovers need the owner's decision, and
the owner who performs the cleanup, not the test suite, should run it.
