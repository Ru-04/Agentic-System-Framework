# Governance Decision Register (WebDesk Increment 3)

Each decision below was made by the WDS governance owner and is recorded here so that specifications,
code and tests can be aligned to it. A decision is binding for Increment 3 until a later register entry
supersedes it. Decisions do not alter the approved v0.3.10 Foundation specification.

## GD-001 Last Administrator: self-disable and last-Administrator disable or revocation

- **Decision:** Ordinary in-application self-disable is prohibited. Disabling or revoking the last
  active Administrator is prohibited. A zero-Administrator state may arise only through external loss of
  access, and only the approved offline recovery applies to it. In-application recovery from zero active
  Administrators is refused.
- **Implementation:** `webdesk_guard.fn_disable_user` (migration 0018) and `webdesk_guard.fn_revoke_role`
  (migration 0016) each refuse self-action and the last active Administrator in the database. The services
  `identity/disable.py` and `rbac/revoke.py` check the same rules first, so each refusal is audited.
- **Tests:** `tests/integration/test_disable_user.py`; `tests/integration/test_role_revocation.py`;
  `tests/integration/test_denial_branches.py::test_recovery_with_zero_active_administrators_is_refused_and_audited`
  (zero-Administrator state created by an external-state fixture, then the recovery refusal is asserted).
- **Test fixture scope:** the external-state fixture (`tests/support/people.py::external_loss_of_access`)
  is test-only. It represents an account losing access outside the application. It is not reachable from
  any production code path.

## GD-002 Zero-Administrator recovery

- **Decision:** Recovery from a zero-Administrator state is available only through the approved offline
  recovery procedure. The in-application recovery service refuses it with `zero_active_administrators`,
  and that refusal is audited.
- **Implementation:** `ceremony/recovery.py` (unchanged refusal); audit event `ceremony.recovery.denied`.
- **Tests:** as GD-001.

## GD-003 Test deadlines: injectable clocks and windows

- **Decision:** Isolated, test-only injectable clocks and database fixtures are approved to verify the expiry
  of installation and recovery approvals. There must be no production bypass.
- **Implementation:**
  - `apply_install(..., activation_window=...)` and `apply_recovery(..., activation_window=...)` accept a
    deadline window. The default is the approved 24-hour window. The production command-line path passes no
    window, so production always uses 24 hours.
  - The `clock` parameter already present on both services supplies the reference time. Tests may inject it.
- **Tests:** deadline and expiry tests use short windows (seconds) and a real wait, so the database clock
  and the service clock agree. No protected column is back-dated.
- **Limits:** no window can be set through configuration, the command line, or the HTTP layer.

## Consequences for the eight blocked tests

The eight tests in the Phase 1 evidence (zero-Administrator recovery, recovery appointments (4), the sweep of an
unconsumed appointment, the reserved-contact installation, and the install contact past its deadline) are
restored and must pass under GD-001 to GD-003. None is waived.
