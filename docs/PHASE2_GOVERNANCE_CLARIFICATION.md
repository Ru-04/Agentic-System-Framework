# Phase 2 governance clarifications (QA remediation sprint)

These records apply WDS decisions given in the Phase 2 QA remediation authorisation. They do not change any approved
specification text. The approved references are cited for each.

## 1. Status codes for refusals (F-04, applied)

WDS rule:

- **403 Forbidden**: missing or insufficient authorisation; wrong actor or wrong target; a missing required
  appointment or approval; a target ineligible under the appointment authorisation policy.
- **409 Conflict**: an expired appointment; a consumed appointment; an otherwise authorised operation that conflicts
  with an existing lifecycle state.

Applied to the recovery and role-assignment pathways (approved basis: EVAL-F11f, EVAL-F11h):

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
without an appointment below two Administrators. It now expects 403 `appointment_required`, following EVAL-F11f
("`role.assign` for Administrator MUST reject an existing active staff user without an approved, unexpired
ceremony-backed Administrator-appointment approval (403)").

WDS has acknowledged this correction as the implementation of the approved requirement. The approved 403/409
semantics are kept. The earlier assertion is not restored.

## 3. Injected approval windows for tests (F-07)

The 24-hour contact-change deadline is approved (EVAL-F11d). Production uses the database default of 24 hours.
Tests pass a short window to `contacts.request_change(..., window=...)` and to the guard
`fn_request_change_with_proof(..., p_window)`. No approval row is back-dated.

Approved basis: P-INC3-TEST-CLOCK-05 (deterministic test-only injected time and disposable databases for installation,
contact activation and expiry scenarios), and the installation-window precedent (GD-003). The injected value is never
set by production code.

## 4. Expiry of stale pending contact changes (F-07, applied)

The approved rule (EVAL-F11d): a pending contact change expires at 24 hours and releases its target reservation.
The expiry sweep applies that transition, but nothing schedules the sweep in production.

Applied: when a new change request for an address is made, pending changes for that address that are past their
deadline are expired and their reservations released first. This is the same transition the sweep applies, limited
to the address needed. It can grant nothing and cannot touch a live request. Each expiry writes an `approval.expired`
audit event. Tests: `tests/committed/test_change_expiry.py`.

The sweep remains a dependency for the other expiries (appointments, tokens, and changes that are not requested
again). Its scheduling belongs to the later operational phase.

## 5. Scope of token delivery (F-06)

Activation and reset token delivery is not implemented in this sprint. `tokens.issue` has no production caller. Its
delivery and wiring belong to the later approved notification and outbox phase (H-50, H-52; ARCHITECTURE
"account contact outbox"). This sprint does not implement production notification infrastructure.
