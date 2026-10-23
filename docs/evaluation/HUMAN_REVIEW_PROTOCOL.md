# Human relevance review protocol — Sprint 2 (S2-D10, S2-D11)

**Status:** protocol prepared. **No review has been performed.** No label is recorded in this repository. The proposed reviewer is AS, who must confirm the role and sign the completed review personally.

## 1. What is reviewed

Each of the 55 pairs in `HUMAN_REVIEW_SHEET_SPRINT2.md` is one requirement and one passage of Shopify developer documentation. The reviewer does not see the system's grade for the pair, nor any AI-agent label.

Passage text is **not** in this repository. It is held in the review package, which the decision-maker must make available to the reviewer through an approved channel.

## 2. Label definitions

- **DIRECT**: the passage states information that answers the requirement, or establishes whether the platform can do what the requirement asks.
- **PARTIAL**: the passage addresses part of the requirement, or a closely related capability, but does not on its own answer it.
- **IRRELEVANT**: the passage is not about the requirement's subject.

Judge only from the text of the passage. Do not assume platform facts the passage does not state. If the passage is unclear, choose the weaker label and mark it uncertain.

## 3. Fields

| Field | Required | Allowed values |
|---|---|---|
| `pair_id` | yes (given) | as in the sheet |
| `label` | yes, unless the pair is deliberately left unlabelled | DIRECT, PARTIAL, IRRELEVANT |
| `reviewer` | yes if labelled | the reviewer's name |
| `confidence` | recommended | high, medium, low |
| `uncertain` | yes if labelled | yes, no |
| `comment` | optional | free text, one reason |

A row left blank is treated as unlabelled. It is counted and left out of every metric. It is never filled in by inference.

## 4. Process

1. The reviewer reads the reviewer reading file and fills in the labels file.
2. The completed labels file is returned through a channel the decision-maker approves.
3. The labels are imported and checked by `webdesk.evidence.evaluation.import_labels`. The import refuses duplicates, unknown pair IDs, invalid labels and malformed headers. It does not partially import.
4. Metrics are computed by `evaluate` and reported by `python -m webdesk.evidence.evaluation_cli`.

## 5. Metrics reported

- Precision and recall for DIRECT, where DIRECT is the positive class. Either is reported as undefined (not zero) when its denominator is zero.
- The 3 by 3 confusion matrix: human label against system grade.
- False-positive and false-negative counts for DIRECT.
- Disagreement analysis: every pair where the human label and the system grade differ, grouped by the two values.
- Requirement-level direct-evidence coverage: for each requirement, whether a DIRECT passage exists according to the human, and according to the system.
- Uncertain-marked pairs, listed separately.

## 6. Rules for using the results

- Thresholds are not tuned against these labels. Any change to a threshold after the labels are received needs a new, separate held-out label set, or it is reported as tuned.
- A result from fewer than the full 55 pairs is reported as partial, with the unlabelled count.
- The AI-agent labels from earlier are not human labels and are not used in these metrics.
- Human review does not establish platform capability on its own. It measures whether the system's grades agree with a human reader.

## 7. Sign-off

The reviewer signs the completed review personally, stating name, role, date and the commit tested. The sign-off is recorded in the Sprint 2 evidence package, section 13. This protocol does not record any sign-off.
