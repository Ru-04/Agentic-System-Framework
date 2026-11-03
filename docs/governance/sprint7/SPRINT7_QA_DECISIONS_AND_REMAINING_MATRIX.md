# Sprint 7: QA history, provisional decision register and remaining requirement matrix

Branch: `feature/sprint7-human-review-estimation`. Scope is the GREEN and AMBER subset (S7-03, S7-05,
S7-06, S7-08, S7-09). Engineering candidate status only. This document is not WDS final acceptance,
and it does not waive independent QA or any Sprint 6 gate.

## 1. QA history

| Step | SHA | Result |
|---|---|---|
| Implementation | `0639240` | Engineering candidate, submitted for independent QA |
| Independent QA 1 (separate clone, reviewer did not author the commit) | `0639240` | **FAIL**: 3 major, 8 minor findings (D1 to D11). Checks, lint and types passed. 127 Sprint 7 tests passed. |
| Remediation | `c2c3651` | D1 to D11 addressed with regression tests in `tests/unit/test_sprint7_regressions.py` |
| Independent QA 2 (fresh reviewer) | `c2c3651` | **FAIL**: N1 (major, D1 still open), N2 (major), N3 to N6 (minor), D5, D7, D9, D10 partially closed. Checks, lint, types and 168 Sprint 7 tests passed. |
| Remediation round 2 | `61aa95c` | N1 to N6, D5, D7, D9, D10 addressed in `tests/unit/test_sprint7_regressions_round2.py` |
| Independent QA 3 (fresh reviewer) | `61aa95c` | See section 1.2 |

### 1.1 Finding closure for 0639240

| ID | Severity | Requirement | Finding | Closure in c2c3651 |
|---|---|---|---|---|
| D1 | major | S7-03 | `dataclasses.replace()` could relabel an acknowledged inference as client-stated | Acknowledgement is bound to its requirement and allowed only on a confirmed inferred requirement; replace() that breaks the binding raises |
| D2 | major | S7-03, S7-08 | Raw-string `source_type` bypassed `is` comparisons and was dropped from the SOW | Enum fields coerced in `__post_init__`; comparisons use `==`; raw-string requirement appears in the SOW |
| D3 | major | S7-06 | Raw-string line status made an uncertain line disappear and the set publishable | Line status coerced; comparisons use `==`; incomplete sets never publish |
| D4 | minor | S7-03 | Any object accepted as acknowledgement | `isinstance` check at construction and in `acknowledge_inference` |
| D5 | minor | S7-03 | Naive, text or far-future timestamps accepted; reviewer not normalised | Timezone-aware datetime required; future relative to caller `now` plus 5 minutes refused; reviewer and reason stripped |
| D6 | minor | S7-03 | Acknowledgement time and reason not rendered | Rendered in the SOW requirement row |
| D7 | minor | S7-06 | Default 28-digit context made sums order-dependent | Values bounded (1,000,000 per line; 30 significant digits); sums under explicit 80-digit precision |
| D8 | minor | S7-06 | Float raised AttributeError; negative zero accepted | Float and text refused with ValueError; negative zero stored as zero |
| D9 | minor | S7-08 | Watermark and approval state overridable on a DraftSow | `DraftSow` and `render_html` both require the draft watermark and `draft_unapproved` state |
| D10 | minor | S7-05 | Edition and version free text rendered verbatim | **Not changed.** The text is recorded metadata, HTML-escaped, and never sets the citation status. Whether this needs a change is for QA 2 to judge. |
| D11 | minor | S7-06, S7-08 | Drivers, dependencies and owner not rendered | Rendered in the SOW estimate section |

Design observation from QA 1, now changed: a partial estimate used to show its known-hours sum next
to "total not stated". That sum is no longer shown. Only counts and per-line ranges appear.

### 1.2 QA 2 findings on c2c3651 and their closure in 61aa95c

