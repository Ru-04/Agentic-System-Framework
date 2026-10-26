# Synthetic Evaluation (synthetic-eval-v1)

The dataset is `src/webdesk_ai/evaluation/cases.py`. Run it with:

    uv run python -m webdesk_ai.evaluation.runner docs/ai-engine/evaluation_report.json

## What is measured

Each case runs the real workflow against scripted model output and a mock ai-read/v1 server. Each case
has a hand-written expectation. The aggregate metrics and their targets are:

| Metric | Target | Meaning |
|---|---|---|
| decomposition_accuracy | 1.0 | cases with the expected requirement count |
| traceability_rate | 1.0 | source references whose quote is verbatim in a visible segment |
| hallucinated_refs_in_output | 0 | accepted references to segments that were not supplied |
| clarification_completeness | 1.0 | flagged requirements that have a question |
| unsupported_claims_accepted | 0 | accepted claims marked supported without approved evidence |
| verified_claims_in_outputs | 0 | claims marked verified (no approved evidence exists here) |
| routing_accuracy | 1.0 | expected routing recommendations present |
| invalid_schema_detection_rate | 1.0 | injected schema faults that were detected |
| approval_boundary_violations | 0 | requirements in verified or accepted-for-scope status |
| review_flags_fixed | 1.0 | review packages with the fixed approval flags |

## Limits of these numbers

- The expectations were written from intended pipeline behaviour. The scores show that validation,
  routing, gating and disclosure behave as designed. They do not show how a live model would
  decompose a real brief. A live model would need its own dataset, graded by humans.
- Every evidence item is synthetic. A passing `verified_claims_in_outputs = 0` does not mean any
  Shopify claim is true. It means no claim was labelled verified.
- The dataset is small (17 cases). Confidence intervals are not computed.
