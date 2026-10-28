# Sentence-level matching rule: audit (28 October 2026)

**Rule in force.** A capability is supported by a page only if one sentence of that page contains every required term, using whole-word matching on the term or its listed inflections (`WORD_FORMS` in `src/webdesk/investigation/engine.py`). Terms in different sentences do not match. The requirement matcher (`matched_capabilities`) uses the same whole-word function.

**Conservative threshold kept.** No looser rule is proposed. The version check and the single-passage check both remain required for a citation.

## Defects found and fixed in this audit
| Case | Before | After |
|---|---|---|
| "Pricing is set per variation." for the term "price" | Not matched (false negative: plain substring) | Matched through the inflection table |
| "A prickly price list ..." style text | Could match on the stem "pric" (earlier design) | Not matched: whole-word only |
| Terms split across two sentences | Matched across the page (false positive) | Not matched |

## Deterministic regression cases
These run in `tests/unit/test_capability_overstatement.py` and fail if the rule changes.

| Term | Text | Expected |
|---|---|---|
| price | Each variation has its own price. | match |
| price | Pricing is set per variation. | match |
| price | Prices are shown in the cart. | match |
| price | A prickly cactus has spines. | no match |
| price | This is priceless advice. | no match |
| variation | Variations are listed by parent. | match |
| product | Get Product on the catalog. | match |
| product | The productivity report. | no match |
| store api | The Store API lists products. | match |
| store api | The store and the api differ. | no match |

## Known limits of the rule
- Synonyms are not matched. A page that says "cost" instead of "price" is not a match. This is a deliberate false negative, to avoid unsupported claims.
- Inflections are a fixed list. A new form needs a reviewed entry in `WORD_FORMS`.
- Sentence splitting is simple punctuation and line breaks. Unusual punctuation can merge or split sentences.
