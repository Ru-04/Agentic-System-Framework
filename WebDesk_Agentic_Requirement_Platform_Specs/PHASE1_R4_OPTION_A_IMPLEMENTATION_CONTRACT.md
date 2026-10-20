# WebDesk Phase 1 — R4 Option A Implementation Contract (WDS-confirmed)

**Decision:** P-INC3-ACTOR-SESSION-06 (2026-10-20), WDS approves reviewer R4 Option A. **Status:** NORMATIVE governance contract, NOT an implementation-complete claim. Base: approved v0.3.10 limited Foundation + A1. Do not rewrite historical baseline records.

## Security objective / threat model

Protect separation-of-duties rules even if the ordinary application database login `webdesk_app_login` is compromised. That connection cannot mint/edit credentials or sessions, impersonate an Administrator by supplying an actor ID, or forge two distinct approvers. Preserve residual risk from trusted issuer, database owner/guard owner, and colluding administrators; do not imply those are solved.

## Required design boundaries

1. A protected **authentication authority** (a separately restricted credential/session issuer or equivalent strongly isolated signing authority) validates password or activation/reset token, mints/revokes sessions, controls authoritative session state, and never exposes its secret, proof-minting ability or writable trust data to the ordinary application role. Document the isolation mechanism and its deployment prerequisites. An HTTP-layer assertion alone is insufficient.
2. For each privileged mutation, guard-side verification **derives the actor** from authenticated proof bound to a session and scoped operation/resource. Do not treat an actor_user_id parameter or mutable GUC as proof. Proof cannot be minted by `webdesk_app_login`; a readable hash from `sessions` cannot be reused as proof. Check user active status, session expiry/revocation, session_epoch, and contact_revision where relevant. Keep checks and mutations atomic, including concurrent attempts.
3. Credentials and Sessions: REVOKE unrestricted DML from application/ceremony login roles, grant only limited routines actually required. Guard owner/issuer tables, secrets and functions against untrusted roles. Protect verification material and session identifiers from query leakage, logs and API output. Document session issue/reset/logout transaction boundaries and denial audit persistence.
4. Appointment/approval guard: verify acting session, target, role, source approval, issuer authority, no-self and distinct-user rules; reject a single application login faking two administrator identities. Any system ceremony exception is explicit, narrowly scoped and authorized by signed owner artifact and dedicated ceremony role; no in-app zero-admin path.
5. Reject and audit unauthorized access including mismatched actor, revoked/expired session, signature/proof manipulation and replay. Use neutral external responses, retaining required 403/409 rules, and do not lose audits in rolled-back savepoints.

## Engineering choices to propose before the security-sensitive code change

- Where does the separately trusted issuer run, and how are its credentials/keys protected from the app database login? (Dedicated DB role and callable protected verifier, external signing service, or comparable design.)
- What exactly is the bounded session proof (subject, session ID, issued-at/expiry, operation/resource, unique nonce, signing or validation), and who verifies it?
- How are replay, concurrent use, logout, password reset, session_epoch changes and emergency role revocation handled consistently?
- What database roles and GRANT/REVOKE privileges enforce the separation? How is migration-owner guard role access removed from production runtime?
- How are client authentication endpoints and existing bearer-token routes bridged without exposing unprotected session minting? Phase 1 may add only the minimum necessary auth plumbing; defer general-purpose UX and Phase 2 features.

## Release-blocking validation

- Run EVAL-F11j (in EVALUATION_PLAN.md) and the existing F11b–F11i as ordinary tests, on fresh real PostgreSQL, using `webdesk_app_login` and a separately provisioned legitimate trusted issuer role.
- Prove direct credentials/sessions manipulation refused, forged actor context refused, other-user proof refused, revoked and expired sessions refused, stale epoch refused, repeated proof refused where applicable, and two-approver spoofing refused; prove legitimate operations work.
- Confirm R1 guard search-path hardening and TEMP privileges, R2 24h DB constraint, R3 `coverage_sufficient` audit test, N1 reservation protection, N2 PostgreSQL 16 deployment checklist and migration-owner privilege removal.
- Complete full regression and restricted-role security suites, Ruff, strict mypy, Alembic upgrade/downgrade/upgrade and per-case evidence. Do not report READY before independent review.

## Scope control

Phase 1 only; no Phase 2, AI agents, specialist routing, RAG, estimation, SOW, production hosting, or live email. Commit verified changes separately; do not push or merge without approval.