| ID | Severity | Finding | Closure in 61aa95c |
|---|---|---|---|
| N1 | major | `replace(acknowledgement=None)` relabelled an acknowledged inference as client-stated | Inference seal: a digest over identity, text, source and acknowledgement, checked on every construction. Replacements that drop or alter the acknowledgement fail. |
| N2 | major | `replace()` on a DraftSow could set `estimate_summary`, `citation_views` or `sow_id` to values the source does not produce | DraftSow recomputes all three from its source and refuses any other value |
| N3 | minor | An acknowledgement dated 2999 was accepted through the constructor | Time bound is checked in `acknowledge_inference`, which takes an explicit `now`. The constructor has no clock and does not repeat the check. Documented in the module. Judged adequate for rebuilds of accepted records; QA 3 asked to judge. |
| N4 | minor | An in-scope item resting on an unacknowledged inference was not flagged | Flagged in every section of the SOW |
| N5 | minor | Extreme exponents (1E-999999) made totals order-dependent | Smallest value is 1E-6 hours; larger exponents refused |
| N6 | minor | A generator of lines was consumed; a caller's list could change the set after validation | Lines copied into a tuple first; non-EstimateLine values refused |
| D5 | minor (partial) | Future check only in one path | Same as N3 |
| D7 | minor (partial) | Order dependence with extreme exponents | Same as N5 |
| D9 | minor (partial) | DraftSow derived fields replaceable | Same as N2 |
| D10 | minor (open) | Edition or version text could spoof a second "Verified" flag | Edition and version containing a verification claim are refused |

Residual limit, recorded in the module and in tests: a pure model cannot stop code that builds a
new client-stated requirement from nothing. That control belongs to where requirements are created
from source material, which is S7-02 and S7-10 authority.

### 1.3 Independent QA 3 and the round-3 redesign

| Step | SHA | Result |
|---|---|---|
| Independent QA 3 | `61aa95c` | **FAIL**. N1 open: a `replace(inference_seal=None)` removed the seal check; `replace(text=...)` kept the acknowledgement. N4 partial (flags depend on the requirements supplied). ND-A, ND-B, ND-C reproduced. D10 open for free text (homoglyphs, zero-width, spacing). D5 and D7 partial. |
| Round-3 redesign | `f58c4de` | Seal removed. The acknowledgement carries a `binding` over identity, text, source, type, reviewer, time and reason. Only an acknowledged inference can be confirmed (P6). Free-text verification guard is normalised. ND-A to ND-C fixed. |
| Independent QA 4 | `f58c4de` | Not yet run. See the decision in section 5. |

**Residuals that remain after `f58c4de`** (each is stated in code and tests, none is hidden):
- R1: a pure in-memory model cannot stop code that constructs a new object. A confirmed acknowledged inference can be rebuilt as a pending client-stated requirement by `replace()` with the acknowledgement removed. Such an object has no confirmed record and no acknowledgement, but its label is then "Client-stated". Preventing this silent relabel needs an append-only, immutable store (S7-02 and S7-10, not approved).
- R2: the binding is an unkeyed SHA-256. It detects accidental or partial edits. It does not authenticate a reviewer. Anyone who computes the digest can forge an acknowledgement. Authentication belongs to the Foundation identity contract (OPEN-17).
- R3: the acknowledgement time is bounded only in `acknowledge_inference`, which takes an explicit `now`. The constructor has no clock. A stored acceptance time bound belongs to S7-10.
- R4: the SOW flags an unacknowledged inference only when the requirement is supplied in its requirements list. A reference to an absent requirement is not known to be inferred. S7-02 must supply the full list.
- R5: the D10 guard is best effort. It normalises NFKC, zero-width and combining characters, and spacing, but it does not map cross-script look-alikes (for example Cyrillic letters). The status path does not depend on the guard: status values come from a closed vocabulary.
- R6: edition, version and source reference are free text. They are escaped, and they cannot set the status. A verification claim in them is refused where detected (R5 limits detection).

## 2A. Decision P6 (new, this round)

| ID | Decision | Status | Evidence and limits |
|---|---|---|---|
| P6 | Client-stated requirements are never CONFIRMED in this model. Only an acknowledged inference can be confirmed. | Adopted as a model rule, provisional | Confirmation of a client statement is a reviewer act that belongs to the S7-02 decision record. Until that record exists, a client statement stays pending. |

## 2. Provisional decision register

These decisions were authorized by WDS for the non-production prototype. None is a production
contract.

