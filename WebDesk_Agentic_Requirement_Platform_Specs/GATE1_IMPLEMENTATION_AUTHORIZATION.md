# Gate 1 Limited Foundation Implementation Authorization — v0.3.10

**Independent review date:** 2026-10-16  
**Verdict:** READY FOR LIMITED FOUNDATION IMPLEMENTATION  
**Source:** WebDesk Platform v0.3.10 — Final Gate 1 Review (independently provided by the user).  
**Status:** Foundation implementation-ready; no application code has been written or run by this baseline finalization. A separate user request is needed to start coding.

## Editorial closure (no policy changes)

- Corrected EVALUATION_PLAN.md `EVAL-F11h` to reference WDS-confirmed `P-GATE1-ZERO-ADMIN-RECOVERY-03`, rather than pending acceptance.
- Corrected the inaccurate targeted-search statement in `VALIDATION_REPORT_v0.3.10_FINAL_REVIEW.md`.
- Updated README status to reflect the independent limited-Foundation verdict. No normative business contracts, evaluation outcomes, YAML semantics, or later-phase constraints were changed.

## Authorized implementation scope

- **Identity/access:** account states, contact approval and reservation, withdrawal, activation and reset tokens, sessions and rate limits, outbox, role assignment, project and restricted-content grants, audited installation and one-Administrator recovery CLI.
- **Projects:** create, initial member assignment, membership administration, archive only.
- **Source intake:** upload type/size checks, quarantine, subject/body EML extraction, stable typed segments, atomic parse outcome and Administrator-only `source.reparse`.
- **Execution:** PostgreSQL durable jobs and leases, run state and one active run/project, Analyst-only run start, snapshot/hash/staleness rules, ID-only workflow checkpoint skeleton.
- **Governance/audit:** three DataClass values, audit tombstone schema (not deletion execution), append-only audit of mutations, denials and client-content reads.
- Every part is only complete when its relevant release-blocking EVAL-F tests pass.

## Development controls

- Use a **non-production email capture sink**, and prevent its use in production.
- Missing domain allowlist, alias denylist, owner public key, or required rate-limit configuration MUST fail closed for account onboarding and ceremonies.
- Ceremony tests may use a test-only signing key.
- Never implement an in-app zero-Administrator recovery, a second bootstrap role grant, or a second installation ceremony.

## Excluded from Gate 1

Specialist routing; LLM/model-provider calls; RAG or vendor retrieval; estimation; claims/review/SOW outputs; live external egress; retention periods or purge; hosting/production deployment; production email; real owner identities/keys; SSO/multi-organization; execution of the offline restore runbook.

## Production prerequisites still open

WDS domain allowlist and alias denylist; signing owner and key custody; independent identity/mailbox verification procedure; production email; approved offline recovery runbook and rehearsal; outbox dead-letter threshold; final rate limits; hosting/deployment authorization.

**Policy:** `P-GATE1-ZERO-ADMIN-RECOVERY-03` is WDS-CONFIRMED; zero-admin recovery remains outside the application, with owner-authorized, audited offline restore/reinstallation only.
