# Magento / Adobe Commerce Specialist: master specification

**Status: DRAFT FOR REVIEW. No platform fact is verified.** Labels used: PENDING OFFICIAL EVIDENCE, UNKNOWN, NOT APPLICABLE, REQUIRES PROJECT-SPECIFIC INPUT.

| Field | Value |
|---|---|
| Canonical capability ID | `CAP-MAGENTO-ADOBE-COMMERCE` (from `AGENT_REGISTRY.yaml` and `src/webdesk/specialists/catalog.py`) |
| Registry status | proposed (AGENT_REGISTRY.yaml is a working draft, unapproved) |
| Alias | None |
| Machine-readable companion | `docs/specialists/knowledge/magento_adobe_commerce.json` |
| Source manifest | `docs/specialists/knowledge/sources.json` |

## 1. Identity, ownership and supported scope
- Scope: Magento and Adobe Commerce modules, storefront customizations, commerce workflows, architecture, integrations and version-specific constraints (registry). Editions are kept separate.
- Ownership of this specification: engineering draft, pending WDS review. Platform ownership: see sources.json.

## 2. Platform overview
Three separate evidence groups: Adobe Commerce exact pages (REST, GraphQL, events); a shared PHP extension page; Magento Open Source release notes only.

## 3. Architecture and deployment models
PENDING OFFICIAL EVIDENCE

## 4. Supported technology ecosystem
PENDING OFFICIAL EVIDENCE

## 5. Capability catalog and canonical IDs
| Capability | Platform | Edition | Claim kind | Required terms |
|---|---|---|---|---|
| REST product read | adobe_commerce | adobe_commerce | feature | rest, product |
| GraphQL query | adobe_commerce | adobe_commerce | feature | graphql |
| release history | magento_open_source | magento_open_source | release_version | release |
| catalog import | magento_open_source | magento_open_source | feature | catalog |

Canonical ID: `CAP-MAGENTO-ADOBE-COMMERCE`. The knowledge file and the code are checked against this table by tests.

## 6. Technical extension mechanisms
Shared PHP extension statements only (labelled shared). Edition-exclusive extension claims: UNKNOWN.

## 7. APIs and authentication
Adobe Commerce REST and GraphQL overview pages and the events page are approved (inactive). Endpoint detail: PENDING OFFICIAL EVIDENCE.

## 8. Data models and business entities
PENDING OFFICIAL EVIDENCE

## 9. Integration capabilities
Event-driven integration is Adobe Commerce only; not attributed to Magento Open Source (ADOBE-01).

## 10. Customization methods
PENDING OFFICIAL EVIDENCE

## 11. Security and permissions
No assumed module or API support (registry). Edition and deployment context required.
- Operator confirmation is required before any investigation. Workspace isolation applies to every page.

## 12. Version and edition differences
Edition, version and deployment must be stated. Release notes support version and release claims only (MAGENTO-01).

## 13. Performance, operational and platform limitations
Magento Open Source feature support: UNSUPPORTED_SOURCE (no approved feature page). Adobe-only pages are not applied to Open Source.

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

## 19. Example requirements and investigation scenarios
- REST product read on an Adobe Commerce page: INVESTIGATE, synthetic; Adobe Commerce edition stated.
- Catalog import on Magento Open Source: UNSUPPORTED_SOURCE.

Full draft scenario set: `docs/governance/SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md`.

## 20. Evaluation and QA acceptance criteria
- Machine-readable checklist: `docs/specialists/knowledge/magento_adobe_commerce.json` (qa_acceptance_checklist).
- Acceptance dependency: Activation approvals (ADOBE-01, MAGENTO-01), and confirmation that the Adobe paths are Adobe Commerce only.
- Evaluation criteria: PROPOSED only (see `docs/governance/SPRINT4_5_ACCEPTANCE_RECONCILIATION_PROPOSED_2026-10-28.md`).
