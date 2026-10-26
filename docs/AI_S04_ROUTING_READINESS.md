# AI-S04 Specialist Routing Readiness

Status: **not ready for runtime selection.** This report states what is in place and what must be true before any
commerce specialist can be selected at runtime. It does not change routing.

## 1. What is in place

- Explicit selection exists in the AI-2 task builder. An operator-built `ExplicitSelection` plus `build_specialist_task`
  is the only entry point for the five commerce specialists.
- Each specialist is refused outside its platform and its requirement scope. Runs are offline and synthetic only.
- No AI-S04 module is referenced by any router or workflow. The workflow default remains the AI-1 Shopify specialist.
- The requirement-analysis agent proposes a specialist only for Shopify keywords (AI-1 code, unchanged).

## 2. Gates before runtime activation

Activation requires all four. None is met today.

| # | Gate | Source | Status |
|---|---|---|---|
| G1 | Foundation-authenticated actor identity | AI-S01 dependency 1; Foundation | Not available |
| G2 | Project permissions and specialist-execution authorisation enforced | AI-S01 dependencies 2 and 3; Foundation | Not available |
| G3 | Structured routing rules with governance approval | `AGENT_REGISTRY.yaml` `machine_routing_enabled: false`; "structured router is approved"; pending C-05 | Not approved |
| G4 | Explicit operator confirmation of each AI-proposed specialist before execution | WDS final authorisation (operator confirmation mandatory) | Designed; not connected to a runtime |

## 3. Code changes that activation would need (separate authorisation)

- `requirement_analysis/agent.py` proposes only Shopify today. Each commerce category would need its own proposal rule.
- `demo/workflow.py` defaults to the Shopify specialist. A selection step is needed in the workflow.
- `rag/specialist.py` lists `SEVEN_SPECIALIST_CATEGORY_IDS`, which already includes all five commerce categories. Its
  category identifiers must match the registry after any migration.

WDS authorised design, contracts and offline tests only, so none of these changes is made under AI-S04.

## 4. Prohibited until gates G1 to G4 are met

- Automatic specialist execution.
- Runtime selection of any commerce specialist.
- Any AI-1 routing or execution change under AI-S04.

## 5. Readiness verdict

Offline readiness: met for the five specialist modules. Runtime readiness: not met (G1 to G4 open). No change is
requested to the registry's `machine_routing_enabled` setting.
