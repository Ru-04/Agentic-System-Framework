# v0.3.1 Foundation In-Place Change Log

**Status:** Candidate for independent review; not approved for coding. Source: last v0.3.0 decisions-updated package.

| Finding | Primary location | Change |
|---|---|---|
| F-1 | GOVERNANCE §11; REQUIREMENT_SCHEMA §3.1 and §4.10 | Approved project-scoped action x role matrix; submitted_by/prepared_by |
| F-2 | GOVERNANCE §8; REQUIREMENT_SCHEMA §3.1 and §4.1–4.2 | Typed three-class classification, tombstone shape; retention periods pending |
| F-3 | ARCHITECTURE §13 | Proposed allowed MIME/limits and per-type extraction/locator rules |
| F-4 | REQUIREMENT_SCHEMA §4.3 and §7 | Persisted segment_id canonical; examples no Shopify inference |
| F-5 | REQUIREMENT_SCHEMA §3.1 | ProjectCreateRequest and SourceIngestRequest contracts |
| F-6 | ARCHITECTURE §7 and §16 | Durable PostgreSQL job model and worker, retry, lease, interrupt/resume |
| F-7 | ARCHITECTURE §7 | One active run/project and optimistic expected_revision=409 |
| F-8 | ARCHITECTURE §7 | Domain PostgreSQL authority; workflow checkpoints IDs and flags only |
| F-9 | ARCHITECTURE §5 and §7 | Canonical state table; diagrams illustrative; routing disabled pending C-05 |
| F-10 | ARCHITECTURE §7; REQUIREMENT_SCHEMA §3.1 | Input hashes, stale state propagation and rerun requirement |
| N-01 | GOVERNANCE §18; ARCHITECTURE §19.4 | D-01 platform meaning confirmed, ID pending |
| N-09 | REQUIREMENT_SCHEMA §4.3 | Materiality now required in entity fields |
| N-13 | ARCHITECTURE §16 and §18 | Moved durable job to Foundation and replaced stale open-decision list |
| N-14 | REQUIREMENT_SCHEMA §9.1 | Claim.subject_refs always nonempty |
| X-07 | ARCHITECTURE §5 and §7 | Single authoritative workflow state table |
| X-13 | REQUIREMENT_SCHEMA §4.3 and §7 | Canonical segment locator and examples rewritten |
| N-18 | REMEDIATION_LOG | Outstanding contradiction register retained for independent re-review |

## Not resolved by this Foundation patch

C-05 machine routing and routing vocab; evidence/RAG completeness (C-06/C-07), estimation basis (C-08), downstream reviewer/output/DTO contracts and remaining X/N contradictions await their phase. Pending: D-12 model/budget, D-13 retention durations, D-15 alias map, D-16 hosting, vendor allowlist and source approvals. This package does not claim full implementation readiness.
