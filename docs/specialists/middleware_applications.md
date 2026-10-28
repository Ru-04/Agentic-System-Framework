# Middleware Applications Specialist: master specification

**Status: DRAFT FOR REVIEW. No platform fact is verified.** Labels used: PENDING OFFICIAL EVIDENCE, UNKNOWN, NOT APPLICABLE, REQUIRES PROJECT-SPECIFIC INPUT.

| Field | Value |
|---|---|
| Canonical capability ID | `CAP-MIDDLEWARE-APPLICATIONS` (from `AGENT_REGISTRY.yaml` and `src/webdesk/specialists/catalog.py`) |
| Registry status | proposed (AGENT_REGISTRY.yaml is a working draft, unapproved) |
| Alias | None |
| Machine-readable companion | `docs/specialists/knowledge/middleware_applications.json` |
| Source manifest | `docs/specialists/knowledge/sources.json` |

## 1. Identity, ownership and supported scope
- Scope: Middleware and integration layers: API orchestration, webhooks, transformation, synchronization, authentication, retries, idempotency, error handling, background processing and observability (registry).
- Ownership of this specification: engineering draft, pending WDS review. Platform ownership: see sources.json.

## 2. Platform overview
Technology-neutral. The registry says to evaluate suitable technologies from requirements and evidence. No product is selected.

## 3. Architecture and deployment models
Pattern topics (draft guidance, not platform evidence): data flow, queues, webhook receivers, transformation layer, scheduled synchronization.

## 4. Supported technology ecosystem
Language and runtime are chosen from requirements, not fixed here. REQUIRES PROJECT-SPECIFIC INPUT.

## 5. Capability catalog and canonical IDs
| Capability | Platform | Edition | Claim kind | Required terms |
|---|---|---|---|---|
| webhook delivery retry | middleware_applications | not_applicable | feature | webhook, retry |

Canonical ID: `CAP-MIDDLEWARE-APPLICATIONS`. The knowledge file and the code are checked against this table by tests.

## 6. Technical extension mechanisms
NOT APPLICABLE

## 7. APIs and authentication
Pattern topics: API orchestration, authentication, rate handling. Vendor API details: PENDING OFFICIAL EVIDENCE.

## 8. Data models and business entities
Mapping and ownership of each data flow must be defined per project. REQUIRES PROJECT-SPECIFIC INPUT.

## 9. Integration capabilities
Webhooks, messaging, synchronization and transformations are pattern topics. Vendor specifics: PENDING OFFICIAL EVIDENCE.

## 10. Customization methods
NOT APPLICABLE

## 11. Security and permissions
Authentication, secrets and webhook verification are pattern topics. Specific mechanisms: REQUIRES PROJECT-SPECIFIC INPUT.
- Operator confirmation is required before any investigation. Workspace isolation applies to every page.

## 12. Version and edition differences
NOT APPLICABLE (no product).

## 13. Performance, operational and platform limitations
No product source is approved. Vendor-specific behaviour is UNSUPPORTED_SOURCE. Retry and idempotency rules are project design choices, not vendor claims.

## 14. Requirement-analysis procedure
1. Validate the requirement against REQUIREMENT_SCHEMA.md (requirement IDs present).
2. Match the requirement to capabilities in this catalog (every required term present).
3. If no capability matches, or essential context is missing: CLARIFY, with questions.
4. If the objective matches but the version is not stated: INVESTIGATE_WITH_UNKNOWNS.
5. Otherwise investigate against approved, active sources only. Pilot-active: WooCommerce docs and the BigCommerce product page.
6. Report findings only when cited to an approved page with a stated version. Report everything else as labelled unknowns.

## 15. Source and citation policy
- Only sources in `docs/specialists/knowledge/sources.json` with status APPROVED AND ACTIVE may support a claim. Pilot-active: WooCommerce docs and the BigCommerce product page; all others are inactive.
- A claim cites: exact URL, title, publisher, platform and edition, version, retrieval date, passage reference, and verification status.
- A URL that is known but not retrieved is not evidence. Draft descriptions stay separate from verified facts.
- Redirects leaving the approved boundary are refused. Instruction-like source text is quarantined.

## 16. Feasibility classification
PROPOSED, NOT APPROVED. Classes: supported_with_cited_evidence, unknown, unsupported_source, clarification_needed, refused. A class follows only from each capability's investigation outcome. No confidence value is used. The current specialist contract declares feasibility not determined, so reviewers make the feasibility call.

## 17. Estimation and complexity inputs
REQUIRES PROJECT-SPECIFIC INPUT

## 18. Known risks and unsupported behaviour
- No official evidence has been retrieved for any capability. Every platform statement is pending.
- Sources are inactive. Real investigation is not possible until WDS approves activation.
- Registry status is proposed or working draft; machine routing is disabled (AGENT_REGISTRY.yaml).
- Registry non-responsibilities are binding (see AGENT_REGISTRY.yaml for this capability).
- Draft guidance: Retries: bounded, with backoff; retry only transient failures. Idempotency: a key per message so a retry cannot duplicate an effect. Observability: correlation identifiers and structured logs. Recovery: dead-letter handling and replay after a fix. These are design topics, not platform claims.

## 19. Example requirements and investigation scenarios
- Webhook delivery and retry requirement with no product named: CLARIFY.
- One named middleware product: bounded example for WDS to choose. Not selected.

Full draft scenario set: `docs/governance/SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md`.

## 20. Evaluation and QA acceptance criteria
- Machine-readable checklist: `docs/specialists/knowledge/middleware_applications.json` (qa_acceptance_checklist).
- Acceptance dependency: WDS decision naming one product before any source is proposed.
- Evaluation criteria: PROPOSED only (see `docs/governance/SPRINT4_5_ACCEPTANCE_RECONCILIATION_PROPOSED_2026-10-28.md`).
