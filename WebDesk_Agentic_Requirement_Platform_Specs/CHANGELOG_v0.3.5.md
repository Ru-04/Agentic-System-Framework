# v0.3.5 Specification Change Log

Status: **Foundation review candidate — NOT implementation approved**.

| Review finding | Files | Change |
|---|---|---|
| Source parse recovery | GOVERNANCE §11; REQUIREMENT_SCHEMA §3.1; ARCHITECTURE §7; EVALUATION_PLAN | Individual parse failures isolated; Administrator-only reasoned/audited `source.reparse` resets failed source version for next Analyst run; EVAL-F14 and EVAL-F13. |
| Credential provisioning | GOVERNANCE §11; REQUIREMENT_SCHEMA §3.1; EVALUATION_PLAN | Pending activation; no administrator credentials; private single-use expiring token for activation and reset, explicit delivery gate and audit; EVAL-F11c. |
| Review cleanup | ARCHITECTURE §7/§13 | Input sort key clarified and EML metadata narrowed to message ID only. |
| Versioning/decisions | Normative specs, YAML, DECISION_REGISTER, README, REMEDIATION_LOG | Bumped review version and recorded user-approved decisions. |

No application code was created or modified. No tests were executed. Prior normative safeguards must remain intact.
