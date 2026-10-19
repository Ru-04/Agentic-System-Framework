# WebDesk v0.3.9 — Gate 1 C1–C4 cross-document correction

**Status:** REVIEW CANDIDATE. Zero-active-Administrator offline restore/reinstall is NOT yet WDS-approved; no implementation authorization.

| Finding | Corrected original sections |
|---|---|
| C1 | ARCHITECTURE §7 install and outbox, GOVERNANCE §11, REQUIREMENT_SCHEMA §3.1, EVAL-F11f: first system bootstrap role only; first active Administrator ordinarily grants second; below-two promotion only for unexpired ceremony-backed appointee |
| C2 | EVAL-F11d: exactly one proof_ref; ceremony approvals require null human approver |
| C3 | GOVERNANCE §11, REQUIREMENT_SCHEMA §3.1, EVAL-F11d: rejected/expired create approval and disabled user retain address; audited withdrawal restricted to never-approved pending account |
| C4 | GOVERNANCE §11, REQUIREMENT_SCHEMA §3.1, ARCHITECTURE §7, EVAL-F11f: 24-hour install contact deadlines; first/second missed-activation outcomes |

Prior normative security safeguards are not intentionally removed. Historical changelogs and reports retained unchanged.

**C3 additional authorization closure:** Administrator-only `user.withdraw` permission, justification/revision, DB guarded clear, atomic audit and negative tests.
