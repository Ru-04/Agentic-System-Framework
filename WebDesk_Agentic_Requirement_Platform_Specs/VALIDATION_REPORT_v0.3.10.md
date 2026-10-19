# v0.3.10 Mechanical Validation Report

This is a **static specification check**, NOT independent approval, executable SQL validation, race testing, or a claim of no contradictions.

| Check | Result |
|---|---|
| ZIP structural integrity | PASS (checked after archive creation) |
| Agent registry and service catalog YAML parse | PASS |
| Five normative Markdown version headers = 0.3.10 | PASS |
| Both YAML version labels = 0.3.10 | PASS |
| Single-use appointment field and grant reference specified | PASS (presence) |
| RoleAssignment database trigger and existing-staff recovery contract | PASS (presence) |
| EVAL-F11h appointment cases | PASS (presence) |
| Withdrawal test fixes 403 vs 409, never-approved eligibility | PASS (presence) |
| Named UserWithdrawal and pending-create cancellation | PASS (presence) |
| Pending zero-Administrator recovery acceptance preserved | PASS (presence) |

Existing routing remains a later-phase issue; no application code, SQL migrations, delivery tests or independent Gate 1 approval were performed. Production prerequisites remain unconfigured.
