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

### 1.4 Independent QA 4 and 5, and the round-5 remediation

| Step | SHA | Result |
|---|---|---|
| Independent QA 4 | `f58c4de` | **FAIL**: N-1 major (a bare string used as references was split into characters); N-2 to N-8 minor. |
| Remediation | `784a368` | N-1 to N-8 addressed; regression tests in `tests/unit/test_sprint7_regressions_round4.py` |
| Independent QA 5 | `784a368` | **FAIL**: F1 to F5 major (caller-supplied subclasses and duck types defeated `!=`, `>` and `isinstance`); F6 to F12 minor. |
| Round-5 remediation | this commit | The category is closed by construction: every boundary accepts exact types only (`type(x) is cls`), and every comparison is made on exact types. `EstimateTotal` no longer publishes a range; `publishable_range(estimate)` recomputes from the estimate. `render_total` compares fields by exact type. Identifiers and free text are cleaned by different rules (see textutil). Regression tests: `tests/unit/test_sprint7_regressions_round5.py`. |

**New residual, found in QA 5 and accepted as a text-guard limit (R7):** the verification-claim guard
folds a finite list of same-script Latin look-alikes. A visually similar letter outside that list,
for example U+0192 (f with hook) in a word where it stands for a letter that the fold does not
reconstruct ("Verƒied" reads as "Verified" but folds to "Verfied"), is not caught. This is a display
spoof in free text only. The citation status cannot be upgraded by it, because status values come from
a closed vocabulary.

### 1.5 Independent QA 6 and the round-6 remediation

| Step | SHA | Result |
|---|---|---|
| Independent QA 6 | `9409225` | **FAIL**: D-1 major (a free-text citation status could spoof a verification line); D-2 medium (a non-text status ran caller code before the check, and a hostile repr broke export); D-3 medium (sets and dicts accepted as ordered sections, so the identifier differed between runs); D-4 medium (a public total summed unresolved work as zero); D-5 low (an estimate row did not flag a pending inference); D-6 to D-9 low. |
| Round-6 remediation | `614c992` | D-1 to D-9 addressed. Regression tests: `tests/unit/test_sprint7_regressions_round6.py`. |

**Behaviour changes made in round 6 (for WDS to note):**
- A citation whose source status or confidence is outside the closed vocabularies is now refused at construction. The earlier design displayed such a value as "Status unknown". "verified" is therefore refused, not displayed.
- Sections, requirements, citations and references must be a list or a tuple. Sets, dicts and generators are refused, because their order is not fixed.
- A public total gives no sum for a partial estimate. The counts remain.
- The verification-claim guard refuses only the assertion forms "verified", "verify" and "verifier". Ordinary words such as "verification" and "unverified" are accepted, and an empty edition or version means "not recorded".
- Free text (requirement text, titles, assumptions) is kept as written. NFKC is applied to identifiers only, so "m²" is not changed to "m2".
- The SOW identifier and the acknowledgement binding treat equal values as equal: Decimal values are normalised, and datetimes are compared in UTC.

**Residual R7 is unchanged** (same-script look-alikes outside the fold table). Round 6 also reports that
the free-text guard can be bypassed by a visual look-alike; R7 covers this, and the citation status
cannot be upgraded by it.

### 1.6 Independent QA 7 and 8, and the round-8 remediation

| Step | SHA | Result |
|---|---|---|
| Independent QA 7 | `614c992` | **FAIL**: N-1 major (reopens D-1: "Run. Verified: yes" escaped the guard because a word ending in "un" blocked the match); N-2 to N-4 minor. |
| Remediation | `ffd42d5` | Word-level guard; spelled-letter join; invisible-only edition is not recorded; timestamps out of range are a ValueError; the identifier covers the rendered text. |
| Independent QA 8 | `ffd42d5` | **PASS WITH FINDINGS**: D-A medium (regression: "Notverified", "Reverified", "Veri fied" accepted); D-B minor (ordinary single-letter labels refused); D-C minor (invisible filler recorded as text); D-D minor (decimal_text not exact-typed). |
| Round-8 remediation | this commit | The guard matches claim stems on the joined letters of the whole text and excludes only a match wholly inside the status label "unverified". Single-letter pooling is removed. Filler characters and lone combining marks at the edges are noise. `decimal_text` requires an exact Decimal. Regression tests: `tests/unit/test_sprint7_regressions_round8.py`. |

**Accepted limit, recorded (part of the verification-claim guard, R7 family):** misspellings such as
"verfied" and "vrified" are not claims under the stated rule, and digit look-alikes such as "ver1f1ed"
are not caught. The citation status cannot be upgraded by free text, because status values come from a
closed vocabulary and are refused at construction otherwise.

### 1.7 Independent QA 9, and the round-9 remediation

| Step | SHA | Result |
|---|---|---|
| Independent QA 9 | `6064d64` | **PASS WITH FINDINGS**: D-E minor (the adverb and noun forms "verifiably" and "verifiability" were accepted); D-F minor (ordinary phrases such as "Recover if you lose access" and "Not verified" are refused because letters join across a word boundary); D-G minor (decimal_text on sNaN or infinity raised InvalidOperation or returned "Infinity"). |
| Round-9 remediation | this commit | D-E: the stem list covers verifiab-forms. D-G: a non-finite number is a ValueError. D-F: a documented trade-off, see below. Regression tests: `tests/unit/test_sprint7_regressions_round9.py`. |

