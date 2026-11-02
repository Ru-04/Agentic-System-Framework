# Shopify 55-pair submission: verification (2 November 2026)

**Result: the submitted file contains no human judgments. Not accepted as the labelling output.**

## 1. File inspected

- File: `Shopify_55_Pair.docx` (Downloads folder), 144,390 bytes.
- SHA-256: `f7bea8947e46e2a730da68bcf6cdc4e9c904a88a7a14352ea71432d77de0885f`.
- Title: "Shopify Specialist — 55-Pair Human Relevance Review", "Draft v0.1, 02 November 2026".
- Content: 55 blocks, each with a pair ID `S5-SH-DRAFT-001` to `S5-SH-DRAFT-055`, a requirement, and a "candidate passage". Grouped by topic (Webhooks, Orders, Products, Inventory, Checkout, Customers, and others).

## 2. Checks

| Check | Result |
|---|---|
| Judgment fields (`DIRECT`, `PARTIAL`, `IRRELEVANT`, label, reviewer, initials, confidence, uncertain) | **0 occurrences.** No judgment anywhere in the file |
| Pair IDs against the frozen dataset (`P001`–`P055`, `SH-CASE-…`) | **0 of 55** match. The file uses different IDs (`S5-SH-DRAFT-…`) |
| Requirement text against the 55 frozen requirements | **0 of 55** match |
| Passage text against the 55 frozen source passages | **0 of 55** match |
| Reviewer identity, date of review, commit tested | **Not present** |

The file's pairs are a different set of requirement and candidate-passage texts. They are not the Sprint 2 pairs, and they are not labelled.

## 3. Consequence for the metrics

- Valid human judgments: **0 of 55.**
- Precision, recall, confusion matrix, false-positive and false-negative counts, and disagreement analysis: **undefined**. Nothing is computed. Under the protocol, unlabelled rows are excluded and never inferred.
- Shopify relevance threshold: **THRESHOLD PENDING**, unchanged.

## 4. Action required

AS returns the labelling file that corresponds to the frozen review package (`reviewer_labels_TO_FILL.csv`, pair IDs P001–P055), with AS's own judgments, name, role, date and the commit tested. No label is inferred from this submitted draft.

The file was not stored in the repository, because it contains passage-like text outside the approved source set.
