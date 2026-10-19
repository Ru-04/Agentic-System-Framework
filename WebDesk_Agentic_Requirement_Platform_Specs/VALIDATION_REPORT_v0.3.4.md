# v0.3.4 — Mechanical Validation Report

**Status: review candidate, NOT independently approved for implementation.** No application code was written or executed.

- PyYAML: both AGENT_REGISTRY.yaml and SERVICE_CATALOG.yaml parsed successfully.
- Registry: 15 entries; 6 tools; 3 model configurations; 13 routing rules.
- Checked `allowed_tools`, `dependencies`, `handoffs`, `model_config_ref`, and list-valued `activate` against exact IDs in entries, services_and_tools, and model_configuration. **0 dangling ID references**.
- Non-ID activation values: **1**: ROUTE-CROSS-PLATFORM-001. Pre-existing prose route remains disabled for Foundation.
- Foundation static assertions: 9/9 passed: pending_snapshot, R2_exception, R3_archiving, stale_resume_removed, F11b, F13_first_run, F09_archive, all_versions, no_malformed_schema_join. These are presence/shape checks, not semantic proof.
- EVAL-F01–F13 plus EVAL-F11b are **specification definitions**, not executed tests.
- Independent review must verify R1 pending snapshot, R2 bootstrap/auto-membership exception safety, R3 archive concurrency, and preserved safeguards.
- Later-phase routing, evidence, estimation, hosting and retention details are not approved by this report.
