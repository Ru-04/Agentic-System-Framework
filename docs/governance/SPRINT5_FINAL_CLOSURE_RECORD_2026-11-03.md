# M2 Sprint 5: final closure record (3 November 2026)

## Determination

**M2 SPRINT 5 — FORMALLY ACCEPTED UNDER WDS-APPROVED REVISED MVP EVALUATION SCOPE.**

This record finalises the scope amendment in `SPRINT5_SCOPE_AMENDMENT_AND_CLOSURE_2026-11-03.md` (commit `74608aa`). It does not reopen that amendment and does not require the superseded Shopify benchmark. The original frozen requirements are not described as fully completed. Superseded and deferred items are listed in Section 4.

## 1. Approver and channel

- **Approver:** WDS Authorized Approver. The approver identified themself by this role in chat. A personal name has not been provided and is not recorded here.
- **Channel:** formal WDS directive in the Sprint 5 session (chat), dated 3 November 2026.
- **Not inferred:** the Foundation ruling 5 approver (Sprint 6 D-10) is a separate decision. It is not the Sprint 5 approver, and this record does not treat it as one.

## 2. Exact SHAs and CI

| Item | SHA | Status |
|---|---|---|
| Tested code (Sprint 5 implementation) | `b885ad740aac7a7dccacbc7b250cd919069c7abd` | CI run `41423137005` on `specialist-ci`: **success**. Jobs `lint-type-unit` and `postgres-tests` both success |
| Governance commits (docs only, on top of tested code) | `74608aa` (scope amendment and closure records), and the commit that adds this record | Pushed to `claude/sprint5-specialist-evaluations`. Remote head verified as `74608aaa0a852d52622307429421a75bccd0491b` |
| CI on pushed head `74608aa` | Run `41599741809`, `specialist-ci` | **In progress at time of writing.** To be recorded when it completes |

No `src`, `tests` or `pyproject.toml` changes exist between `b885ad7` and `74608aa`. The tested code is therefore `b885ad7`.

## 3. Accepted scope

| Area | Accepted result |
|---|---|
| Seven-specialist scope | Requirement-level coverage, 36 synthetic scenarios (v8). Routing and refusal behaviour only. Not vendor accuracy. Not verified feasibility |
| Thresholds (amendment v1) | Refusals missed 0, authorization overreach 0, unsupported claimed as supported 0, INVESTIGATE match 1.00 (2 scenarios), version-unknown WITH_UNKNOWNS 1.00 (4), CLARIFY match 1.00 (9), repeatability identical over 3 runs. All MET |
| Documentation evidence | BigCommerce single-product exact page `get-product`. One cited passage supports one stated claim |
| S5-005, S5-007, S5-011 | Preserved. S5-011 not reopened |
| Remediation | None reported as necessary |

## 4. Deferred and superseded obligations

Each item below stays on the roadmap. None is described as completed.

| Obligation | Disposition | Future owner |
|---|---|---|
| Original frozen `P001–P055` Shopify human benchmark (DIRECT precision and recall, rater agreement) | Superseded for Sprint 5. Retained as a deferred obligation | WDS Authorized Approver to commission. AS to label the original pairs when commissioned |
| Real-citation correctness on real retrieval | Removed from Sprint 5 acceptance. Reported NOT MEASURED. Retained as deferred | WDS to name an evaluation owner |
| Feasibility reasoning, practical suitability | Not demonstrated. Deferred | WDS to name an owner |
| Evidence relevance and documentation investigations for six specialists beyond BigCommerce | Deferred | WDS to name an owner |
| Capability-accuracy evidence (2 scenarios only) | Weak evidence, recorded as a limitation | Evaluation owner, when the set is extended |

## 5. PG management exception (preserved as approved)

**Operative wording, as approved on 3 November 2026 (directive G7):**

> PG QA — PASS REPORTED BY WDS MANAGEMENT; PERSONAL PG ATTESTATION WAIVED FOR SPRINT 5.

Scope: Sprint 5 only. Not applicable to Sprint 6 D-13 or to security-review gates. No PG signature, review timestamp, reviewed SHA, independence statement or independently authored report is claimed.

**Earlier wording, from the first closure directive of 3 November 2026.** It is preserved in `SPRINT5_PG_QA_MANAGEMENT_EXCEPTION_2026-11-03.md` and is not edited:

> PG QA — PASS REPORTED TO WDS; MANAGEMENT ACCEPTED WITHOUT PERSONAL PG ATTESTATION.

The directive G7 wording governs the revised acceptance. Both are on record, and neither has been altered.

## 6. Replacement Shopify Word document

The directive refers to `Shopify_55_Pairs_AS_Approval_Review_DRAFT(1).docx`. It was not found in Downloads. The only related file is `Shopify_55_Pairs_AS_Approval_Review_DRAFT.docx`, which has no judgments and uses `S5-SH-DRAFT` IDs.

Per directive item 6, this is **not** a mandatory Sprint 5 acceptance gate. Its approval is not executed, and no human-reviewed result is claimed. It may be approved later as a synthetic candidate if WDS identifies the file.

## 7. Sprint 5 acceptance matrix (revised baseline)

| # | Gate (revised) | Status |
|---|---|---|
| G1 | Seven-specialist requirement-level scope | MET under revised scope |
| G2 | Final CI on exact tested SHA | MET for `b885ad7` (run `41423137005`). Pushed head `74608aa` pending run `41599741809` |
| G3 | Amended approved thresholds | MET for the six measurable rows. Real-citation and Shopify rows superseded or not measured, not passed |
| G4 | Shopify human evaluation | SUPERSEDED for Sprint 5 (not completed) |
| G5 | Minimum real-evidence coverage (BigCommerce pilot) | MET as amended |
| G6 | S5-005, S5-007, S5-011 | MET |
| G7 | PG QA exception (management) | RECORDED as approved. Sprint 5 only |
| G8 | Remediation | No remediation reported as necessary |
| G9 | Closure | FORMALLY ACCEPTED under revised MVP scope |

## 8. Records

- Scope amendment and closure (base): `SPRINT5_SCOPE_AMENDMENT_AND_CLOSURE_2026-11-03.md` (commit `74608aa`).
- PG exception, earlier wording: `SPRINT5_PG_QA_MANAGEMENT_EXCEPTION_2026-11-03.md` (commit `74608aa`).
- Closure determination of 2 November 2026 (`NOT YET ACCEPTABLE` against the original gates): unchanged, superseded only for the revised baseline from 3 November 2026.
- Handoff to Sprint 6: `SPRINT5_TO_SPRINT6_HANDOFF_2026-11-03.md`.
