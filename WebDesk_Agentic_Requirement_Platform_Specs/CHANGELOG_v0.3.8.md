# WebDesk v0.3.8 — Foundation remediation change log

Source: v0.3.7 consolidated Gate 1 review, findings B1–B4 and S1–S8.

- B1 (GOV §11, SCHEMA §3.1, EVAL-F11b/F11f): one system bootstrap role only; first activated Admin grants second activated user through ordinary `role.assign`. One-admin ceremony recovery same. Zero-admin in-system recovery explicitly denied; owner-authorized offline restore/reinstall documented as **proposed and pending WDS acceptance**.
- B2 (GOV §11, SCHEMA §3.1, EVAL-F11f): effective coverage includes pending replacements, 24-hour activation deadline and denial of repeated ceremonies.
- B3 (SCHEMA §3.1, EVAL-F11d): requester-null CHECK, approver/creator/active-admin cross-table triggers and protected User transition trigger.
- B4 (SCHEMA §3.1, EVAL-F11d): ContactReservation surrogate UUID primary key, partial active-email unique index.
- S1 (SCHEMA §3.1, EVAL-F11g): notice lease ownership, expiry, recovery and in-app outage alerts.
- S2 (SCHEMA §3.1, EVAL-F11d): create approval expiry/rejection semantics; explicit injectable clock.
- S3 (SCHEMA §3.1, EVAL-F11d): NFC, ASCII local part, normalized domain check.
- S4 (EVAL-F14b): deterministic partial/failed/unsupported cases.
- S5: removed duplicated normative paragraphs.
- S6: added explicit Session persistence and epoch validation.
- S7: clock injection for contact approval expiry tests.
- S8: corrected credential activation wording.
- Normalized v0.3.8 labels in normative documents/YAML. Existing unrelated approved decisions and later-phase blockers retained.
