# WebDesk v0.3.7 — Consolidated Gate 1 T1–T11 remediation

Status: **WDS CONTACT-01 and BOOTSTRAP-02 approved; independent Gate 1 review pending.** No application code.

| Finding | In-place remediation |
|---|---|
| T1 | Schema and Governance ceremony-backed approval exception; bounded initial install plus owner-signed recovery; CLI, DB guard and EVAL-F11f |
| T2 | Ordinary `pending_contact_approval → pending_activation → active` lifecycle in Governance, Schema and EVAL-F11c; disabled blocked |
| T3 | AccountActivationToken.contact_revision/revoked_at/revocation_reason; unique unrevoked-unconsumed token; session_epoch |
| T4 | OutboxNotice transactional creation; async retries and audited terminal alert; EVAL-F11g |
| T5 | Uniqueness covers pending/active/disabled and pending contact reservations |
| T6 | Configurable per `(account,IP)` and higher per-IP login rate limit |
| T7 | EVAL checks nonempty proof_ref + independent approver, not external mailbox ownership |
| T8 | 24h pending contact-change TTL, audited cancellation and reset-block expiration |
| T9 | Lowercase after trimming, mixed-case accepted, configured denylist for aliases, plus-tags denied |
| T10 | Shared v0.3.7 version label across YAML and five normative MD files |
| T11 | Parser boundary added in Schema and Architecture |

**Additional:** WDS approved and acknowledged collusion/mail-domain residual risks; actual domain allowlist, owner signing authority, out-of-band identity verification procedure and production provider remain open. Historic version-specific changelogs are deliberately retained unmodified.
