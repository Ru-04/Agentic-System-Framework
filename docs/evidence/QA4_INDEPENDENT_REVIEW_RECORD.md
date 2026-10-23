# Independent QA4 review — record and final dispositions

**Reviewer:** an independent AI QA agent with no implementation history. **This is not a human QA signatory and is not AS's sign-off.**
**Reviewed commit:** `fd83e7e` (S2-D07 to S2-D12 changes). **Review result:** 370 unit tests passing at that commit; 18 adversarial defects in 78 checks; 16 findings (3 High, 4 Medium, 8 Low, 1 design note).
**Status of this record:** dispositions below are engineering evidence, verified by the regression tests named. They are not independent human confirmation.

## Findings and final dispositions

| ID | Severity | Finding (summary) | Disposition | Commit | Regression evidence |
|---|---|---|---|---|---|
| QA4-01 | High | Scoped allowlist accepted dot segments and percent-encoded traversal (`/pricing/../features`, `%2e%2e`) | Fixed: refuse encoding, backslashes and dot segments on scoped hosts | `2e00f10` | `tests/unit/test_allowlist_scopes.py` |
| QA4-02 | Medium | CRA exact entries accepted child paths | Fixed: exact-match entries | `2e00f10` | `test_allowlist_scopes.py` |
| QA4-03 | High | Origin rule accepted traversal paths for vendor records | Fixed: origin rule uses the scoped check | `2e00f10` | `test_origin_rule_refuses_traversal_for_vendor_records` |
| QA4-04 | High | Platform-generic words counted as relevance evidence | Fixed: generic words excluded. **Consequence:** no cited capability findings remain for the 17 requirements; reported, not hidden | `2e00f10` | `tests/unit/test_s2_qa4_regressions.py` |
| QA4-05 | Medium | Relevant passages beyond the candidate limit dropped silently | Mitigated: limit reached is reported. Retriever ordering is by term overlap, so a relevant passage beyond the limit is not assessed. Disclosed | `2e00f10` | `test_candidate_limit_is_reported_not_silent` |
| QA4-06 | Medium | Quarantined records could consume candidate slots | **Fixed:** eligibility and quarantine run inside the retriever before ranking and the limit | `54aef28` | `tests/unit/test_s2_remediation.py` (positive, negative, boundary, failure) |
| QA4-07 | Medium | Evaluation reported at top-5 while the pipeline uses top-20 | Fixed: re-run at top-20 and record regenerated | `2e00f10` | `docs/evaluation/SHOPIFY_REAL_INVESTIGATION_2026-10-22.md` |
| QA4-08 | Low | `-es` plurals not folded | **Fixed for sibilant endings** (`sses`, `shes`, `ches`, `xes`, five letters or more). Recorded limits: `caches`/`cache`, `APIs`/`api` | `54aef28` | `test_s2_remediation.py` (appropriate plurals, false-match controls, one-word-one-form regression) |
| QA4-09 | Low | `https` folded to `http` | Fixed | `2e00f10` | `test_https_does_not_fold_to_http` |
| QA4-10 | Low | Hyphen joining creates cross-word matches | Accepted by design | — | — |
| QA4-11 | Low | Relevance docstring said PARTIAL = two terms | Fixed | `2e00f10` | — |
| QA4-12 | Low | Allowlist docstring wording on case | Accepted; not a bypass | — | — |
| QA4-13 | Low | Allowlist comment claimed HTTP 200 for plan pages | Fixed: comment corrected | `2e00f10` | — |
| QA4-14 | Low | Evidence package figures stale | Fixed by explicit supersession notes | `2e00f10` | `docs/evidence/SPRINT2_EVIDENCE_PACKAGE.md` |
| QA4-15 | Low (structural) | Workspace filter applied after the retriever limit | **Fixed:** workspace scope enforced in the retriever before any scoring; a retriever contract check now guards any future retriever | `54aef28`, `52eb202` | `test_s2_remediation.py`; `tests/support/retriever_contract.py`; `tests/unit/test_retriever_contract.py` |
| QA4-16 | Note (design) | Requirements with fewer than three specific terms could never grade PARTIAL or DIRECT | Handled: a clarification request is raised (S2-R2) | `67c9e33` | `test_s2_preserved_decisions.py` |

## Defect found during remediation (not in the QA4 list)

A first plural version gave one query word two term forms, so one word could satisfy the two-term retrieval floor. A regression test (`test_one_word_cannot_satisfy_the_two_term_floor`) caught it. Fixed in `54aef28` with one canonical form per word.

## Open items after QA4

1. Plural limits: `caches`/`cache` and `APIs`/`api` do not match (recorded, tested as limits).
2. QA-07 (authority declared, not enforced at run time) remains deferred to M3 S6 by decision.
3. No production retriever exists. Any future retriever must pass `check_retriever_contract` before production use.
4. This record does not replace an independent human QA review.
