"""Generates the seven master specifications from the shared registry and catalog.

Run from the repository root with PYTHONPATH=src. Not imported by the application.
"""

from __future__ import annotations

import pathlib

from webdesk.investigation.specialists import CATALOG
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId

P = "PENDING OFFICIAL EVIDENCE"
U = "UNKNOWN"
NA = "NOT APPLICABLE"
REQ = "REQUIRES PROJECT-SPECIFIC INPUT"

PROC = (
    "1. Validate the requirement against REQUIREMENT_SCHEMA.md (requirement IDs present).\n"
    "2. Match the requirement to capabilities in this catalog (every required term present).\n"
    "3. If no capability matches, or essential context is missing: CLARIFY, with questions.\n"
    "4. If the objective matches but the version is not stated: INVESTIGATE_WITH_UNKNOWNS.\n"
    "5. Otherwise investigate against approved, active sources only. Pilot-active: WooCommerce docs and the BigCommerce product page.\n"
    "6. Report findings only when cited to an approved page with a stated version. "
    "Report everything else as labelled unknowns."
)
SOURCE_POLICY = (
    "- Only sources in `docs/specialists/knowledge/sources.json` with status APPROVED AND ACTIVE "
    "may support a claim. Pilot-active: WooCommerce docs and the BigCommerce product page; all others are inactive.\n"
    "- A claim cites: exact URL, title, publisher, platform and edition, version, retrieval date, "
    "passage reference, and verification status.\n"
    "- A URL that is known but not retrieved is not evidence. Draft descriptions stay separate "
    "from verified facts.\n"
    "- Redirects leaving the approved boundary are refused. Instruction-like source text is "
    "quarantined."
)
FEASIBILITY = (
    "PROPOSED, NOT APPROVED. Classes: supported_with_cited_evidence, unknown, "
    "unsupported_source, clarification_needed, refused. A class follows only from each "
    "capability's investigation outcome. No confidence value is used. The current specialist "
    "contract declares feasibility not determined, so reviewers make the feasibility call."
)
RISKS_COMMON = [
    "No official evidence has been retrieved for any capability. Every platform statement is pending.",
    "Sources are inactive. Real investigation is not possible until WDS approves activation.",
    "Registry status is proposed or working draft; machine routing is disabled (AGENT_REGISTRY.yaml).",
]

