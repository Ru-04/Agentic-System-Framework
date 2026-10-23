# Production boundary (WDS decision 7, 2026-10-23)

**Status: production deployment is BLOCKED.** This document records what production requires and what
the repository verifies today. It does not authorize a deployment, and nothing here claims production
readiness. Development and security validation continue in isolated, non-production environments.

## What is verified in this repository (non-production)

- Database privileges: migrations 0001 to 0038 on fresh databases, with the restricted-login, worker,
  outbox, ceremony and authority suites (`tests/hardening`, `tests/committed`, `tests/integration`).
  See `tests/hardening/test_privilege_audit.py` and `docs/INCREMENT_3_EVIDENCE.md`.
- The authority runs as a separate process on loopback, with a shared secret of at least 32
  characters, and refuses `WEBDESK_ENV=production` (`src/webdesk/authority/server.py`).
- Reset delivery is disabled by default. The SMTP adapter is refused unless every gate is set,
  including `WEBDESK_SMTP_VERIFIED=true` (`src/webdesk/delivery/smtp.py`).

## Blockers and dependencies

Each item must be satisfied, and its verification recorded, before production is considered.

### 1. Trusted authority deployment

- The authority is a local integration process. It has no production deployment, supervision,
  restart policy, resource limits or network placement.
- Required: a deployment that runs the authority under its own operating-system identity, with no
  access to the application's files, and that is reachable only from the application tier.
- Current gap: the authority and the application run on one development machine.

### 2. Signing-key and secret custody

- The authority secret is an environment value. Database login passwords are in git-ignored
  `.env.*.local` files. The outbox contact-encryption key is an environment value.
- Required: a key-management service or hardware-backed store; documented rotation; no secret in
  files, logs or audit details; separate keys per environment.
- Current gap: no key custody, no rotation procedure, no revocation procedure for compromised keys.

### 3. Authenticated transport

- The application reaches the authority over loopback HTTP with a bearer shared secret. There is no
  TLS and no client-certificate authentication.
- Required: mutually authenticated transport (for example mTLS) between the application and the
  authority, with certificate issuance and rotation documented.
- Current gap: the transport is unauthenticated beyond the shared secret and is not encrypted.

### 4. Separate database identities

- Required, all provisioned by deployment (not by a migration, because migrations do not hold
  secrets):
  - `webdesk_app_login`: member of `webdesk_app` only.
  - `webdesk_authority_login`: member of `webdesk_authority` only.
  - `webdesk_intake_worker_login`: member of `webdesk_worker` only (decision 8, tested).
  - An outbox worker login: member of `webdesk_outbox` only.
  - An owner role for migrations that is **not** a superuser.
- Current gap: the local Docker setup uses a superuser for the database. That must not be copied to
  any deployment.

### 5. Worker deployment and isolation

- The intake worker (`process_one`) has no production caller in this repository. Its scheduler,
  process supervision and monitoring are not built.
- The outbox worker (`OutboxWorker`) likewise has no production process definition.
- Required: each worker in its own process under its own login, with its own restart policy, and with
  the lease and retry parameters documented.

### 6. Approved email transport

- The transport interface is provider-independent. Only the SMTP adapter exists, and it is disabled by
  default.
- Required before any real reset or activation delivery: an approved approved-contact transport
  configured with its credentials, a delivery test to an approved contact, and only then
  `WEBDESK_RESET_DELIVERY=smtp`, `WEBDESK_SMTP_VERIFIED=true`. Activation delivery needs the same
  verified transport.
- Current state: no real delivery is enabled. The local test suite uses the capture transport only.

### 7. Operational monitoring and recovery

- Monitoring: an alert on `ops.alert.delivery_failed`, on `authority.proof.refused` and
  `source.content.denied` volumes, and on failed authentication. None is wired to an alerting system.
- Recovery: backup and restore of the database, tested; the zero-Administrator recovery process
  (GD-002) rehearsed with the approved owner signing ceremony; incident response for a compromised
  authority, a compromised worker and a leaked read grant.
- Current gap: none of these procedures is written or rehearsed.

## Items that are not production dependencies but must not be mistaken for them

- The approved email transport and the trusted authority are separate blockers. Passing the
  repository's tests does not satisfy either.
- The authority in this repository is a development process. Its correctness against the test suite
  is not evidence of its production security.

## Sign-off

Production sign-off requires: independent Phase 1 review passed; each blocker above closed with
evidence; the deployment checklist (`docs/DEPLOYMENT_CHECKLIST.md`) completed; and an explicit WDS
approval of the production deployment. No item in this document is approved.
