# Project-local test IDs (C-6)

These IDs are not in the approved specification. They are proposals used to name tests in this
repository. Registering any of them in `EVALUATION_PLAN.md` requires explicit WDS approval (GOVERNANCE
§2 and the specification change rules). Until then they are project-local.

| Project-local ID | Purpose | Proposed governing text | Test files |
|---|---|---|---|
| F-CFG-01 | Settings profiles fail closed without production configuration | ARCH §14; GOV §8 | `tests/unit/test_config.py` |
| F-CLI-01 | Installation CLI refuses without database configuration | P-GATE1-BOOTSTRAP-02 | `tests/unit/test_install_authorization.py` |
| F-MIG-01 | Migrations apply and reverse cleanly | ARCH §14 | run via `alembic upgrade head` / `downgrade` (no pytest file) |
| F-OUT-01 | Sealed prior-contact address is readable only for its row | EVAL-F11g (sealing) | `tests/unit/test_contact_box.py` |
| F-API-01 | Domain refusals map to stable reasons; auth replies neutral | SCHEMA §3 DTOs; EVAL-F11e | `tests/unit/test_api_app.py` |
| F-TX-01 | Refusals keep denial audits; other errors roll back | EVAL-F12 | `tests/committed/test_committed_phase_a.py` |
| F-EXP-01 | Expiry sweep expires requests and revokes lapsed tokens | EVAL-F11d, F11f | `tests/integration/test_phase_a.py` |
| F-REP-01 | Replacement create only after rejection or expiry, same contact | SCHEMA §3.1 (C3) | `tests/integration/test_phase_a.py` |

## Note on the committed-row tests

`tests/committed/` creates and drops a fresh PostgreSQL database for each pytest session, because
installation can run only once per database. This keeps the shared test database clean.
