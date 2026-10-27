# AI-S09 Implementation Record: Detailed WDS Draft Statement of Work

Status: engineering checkpoint, isolated offline scope, draft only. Not formal acceptance. Baseline: AI-S08 `f01f76d0fe8e4ad185c46aecacb5351640d133d9` (formally accepted for isolated offline engineering by WDS), with record commit `f0fc850`.

Companion documents: `AI_S09_SOW_CONTRACT.md` (structure, safety, estimate semantics), `AI_S09_QA_AND_ACCEPTANCE_MATRIX.md`, `AI_S09_QA_FINDINGS_REGISTER.md`, `AI_S09_GOVERNANCE_AND_FOUNDATION_DEPENDENCIES.md`, `AI_S10_HANDOFF_FROM_AI_S09.md`.

## 1. What was implemented

Package `ai_engine/src/ai_engine/sow/`:
- `contracts.py`: the input model (`SowRequest` and its parts), the output model (`DraftSow`, its sections, views, traceability rows and approval placeholder), enumerations (dispositions, assumption and risk statuses, claim kinds, technical topics, client item kinds, section states), identifier patterns, and the sanitised error type `SowInputError`.
- `engine.py`: `generate`, `build_request`, `compare_versions`, and the structural, coverage, governance, estimate and integrity logic.

Reused without change: AI-S08 `EstimateDraft`, `GovernanceSummary` and readiness from `ai_engine.estimation`; AI-S07 review data through the AI-S08 bridge; AI-S06 orchestration in the pipeline test.

## 2. Capabilities against the brief

| Brief item | Where | Status |
|---|---|---|
| Sections A-K | `DraftSow` fields (see contract section 2) | Implemented as a structured model |
| Bidirectional traceability | `traceability` rows; deliverable and workstream views | Requirement to findings, governance, estimate lines, deliverables and workstreams |
| Unrepresented requirements, duplicates, contradictions, unsupported deliverables, unresolved dependencies, incomplete estimate totals, stale revisions | `unrepresented_requirement_ids`, `integrity_issues` | Implemented and tested |
| Draft-only and no commitment | `approval`, `draft_state`, schema has no approval, price or signature fields | Implemented and tested |
| Injection resistance | `_INSTRUCTION` check over every source text; verbatim copying | Flagged, never executed; tested |
| Versioning | `previous_version`, requirement revision map, `compare_versions` | Implemented and tested |
| Deterministic output | Sorted collections; reordered inputs give identical JSON | Tested |
| Export | Not implemented (D-10 pending) | Structured JSON only |

## 3. Test results

Final candidate (this checkpoint):
- Full suite: 1696 passed, 3 skipped. The skips are the Foundation tests at lines 357, 362 and 367 of `test_ai_s02_s04_acceptance_distinctions.py`, visibly skipped and not run offline.
- AI-S09 focused: 56 tests in `test_ai_s09_sow.py`, all passing.
- Regression subset (AI-S02 guard and contracts, AI-S05, AI-S06, AI-S07, AI-S08, AI-S09): 458 passed.
- Ruff check and format check: clean. Strict mypy across source and tests: clean (144 files).
- The 1696 count includes tests from three untracked Foundation files in the development worktree (not committed). See the QA and acceptance matrix for the committed-tree count.

## 4. Defects found during construction (fixed before this checkpoint)

- The SOW read readiness from the estimate alone, so a governance blocker in the SOW's own review was not visible when the estimate was built without it. Fixed: the stricter of governance readiness and estimate readiness. Test: `test_a_blocking_governance_finding_stays_visible_and_is_not_suppressed`.
- A deliverable with no estimated line showed zero hours with `complete=False`. Fixed: no number is presented when no line is estimated. Test: `test_a_line_without_hours_is_never_converted_into_a_number`.
- The index helper used `getattr` with a computed attribute name, which the AI-S02 import guard rejects. Fixed: key-extraction functions are passed in; the guard is unchanged.
- The error sanitiser echoed mapping keys. Fixed: the same whitelist approach as AI-S08 (known field names by name; positions and other keys as placeholders). Test: `test_error_messages_do_not_echo_sentinel_values`.

## 5. Limitations accepted for this checkpoint

- No rendered document. DOCX and PDF await the D-10 house template.
- No house wording. Section titles and labels are structural; approved client and WDS responsibility text was not supplied.
- No approval workflow, persistence or approver identity. These are Foundation services.
- Instruction detection is a pattern screen. It flags; it does not decide what is harmful.
- The engine does not verify that a requirement statement is faithful to the client's source.
- Estimate values are the AI-S08 draft values, with their own limitations (see the AI-S08 contract).
- Commitment, materiality and criticality are not determined here. They remain human or Foundation decisions.

## 6. Foundation and governance dependencies

See `AI_S09_GOVERNANCE_AND_FOUNDATION_DEPENDENCIES.md`.

## 7. Checkpoint

The engineering checkpoint commit is reported with its SHA after commit. It is not formal acceptance. Next: independent QA of the complete implementation, then consolidated remediation, then WDS acceptance.
