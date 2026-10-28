# AI-S10 Stale-Input Policy Decision

Decision type: WDS-authorised engineering-policy interpretation of the AI-S10 specification.
Date: 2026-10-28. Authority: WDS Project Owner master directive (AI-S10 resumption).
Status: ratified for the offline synthetic AI-S10 scope. Not a change to any accepted upstream sprint contract.

## 1. Decision

Stale inputs are:

1. detected and reported,
2. traceable to the stale input (requirement ID, evidence ID or task ID),
3. excluded from authoritative use,
4. carried forward as unresolved integrity findings.

This replaces the earlier requirement in AI-S10 specification section 8 that every stale input be **rejected**.

## 2. Scope of the decision

| Category | Behaviour |
|---|---|
| Stale evidence | Reported; never backs a requirement (AI-S07). Traceable by evidence ID. |
| Stale analytical inputs (revisions, snapshots, reference versions) | Reported as integrity findings or `needs_inputs`; no authoritative numerical values; no completed or approved outcome. Traceable by requirement or task ID. |
| Stale operator confirmations or selections | **Rejected** (refused at the decision boundary). Example: `StaleSelectionError` (AI-S01). |
| Replayed or mismatched execution authorisation | **Rejected** at the confirmation gate (AI-S06): ledger replay, expiry, binding mismatch, unauthorised mock. |

Non-authoritative diagnostic reporting remains permitted where the applicable contract allows it (for example
the SOW still being produced with its integrity findings listed).

## 3. Rationale

The accepted contracts already implement flag-and-exclude for stale inputs:

- AI-S05: stale evidence is reported as a question and is not cited.
- AI-S07: stale evidence never backs a requirement; the review is not refused.
- AI-S08: a changed requirement revision marks the line `needs_inputs`; no numbers are presented.
- AI-S09: a stale requirement revision is an integrity issue; the draft is still produced, not complete.

Only stale operator decisions and replayed or mismatched authorisations are refused, and that is already
implemented. Requiring every stale input to be rejected would have contradicted these accepted contracts.

## 4. Consequences for AI-S10 evaluation

- `STL-05` moves from **BLOCKED** (governance decision) to **EXECUTED**, testing the exclusion behaviour.
- `STL-01`, `STL-02`, `STL-03`, `STL-06` keep their executors and expectations.
- `STL-04` (stale operator selection rejected) and the replay and authorisation scenarios keep their rejection
  expectations.
- No upstream engine code changes.

## 5. Specification amendment record

Specification: `docs/sprints/AI_S10_EVALUATION_ACCEPTANCE_SPRINT_SPEC.md`.
Provenance: that file is **untracked** in the worktree. It has no committed version. It was amended in place.
This decision record is committed. The amended specification is not part of any commit unless WDS authorises
it explicitly.

Amended text (section 8), replacing `stale input rejected.`:

> stale input handled under the stale-input policy below. Stale-input policy (amended 2026-10-28, WDS-authorised):
> stale inputs are flagged, excluded from authoritative use, and carried forward as unresolved integrity findings.
> This replaces the earlier requirement that every stale input be rejected. Stale operator confirmations and
> replayed or mismatched execution authorisations are rejected.

## 6. Limits

- The decision applies to AI-S10 offline synthetic evaluation. It does not decide any production stale-data policy.
- The decision does not authorise changes to AI-S08 or AI-S09 contracts.
