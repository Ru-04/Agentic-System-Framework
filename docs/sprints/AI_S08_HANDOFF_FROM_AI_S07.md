# AI-S08 Handoff from AI-S07

Status: handoff note. AI-S07 is not formally accepted; see `AI_S07_ACCEPTANCE_MATRIX.md` for the open decisions AI-S08 must not assume away.

## What AI-S08 can rely on

- An independent reviewer exists offline (`ai_engine/src/ai_engine/governance/`). It returns a `ReviewReport` with findings, a per-requirement `ReviewStatus`, traceability, escalations and an input fingerprint.
- `EVIDENCE_BACKED` means only: a reviewer assessment that an admitted, verified record supports a requirement, under the gates in `AI_S07_GOVERNANCE_REVIEWER_CONTRACT.md`. It is not an approved estimate, materiality decision, SOW commitment or human approval.
- Estimation inputs should treat `NOT_EVIDENCE_VERIFIED`, `CONFLICTED` and `UNSUPPORTED` as unresolved, and treat `MISSING_REVIEW_PARAMETER` as a reason no backing was established at all.

## What AI-S08 must not assume

- That any requirement is backed in production. All AI-S07 evidence is offline or mock. Mock evidence never backs.
- That the served-status interpretation (D-EVB-1) is more than an isolated-engineering approval. WDS approved it for isolated engineering only. If WDS revokes it, EVIDENCE_BACKED becomes unreachable from validated output and the estimation inputs must be re-derived.
- That the relevance screen is semantic relevance. It is lexical.
- That verification authority is decided (D-06, D-09 open). Who sets an admitted record's verified provenance is not settled.
- That durable audit exists. The input fingerprint is a correlation key only.
- That specialists can self-verify. They cannot; the output contract refuses verified claims.

## Decisions AI-S08 must take from WDS, not infer

1. Ratify D-EVB-1 or direct a contract amendment to the served-evidence rules (AI-S03 and the specialist contract).
2. Decide evidence verification authority (D-06, D-09).
3. Decide acceptance of the consolidated AI-S07 candidate and the commit of its files.

## Foundation dependencies for real estimation authority

Authoritative requirement and source reads; verified provenance from the admission authority; collection authorisation for the actor and project; authoritative supersession and conflict records; durable, tamper-evident review and audit persistence.

## Scope of the AI-S08 isolated estimation work

AI-S08 proceeds as the WDS master plan defines it (`AI_S08_EFFORT_ESTIMATION_SPRINT_SPEC.md`). It must not add approval, materiality or estimate-acceptance logic to the governance package.