| ID | Decision | Status | Evidence and limits |
|---|---|---|---|
| P1 | HTML-only draft export is acceptable for the current prototype | Authorized, provisional | `render_html` is the only renderer. Preview and export use the same output. No PDF or DOCX. Export infrastructure is out of scope. |
| P2 | Unacknowledged inferred requirements may appear in draft SOWs only when visibly flagged | Authorized, implemented | Each one is labelled `Inferred (not client-stated)` and `pending review`. Regression tests cover raw-string and typed paths. |
| P3 | Unestimated or uncertain work is never treated as zero | Authorized, implemented | Hours are not stored for such lines. A partial total is not stated. The SOW shows "not estimated, hours not stated" or "uncertain, hours not stated". |
| P4 | Estimate schema remains provisional | Authorized, provisional | Labelled as a proposal in `estimates.py`. No approved estimate schema exists in the repository or in the governance record reachable from this checkout. |
| P5 | OPEN-07 and OPEN-08 vocabulary must be reconciled with authoritative requirements before final approval | **Not reconciled** | The authoritative OPEN-07 and OPEN-08 definitions are not in this repository or on `claude/sprint5-specialist-evaluations`. The matrix cites them as entries in the "Sprint 6 contract v1.1 register", which I could not locate. All labels stay marked `[provisional OPEN-07]` or `[provisional OPEN-08]`. A WDS or Sprint 6 owner must supply the register before this decision can close. |

## 3. Remaining Sprint 7 requirements (S7-01, S7-02, S7-04, S7-07, S7-10, S7-11, S7-12)

These are not implemented. Each row states what the normative requirement needs, what the repository
already provides, and what is blocked. Nothing here invents an identity, authorization or audit
contract.

**Repository facts used below**, verified in this checkout (`5974d59` base plus Sprint 7 modules):
- No workspace entity exists. A search of `src/webdesk` and the migrations for "workspace" returns nothing.
- Project membership and access grants exist (`projects/service.py`, migration 0001).
- Administrator role assignment with trigger-enforced rules exists (`rbac/assign.py`).
- An append-only `audit_events` table and `record_event` with server-side redaction exist (`audit/service.py`). The S7-10 contract has not been approved.
- Run staleness with downstream marking and a `require_fresh` gate exists (`runs/staleness.py`), and input revision hashing exists (`runs/hashing.py`).
- Specialist contract code exists only on `claude/sprint5-specialist-evaluations` (`src/webdesk/specialists/`), not in this checkout.

