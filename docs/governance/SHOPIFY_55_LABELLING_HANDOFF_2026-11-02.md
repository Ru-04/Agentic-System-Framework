# Shopify 55-pair labelling: handoff (2 November 2026)

**Status: APPOINTED, LABELS NOT RECEIVED. 0 of 55 labelled.** WDS appointed AS as the human relevance evaluator for the 55 pairs (WDS formal decision, Sprint 5, section 1). AS has not yet supplied judgments. Nothing in this repository is a label, and no label may be entered or inferred on AS's behalf.

## 1. Roles and what is still missing

| Role | Status | Basis |
|---|---|---|
| Human relevance evaluator | **Appointed: AS.** Judgments not received | WDS decision, section 1 |
| Second independent rater (agreement) | **Not appointed.** Required only if the agreement measurement is approved | The protocol specifies one reviewer. Agreement needs a second rater, which WDS has not approved |
| Adjudicator for disagreements | **Not appointed** | Depends on the second rater |
| Passage channel | **Blocker.** The passage text is not in the repository and no review package containing it is available here | Protocol section 1 |
| Agreement threshold | **Pending WDS** | Threshold proposal, section 2 |

Do not assume AS alone satisfies a multi-rater requirement. The directive asks for those roles to be identified separately, and they are identified here as not yet approved or appointed.

## 1a. Package for AS

What AS needs and what is in place:

- Label definitions and rules: `docs/evaluation/HUMAN_REVIEW_PROTOCOL.md`, sections 2 and 3 (in place).
- Blinded sheet: `docs/evaluation/HUMAN_REVIEW_SHEET_SPRINT2.md` (in place; no labels; no grades shown).
- Passage text for each pair: **not in place**. Held in the external review package, to be released through a channel WDS approves.
- Return format: the labels file accepted by `import_labels` (protocol section 3 fields). Blank rows stay unlabelled.

## 2. Frozen inputs

| Input | Path | SHA-256 |
|---|---|---|
| Review sheet (55 pairs, no labels) | `docs/evaluation/HUMAN_REVIEW_SHEET_SPRINT2.md` | `13ad2af9290e6c30239adaa4706510cd272bdb70a523dc65247c7688e3b5f9ae` |
| Review protocol (label definitions) | `docs/evaluation/HUMAN_REVIEW_PROTOCOL.md` | `71bd8f4eb03f5b157d91adb50b16b36bb9eb5fc956f818d728be4d10b2039cf5` |

Scoring is not computed from the sheet's own content. It is computed from the labels file imported under the protocol.

## 3. Rater instructions (neutral)

Use `HUMAN_REVIEW_PROTOCOL.md`, sections 2 and 3, unchanged:

- DIRECT: the passage answers the requirement or shows whether the platform can do what it asks.
- PARTIAL: the passage addresses part of the requirement or a closely related capability.
- IRRELEVANT: the passage is not about the requirement's subject.
- Judge only the passage text. Do not assume platform facts it does not state. If unclear, choose the weaker label and mark it uncertain.
- The rater must not see the system's grade, any agent label, or the rule that produced the pair. The sheet already omits them.

## 4. Adjudication rule (proposed; needs WDS approval, and a second rater first)

- Two independent raters label every pair. Neither sees the other's labels.
- Agreement is computed on pairs both raters labelled.
- A disagreement is resolved by the named adjudicator, who records the reason in the comment field.
- A blank row stays unlabelled. It is excluded from every metric and never filled by inference.

## 5. Import and scoring (existing tooling)

The repository already has the import and metric code:

- `webdesk.evidence.evaluation.import_labels` refuses duplicates, unknown pair IDs, invalid labels and malformed headers. It does not import partially.
- `webdesk.evidence.evaluation.evaluate` computes precision and recall for DIRECT, and the 3 by 3 confusion matrix against the system grade.
- The CLI takes the pair file from the review package and the labels file:

```bash
.venv/Scripts/python.exe -m webdesk.evidence.evaluation_cli --pairs <review-package-pairs-file> --labels <labels-file>
```

The pairs file is outside this repository, so the command cannot be run here.

## 6. Leakage check

- None of the 55 pair IDs or requirement IDs (`SH-CASE-…`) appear in the Sprint 5 scenario dataset v4. Checked on 2 November 2026: 0 occurrences.
- Scenario development did not use the review sheet.

## 7. Reporting rule

Until genuine labels exist, the scorecard reports `labelled: 0, total: 55` and every Shopify relevance metric is THRESHOLD PENDING. No relevance result may be quoted from this repository.
