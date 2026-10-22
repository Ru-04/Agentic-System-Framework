# M1 Sprint 2 — Completion Report

**Sprint objective:** Shared Evidence Services and Real Shopify Investigation (frozen baseline, M1 S2).
**Branch:** `claude/webdesk-specialist-baseline-v1-3b21b1`
**Status: PARTIAL — NOT ACCEPTED.** The evidence services and the evidence-bound Shopify specialist are implemented and tested. The "real Shopify investigation" is **not** achieved: no live official Shopify documentation was retrieved, and the comparison and feasibility work is not implemented. Sprint 2 cannot be accepted until those items are done or formally re-scoped by the decision-maker.

## 1. Implementation summary

| Requirement (Sprint 2) | Status | Where |
|---|---|---|
| Common retrieval interface | Done | `src/webdesk/evidence/retrieval.py` (`Retriever` protocol) |
| Approved internal RAG retrieval | **Not done.** Only an in-memory retriever exists for tests. No production internal RAG store is in the repo. | `InMemoryRetriever` (fixtures only) |
| Official vendor-document retrieval with allowlist enforcement | Done, with the allowlist **proposed** (D08 approves the approach, not the list) | `allowlist.py`, `http_vendor.py` |
| Workspace-based access restrictions | Done for retrieval, citations and specialist output | `retrieval.py`, `citations.py`, `shopify.py` |
| Source identity, provenance, timestamps, citations | Done | `sources.py` (SHA-256, origin, retrieved_at, version), `citations.py` |
| Evidence freshness and version handling | Done (freshness window; stale gives unverified; future-dated or naive clock gives unknown) | `sources.py`, `shopify.py` |
| Missing evidence vs retrieval failure | Done (`NO_EVIDENCE` vs `RetrievalError`) | `retrieval.py`, `shopify.py` |
| Citation verification and unsupported-claim detection | Done | `citations.py` |
| Error handling, retries, safe failure | Done (bounded retries, retryable only for transient faults, failure gives `failed` output with no internal text) | `retrieval.py`, `http_vendor.py`, `shopify.py` |
| Prompt-injection defences, untrusted-source isolation | Done as a heuristic (normalized screening, whole-source quarantine). Known limits in section 5. | `untrusted.py` |
| Shopify: requirement interpretation, native features, API capability, plan/version limits, themes/apps/extensions | **Partial.** Topic detection over a fixed keyword table for 7 capability areas, and plan/version wording becomes an unknown. No interpretation of requirement text. | `specialists/platforms/shopify.py` |
| Shopify: native vs third-party vs custom comparison, technical feasibility, risks, assumptions, clarification questions | **Not done.** Reported as an explicit unknown in every output. | — |
| Evidence-backed structured findings; explicit unknown and unsupported handling | Done | `shopify.py` |
| Compatibility with the shared contract | Done. Harness unchanged. | `specialists/harness.py` (untouched) |

## 2. Files created or modified (Sprint 2)

Created:
- `src/webdesk/evidence/__init__.py`, `sources.py`, `retrieval.py`, `allowlist.py`, `untrusted.py`, `citations.py`, `http_vendor.py`
- `src/webdesk/specialists/platforms/__init__.py`, `shopify.py`
- `tests/unit/test_evidence_services.py` (56 tests, initial)
- `tests/unit/test_shopify_specialist.py`
- `tests/unit/test_evidence_qa_regressions.py` (29 tests, QA2 regressions)
- `docs/governance/DECISION_RECORD_2026-10-22.md`, `docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md`, `docs/governance/SPECIALIST_LANE_INTERFACES.md`
- `docs/M1_S2_COMPLETION_REPORT.md` (this file)

Modified: `.github/workflows/specialist-ci.yml` (committed earlier; not changed in Sprint 2).

Shared contract, harness, authority, workspace, errors, catalog and mock: **not modified** (verified by the independent QA boundary check, and by `git diff` on those paths).

## 3. Tests — actual executed results

| Command | Result |
|---|---|
| `uv run ruff check src tests migrations` | All checks passed |
| `uv run ruff format --check src tests` | 129 files already formatted (before the final edit) |
| `uv run mypy` (strict, `src/webdesk`) | Success: no issues in 71 files |
| `uv run pytest tests/unit -q -p no:warnings` | **322 passed** (237 Sprint 1 + 56 Sprint 2 + 29 QA2 regressions) |

Integration suites (`tests/integration`, `tests/committed`, `tests/hardening`) were **not re-run** for Sprint 2. Sprint 2 does not touch the database. The last recorded run on the Sprint 1 head `5122012` is listed in section 6.

Not executed in Sprint 2:
- Live Shopify retrieval (no approved allowlist; no fetch approval; no network test).
- Shopify evaluation against approved realistic cases (none available; D11).
- Retrieval outage tests against a real store (no production retriever exists).

## 4. Independent QA

An independent QA agent (separate context, no implementation history) reviewed the code, ran the suites, and wrote 101 adversarial cases in a scratch file, which it deleted afterwards.

Its findings and the resolution of each:

| ID | Severity | Finding | Resolution |
|---|---|---|---|
| QA2-01 | Medium | Truncated or malformed transport errors escaped as raw exceptions | **Fixed.** Classified: `IncompleteRead` retryable; `HTTPException` and `ValueError` non-retryable. Tests added. |
| QA2-02 | Medium | Non-`RetrievalError` exceptions from the retriever escaped | **Fixed.** Any retrieval fault gives `failed`; exception text is not echoed. |
| QA2-03 | Medium | A foreign-workspace source identifier was named in this workspace's output | **Fixed.** Passages outside the request workspace are dropped before any message is built. |
| QA2-04 | Medium | Tab or other whitespace inside a URL was accepted by `permits()` and reached the opener | **Fixed.** Any control, whitespace or non-ASCII character refuses the URL before parsing. |
| QA2-05 | Medium | Zero-width, homoglyph and line-split injection phrasings were not quarantined | **Fixed as a heuristic.** Normalized screening (format characters removed and spaced, confusables, whitespace collapsed). Whole-source quarantine. Residual risk in section 5. |
| QA2-06 | Medium | HTML not stripped when markup was not near the start | **Fixed.** Markup detected anywhere in the body. |
| QA2-07 | Medium (design) | No approved-source model: any `VENDOR_DOC` record is trusted regardless of origin | **Not fixed. Escalated** (section 5, decision needed). |
| QA2-08 | Low | Findings cap checked per passage, not per finding | **Fixed.** Cap enforced per finding. |
| QA2-09 | Low | Phrasings "disregard the safety policies", "forget your instructions", mid-line "System :" not flagged | **Fixed** (patterns extended). |
| QA2-10 | Low | Duplicate source identifier across workspaces dropped a legitimate finding | **Fixed** by the workspace filter (QA2-03). |
| QA2-11 | Low | `attempts=0` raised at run time; naive clock raised `TypeError` | **Fixed.** Validated at construction. Naive clock gives unknown freshness, so findings are unverified. |
| QA2-12 | Low (cosmetic) | `:0443` port spelling accepted | **Fixed.** Netloc must be the host or `host:443`. |
| QA2-13 | Low (not reproduced) | Environment proxies are honoured by the default opener, so the allowlist is not enforced at the proxy hop | **Not fixed. Escalated** (section 5, decision needed). |

Adversarial result after fixes: all QA2 cases now refuse or flag as expected. The regression file covers each fixed item.

The QA agent's work was reviewed for accuracy against the code. Its findings are reproduced in the regression tests, so the tests fail if a fix is reverted.

## 5. Residual risks and limits (not accepted silently)

1. **Approved-source model (QA2-07).** The specialist trusts any record marked `VENDOR_DOC`. Nothing in the code tests where a record came from, except at fetch time. A future retriever must enforce origin, or this must be added as a shared control. Decision needed.
2. **Proxy hop (QA2-13).** `http_vendor` uses urllib's default proxy handling. Environment proxies can route a permitted request through a host the allowlist did not approve. Decision needed: disable environment proxies, or document an approved proxy.
3. **Prompt-injection screening is heuristic.** It uses a small confusables table, and a fixed list of phrasings. Novel phrasings and other scripts are not caught. Quarantine reduces risk; it does not make untrusted text safe. Untrusted text is never executed, and the findings text is fixed by code, not copied from sources.
4. **Keyword topic mapping is not reasoning.** A passage that mentions a topic is cited as addressing it. Relevance and correctness of the statement are not judged.
5. **The output is always incomplete.** That is deliberate: comparison and feasibility are not performed.
6. **Shared contract limit.** Contract 1.0.0 cannot carry a citation quote or hash. Citations are verified inside the specialist, and the output carries only the source identifier and a character span. A contract change would be needed to carry them, and the contract is core-owned.
7. **Allowlist is proposed.** `shopify.dev` and `help.shopify.com` are the proposed Shopify hosts. Live fetches under them are not approved until D08 approves the list.

## 6. Commits and CI

- Sprint 1 head pushed: `5122012`. GitHub Actions run `39796042409` (`specialist-ci`):
  - `postgres-tests`: **success** (integration, committed and hardening suites, provisioned as in the CI job).
  - `lint-type-unit`: in progress at the time of writing. Result to be recorded.
- Sprint 2 changes: see the commit recorded in section 7 (pending).

## 7. Sprint 2 acceptance status

**NOT ACCEPTED. Status: PARTIAL.**

- Met: shared evidence services (except the production internal RAG store), citation verification, workspace isolation, freshness and failure classification, and the QA regression cycle.
- Not met: real Shopify investigation against official documentation; comparison and feasibility; Shopify evaluation on approved real cases; independent human QA sign-off; a Sprint 2 CI run on GitHub.

## 8. Decisions needed to complete Sprint 2