| ID | Normative requirement (summary) | Dependencies | Technically available now | Genuinely blocked | Safe non-production work now | Integration contract required | Minimum next action |
|---|---|---|---|---|---|---|---|
| S7-01 | Review queue and case status. Operator lists and opens runs and requirements in their permitted workspace or project. Status transitions: queued, in-review, needs-clarification, approved-for-draft, rejected. | OPEN-11 (workspace), Sprint 6 read path, Foundation authz | Project membership and grants; `workflow_runs` table; staleness gate | No workspace entity, so cross-workspace denial cannot be enforced for real. Scoping by project is a substitution that needs a WDS decision. | A pure transition model for the five statuses with fixture-only scoping, labelled non-production | Approved workspace-membership read contract (OPEN-11) and the Sprint 6 run read API | WDS decision: workspace scoping, or project scoping as an interim. Then build the transition model. |
| S7-02 | Human review of each requirement and finding: accept, amend, reject, or request clarification, with rationale. Reviewer, timestamp, previous and new version are durable. Stale versions and concurrent edits fail safely. | OPEN-11 for authz; S7-10 for durable audit (RED); Foundation authz | Pure decision model is possible; `runs/hashing.py` provides revision-hash style identity | Durable record and audit need S7-10. Authority to approve needs the identity contract. | Pure decision model with versioned compare-and-set on fixtures, no persistence, no approval authority | Approved decision-record schema and audit event vocabulary (OPEN-17, OPEN-25) | Build the in-memory decision model only after WDS confirms the decision-record fields. |
| S7-04 | Clarification workflow: questions with owners, status and resolution linked to affected findings. No invented client answers. Resolution is permission-checked. | OPEN-11 and membership for the permission check; S6 findings | Nothing specific beyond the review model | Resolution permission check (RED with WS) | Clarification model with status transitions and link validation on fixtures. Must never fill in a client answer. | Membership check contract (OPEN-11) and the finding identifier contract from Sprint 6 | Build the model; leave the permission check as an explicit, failing-closed interface. |
| S7-07 | Authorized operator updates or approves draft estimate line items, preserving history. Authorization, reason, version conflicts, total recalculation, rejected and partial estimates tested. | S7-10 (RED); Foundation authz; S7-06 | `EstimateSet` is a draft with a version field; totals are deterministic (S7-06) | Approval and history need authorization and audit. An approval transition must not exist until the authority contract is approved. | None that adds an approval transition. A revision-history model without approval authority is possible after S7-10 is specified. | Approved authorization contract and the audit contract (S7-10, OPEN-17, OPEN-25) | Do not implement an approval transition now. Specify the approval authority with WDS first. |
| S7-10 | Audit and traceability: review decisions, change history, estimate revisions, report snapshots and actor authorization, via Foundation-owned audit, ordered and append-only. | Foundation audit contract (not approved), OPEN-17 (writer identity), OPEN-25 (audit events) | `audit_events` append-only table and `record_event` with redaction exist in Foundation | Event vocabulary for S7 and writer identity are unapproved. Building new event types would invent a contract. | Read-only tests that the existing `record_event` redacts S7 payload shapes, if WDS names them | Approved Foundation audit contract with S7 event types (OPEN-17, OPEN-25) | WDS decision on the S7 event vocabulary and writer identity. No new event types before then. |
| S7-11 | Run and report lifecycle: partial specialist results, missing evidence, canceled or failed runs, revisions and regeneration. A report cannot hide incomplete evidence or claim full verification. A stale report is detected. A failed regeneration keeps prior approved records. | S6-INT run lifecycle (not complete); Foundation staleness | Staleness marking and `require_fresh` gate in `runs/staleness.py`; revision hashing in `runs/hashing.py` | Full lifecycle needs the S6-INT run lifecycle | A pure stale-detection function: given a report's recorded input tuple and the current tuple, report stale or fresh, using the existing hashing. Fixture-only. | Sprint 6 run-lifecycle contract (S6-INT) | Build the stale-detection function on the existing hash. Full lifecycle waits for S6-INT. |
| S7-12 | All seven specialist categories (Shopify, Shift4Shop, WordPress/WooCommerce, BigCommerce, Magento, Standalone, Middleware) consumed through shared contracts, without special-casing Shopify. | S6-INT; OPEN-12, OPEN-22; specialist contract | Specialist contract code exists only on the sprint5 branch, not in this checkout | Integrated seven-specialist behavior needs S6-INT and OPEN-12, OPEN-22 | Fixture conformance tests written against the shared contract once it is merged into this branch, labelled non-production | Shared specialist contract (`ai-read/v1`, adapter 0.2) merged to this branch, plus OPEN-12 and OPEN-22 | Wait for the S6-INT specialist contract. Do not add specialist code here. |

**Safe independent work now (no invented contract):** the S7-01 transition model, the S7-04 clarification
model, and the S7-11 stale-detection function. Each is pure, fixture-tested, and labelled as
non-production. Everything else waits on a named WDS or Sprint 6 decision.

## 4. Foundation and Sprint 6 integration prerequisites

1. WDS decision on workspace identity (OPEN-11), or on project scoping as an interim, which is not yet approved.
2. Approved Foundation audit contract with S7 event types and writer identity (OPEN-17, OPEN-25).
3. OPEN-07 and OPEN-08 vocabulary register (P5).
4. Sprint 6 run-lifecycle contract (S6-INT) and the seven-specialist contract (OPEN-12, OPEN-22).
5. Approved estimate schema, to replace the provisional one (P4).
6. Export format decision beyond HTML, if the prototype is to become production (P1).

## 5. Candidate readiness

- Engineering candidate status: the implemented subset is at `f58c4de` (round-3 redesign). QA 3 failed `61aa95c`, and the residuals R1 to R6 above are open for WDS decision. QA 4 has not run.
- Not ready for WDS acceptance. Independent QA has not passed a full Sprint 7 scope, and S7-01, S7-02, S7-04, S7-07, S7-10, S7-11 and S7-12 are not implemented.
- Nothing has been pushed, merged or deployed.
