# AI Engine Orchestration Note (Increment 2)

Status: implementation note for independent review. Not an approved design.

## Why no LangGraph dependency

`ARCHITECTURE.md` names LangGraph as the workflow orchestrator. Three facts keep this increment from
adding it:

1. LangGraph is not installed or locked in this repository (`pyproject.toml`, `uv.lock`).
   Adding it changes the dependency set that Foundation packaging uses.
2. `ARCHITECTURE.md` (section on the LangGraph workflow, row "Benchmark shows unacceptable
   complexity") and its note that conditional routing and fan-out are future behaviour pending C-05.
3. `docs/INCREMENT_2_PLAN.md` decision D-5 defers LangGraph for the Foundation increment.

The orchestrator in `webdesk_ai/orchestration.py` is a plain stage graph. Each stage is a function
that reads and writes one state object, and each would map to one LangGraph node. Edges are explicit.
The two conditional edges are:

- analysis failure or a blocked traceability check goes straight to the review stage;
- a specialist runs only when it was both routed and explicitly authorized.

Moving to LangGraph later means wrapping these functions as nodes. It does not change stage logic.

## Stages

| # | Stage | Output | Gate |
|---|---|---|---|
| 1 | load_context | project, run, readable versions, segments | run must be active; any read refusal stops the run |
| 2 | analyze_requirements | validated proposals | at most two content attempts; transport retries inside |
| 3 | validate_analysis | independent traceability re-check | any violation blocks |
| 4 | determine_clarifications | gap list | flagged requirements without a question are reported |
| 5 | plan_specialist_routing | routing recommendations | `machine_routing_enabled` stays `false` |
| 6 | run_authorized_specialists | isolated specialist results | only categories in `authorized_categories` |
| 7 | validate_outputs | unsupported-claim count | any unsupported claim is recorded |
| 8 | human_review_package | `ReviewPackage` | flags are fixed by construction |

## What is never automated

`ReviewFlags` uses `Literal[False]` and `Literal[True]` fields. Constructing it with an approval value
fails validation. Requirements cannot reach `verified` or `accepted_for_scope` through this code.
No Foundation write exists, and every read goes through the ai-read/v1 client.

## Logging

Stages log their name, outcome and counts. They never log prompts, client text, model responses,
tokens or evidence text. `tests/ai_engine/test_ai_orchestration.py` checks this with a log capture.