1. Approve the Shopify vendor allowlist (`shopify.dev`, `help.shopify.com`), or name the approved official domains (D08).
2. Decide the approved-source enforcement model (QA2-07): where origin is checked, and whether the fixture origin is allowed outside tests.
3. Decide the proxy policy for vendor fetches (QA2-13).
4. Approve a live retrieval test window, or confirm that the Sprint 2 real-investigation acceptance is deferred.
5. Provide approved realistic Shopify cases from WDS projects (D11), sanitized.
6. Provide the independent human QA signatory for Sprint 2 (D04).

## 9. Update after management answers (22 October 2026)

| Item | Status |
|---|---|
| 1. Shopify allowlist | Working selection: `shopify.dev`, `help.shopify.com`. Formal approval as official vendor domains still to be confirmed. |
| 2. QA2-07 origin enforcement | Proposal P1 written (`docs/governance/PROPOSALS_PENDING_APPROVAL_QA2.md`). **Not implemented**, awaiting approval. |
| 3. QA2-13 proxy policy | Proposal P2 written (same file). **Not implemented**, awaiting approval. |
| 4. Live retrieval window | Approved. One live fetch done: `https://shopify.dev/docs/api/storefront/latest`, success, 32,212 characters. Metadata only in `docs/evidence/SHOPIFY_LIVE_RETRIEVAL_2026-10-22.md`. |
| 5. Real Shopify cases | Four sanitized briefs in `docs/evaluation/SHOPIFY_CASE_BRIEFS_SANITIZED.md`. Client approval for use is not recorded. |
| 6. Human QA signatory | Designated: **AS**. No sign-off recorded. |

Findings from the live step:
- The specialist ran on the live page for three tasks. It produced cited topic findings, all declared incomplete. These are topic mentions, not an investigation, so they are not acceptance evidence.
- `shopify.dev` redirects same-host to `/latest`. The fetch refuses redirects, so the canonical URL is needed. That is a usability limit, not a bypass.
- `help.shopify.com` returned HTTP 403 to a plain client. No bypass was attempted.

Sprint 2 acceptance is still **NOT ACCEPTED**. The real Shopify investigation still needs the approved evaluation runs on the briefs, the open proposals P1 and P2, and the QA signature.

### Update: P1 and P2 implemented (22 October 2026)

- QA2-07 (P1, approved): origin enforced in `SourceRecord`. Vendor records need an allowlisted https origin. Internal records need `internal:`. Fixtures go through `tests/support/evidence_fixtures.py` only.
- QA2-13 (P2, approved): vendor fetches install no proxy handler, so environment proxies are ignored.
- Unit tests: 336 passed. Ruff, format and strict mypy are clean.
- Sprint 2 acceptance is still NOT ACCEPTED. The real investigation runs on the four briefs are still outstanding, and so is the QA signature.

## 10. Update: Shopify functionality and real run (22 October 2026, commit `45df73c`)

**Approval basis:** P1 and P2 approved and implemented (commit `2b0cef2`). The specification package is committed for formal review, not as an approved specification. Continuation under the non-production authorization.

### What the Shopify specialist now does

| Area | Status | Notes |
|---|---|---|
| Option classes (native configuration, app or extension, custom API) | Implemented | Keyword-based, cited, with coverage per class |
| Solution comparison | **Partial** | Coverage per option class for the retrieved evidence only. No client-fit or cost comparison. |
| Feasibility analysis | **Not implemented, by design** | Always reported as `not_determined`, with a clarification question. A keyword rule cannot make this judgement, and a live model call is not authorized (D09). |
| Gaps and clarification questions | Implemented | Each uncovered option class gives a gap line and a CLARIFY question. Every output asks for the plan tier. |
| Relevance | Improved | A match needs two distinct meaningful terms after stopwords are removed |
| Real investigation on the four briefs | **Executed** | 17 requirements, one run each, against 16 live allowlisted `shopify.dev` pages |

### Real run results (from `docs/evaluation/SHOPIFY_REAL_INVESTIGATION_2026-10-22.md`)

- Corpus: 16 of 16 pages retrieved live. Help-centre pages were not reachable (HTTP 403).
- Requirements with at least one cited finding: **7 of 17**.
- Requirements with no cited finding: **10 of 17**. These are gaps. The approved corpus does not cover them: Canadian address and province rules, customer account creation after purchase, guest renewal, campaign tracking, partner stores, staff roles, search and autocomplete, pickup blackout dates, dashboards, and workflow automation.
- Every output is `incomplete`. None reports `completed`.
- Spot-checks showed that some matches are relevant (for example, local pickup through Shopify Functions) and others are tangential. The record makes no relevance claim beyond the matched-term rule.

### Acceptance status

**Still NOT ACCEPTED.** The run is an executed record, not acceptance evidence. Acceptance needs:
1. Independent QA of the new code and the run record. An independent QA agent has been run on commit `45df73c`; its result is recorded in section 11 when received.
2. Additional approved official sources for the ten uncovered requirements, or a decision that those requirements are out of scope for the Shopify acceptance.
3. An approved evaluation method for relevance. The current keyword rule is not a relevance judgement.
4. Human QA sign-off by the designated signatory **AS**. Not given. No sign-off is recorded in this repository.
