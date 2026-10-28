# Phase 2 governance clarifications (QA remediation sprint)

These records apply WDS decisions given in the Phase 2 QA remediation authorisation. They do not change any approved
specification text. The approved references are cited for each.

## 1. Status codes for refusals (F-04, applied)

WDS rule:

- **403 Forbidden**: missing or insufficient authorisation; wrong actor or wrong target; a missing required
  appointment or approval; a target ineligible under the appointment authorisation policy.
- **409 Conflict**: an expired appointment; a consumed appointment; an otherwise authorised operation that conflicts
  with an existing lifecycle state.

Applied to the recovery and role-assignment pathways (approved basis: EVAL-F11f, EVAL-F11h). The EVAL-F11h text (v0.3.10)
states "403 for authorization, 409 for stale/consumed/deadline conflict". The classification of
`appointment_target_ineligible` as 403 is an interpretation of that rule, not a quoted row. No WDS record of its
approval was located (see section 4).

| Refusal | Code | Class | Where |
|---|---|---|---|
| `appointment_target_ineligible`: appointment target is not an active account, or already holds the Administrator role | 403 | target ineligible under the appointment policy | `ceremony/recovery.py` |
| `coverage_sufficient`: two Administrators are effective | 409 | lifecycle state | `ceremony/recovery.py` |
| `replacement_reserved`: a replacement is already reserved | 409 | lifecycle state | `ceremony/recovery.py` |
| `zero_active_administrators` | 409 | lifecycle state (in-system recovery is not permitted; P-GATE1-ZERO-ADMIN-RECOVERY-03) | `ceremony/recovery.py` |
| `contact_reserved`: the contact is reserved | 409 | lifecycle state | `ceremony/recovery.py`, `identity/contacts.py` |
| Grant without a required appointment (below two Administrators) | 403 `appointment_required` | missing appointment | `rbac/assign.py` |
| Appointment not held, not an approved administrator appointment, or for another account | 403 `appointment_not_held` | target or appointment authorisation | `rbac/assign.py` |
| Appointment expired or consumed | 409 `appointment_consumed_or_expired` | expired or consumed appointment | `rbac/assign.py` |
| Grantor not an active Administrator | 403 `not_administrator` | authorisation | `rbac/assign.py` |
| Recipient not active | 409 `recipient_not_active` | lifecycle state of the recipient | `rbac/assign.py` |

Distinction preserved: the recipient of an Administrator grant that is not active returns 409, because the recipient's
lifecycle state conflicts with the grant, not because of the identity of the actor. An appointment target that is not
an active account returns 403, because it is not an eligible target under the appointment policy. The two causes
behind `appointment_target_ineligible` (not active, already an Administrator) share one code and one rule.

Database-raised conflicts that have no named reason return 409 (`recovery.py`, `database_refused`).

Tests: `tests/integration/test_recovery_status_codes.py` (403 for an inactive target and for the remaining
Administrator; 409 for coverage sufficient); `tests/integration/test_role_assignment.py` (403 for the missing
appointment); `tests/committed/test_deadlines.py` (409 for expired and consumed appointments).

## 2. Acknowledgement of the H-12 Phase 1 test correction (F-09)

The Phase 1 test `test_below_two_an_administrator_grant_needs_an_appointment` previously expected 409 for a grant
without an appointment below two Administrators. It now expects 403 `appointment_required`.

Spec basis (located): EVAL-F11f in `WebDesk_Agentic_Requirement_Platform_Specs/EVALUATION_PLAN.md` states that with
exactly one active Administrator, `role.assign` for Administrator MUST reject an existing active staff user without an
approved, unexpired ceremony-backed Administrator-appointment approval (403). The implementation follows that text.

WDS acknowledgement (not located): this document previously stated that WDS acknowledged the correction. No record
of that acknowledgement exists in the repository: the specs and governance registers contain no entry for the Phase 2
test correction. Evidence status: **the requirement is located; the WDS acknowledgement is missing**. No approver
identity or retrospective approval is recorded here. QA F-09 remains blocked on that record (section 4).

## 3. Contact-change approval window (F-07, D2)

Normative duration (located): 24 hours. Sources: changelog v0.3.7, item T8 (`24h pending contact-change TTL`);
EVAL-F11d (`24 hours` deadline from contact approval); GOVERNANCE P-INC3-TEST-CLOCK-05 (test-only injected time is
approved for tests; production uses real authoritative time and rejects any test-only clock mechanism).

Implementation (migration 0046, QA D2):

- The database boundary fixes the window. `fn_request_change_with_proof` accepts a window other than 24 hours only when
  the session login belongs to `webdesk_test_clock`. The check runs before the proof is consumed. The deadline is
  `now()` on the database clock plus the window.
- `webdesk_test_clock` is a group role with no members in production. Only a test cluster grants it to its integration
  owner (`docs/PHASE2_DEDICATED_TEST_CLUSTER.md`, step 5).
- Restricted-login tests (`tests/hardening/test_contact_change_window.py`) show that a 1-hour window is refused with
  SQLSTATE 42501 and that the 24-hour window reaches the proof check.
- The application never passes a window; the default is 24 hours.

## 4. Governance evidence status (QA D6, F-06, F-09)

| Item | Status | Evidence located | Missing |
|---|---|---|---|
| F-04 403/409 mapping | Interpretation documented | EVAL-F11f (403 for missing appointment), EVAL-F11h (403 authorization, 409 conflict) | A WDS record for the classification of `appointment_target_ineligible` as 403. |
| F-09 H-12 test correction | Requirement located; acknowledgement missing | EVAL-F11f text (403) | The WDS acknowledgement of the correction. |
| D6 (this document's citations) | Evidence gap | The specs folder contains no record of the Phase 2 QA remediation authorisation. | The authorisation record itself. |
| F-06 token issuance | Phase 6 dependency (approved scope) | `docs/INCREMENT_3_HARDENING_PLAN.md`: H-50 recovery CLI and H-52 outbox are Phase 6 items. | None for Phase 2; production dependency for Phase 6. |

No approver, date or approval is invented for any row. Each gap is a governance dependency for WDS, not an implementation
defect.
