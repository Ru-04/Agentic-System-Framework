# WebDesk v0.3.5 — Specification Validation Report

**Status:** Review candidate; these are mechanical checks, NOT independent approval or executed application tests.

- Both YAML documents parsed using PyYAML.
- Registry references checked against all entry IDs, service/tool IDs and model configuration IDs, including deterministic services.
- Number of dangling identified references: **0**.
- Routing rules with non-list / prose `activate`: **1**; legacy machine routing remains disabled and is outside Foundation Gate 1.
- Governance/Schema/Architecture/Evaluation source recovery and activation obligations: **10/10** static presence checks passed.
- EVAL-F11c and EVAL-F14 are **test specifications only**; no tests were executed.
- `GOVERNANCE.md`, `ARCHITECTURE.md`, `REQUIREMENT_SCHEMA.md`, `REVIEW_POLICY.md`, and `EVALUATION_PLAN.md` headers were updated to the v0.3.5 review-candidate version, as were both YAML versions.

## Recorded WDS choices

1. Administrator-only audited `source.reparse`, with nonempty reason, applies to individual failed Source versions. Other files continue to parse.
2. Administrator cannot set or view user credentials. Users activate via privately delivered, single-use expiring tokens. Password resets use the same approach.

## Outstanding review and implementation prerequisites

- Independent Gate 1 reviewer must verify business-rule consistency, including whether one parse failure can ever trigger a run-level failure.
- Before implementation of account onboarding, WDS must select/configure and test a **private activation delivery transport**; there is no administrator-password fallback.
- Token-generation library, rate limiting, token delivery/reissue behavior, and session implementation must be assessed in engineering/security review; no specific vendor is approved here.
- Later phase: machine routing rules, vendor evidence access, estimation reference data, retention periods and production hosting remain pending.
