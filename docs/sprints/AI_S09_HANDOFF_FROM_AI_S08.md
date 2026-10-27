# AI-S09 Handoff from AI-S08

Status: handoff for the draft SOW sprint. AI-S08 is an engineering checkpoint, not formally accepted. AI-S09 must not treat these estimates as approved, and must not create commitments from them.

## What AI-S09 receives

An `EstimateDraft` (`ai_engine/src/ai_engine/estimation/contracts.py`) with:
- `estimate_version`, `requirement_revisions`, `governance_fingerprint`, `specialist_result_refs`: the references AI-S09 needs for traceability.
- `lines`: one per task-resource combination after merging by implementation key. Each line lists its task IDs, requirement IDs, work category, discipline, status (`indicative` or `needs_inputs`), readiness, numbers (None when `needs_inputs`), basis kinds, assumptions, dependencies, external dependencies, client inputs, access requirements, uncertainty and supporting references.
- `by_discipline`, `by_requirement`, `by_work_category`, `project`: totals, each with `complete` and `excluded_line_ids`.
- `requirement_readiness` and `readiness`: how ready each requirement and the project are for a human reviewer.
- `outstanding_issues`: every unresolved item, including the fixed approval and policy-dependency notes.
- `calculation_provenance`: how totals were computed.
- `draft_status`: always `draft_not_approved`.

## What AI-S09 must respect

1. An estimate with `status == needs_inputs` has no numbers. Do not fill it in.
2. `complete == False` means the totals exclude at least one unestimated line, or the estimate is empty, or a requirement has no task. Show the excluded line IDs and the outstanding issues; do not present the total as the project estimate. Lines with no hours sit in the `unassigned` discipline bucket.
3. A line with readiness `blocked`, `unresolved` or `provisional` is not established. Carry its readiness into the draft SOW. A project readiness of `blocked` can come from a governance blocker that names no requirement.
4. By-requirement subtotals can include shared lines and do not add to the project total. Use `project` for the overall figure.
5. Numbers come from caller-supplied bases. The WDS reference dataset and authorised historical data are not provided (C-08, D-04). Record that dependency in the draft SOW.
6. Governance `evidence_backed` means an admitted record supports the requirement under the AI-S07 gates. It is not an approval, a materiality decision or a commitment.
7. The draft SOW must not create binding commercial commitments. Commitments belong to authorised WDS reviewers and Foundation approval services.

## Traceability to carry forward

Requirement IDs and revisions; task IDs in each line; implementation keys; the governance fingerprint; specialist result references; and every issue in `outstanding_issues`.

## Foundation and governance dependencies

Authoritative requirement revisions and approval status; approved reference ranges and authorised historical data; authority over human estimators; draft and approval persistence; the blocking effect of governance findings on approval; scope acceptance (D-07) and commitment rules (Gate D).

## Open decisions AI-S09 cannot settle

The reference dataset (D-04, C-08), role holders (D-14), the work-category to discipline mapping, expected value and contingency (no approved basis), and every commitment decision.
