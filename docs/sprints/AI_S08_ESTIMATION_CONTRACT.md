# AI-S08 Estimation Contract

Status: engineering contract for the isolated draft estimation engine. Not approved by WDS as a numeric method. Every estimate it produces is a draft.

Governing text: REQUIREMENT_SCHEMA.md section 9.2 (task fields, seven disciplines, non-negative ordered hours, no invented numbers) and section 4.8 (estimate fields, unit rules); decision D-04 (numeric basis from authorised historical data and WDS reference ranges, or human estimator input; AI proposes, an authorised human approves); D-14 (role holders pending); C-08 (reference dataset not yet provided).

## 1. What the engine is

`ai_engine.estimation.engine.estimate(request) -> EstimateDraft`. It reads one `EstimateRequest` and returns one draft. It does not read Foundation, the network, a provider, a clock or the file system. It never mutates its input. Its outputs are frozen.

## 2. Inputs

- `RequirementSnapshot`: requirement ID, project ID and revision (a strict integer of at least 1). Requirements are approved-shape inputs supplied by the caller; the engine does not read them from Foundation.
- `TaskInput`: task ID, implementation key, requirement ID and the revision it was built on, work category, title, one `ResourceAllocation` per discipline, an optional `EstimateBasis`, specialist category IDs, dependencies (task IDs), external dependencies, client inputs, access requirements, assumptions, and an uncertainty note.
- `ResourceAllocation`: a discipline and a `ThreePoint` (low, likely, high hours).
- `EstimateBasis`: kind, reference ID, project ID, version and provenance text.
- `GovernanceSummary`: a copy of an AI-S07 review: run ID, project ID, input fingerprint, per-requirement review status, blocking requirement IDs, escalation count and whether any blocker exists. Built by `estimation.bridge.governance_summary`.
- Specialist result references (category to reference string), built by `estimation.bridge.specialist_result_refs` from an AI-S06 result.
- Authorised reference projects, current reference versions, and a flag that permits synthetic fixtures (default off).

## 3. Resource and task taxonomy

Disciplines (REQUIREMENT_SCHEMA 9.2; the only valid resource categories): `business_analysis`, `ui_ux`, `frontend`, `backend`, `qa`, `project_management`, `devops_deployment`.

Work categories (the brief's breakdown; a taxonomy of the work, not a resource): discovery and clarification, solution architecture, frontend development, backend development, platform configuration, app or plugin integration, API and middleware integration, data migration, QA and regression testing, deployment preparation, technical documentation and handover.

Each task names its discipline explicitly. The engine never infers a discipline from a work category. The mapping from work category to discipline is a policy dependency (section 8).

## 4. Numeric basis and status

`BasisKind`: `approved_reference_range`, `authorised_historical`, `human_estimator`, `synthetic_fixture`.

A line has numbers only when every basis and input check passes. Otherwise the line is `needs_inputs`, with no numbers, and the issues say why. A synthetic fixture is accepted only when the request allows it, and its provenance must say it is synthetic. A human estimator basis is accepted on the caller's word; the engine records its kind but cannot verify who the estimator was.

`EstimateStatus` is `indicative` (numbers present) or `needs_inputs`. `approved` is not a member. The draft status is always `draft_not_approved`.

## 5. Readiness

Readiness is separate from hours, and it never means approval.

Per requirement, from the governance status:
- `evidence_backed` gives `ready_for_review`.
- `not_evidence_verified` gives `provisional`.
- `unsupported` gives `unresolved`.
- `conflicted`, or any requirement named in the blocking list, gives `blocked`.

Per line: `needs_inputs` if the line has no numbers, otherwise the most restrictive readiness of the requirements it lists. Per project: the most restrictive of all line and requirement readiness, `needs_inputs` if any requirement has no task, and `blocked` whenever the governance review reports a blocking finding (even one that names no requirement).

Readiness never removes a line from totals. Totals always show the numbers the line holds, and the readiness states beside them.

## 6. Validation (fail closed)

Refused with an `EstimationInputError`. Error messages name fields and error types only: list positions appear as `<index>`, mapping keys and unknown field names appear as `<key>`, and requirement and task identifiers are never echoed. Refused:
- Malformed identifiers (requirement, task, implementation key, reference, version, category).
- Non-finite, negative, unordered or non-float hours. Integers are stored as floats; text and booleans are refused.
- A discipline outside the seven, or the same discipline twice on one task.
- A basis that claims a synthetic kind without marking it synthetic.
- Duplicate tasks or duplicate requirement snapshots.
- A snapshot, task or governance review that belongs to another project.
- A task for a requirement not in the request, or citing an unknown specialist result.
- A dependency on a task not in the request.
- A missing governance review, or a requirement with no governance assessment.

## 7. Calculation and aggregation

1. Tasks with the same implementation key and discipline form one line. Its task IDs and requirement IDs are listed; its hours are counted once.
2. A line is `needs_inputs` if any member task has an issue (stale revision, no hours, no basis, unauthorised cross-project basis, synthetic fixture not permitted, unconfirmed or stale reference version), or if members disagree on hours, basis or work category.
3. Totals are the sum of the low, likely and high of estimated lines, in line-ID order, using built-in float addition. There is no weighting, expected value, contingency, confidence score, duration or rate.
4. Project totals count each estimated line once. `complete` is False whenever any line in the group is unestimated, and the group lists the excluded line IDs. An empty estimate, and any requirement with no task, is incomplete: its totals say so, and it is an outstanding issue.
5. By-requirement totals include every line that lists the requirement. A shared line therefore appears in each requirement's subtotal, and the subtotals do not add to the project total. This is stated in the draft's calculation provenance.
6. By-discipline and by-work-category totals group lines by their discipline and work category. Lines with no hours have no discipline; they form an `unassigned` bucket in by-discipline totals. A line whose members disagree on work category is `needs_inputs`, so a line has one category.

## 8. Open policy decisions (recorded; not decided here)

1. The WDS reference dataset and the authorised historical data (D-04, C-08). Until they are provided, numbers come only from caller-supplied bases, and the output carries that dependency as an outstanding issue.
2. The mapping from work categories to disciplines.
3. Role holders and the role set for allocation (D-14).
4. Whether a human estimator basis needs a named authorised estimator recorded beside it.
5. The approval workflow for a draft estimate, which belongs to Foundation and authorised WDS reviewers.
6. Expected value, weighting, contingency and confidence scoring: no basis is approved, so none is computed.

## 9. Foundation and governance dependencies

Authoritative requirement revisions and their approval status; authorised historical and reference data with verified version and provenance; the authority that decides a human estimator's standing; persistence and approval of drafts; collection and project authorisation for any cross-project reference; and the blocking effect of governance findings on approval.
