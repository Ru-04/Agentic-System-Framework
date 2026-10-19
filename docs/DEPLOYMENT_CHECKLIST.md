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
