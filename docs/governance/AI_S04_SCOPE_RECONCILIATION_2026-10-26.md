# AI-S04 scope reconciliation against the frozen M2 Sprint 3–5 scope (26 October 2026)

**Status: scope reconciliation only.** This is not an additional sprint and not an acceptance. WDS decided (26 Oct 2026): AI-S04 is an internal workstream label, its commits are kept on the integration branch, and its work maps to the existing frozen M2 Sprint 3–5 scope. No work moves between frozen sprints without WDS authorization.

## Frozen scope (baseline v1.0, 22 Oct 2026)
- **S3 (M2):** initial executable implementations for the six platforms; smoke and contract tests on each; platform test fixture validation.
- **S4 (M2):** deep platform-specific investigation, integration and option feasibility, restrictions, evidence capture, technical risk and unknowns, estimation inputs. Tests: platform-specific functional and negative cases; evidence integrity.
- **S5 (M2):** all seven independently evaluated against agreed scenarios; repeatability; graceful degradation; scorecards and gap closure.

## AI-S04 code and where it maps
| Code (integration branch) | Commit | Mapped frozen deliverable | Covered now | Not covered |
|---|---|---|---|---|
| WooCommerce agent and synthetic evidence | `ac1ef7e` | S3 initial executable implementation (partial, synthetic) | Synthetic agent; `test_ai_s04_woocommerce.py` | Real platform evidence (none approved); S4 investigation; S5 scenario evaluation |
| BigCommerce agent and synthetic evidence | `ac1ef7e`, wording `2988913` | S3 (partial, synthetic) | Synthetic agent; `test_ai_s04_bigcommerce.py` | Same as above |
| Shift4Shop agent and synthetic evidence | `2988913` | S3 (partial, synthetic) | Synthetic agent; `test_ai_s04_shift4shop.py` | Same as above |
| Magento / Adobe Commerce agent and synthetic evidence | `2988913` | S3 (partial, synthetic) | Synthetic agent; `test_ai_s04_magento.py` | Same as above |

## Rules applied
- Synthetic tests count only toward S3 smoke and contract checks. Under baseline rule 4 and the M2 gate, synthetic fixtures do not count as real specialist acceptance.
- S4 and S5 are not met by these commits. They need approved evidence sources (none is approved for any of the six platforms, D08).
- The AI-S04 code is in the AI-engine framework. The S3 foundations for the same platforms are in the webdesk framework (see the matrix). Mapping the AI-engine code to the webdesk modules is an architecture decision for WDS.

## What remains
- **Sprint 3:**
  1. Architecture decision on the two frameworks (one framework for the six platforms, or a documented split).
  2. Standalone Applications and Middleware Applications have no executable agent in either framework. Under S3 they still need one (BD is the assigned developer, as reported).
  3. Common harness conformance across the six, on the chosen framework.
  4. Smoke and contract tests run and recorded at the current head (blocked on the webdesk side; see the test register).
  5. Platform test fixture validation, recorded as fixture-only.
  6. Independent Sprint 3 QA by PG (independence pending).
- **Sprint 4:** approved evidence sources for each platform (none yet), real platform investigation, feasibility and option assessment, evidence capture. Not started.
- **Sprint 5:** scenario evaluation of all seven, repeatability, scorecards. Not started.

## Recorded decisions
- AI-S04 is an internal workstream label, not a tenth sprint.
- Scope mapping pending WDS confirmation. Nothing here is accepted.
