# Architecture compatibility assessment: WebDesk specialist framework vs AI Engine specialist framework (26 October 2026)

**Status: assessment only.** No framework has been merged or replaced. Preferred direction (WDS): WebDesk is the primary platform, and reusable AI Engine capabilities are connected through adapters. Any change needs a verified compatibility and security review first.

## 1. What each framework is
| Area | WebDesk (`src/webdesk`, branch `claude/webdesk-specialist-baseline-v1-3b21b1`) | AI Engine (`ai_engine/`, branch `integration/ai-s01-s02-s03`) |
|---|---|---|
| Specialist contract | `SpecialistInput` / `SpecialistOutput`, contract version 1.0.0, Pydantic models with `extra="forbid"` | `SpecialistAgent` Protocol, `SpecialistContext`, `SpecialistTask`, `SpecialistInvestigationResult` (pydantic contracts package) |
| Orchestration | `run_specialist` harness: validates input, checks workspace and actions, calls provider, validates output | `run_specialist` execution wrapper: task builder, registry lookup, evidence view, result envelope |
| Registry | `SpecialistId` catalog and `REGISTRY_CAPABILITY_IDS` (includes legacy Shift4Shop alias) | `AgentRegistry.from_yaml` reading the spec registry (`AGENT_REGISTRY.yaml`) |
| Evidence retrieval | `InMemoryRetriever`, `RetrievalQuery`, citations, relevance grading, vendor allowlist with origin rule | `MockEvidenceLookup`, RAG package (`ai_engine/rag`), synthetic evidence per specialist |
| Authority | `Action` allowlist (read_evidence, propose_candidates, declare_unknowns); `FORBIDDEN_ACTIONS` refused by `check_actions` | `PermissionDeniedError`; evidence allowlist per task; ApprovalGuard for LLM calls (in-process, not Foundation authorization) |
| Security controls | Workspace checks at retrieval; quarantine of instruction-like text; approved-source origin rule; no live model (D09) | Snapshot-once allowlist (AI-S01 P0-1), stale-selection refusal (P1-2), rationale refusal (P1-4), import scan, `safe_load` YAML, ApprovalGuard |
| LLM | None | Provider-neutral port, adapters, structured-call runner (no provider enabled) |
| Platform coverage | Shopify investigation; six foundations (profile + shared base, no approved source) | Shopify synthetic agent; AI-S04 synthetic agents for WooCommerce, BigCommerce, Shift4Shop, Magento; none for Standalone or Middleware |
| Tests | 536 unit tests at last verified run (`e3ba3b7`); blocked at current head (error 4551) | 1253 passed in a clean-room run of `2988913` |

## 2. Compatibility findings
1. **Contracts are not interchangeable.** Field names, status enums and output shapes differ. A bridge is needed in both directions. No shared schema exists.
2. **Orchestration differs.** WebDesk validates input and output at the harness boundary. The AI Engine wraps execution with a task builder and registry lookup. Both enforce permissions, but at different points.
3. **Authority is implemented twice.** WebDesk's action allowlist and the AI Engine's permission and approval checks cover overlapping concerns. Neither is a Foundation authorization service. Runtime enforcement of authority is still a dependency (QA-07).
4. **Security controls are not shared.** The AI-S01 fixes exist only in the AI Engine. The WebDesk origin rule and quarantine exist only in WebDesk. Each adapter must keep the stricter rule of the two.
5. **Evidence is handled differently.** WebDesk fetches only approved vendor origins; the AI Engine uses synthetic evidence. An adapter that lets AI Engine evidence reach a WebDesk output would break the origin rule and must not be built without a decision.
6. **Duplicate platform work.** Six platforms appear in both frameworks. Keeping both is duplication. Keeping one needs a WDS decision.
7. **Deployment boundary.** Neither framework has production activation. The AI Engine's LLM port is disabled. Any adapter must keep the LLM disabled (D09).

## 3. Proposed adapter boundary (for WDS decision; not implemented)
- WebDesk remains the host. Its contract, harness, authority and origin rules are authoritative.
- AI Engine capabilities are reached through adapters that (a) translate `SpecialistInput` into the AI Engine task, (b) return only results in the WebDesk output contract, (c) apply WebDesk's origin and workspace rules to any evidence, and (d) keep the LLM port disabled.
- AI-S04 synthetic agents stay in the AI Engine as reference implementations. They are not connected to WebDesk outputs.

## 4. Risks not yet verified
- No adapter exists, so no compatibility is proven by tests.
- The AI-engine security tests were not run against any WebDesk adapter.
- Two registries (`AGENT_REGISTRY.yaml` and the WebDesk catalog) can drift.

## 5. Not decided here
Which framework keeps each platform; the adapter design; the shared contract version; whether the AI Engine modules move into WebDesk.
