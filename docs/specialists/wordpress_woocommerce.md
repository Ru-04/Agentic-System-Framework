# WordPress & WooCommerce Specialist: master specification

**Status: DRAFT FOR REVIEW. No platform fact is verified.** Labels used: PENDING OFFICIAL EVIDENCE, UNKNOWN, NOT APPLICABLE, REQUIRES PROJECT-SPECIFIC INPUT.

| Field | Value |
|---|---|
| Canonical capability ID | `CAP-WORDPRESS-WOOCOMMERCE` (from `AGENT_REGISTRY.yaml` and `src/webdesk/specialists/catalog.py`) |
| Registry status | proposed (AGENT_REGISTRY.yaml is a working draft, unapproved) |
| Alias | None |
| Machine-readable companion | `docs/specialists/knowledge/wordpress_woocommerce.json` |
| Source manifest | `docs/specialists/knowledge/sources.json` |

## 1. Identity, ownership and supported scope
- Scope: One combined specialist for WordPress CMS and WooCommerce commerce, with CMS and commerce concerns kept distinct inside findings (registry).
- Ownership of this specification: engineering draft, pending WDS review. Platform ownership: see sources.json.

## 2. Platform overview
WordPress core: no approved source. WooCommerce: approved boundary developer.woocommerce.com /docs/* and /guides/* (pilot-active since 28 Oct 2026). The Store API products page is retrieved, states no version, and has no single sentence with both variation and price, so variation pricing is UNKNOWN from it.

## 3. Architecture and deployment models
PENDING OFFICIAL EVIDENCE Plugin and theme architecture: WordPress core documentation is not approved.

## 4. Supported technology ecosystem
PENDING OFFICIAL EVIDENCE

## 5. Capability catalog and canonical IDs
| Capability | Platform | Edition | Claim kind | Required terms |
|---|---|---|---|---|
| product variation pricing | woocommerce | not_applicable | feature | variation, price |
| REST API product read | woocommerce | not_applicable | feature | rest, product |
| Store API cart | woocommerce | not_applicable | feature | store api, cart |

Canonical ID: `CAP-WORDPRESS-WOOCOMMERCE`. The knowledge file and the code are checked against this table by tests.

## 6. Technical extension mechanisms
Hooks, filters, extensions and PHP extension questions: PENDING OFFICIAL EVIDENCE (WooCommerce docs only, once activated).

## 7. APIs and authentication
WooCommerce REST API product read and Store API cart are catalog capabilities. Endpoints: PENDING OFFICIAL EVIDENCE.

## 8. Data models and business entities
PENDING OFFICIAL EVIDENCE Products, variations and orders: topics only.

## 9. Integration capabilities
PENDING OFFICIAL EVIDENCE

## 10. Customization methods
PENDING OFFICIAL EVIDENCE

## 11. Security and permissions
Plugin compatibility is never assumed (registry). Hosting dependencies: PENDING OFFICIAL EVIDENCE.
- Operator confirmation is required before any investigation. Workspace isolation applies to every page.

## 12. Version and edition differences
WordPress and WooCommerce versions must be stated. Plugin versions must be stated where a claim depends on them.

## 13. Performance, operational and platform limitations
WordPress core is not approved. Plugin compatibility is unknown.

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
- Product variation pricing on an approved WooCommerce docs page: INVESTIGATE, synthetic until activation.
- Redirect to an unapproved host: REFUSED.

Full draft scenario set: `docs/governance/SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md`.

## 20. Evaluation and QA acceptance criteria
- Machine-readable checklist: `docs/specialists/knowledge/wordpress_woocommerce.json` (qa_acceptance_checklist).
- Acceptance dependency: Activation approval (B2 with conditions) and ownership confirmation on developer.woocommerce.com.
- Evaluation criteria: PROPOSED only (see `docs/governance/SPRINT4_5_ACCEPTANCE_RECONCILIATION_PROPOSED_2026-10-28.md`).
