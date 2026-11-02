# Shopify 55-pair labelling: handoff (2 November 2026)

**Status: READY FOR ASSIGNMENT. 0 of 55 labelled. No rater has been appointed.** This document prepares the handoff. It does not name a rater, and no label has been created or inferred.

## 1. What WDS must do before labelling can start

1. **Name the rater.** The protocol lists `AS` as the proposed reviewer. That is a proposal. WDS must confirm the person, their role and their independence from the system's build. Engineering and Claude must not fill the labels.
2. **Name an adjudicator** for disagreements, if two raters are used.
3. **Arrange the passage channel.** Passage text is not in this repository, by design. It is held in the review package and must reach the rater through a channel WDS approves.
4. **Approve the agreement threshold** (see `SPRINT5_THRESHOLD_PROPOSAL_2026-11-02.md`, section 2).

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

## 4. Adjudication rule (proposed, needs WDS approval)

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