SPECS: dict[SpecialistId, dict[str, object]] = {
    SpecialistId.SHOPIFY: dict(
        name="Shopify Specialist",
        reg_status="proposed",
        alias="None",
        scope=(
            "Shopify-specific storefronts, apps, extensions, APIs, constraints and customization "
            "options (registry purpose). Does not assume plan or permission."
        ),
        overview=(
            P + ". Repository context: the Shopify platform module and the frozen Sprint 2 "
            "relevance thresholds (S2-D15) govern the existing Shopify evidence path."
        ),
        arch=P,
        ecosystem=P,
        extension=(
            P + ". Storefront, theme, app and checkout-extensibility mechanisms are topics only "
            "until evidence is checked."
        ),
        apis=(
            "Approved boundary: shopify.dev and help.shopify.com under plan scopes (inactive). "
            "Endpoints: " + P + ". The Sprint 2 corpus is not a verified record in the repository."
        ),
        data=P,
        integrations=P + " Webhooks and apps are topics only.",
        custom=P,
        security=(
            "Registry permissions: project_scoped_read, evidence_lookup_allowlist, "
            "candidate_analysis_write. No autonomous approval. Plan and permission assumptions "
            "are forbidden."
        ),
        versions=(
            "No edition split is recorded. Version must be stated per page. Plan-dependent "
            "features need the plan stated."
        ),
        limits=P + ". Plan-dependent features: UNKNOWN until the plan is stated.",
        examples=[
            "Plan feature availability on an approved plan page: INVESTIGATE, synthetic only "
            "until a source is active.",
            "Request with no recognisable feature: CLARIFY.",
        ],
        estimation=REQ,
        acceptance=(
            "Shopify 55-pair human relevance review: 0 of 55, outstanding. Existing relevance "
            "thresholds unchanged."
        ),
    ),
    SpecialistId.SHIFT4SHOP: dict(
        name="3dcart / Shift4Shop Platform Specialist (legacy identifier)",
        reg_status="proposed_canonical_name_and_alias_pending",
        alias=(
            "3dcart (legacy). Identifier CAP-3D-CART-SHIFT-SHOPIFY kept for compatibility. "
            "Canonical name pending (D-01, C-01)."
        ),
        scope=(
            "Shift4Shop (formerly 3dcart) as an independent eCommerce platform: native features, "
            "themes, catalog, checkout, APIs, integrations, settings, security, version constraints. "
            "Not Shopify, not 3D visualization, not migration (registry)."
        ),
        overview=(
            P + ". Product identity and version must be established before any platform claim "
            "(registry)."
        ),
        arch=P,
        ecosystem=P,
        extension=P,
        apis=P + ". No approved source. Vendor REST portal relationship unverified (B4 deferred).",
        data=P,
        integrations=P,
        custom=P,
        security=(
            "Registry permissions as for all categories. Unknown product identity becomes a "
            "clarification, never a guess."
        ),
        versions="Exact version must be identified before supporting any version-specific claim.",
        limits="No approved source. Every capability is unsupported-source until a source is approved.",
        examples=[
            "Product read API: UNSUPPORTED_SOURCE, no claim.",
            "Requirement with no product or version named: CLARIFY.",
        ],
        estimation=REQ,
        acceptance=(
            "Source discovery approval (SRC-02) and ownership verification required before any "
            "evidence-backed run."
        ),
    ),
    SpecialistId.WORDPRESS_WOOCOMMERCE: dict(
        name="WordPress & WooCommerce Specialist",
        reg_status="proposed",
        alias="None",
        scope=(
            "One combined specialist for WordPress CMS and WooCommerce commerce, with CMS and "
            "commerce concerns kept distinct inside findings (registry)."
        ),
        overview=(
            "WordPress core: no approved source. WooCommerce: approved boundary "
            "developer.woocommerce.com /docs/* and /guides/* (inactive)."
        ),
        arch=P + " Plugin and theme architecture: WordPress core documentation is not approved.",
        ecosystem=P,
        extension=(
            "Hooks, filters, extensions and PHP extension questions: " + P + " (WooCommerce docs "
            "only, once activated)."
        ),
        apis=(
            "WooCommerce REST API product read and Store API cart are catalog capabilities. "
            "Endpoints: " + P + "."
        ),
        data=P + " Products, variations and orders: topics only.",
        integrations=P,
        custom=P,
        security=(
            "Plugin compatibility is never assumed (registry). Hosting dependencies: " + P + "."
        ),
        versions=(
            "WordPress and WooCommerce versions must be stated. Plugin versions must be stated "
            "where a claim depends on them."
        ),
        limits="WordPress core is not approved. Plugin compatibility is unknown.",
        examples=[
            "Product variation pricing on an approved WooCommerce docs page: INVESTIGATE, "
            "synthetic until activation.",
            "Redirect to an unapproved host: REFUSED.",
        ],
        estimation=REQ,
        acceptance=(
            "Activation approval (B2 with conditions) and ownership confirmation on "
            "developer.woocommerce.com."
        ),
    ),
    SpecialistId.BIGCOMMERCE: dict(
        name="BigCommerce Specialist",
        reg_status="proposed",
        alias="None",
        scope=(
            "BigCommerce-specific storefronts, APIs, customizations, extensions, commerce workflows "
            "and constraints (registry)."
        ),
        overview=(
            "Approved boundary: docs.bigcommerce.com /developer/docs/* and one exact product-catalog "
            "page (inactive)."
        ),
        arch=P,
        ecosystem=P,
        extension=P,
        apis=(
            "Single product read on the approved exact page. List endpoint: " + U + " until its "
            "page is approved. API version shown on the page: v3 (per the scenarios document)."
        ),
        data=P,
        integrations=P,
        custom=P,
        security=(
            "No assumed plan or permission (registry). Sibling pages of /api-reference/* are refused."
        ),
        versions=(
            "API version and store plan must be stated. Plan-dependent features: " + U + " without "
            "the plan."
        ),
        limits="Order data: UNSUPPORTED_SOURCE (no approved page). List endpoint: " + U + ".",
        examples=[
            "Single product read on the approved page: INVESTIGATE, synthetic until activation.",
            "Order data: UNSUPPORTED_SOURCE.",
        ],
        estimation=REQ,
        acceptance=(
            "Owner confirmation and API reference check (SOURCE_ALLOWLIST A2) before activation."
        ),
    ),
    SpecialistId.MAGENTO_ADOBE_COMMERCE: dict(
        name="Magento / Adobe Commerce Specialist",
        reg_status="proposed",
        alias="None",
        scope=(
            "Magento and Adobe Commerce modules, storefront customizations, commerce workflows, "
            "architecture, integrations and version-specific constraints (registry). Editions are "
            "kept separate."
        ),
        overview=(
            "Three separate evidence groups: Adobe Commerce exact pages (REST, GraphQL, events); a "
            "shared PHP extension page; Magento Open Source release notes only."
        ),
        arch=P,
        ecosystem=P,
        extension=(
            "Shared PHP extension statements only (labelled shared). Edition-exclusive extension "
            "claims: " + U + "."
        ),
        apis=(
            "Adobe Commerce REST and GraphQL overview pages and the events page are approved "
            "(inactive). Endpoint detail: " + P + "."
        ),
        data=P,
        integrations=(
            "Event-driven integration is Adobe Commerce only; not attributed to Magento Open Source "
            "(ADOBE-01)."
        ),
        custom=P,
        security=(
            "No assumed module or API support (registry). Edition and deployment context required."
        ),
        versions=(
            "Edition, version and deployment must be stated. Release notes support version and "
            "release claims only (MAGENTO-01)."
        ),
        limits=(
            "Magento Open Source feature support: UNSUPPORTED_SOURCE (no approved feature page). "
            "Adobe-only pages are not applied to Open Source."
        ),
        examples=[
            "REST product read on an Adobe Commerce page: INVESTIGATE, synthetic; Adobe Commerce "
            "edition stated.",
            "Catalog import on Magento Open Source: UNSUPPORTED_SOURCE.",
        ],
        estimation=REQ,
        acceptance=(
            "Activation approvals (ADOBE-01, MAGENTO-01), and confirmation that the Adobe paths "
            "are Adobe Commerce only."
        ),
    ),
    SpecialistId.STANDALONE_APPLICATIONS: dict(
        name="Standalone Applications Specialist",
        reg_status="proposed",
        alias="None",
        scope=(
            "Custom web applications, SaaS products, internal tools and application architecture "
            "not primarily implemented as a commerce-platform customization (registry)."
        ),
        overview=(
            "Technology-neutral. No technology is selected and no permanent stack is recommended."
        ),
        arch=(
            "Architecture options are recommendations, not commitments (registry). Deployment and "
            "infrastructure: " + REQ + "."
        ),
        ecosystem=(
            "Frontend, backend, database, authentication and infrastructure are chosen from the "
            "requirement. " + REQ + "."
        ),
        extension=NA,
        apis=REQ + " (API style follows the requirement).",
        data=REQ,
        integrations=REQ,
        custom=NA,
        security=(
            "Security, data and QA needs come from the requirement. Non-functional requirements "
            "must be sourced."
        ),
        versions=NA + " (no platform). Technology versions: " + REQ + ".",
        limits=(
            "No technology source is approved. Any technology-specific claim is UNSUPPORTED_SOURCE "
            "until WDS names the technology and approves its source."
        ),
        examples=[
            "Application architecture selection with no technology named: CLARIFY or "
            "UNSUPPORTED_SOURCE.",
            "One named desktop or mobile framework: bounded example for WDS to choose. Not selected.",
        ],
        estimation=REQ,
        acceptance="WDS decision naming one technology before any source is proposed.",
    ),
    SpecialistId.MIDDLEWARE_APPLICATIONS: dict(
        name="Middleware Applications Specialist",
        reg_status="proposed",
        alias="None",
        scope=(
            "Middleware and integration layers: API orchestration, webhooks, transformation, "
            "synchronization, authentication, retries, idempotency, error handling, background "
            "processing and observability (registry)."
        ),
        overview=(
            "Technology-neutral. The registry says to evaluate suitable technologies from "
            "requirements and evidence. No product is selected."
        ),
        arch=(
            "Pattern topics (draft guidance, not platform evidence): data flow, queues, webhook "
            "receivers, transformation layer, scheduled synchronization."
        ),
        ecosystem="Language and runtime are chosen from requirements, not fixed here. " + REQ + ".",
        extension=NA,
        apis=(
            "Pattern topics: API orchestration, authentication, rate handling. Vendor API details: "
            + P + "."
        ),
        data="Mapping and ownership of each data flow must be defined per project. " + REQ + ".",
        integrations=(
            "Webhooks, messaging, synchronization and transformations are pattern topics. Vendor "
            "specifics: " + P + "."
        ),
        custom=NA,
        security=(
            "Authentication, secrets and webhook verification are pattern topics. Specific "
            "mechanisms: " + REQ + "."
        ),
        versions=NA + " (no product).",
        limits=(
            "No product source is approved. Vendor-specific behaviour is UNSUPPORTED_SOURCE. Retry "
            "and idempotency rules are project design choices, not vendor claims."
        ),
        examples=[
            "Webhook delivery and retry requirement with no product named: CLARIFY.",
            "One named middleware product: bounded example for WDS to choose. Not selected.",
        ],
        estimation=REQ,
        acceptance="WDS decision naming one product before any source is proposed.",
    ),
}