**Decision needed from WDS (two items):**
1. **Scope of the verification-claim guard.** It is applied to the four citation fields (identifier, source reference, edition, version). QA 9 notes that requirement text, SOW items and objective are not guarded, so "Verified: yes" is accepted there. Requirement text is inferred or client-stated text shown with its provenance label; it is not a citation status. WDS to confirm that this scope is intended, or to extend the guard.
2. **Trade-off D-F (accepted unless WDS objects).** The guard joins letters across word boundaries so that a claim split by a space or hyphen is caught ("Veri fied: yes"). In exchange, a phrase whose joined letters form a stem is refused ("Recover if you lose access", "Not verified"). The choice is fail-closed: a refused citation field can be corrected; a missed claim would show a false status. A regex cannot distinguish a spaced claim from a phrase, so the trade-off stays.

### 1.8 Independent QA 10, and the round-10 remediation

| Step | SHA | Result |
|---|---|---|
| Independent QA 10 | `a2fabd3` | **PASS WITH FINDINGS**. All 16 checks pass within the accepted residuals and the two WDS decisions (guard scope; D-F). DEF-1 minor: the guard docstring said a match is excluded when it lies inside the status label, but "Un-verified" is refused, as the code does. DEF-2 low: the public `decimal_text` accepted a number of any size. Observation: NUL and vertical tab in free text reached the export unescaped. Observation: `asdict` in the SOW identifier deep-copies the caller's datetime, which runs the caller's tzinfo copy method, not documented. |
| Round-10 remediation | this commit | DEF-1: docstring corrected to the whole-word rule. DEF-2: `decimal_text` refuses values outside a range far wider than the model's bounds. Control characters are refused in identifiers and free text; tab and newlines become spaces. The provenance docstring now documents the tzinfo copy. Regression tests: `tests/unit/test_sprint7_regressions_round10.py`. |

**Design observation, recorded and not changed:** a total such as "total 10-20 hours" in the SOW summary
is not itself flagged when one of its contributing estimate rows rests on an unacknowledged inference.
The rows are flagged; the summary line is a derived figure.

**Design observation, recorded and not changed:** "verifiable" and "unverifiable" are refused by the stem
rule. This is intended: they assert a verification property in an edition, version or source name.

### 1.9 QA 11, publication, and the remaining Sprint 7 scope

| Step | SHA | Result |
|---|---|---|
| Independent QA 11 (focused, six items) | `8bfbbff` | **PASS**, no mandatory defects. Verified: DEF-1 docstring matches the guard; DEF-2 bounds are consistent with the estimate path (decimal_text is a superset); control characters are refused or normalised in every field (4,485 constructions); the provenance docstring matches the datetime deep-copy effect; 352 Sprint 7 tests pass; no change outside src/webdesk/review. The five unit-suite failures (test_api_app.py, psycopg) are environmental. |
| Published | `8bfbbff` | Pushed to `origin/feature/sprint7-human-review-estimation` (new branch). Remote SHA verified: `8bfbbffbd2bab78189acfc418c48d8e741141f63`. |
| CI | `8bfbbff` | **No CI configured.** The repository has no `.github/workflows` in this checkout, and the GitHub check-runs API returns zero runs for this commit. No CI status is claimed. Verification is local (ruff, mypy --strict, pytest) plus independent QA. |

**Accepted residuals recorded at the freeze (unchanged):** R1 to R7; D-F trade-off; the claim guard
covers the four citation fields only; "verifiable" and "unverifiable" are refused by design.

#### Requirement-by-requirement status (not accepted; independent QA of increment 2 is still needed)

| ID | Status | What is implemented (model, fixtures only) | Blocked by, with the evidence needed |
|---|---|---|---|
| S7-01 | Partially implemented | `review/queue.py`: five case statuses and the allowed transitions; version advances. | Scoped access and cross-workspace denial need workspace identity (OPEN-11) and the S6 read path. Evidence to unblock: an approved workspace entity and membership read contract. |
| S7-02 | Partially implemented | `review/decisions.py`: accept, amend, reject, request clarification; reviewer, time, reason, previous and new version; stale and concurrent decisions refused without change. | Authorization (unauthorized actors cannot approve) needs OPEN-11 and OPEN-17. Durable history needs S7-10. |
| S7-04 | Partially implemented | `review/clarifications.py` and an open-clarifications section in the SOW: owner, linked findings, no answer without a source, resolution only with an explicit authority. | The resolution permission check needs a real authority (OPEN-11 and the authorization contract). With no authority supplied, nothing can resolve. |
| S7-07 | Not implemented (blocked) | None. No approval or revision transition was added, because it would be an unauthorized mutation path. | Authorization (OPEN-11, OPEN-17) and durable audit (S7-10, OPEN-25). Evidence to unblock: approved authorization and audit contracts. |
| S7-10 | Not implemented (blocked) | None. No new audit event types were invented. The Foundation has an append-only audit table and `record_event` with redaction (src/webdesk/audit/service.py). | The S7 event vocabulary and writer identity are not approved (OPEN-17, OPEN-25). Evidence to unblock: an approved event vocabulary and writer identity. |
| S7-11 | Partially implemented | `review/report_state.py`: staleness using the Foundation's `input_revision_hash`; incomplete, partial, canceled and failed runs are never complete; a failed regeneration keeps prior records. | The live lifecycle (partial specialist results, cancel and fail transitions) needs the Sprint 6 run service (S6-INT). |
| S7-12 | Not implemented (blocked) | None. The shared specialist contract exists only on the sprint5 branch, not in this checkout. | S6-INT, OPEN-12 and OPEN-22. Evidence to unblock: the merged Sprint 6 specialist contract and the two register items. |

