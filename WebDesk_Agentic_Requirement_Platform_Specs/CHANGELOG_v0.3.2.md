# v0.3.2 — Foundation Remediation Changelog

Date: 2026-10-16. Status: review candidate only. Source: v0.3.1 FOUNDATION REVIEW. No application code.

## Approved WDS decisions
- B-3 Administrator-controlled run cancel/retry/resume and access operations; Analyst starts assigned runs only.
- B-6 Parked runs release active slot, history retained.
- B-7 EML attachments listed, not ingested.
- B-11 Archive only, no physical deletion in Gate 1.

## Foundation contracts
- B-1: Restored GOV §8 and §11 mandatory safeguards and ARCH §13 audit/threat modelling; rule-preservation check documented.
- B-2: Rewrote SCHEMA §9.5 to keep D-01 confirmed and Foundation contracts normative.
- B-3: Added permission-key matrix with Analyst-run.start only and Administrator run control, grants, downgrade.
- B-4: Added User/RoleAssignment/ProjectMembership/ProjectAccessGrant/RestrictedContentGrant schemas and local-auth adapter baseline.
- B-5: Defined RunStatus and its JobStatus mapping; parked/failed excluded from active-run constraint.
- B-6: Only POST /runs creates run; uploads snapshot and parked-slot behavior defined.
- B-7: Admitted-versus-rejected uploads, .eml attachment behavior, scan status and byte store defined.
- B-8: SourceSegment has LocatorType and type-specific locator fields.
- B-9: Project revision, expected_source_revision and 24h idempotency semantics added.
- B-10: DependencyEdge and RFC8785 canonical JSON SHA-256 rules introduced.
- B-11: Single-org no organization_id; nullable policy ref; Gate 1 archive only.
- B-12: Added EVAL-F01 through EVAL-F10 with explicit Gate 1 assertions.
- B-13: Set job lease TTL/renewal; documented WDS-acknowledged engineering defaults.

## Document update map
- `GOVERNANCE.md`: restored §8 and §11 safeguards, revised §11 permission matrix, typed classification/tombstone.
- `ARCHITECTURE.md`: §7 run state/job/lease and admission rules, §13 upload and audit safeguard.
- `REQUIREMENT_SCHEMA.md`: §3.1 DTOs, authorization and dependency entities, §4 Project/SourceSegment fields, §9.5 pending-text correction.
- `EVALUATION_PLAN.md`: ten named release-blocking Foundation acceptance tests.
- `DECISION_REGISTER.md`: four confirmed selections and acknowledged engineering defaults.
- `REMEDIATION_LOG.md`: B-1–B-13 and regression tracking.
- `AGENT_REGISTRY.yaml`, `SERVICE_CATALOG.yaml`: version tags, governance status marker only; routing remains disabled.

## Deferred
C-05 structured routing; vendor docs and live egress; LLM provider; data retention periods and deletion; complete SOW/estimate/RAG contracts; D-15 aliases; production hosting. No Foundation implementation approval claimed.
