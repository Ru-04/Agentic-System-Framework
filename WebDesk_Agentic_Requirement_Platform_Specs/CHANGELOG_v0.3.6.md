# Changelog — v0.3.6 Consolidated Gate 1 Security Remediation

**Date:** 2026-10-16  
**Source:** v0.3.5 Foundation Review ZIP + Claude v0.3.5 Gate 1 Review (`Untitled(4).md`)  
**Status:** Independent review candidate; WDS sign-off for newly proposed contact and bootstrap policies REQUIRED. No application coding.

| File | In-place change | Review finding |
|---|---|---|
| GOVERNANCE §11 | Proposed domain and alias validation, two-Administrator independent identity/contact approval; `user.approve` matrix key; staged contact changes, fail-closed bootstrap ceremony | Final credential-contact bypass |
| REQUIREMENT_SCHEMA §3.1 | `pending_contact_approval`, typed approval/request data, immutable approved contacts, revision/uniqueness rules, token and setup trust ceremony data contracts | Account impersonation/takeover |
| ARCHITECTURE §7 | Independent contact approval before activation and transactional parse-failure rollback | Cross-document agreement |
| EVALUATION_PLAN | `EVAL-F11d-CONTACT-APPROVAL`, `EVAL-F11e-TOKEN-RATELIMIT`, `EVAL-F14b-PARSE-ATOMICITY`; existing F11c retained | Missing security/edge tests |
| GOVERNANCE, SCHEMA | Private delivery restrictions, at most one live token/user/purpose, no admin-controlled mailbox; rate-limit defaults | Non-blocking additions |
| DECISION_REGISTER | Two *proposed*, not confirmed, WDS policies; config/transport prerequisites identified | Governance traceability |
| REMEDIATION_LOG, README | Remediation lineage; explicit review-only status | Artifact clarity |
| AGENT_REGISTRY, SERVICE_CATALOG, 5 normative file headers | Bumped version label only | Version consistency |
| VALIDATION_REPORT_v0.3.6.md | New mechanical and semantic review summary | Reviewer transparency |

All later-phase open decisions (routing, RAG, hosting, retention, LLM provider, aliases) remain deferred. The v0.3.5 independent review's other resolved blockers are not reopened.