Sprint 7 is not accepted. No requirement is completed or accepted on the strength of QA 11.

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
| P5 | OPEN-07 and OPEN-08 vocabulary must be reconciled with authoritative requirements before final approval | **Reconciled (round 11).** The Sprint 6 OPEN register (`docs/governance/SPRINT6_OPEN_DECISION_REGISTER_2026-11-03.md`, commit `dc590ee` on `claude/distracted-booth-4343a8`, supplied by the contract session) records OPEN-07 as the AI-to-adapter evidence status mapping (contract section 10.4) and OPEN-08 as `check_outcome` with exactly SUPPORTED, UNSUPPORTED, UNKNOWN (section 10.2). Earlier labels in this module were wrong and are corrected: evidence status uses the AI vocabulary (unverified, not_applicable, conflicting; verified and partially_verified are refused as human-only), and check outcome uses the three approved values. The source-condition marker (stale, revoked, absent, synthetic) is not an approved vocabulary and is labelled provisional. |

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


### 1.10 Corrections from the contract session, QA of increment 2, and the S7-05 realignment

| Step | SHA | Result |
|---|---|---|
| Contract register received | n/a | OPEN-07 and OPEN-08 corrected as above (P5). Workspace: none exists on the Foundation candidate; OPEN-11 keeps the project-level boundary, and `workspace_id` is a compatibility label only. Contract corrections `2387fe3` to `e9fb188` are local to the contract session and not pushed; they are not relied on here. |
| Independent QA of increment 2 | `8393059` | **FAIL**: mandatory (1) the S7-11 stale status line dropped the missing-evidence clause; mandatory (2) exact-type gaps in report_state (snapshot, assessment, input tuples) and in the resolution actor identifier. Minor: duplicate entities were refused only at assessment. All other items passed (queue all 25 pairs, decisions, clarification resolution, SOW escaping, no forbidden imports, no change outside review). |
| Remediation | this commit | Both mandatory groups fixed. Duplicate entities refused at construction. S7-05 realigned to the approved vocabularies (see P5). Regression tests: `tests/unit/test_sprint7_regressions_increment2.py`. Full unit suite: 719 passed and 5 failed, with 724 collected. The five failures are in test_api_app.py and are environmental (psycopg libpq). |

**Blocked requirements, corrected reasons (for WDS):**
- **S7-10 (audit):** the approved event list in contract section 14.2 (OPEN-25) covers Sprint 6 events only. The Sprint 7 events (review decisions, estimate revisions, report snapshots) are not in it, so they need a WDS decision to add them. Writing them needs the PW-1 Foundation worker, which does not exist yet (D-DEP-2).
- **S7-01, S7-02, S7-04 (scope and authorization):** workspace identity is not in the Foundation (D-DEP-1). Scoped access and approval authorization stay blocked until the scope entity or rule is defined.
- **S7-07 (estimate approval):** needs authorization (D-DEP-1, OPEN-04 approver rules) and durable audit (S7-10).
- **S7-12 (seven specialists):** needs the merged Sprint 6 specialist contract (adapter 0.3, D-DEP-4) and the shared registry (OPEN-12 decided; the registry lives on Line B).

### 1.11 Independent re-verification of daa0706

| Step | SHA | Result |
|---|---|---|
| Re-verification (scope: changes since 8393059) | `daa0706` | **PASS**, no mandatory defects. The stale status line names missing evidence; exact types hold for snapshots, assessments, input tuples and the actor identifier; the citation vocabularies match the approved OPEN-07 and OPEN-08 values; no approved value can render as "verified"; the claim guard is unchanged. Unit suite: 719 passed, 5 environmental failures (test_api_app.py, psycopg). |

**Non-mandatory residuals recorded from the re-verification:**
- The adapter mapping (`ai_status_from_adapter`) is a constant table. It does not enforce contract 10.4's rule that a cited finding needs at least one citation, because no adapter-record ingestion exists in the review package.
- `check_outcome` is caller-supplied, so a citation can be marked SUPPORTED without a substantiating passage. Contract 10.2 requires substantiation. The AI Engine owns the production of this value, so it is outside the review package.
- The claim guard covers the four citation fields only, as WDS accepted. Other free text, such as SOW item text, can still contain the phrase "Evidence status: verified".
