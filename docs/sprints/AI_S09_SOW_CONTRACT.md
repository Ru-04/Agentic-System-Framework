# AI-S09 Structured Draft SOW Contract

Status: engineering contract for the offline draft SOW engine. Draft only. Not an offer, a commitment or an approved SOW. Not reviewed by WDS.

Governing text: REQUIREMENT_SCHEMA.md 4.4 (ScopeItem), 4.8 (Estimate), 4.9 (Assumption, Risk, Exclusion), 9.1 (ScopeCommitment, Materiality, criticality, origin), 9.4 (scope acceptance); REVIEW_POLICY.md Gate D (no commitment without explicit commitment), Gate E (critical findings not waivable), Gate F (approver separation); DECISION_REGISTER D-05 (no self-approval) and D-10 (house template and DOCX/PDF export pending).

## 1. What the engine is

`ai_engine.sow.engine.generate(request) -> DraftSow`. It reads one `SowRequest` and returns one structured `DraftSow`. It reads no Foundation data, network, provider, clock or file. It never mutates its input, and its output is deterministic.

## 2. Mapping of the brief's sections to the spec's sections

| Brief section (A-K) | Spec section (1-13) | Where it appears in `DraftSow` |
|---|---|---|
| A Document control | (control) | `document_control`, `approval`, manifest |
| B Executive overview | 1 Project overview | `overview`, `overview_state` |
| C In-scope work | 2 Scope, 5 Deliverables | `sections[scope_in]`, `workstreams`, `deliverables` |
| D Out-of-scope | 6 Exclusions | `sections[scope_out]` |
| E Deliverables and acceptance | 5, 11 | `deliverables`, `sections[acceptance]` |
| F Technical approach | 4 Solution and architecture, 7 Integrations | `sections[technical]` |
| G Resource effort | 9 Resource-wise estimates | `resources`, `sections[resources]` |
| H Milestones | 8 Milestones and phases | `milestones`, `sections[milestones]` |
| I Assumptions and responsibilities | 6, 12 | `sections[assumptions]`, `sections[client_responsibilities]` |
| J Risks, questions, decisions | 10 | `sections[risks]` |
| K Change control and approval | (control) | `sections[change_control]`, `approval` |
| Traceability | 3 Requirement-to-deliverable mapping, 13 | `traceability`, `unrepresented_requirement_ids`, `integrity_issues` |

## 3. Input (`SowRequest`)

- Identity: `sow_id`, `sow_version`, optional `previous_version`, `project_id`.
- `requirements`: requirement ID, project, revision, statement (data), origin (`client_explicit` or `inferred`), disposition (`in_scope` or `proposed_exclusion`), and a rationale required for every proposed exclusion.
- `overview` (optional): business objective and solution summary as client-supplied or proposed text, with a source reference.
- `workstreams`, `deliverables` (each with at least one requirement, acceptance criteria if supplied, dependencies, constraints, evidence and finding references, and AI-S08 estimate task IDs), `findings` (AI-S06 specialist category, kind and summary), `tech_notes` (by topic), `assumptions` (key, value and status), `risks`, `questions`, `client_items`, `milestones` (deliverable groupings and dependencies).
- `specialist_result_refs`: the specialist result references for every finding category. A finding whose category is not listed is refused, with or without an estimate.
- `governance` (required): an AI-S07 governance summary, copied from the review.
- `estimate` (optional): an AI-S08 `EstimateDraft`. Without it, no effort is presented.

The request model forbids unknown fields. Approval fields, approver identities, prices, rates and signatures are refused at parse time.

## 4. Output (`DraftSow`)