DRAFT_GUIDANCE: dict[SpecialistId, str] = {
    SpecialistId.MIDDLEWARE_APPLICATIONS: (
        "Retries: bounded, with backoff; retry only transient failures. Idempotency: a key per "
        "message so a retry cannot duplicate an effect. Observability: correlation identifiers and "
        "structured logs. Recovery: dead-letter handling and replay after a fix. These are design "
        "topics, not platform claims."
    ),
    SpecialistId.STANDALONE_APPLICATIONS: (
        "Selection criteria (procedure, not evidence): workload and scale stated by the requirement; "
        "team skills; hosting constraints; data sensitivity; integration needs. No technology is "
        "recommended by default."
    ),
}


def _rows(sid: SpecialistId) -> str:
    return "\n".join(
        f"| {c.name} | {c.platform} | {c.edition.value} | {c.claim_kind.value} | "
        f"{', '.join(c.required_terms)} |"
        for c in CATALOG[sid]
    )


def _render(sid: SpecialistId, s: dict[str, object]) -> str:
    rid = REGISTRY_CAPABILITY_IDS[sid]
    extra = DRAFT_GUIDANCE.get(sid)
    risks = "\n".join("- " + r for r in RISKS_COMMON)
    examples = "\n".join("- " + str(e) for e in s["examples"])  # type: ignore[index]
    guidance = f"- Draft guidance: {extra}\n" if extra else ""
    return f"""# {s['name']}: master specification

**Status: DRAFT FOR REVIEW. No platform fact is verified.** Labels used: PENDING OFFICIAL EVIDENCE, UNKNOWN, NOT APPLICABLE, REQUIRES PROJECT-SPECIFIC INPUT.

| Field | Value |
|---|---|
| Canonical capability ID | `{rid}` (from `AGENT_REGISTRY.yaml` and `src/webdesk/specialists/catalog.py`) |
| Registry status | {s['reg_status']} (AGENT_REGISTRY.yaml is a working draft, unapproved) |
| Alias | {s['alias']} |
| Machine-readable companion | `docs/specialists/knowledge/{sid.value}.json` |
| Source manifest | `docs/specialists/knowledge/sources.json` |

## 1. Identity, ownership and supported scope
- Scope: {s['scope']}
- Ownership of this specification: engineering draft, pending WDS review. Platform ownership: see sources.json.

## 2. Platform overview
{s['overview']}

## 3. Architecture and deployment models
{s['arch']}

## 4. Supported technology ecosystem
{s['ecosystem']}

## 5. Capability catalog and canonical IDs
| Capability | Platform | Edition | Claim kind | Required terms |
|---|---|---|---|---|
{_rows(sid)}

Canonical ID: `{rid}`. The knowledge file and the code are checked against this table by tests.

## 6. Technical extension mechanisms
{s['extension']}

## 7. APIs and authentication
{s['apis']}

## 8. Data models and business entities
{s['data']}

## 9. Integration capabilities
{s['integrations']}

## 10. Customization methods
{s['custom']}

## 11. Security and permissions
{s['security']}
- Operator confirmation is required before any investigation. Workspace isolation applies to every page.

## 12. Version and edition differences
{s['versions']}

## 13. Performance, operational and platform limitations
{s['limits']}

## 14. Requirement-analysis procedure
{PROC}

## 15. Source and citation policy
{SOURCE_POLICY}

## 16. Feasibility classification
{FEASIBILITY}

## 17. Estimation and complexity inputs
{s['estimation']}

## 18. Known risks and unsupported behaviour
{risks}
- Registry non-responsibilities are binding (see AGENT_REGISTRY.yaml for this capability).
{guidance}
## 19. Example requirements and investigation scenarios
{examples}

Full draft scenario set: `docs/governance/SPRINT5_EVALUATION_SCENARIOS_DRAFT_2026-10-28.md`.

## 20. Evaluation and QA acceptance criteria
- Machine-readable checklist: `docs/specialists/knowledge/{sid.value}.json` (qa_acceptance_checklist).
- Acceptance dependency: {s['acceptance']}
- Evaluation criteria: PROPOSED only (see `docs/governance/SPRINT4_5_ACCEPTANCE_RECONCILIATION_PROPOSED_2026-10-28.md`).
"""


def main() -> None:
    out = pathlib.Path("docs/specialists")
    for sid, spec in SPECS.items():
        path = out / f"{sid.value}.md"
        path.write_text(_render(sid, spec), encoding="utf-8")
        print("wrote", path)


if __name__ == "__main__":
    main()
