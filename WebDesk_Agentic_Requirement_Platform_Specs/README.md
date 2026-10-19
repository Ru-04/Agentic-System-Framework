# WebDesk Agentic Requirement Analysis Platform — v0.3.10 APPROVED LIMITED FOUNDATION BASELINE

**Date:** 2026-10-16  
**Status:** READY FOR LIMITED FOUNDATION IMPLEMENTATION per independent Gate 1 review dated 2026-10-16. Foundation-only scope; no production release authorization.

This ZIP is an incremental remediation of the provided v0.2.0 package, **not a completed repair of all independent review findings**. Claude Code may implement ONLY the Gate 1 scope in `GATE1_IMPLEMENTATION_AUTHORIZATION.md` after user authorizes the implementation task. Foundation F-1 through F-10 were revised in the original sections, with unresolved later-phase contradictions tracked in `REMEDIATION_LOG.md`. All legacy routes are **documentation-only**, not approved executable conditions. D-01 is now clarified: 3dcart/Shift4Shop is a separate eCommerce platform. Legacy misleading IDs are preserved pending a canonical alias decision. Do not infer visual configurator or migration from the old names.

## Primary files

1. `GOVERNANCE.md` — top-level binding policies and D-01..D-15 (D-16 deferred) addendum.
2. `REQUIREMENT_SCHEMA.md` — canonical entity contracts and D-01..D-15 (D-16 deferred) addendum.
3. `ARCHITECTURE.md` — runtime architecture plus canonical Foundation workflow and durable execution contract.
4. `AGENT_REGISTRY.yaml` — seven specialist categories with D-01 standalone platform semantics corrected and non-executable prose routing explicitly disabled.
5. `SERVICE_CATALOG.yaml` — proposed catalog plus estimation metadata; vendor patterns are unverified.
6. `REVIEW_POLICY.md` — gate controls including D-09 critical non-waiver.
7. `EVALUATION_PLAN.md` — original plan plus D-01..D-15 (D-16 deferred) regression cases; no tests run.
8. `DECISION_REGISTER.md` — **all sixteen** decisions, approved policy choices and open implementation configuration.
9. `REMEDIATION_LOG.md` — independent review findings and known unresolved contradictions.

## Authority and usage

`GOVERNANCE.md` → `REQUIREMENT_SCHEMA.md` → `ARCHITECTURE.md` → registry/catalog → `REVIEW_POLICY.md` → `EVALUATION_PLAN.md`. Decisions recorded as CONFIRMED are WDS stakeholder intent, but do not supersede missing implementation details. **Do not fill unresolved details by inference.** Gate 1 Foundation contracts have passed independent review; later-phase decisions and production configurations remain open.

## Next steps

1. Apply the confirmed D-01 and D-10..D-15 selections; D-16 is deliberately deferred. Complete outstanding detail-level rules, initial LLM provider, actual retention periods, canonical 3dcart alias and source allowlist.
2. Independent Gate 1 review of F-1 through F-10 completed with READY FOR LIMITED FOUNDATION IMPLEMENTATION. H-02..H-05 and H-13 now have Foundation candidate contracts; C-05, H-14..H-16 and later-phase contracts remain open.
3. Obtain independent review against the original 29-page assessment and confirm closure one finding at a time.
4. Authorize Claude Code only for specifically cleared implementation increments.

**Mechanical validation:** YAML parsing and cross-reference checks should be run. This package contains **specification files only**, no application code or verified vendor capabilities.

## Decision update, 2026-10-16

This revision records user choices D-01 and D-10 through D-16. A standalone 3dcart/Shift4Shop platform specialist replaces previous presumed 3D visualization behavior; a separate migration service pattern is proposed. WDS house-format DOCX/PDF, configurable LLM provider, retention-by-data-class, Technical Lead-owned evaluation, and legacy ID preservation are approved policy directions. Initial model, concrete retention periods, vendor allowlists and hosting remain open/deferred. This version is still **NOT READY FOR IMPLEMENTATION** and is intended only for independent review.

## v0.3.2 Foundation scope and cautions

F-1 and F-2 are WDS-approved policy/contract directions. F-3–F-10 and B-1–B-13 are authored specification candidates pending independent verification. Gate 1 engineering defaults are acknowledged in DECISION_REGISTER.md, subject to validation; they are not production security approval. No Claude Code implementation authorization is conferred. Use `CHANGELOG_v0.3.2.md` and `VALIDATION_REPORT_v0.3.2.md` for the precise scope and mechanical checks.

## v0.3.2 Gate 1 patch
B-3, B-6, B-7, B-11 confirmed. Mandatory safeguards restored. Schema, run lifecycle, role controls, uploads, hashes, locators and Gate 1 evaluation updated. No application source code included. Not independently approved; later phases blocked.


**v0.3.3 Foundation approval candidate:** C-1 through C-9 corrected for independent diff review; no app implementation authorized. See CHANGELOG_v0.3.3.md and VALIDATION_REPORT_v0.3.3.md.

## v0.3.5 scope

The two Foundation blockers identified by the independent v0.3.4 review were amended: isolated source reparse and user-owned private account activation. Tests EVAL-F11c and EVAL-F14 were specified; no software code was implemented and no tests executed. This package still requires independent Gate 1 sign-off.

## v0.3.6 consolidated Gate 1 contact-security review

This package **proposes**, but does not falsely claim WDS has approved, a secure two-Administrator and contact-verification policy to close both v0.3.5 credential-delivery bypasses. Normal onboarding MUST fail closed without a verified second Administrator and private delivery. WDS must explicitly approve both `P-GATE1-CONTACT-01` and `P-GATE1-BOOTSTRAP-02` before Gate 1 baseline approval. All other previously approved policies are preserved. This package contains specifications and evaluation definitions only; no application implementation or executable tests.


## v0.3.10 — Final independent Gate 1 review candidate (WDS operational acceptance recorded)

WDS explicitly **CONFIRMED** P-GATE1-ZERO-ADMIN-RECOVERY-03 on 2026-10-16: recovery with zero active Administrators is restricted to owner-authorized audited offline restore or reinstallation under an approved runbook. This resolves the previously open stakeholder *policy acceptance*, but does not provide a named owner, signing key, operational recovery procedure or independent Gate 1 approval. Earlier sections of this README describe historical review states and must not be read as current approvals. **No application code has been developed or authorized.**