- `document_control`: SOW ID and version, previous version, project, requirement revisions, specialist result references, governance run and fingerprint, estimate version and draft status, generator name, and a source manifest.
- `approval`: state `pending_human_approval`, required role Approver, the separation rule, and `preparer` and `approver` fixed to None.
- `overview`, `overview_state`: the business objective is shown only when supplied; otherwise the item reads "not supported by approved input".
- `sections`: scope_in (with in-scope requirement statements), scope_out, specialist_findings (with finding summaries), deliverables, acceptance, technical, resources, milestones, assumptions, client_responsibilities, risks, change_control.
- `workstreams`, `deliverables`, `milestones`: typed views with traceable references and per-item estimate values.
- `resources`: the AI-S08 draft estimate, presented unchanged, with per-line status and readiness, by-discipline totals with completeness, and a banner that marks partial totals.
- `traceability`: one row per requirement from requirement to findings, governance status and readiness, estimate lines, deliverables and workstreams.
- `unrepresented_requirement_ids`, `integrity_issues`, `calculation_provenance`.

## 5. Estimate semantics (AI-S08 preserved)

- A `needs_inputs` line has no numbers, and the SOW shows none. A deliverable or workstream with no estimated line shows no value either, and never zero. A discipline bucket with no numeric line is shown as not estimated. A workstream is complete only when every deliverable in it is complete.
- A total with any excluded line is marked incomplete. Partial totals are labelled PARTIAL and are not presented as the project estimate.
- Readiness for a requirement is the stricter of the AI-S07 governance readiness in this SOW and the estimate's readiness. A blocker therefore stays visible even when the estimate was built without it.
- No rate, price, discount, weighting, contingency or expected value exists in the model.

## 6. Coverage and integrity checks

Reported in `integrity_issues`, never silently dropped:
- In-scope requirements with no deliverable (`unrepresented_requirement_ids`).
- Proposed exclusions covered by a deliverable (contradictory scope).
- Deliverables with no in-scope requirement, or no supplied acceptance criteria.
- Duplicate deliverables (same normalised title and requirement set).
- In-scope requirements with no specialist finding (evidence gap).
- Contradictory assumptions for one key.
- Stale requirement revisions relative to the estimate, or requirements missing from it.
- Deliverables citing estimate tasks that do not exist.
- Missing estimate reference (resource effort not supported).
- Estimate effort for requirements not in the SOW: the estimate totals include it, so the project total is marked partial and the lines are listed.
- A workstream that holds only proposed exclusions (contradictory workstream scope).
- A milestone that groups no deliverable.
- Instruction-like text in any free-text field (requirement, overview, workstream, deliverable title, description, criteria, dependencies and constraints, finding, technical note, assumption statement and value, risk, question, client item, milestone title), flagged as data and not executed.

Refused at input (`SowInputError`), unconditionally: duplicate identifiers; references to unknown requirements, deliverables, workstreams, findings, specialist results or milestones; dependency cycles in deliverables or milestones; a requirement, governance review or estimate from another project; a missing governance review; a governance review that lacks an assessment for any requirement.

## 7. Milestones and time

Milestones are sequences of deliverables. The contract assigns no calendar dates. Every milestone view carries the note that elapsed duration is not derived from effort hours.

## 8. Draft-only safety

- No approved state, approver identity, signature, price, rate or commitment exists in the output model. A test checks the schema's property names.
- Source text is copied verbatim as data. Instruction-like content is flagged; nothing in it is executed.
- The output is deterministic: sorted collections and identical output for identical or reordered inputs.
- Version traceability: `previous_version`, the requirement revision map, and `compare_versions` for added and removed deliverables and requirements.

## 9. Rendering and export

Not implemented. D-10 requires the approved WDS house template, section mapping and export acceptance tests before any DOCX or PDF export. The structured model is suitable for a later authorised renderer, which must also apply the approved wording. No native export is claimed here.

## 10. Pending decisions

- D-10: house SOW template, section contract and wording conventions. The sections above are a structural proposal, not the house format.
- Gate F and D-05: approver assignment and separation are a Foundation workflow. The engine never records an approver.
- Client and WDS responsibility wording: approved text was not supplied, so none is invented.
- Commitment: ScopeItem commitment (REQUIREMENT_SCHEMA 9.1) is not modelled as committed by this engine. Every item is a proposal for human decision.
- Materiality: unassessed, so it gates as material (REQUIREMENT_SCHEMA 9.1). The engine makes no materiality determination.
