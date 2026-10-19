> **SUPERSEDED / DO NOT USE FOR REFERENCE COUNTS.** Prior report contained false-positive unresolved-reference findings. See `VALIDATION_REPORT_v0.3.4.md`.

# v0.3.2 Foundation — Mechanical Validation Report

**Status:** specification review candidate, not independently approved. No application code or runtime tests were executed.

- YAML parses: PASS (registry and catalog).
- Registry entries: 15; service/tool definitions: 6; model configurations: 3; routing rules: 13; service catalog patterns: 15.
- Reference validation of `allowed_tools`, `dependencies`, `handoffs`, `model_config_ref` and activation targets: **12 legacy unresolved references (outside Gate 1); no new Foundation references added to YAML**.
- Governance safeguard phrase checks: 16/16 present (semantic smoke test, not equivalence proof).
- Gate 1 EVAL-F01–F10 test definitions: 10/10.
- B-3/B-6/B-7/B-11 recorded: PASS.
- Static check issues: 12.

## Legacy out-of-scope reference issues (all present before v0.3.2)
- AG-ORCHESTRATOR: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-ECOMMERCE: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-3D-CART-SHIFT-SHOPIFY: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-WORDPRESS-WOOCOMMERCE: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-BIGCOMMERCE: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-MAGENTO-ADOBE-COMMERCE: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-STANDALONE-APPLICATIONS: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-MIDDLEWARE-APPLICATIONS: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-INTEGRATION-SOFTWARE: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- CAP-AI-AUTOMATION: unknown allowed tool SVC-EVIDENCE-RETRIEVAL
- ROUTE-CROSS-PLATFORM-001: unknown activation Union of only relevant specialist categories; multiple categories may collaborate on a requirement.
- ROUTE-OUTPUT-VALIDATION-001: unknown activation TOOL-SCHEMA-VALIDATOR

## Scope limitations

Mechanical cross-reference checks cannot prove governance completeness, authorization correctness, test adequacy, or implementation readiness. Older v0.2/v0.3 technical issues outside Gate 1 remain deliberately unresolved; routing remains disabled, no live vendor allowlist is approved, no LLM runtime provider chosen, retention periods and hosting remain pending. Independent Gate 1 review is REQUIRED before Claude Code.

**Reviewer note:** `SVC-EVIDENCE-RETRIEVAL` is an architectural logical service without matching registry tool/catalog ID in this package; two prose-based `activate` values are not typed specialist IDs. These are pre-existing non-Foundation issues and are deliberately NOT declared resolved. Routing remains disabled. The previous independent review considered cross-references resolved under a broader semantic interpretation; this strict check distinguishes exact IDs from logical prose.
