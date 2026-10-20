# Deployment checklist (C-10 and open prerequisites)

This list records what must be true before any non-local deployment. It does not authorize one.
Hosting is deferred (D-16); production delivery, key custody and owner signing are open.

## Database roles

- [ ] The owner role used for migrations is **not** a superuser. The local Docker setup uses a
      superuser and must not be copied.
- [ ] `webdesk_app` is a login role with membership in no other role. It holds only the grants in
      migrations `0001`–`0006`.
- [ ] `webdesk_ceremony` is a login role used only by the installation and recovery CLIs and the
      expiry sweep. Its login credentials are held by the operator, not in repository files.
- [ ] Audit tables reject `UPDATE`, `DELETE` and `TRUNCATE` by trigger, including for the owner.
- [ ] Set `WEBDESK_DATABASE_URL` for the owner role and `WEBDESK_APP_DATABASE_URL` for the app role.

## Configuration (fail closed; see `config.py`)

- [ ] `WEBDESK_ENV=production`, with no capture transport.
- [ ] Production delivery provider approved and configured (open: not implemented).
- [ ] `WEBDESK_EMAIL_DOMAIN_ALLOWLIST` and `WEBDESK_EMAIL_ALIAS_DENYLIST` set to WDS-approved values.
- [ ] `WEBDESK_OWNER_PUBLIC_KEY_PATH` points to a reviewed Ed25519 public key (open: owner identity
      and key custody).
- [ ] Rate-limit values and `WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD` set to approved values (open:
      final rate limits).
- [ ] `WEBDESK_OUTBOX_ENCRYPTION_KEY` generated per environment and stored in an approved secrets
      store. Custody and rotation are not decided (C-9).

## Decisions still open

- [ ] Password minimum (proposed 12) and session lifetime (placeholder 8 hours) confirmed (C-8).
- [ ] Owner identity, signing key custody and independent verification procedure (BOOTSTRAP-02).
- [ ] Offline recovery runbook for zero active Administrators (P-GATE1-ZERO-ADMIN-RECOVERY-03).
- [ ] Hosting, network egress and vendor allowlist (D-16, D-02).
- [ ] Outbox dead-letter threshold and final rate limits.

## Not permitted until the above are closed

- No production account onboarding, activation or reset.
- No prior-contact change notices sent to real addresses.
- No live network evidence calls.

## PostgreSQL 16 role and privilege setup (N2, Amendment A2 / Phase 1)

Required before any environment holds real data. Each item is verified by the restricted-login tests
(`tests/hardening/test_app_role_negative.py`, N28 to N30) on a fresh database.

1. Run migrations as a separate migration owner (`webdesk_owner` or equivalent). The runtime login
   (`webdesk_app_login`) must not be that owner and must not be a member of `webdesk_guard_owner`.
2. The runtime login is NOSUPERUSER, NOCREATEROLE, NOCREATEDB and is a member only of `webdesk_app` (and
   `webdesk_ceremony` for the signed installation/recovery CLI, not for the web runtime).
3. `webdesk_guard_owner` is NOLOGIN. It owns the `webdesk_guard` schema and its SECURITY DEFINER functions.
   No runtime connection may SET ROLE to it.
4. `REVOKE CREATE ON SCHEMA public FROM PUBLIC` and `REVOKE TEMP ON DATABASE <db> FROM PUBLIC` (R1). Migration
   0020 revokes TEMP; the schema setting is an operator step for databases created outside the migrations.
5. Every SECURITY DEFINER function runs with `search_path = pg_catalog, public` (R1, migration 0020).
6. Ceremony and approval deadlines are bounded to 24 hours by the database (R2, migration 0020).
7. Credentials and session writes from the runtime login are the open finding R4 (test N26). The
   verified-session authority is not yet deployed; do not deploy to a shared environment until R4 is closed.
