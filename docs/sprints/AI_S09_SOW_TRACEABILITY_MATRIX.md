# AI-S09 SOW Section and Traceability Matrix

Status: structural matrix for the draft SOW. Not a house template; D-10 is pending.

## Section to field

| Section | Field in `DraftSow` | Source inputs | Presented when unsupported |
|---|---|---|---|
| Document control | `document_control`, `approval` | Request identity, requirements, specialist refs, governance, estimate | Always present |
| Executive overview | `overview`, `overview_state` | `overview` | "Business objective: not supported by approved input." |
| In-scope work | `sections[scope_in]`, `workstreams` | `workstreams` | "No workstream is supplied." |
| Out-of-scope work | `sections[scope_out]` | Requirements with `proposed_exclusion` | "No exclusion is proposed." |
| Deliverables | `sections[deliverables]`, `deliverables` | `deliverables` | "No deliverable is supplied." |
| Acceptance criteria | `sections[acceptance]`, `deliverables[].acceptance_criteria` | Deliverable criteria | Per deliverable: "not supported by approved input." |
| Technical approach | `sections[technical]` | `tech_notes` | Per topic: "not supported by approved input." |
| Resource effort | `sections[resources]`, `resources` | `estimate` (AI-S08) | No effort presented |
| Milestones | `sections[milestones]`, `milestones` | `milestones` | "Milestones: not supported by approved input." |
| Assumptions | `sections[assumptions]` | `assumptions` | "Assumptions: not supported by approved input." |
| Client and WDS responsibilities | `sections[client_responsibilities]` | `client_items` | "Client responsibilities: not supported by approved input." |
| Risks, questions, decisions | `sections[risks]` | Governance, `risks`, `questions`, estimate lines, pending decisions, integrity | Always present |
| Change control | `sections[change_control]`, `approval` | Version and approval placeholder | Always present |

## Traceability chain

Requirement (ID and revision) to specialist findings (`finding_ids`) to governance (`governance_status`, `governance_readiness`) to estimate lines (`estimate_line_ids`) to deliverables (`deliverable_ids`) to workstreams (`workstream_ids`). One row per requirement in `traceability`.

## Integrity checks surfaced in `integrity_issues`

Unrepresented in-scope requirement; contradictory scope; deliverable with no in-scope requirement; deliverable with no acceptance criteria; duplicate deliverables; evidence gap (no specialist finding); contradictory assumptions; stale requirement revision; deliverable citing an unknown estimate task; no estimate reference; instruction-like text.
