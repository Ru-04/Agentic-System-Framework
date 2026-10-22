# Sprint 2 — response to independent QA4 (commit fd83e7e)

**Status:** dispositions recorded. **Not a sign-off.** AS's review is still pending.
**Fix commit:** to be recorded when committed. **Unit tests after fixes:** 389 passed; ruff, format and strict mypy clean.

## Dispositions

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| QA4-01 | High | Scoped allowlist accepted `..`, `%2e%2e`, `..%2f` and similar, so a permitted path could reach pages outside its scope | **Fixed.** Scoped hosts refuse percent-encoding, backslashes and dot segments. Regression tests in `test_allowlist_scopes.py`. |
| QA4-02 | Medium | CRA exact entries accepted any child path | **Fixed.** CRA entries are exact-match (`exact=True`). Children refused. |
| QA4-03 | High | Origin rule accepted a traversal path for vendor records | **Fixed.** The origin rule uses the same scoped check. Test added. |
| QA4-04 | High | Platform-generic words ("shopify", "store", "product") counted as evidence and granted DIRECT and option coverage | **Fixed.** Generic words excluded from relevance terms. Tests added. **Consequence:** under the corrected rule the Shopify specialist now produces **no cited capability findings** for any of the 17 requirements. This is the honest result, not a defect. |
| QA4-05 | Medium | Relevant passages beyond the candidate limit were dropped silently | **Partly fixed.** The output now reports when the candidate set reaches its limit. The retriever still ranks by term overlap, so a relevant passage beyond the limit is not assessed. The unknown says so. |
| QA4-06 | Medium | Quarantine interacted with ranking; a flagged source could fill candidate slots | **Open (design).** Quarantine runs after the retriever's cut. Reported through the candidate-limit notice. A retriever contract change (quarantine before limit) is needed. |
| QA4-07 | Medium | Evaluation figures were produced at top-5 while the pipeline uses top-20 | **Fixed.** Evaluation re-run at top-20. Record regenerated. |
| QA4-08 | Low | "-es" plurals not folded ("processes" vs "process") | **Open (known limit).** Recall is lower for these forms. Not fixed here. |
| QA4-09 | Low | "https" folded to "http" | **Fixed.** Words ending in "ss", "us", "is", "ps" are not folded. Test added. |
| QA4-10 | Low | Hyphen joining creates cross-word matches | **Accepted by design.** Noted. |
| QA4-11 | Low | Relevance docstring said PARTIAL = two terms | **Fixed.** Docstring now matches the code (three). |
| QA4-12 | Low | Allowlist docstring said "lowercase" but the host is lower-cased before comparison | **Accepted.** Not a bypass; the docstring is accurate for the comparison. |
| QA4-13 | Low | Allowlist comment said `/pricing` and `/plus` returned HTTP 200 | **Fixed.** Comment rewritten. It records that the plan pages returned HTTP 403 to the fetch client. |
| QA4-14 | Low | Evidence package figures were stale | **Fixed by supersession.** The earlier figures are marked superseded in the evidence package; this response carries the current figures. |
| QA4-15 | Low (structural) | Workspace filter runs after the retriever limit | **Open (contract).** The retriever interface must filter by workspace before applying its limit. Documented here; the in-memory retriever already does. |
| QA4-16 | Note | A requirement with fewer than three content terms can never reach PARTIAL or DIRECT | **Flagged for the decision-maker.** Matches the rule as written. Some short requirements (for example "Keep checkout behaviour unchanged") may need a different treatment. |

## Current figures (commit after the fixes, top-20 pipeline)

- Requirements evaluated: 17 (all retained).
- Passage grades across the run: **0 DIRECT, 5 PARTIAL, 107 IRRELEVANT.**
- Requirements with a cited finding: **0.**
- Citation failures: 0 (on the findings that exist, none).
- Agreement with the 55 agent labels (AI agent, not human): 44 of 55 at a three-term floor, with generic words excluded. Tuned on those labels, so not validated.

## What this means for Sprint 2

- The lexical relevance method has reached its limit for these requirements. It cannot establish platform capability evidence, and under the corrected rules it establishes none for the 17 requirements.
- Remaining routes, each needing a separate decision: (a) human review of the candidate passages; (b) a semantic validator, which needs D09 approval for a provider, model ID, credentials and budget; (c) additional approved sources for the uncovered requirements (see the allowlist expansion record); (d) access to the Shopify plan pages, which return HTTP 403 to the fetch client.
- Sprint 2 acceptance is **not** met. Shopify capability investigation is not demonstrated for the 17 requirements.
