# AI-S05 Sprint Specification: Standalone and Middleware Applications Specialists

**WDS-APPROVED SCOPE BASELINE — IMPLEMENTATION AUTHORIZED**

Authority: WDS Project Owner master directive (26 October 2026). Parent: `AI_S05_S10_MASTER_SPRINT_PLAN.md`.

## 1. Purpose and approved functional scope

Build two real specialist categories on the shared AI Engine specialist contract:

- **Standalone Applications** (`CAP-STANDALONE-APPLICATIONS`, `standalone_applications_specialist`).
- **Middleware Applications** (`CAP-MIDDLEWARE-APPLICATIONS`, `middleware_applications_specialist`).

Both are investigators. They produce structured, unverified findings for later Governance Review,
estimation and SOW generation.

## 2. In scope

Standalone: reuse of an existing application or service; custom standalone web or application build;
frontend and backend architecture; authentication and authorisation; data models and persistence;
external APIs and service integrations; hosting and deployment; security, reliability and
scalability; feasibility, assumptions, limitations and risks; clarification questions and evidence gaps.

Middleware: integration between applications or platforms; APIs, webhooks and events; authentication
and credential dependencies; data mapping and transformation; synchronisation direction and frequency;
idempotency, retries and failure recovery; rate limits and operational dependencies; monitoring and
error handling; integration security and data protection; feasibility, assumptions, limitations and
risks; clarification questions and evidence gaps.

## 3. Out of scope

- Commerce-platform specialists (AI-S04) and their behaviour.
- Routing, multi-specialist orchestration and confirmation (AI-S06).
- Governance review of these findings (AI-S07).
- Estimates, materiality and business judgement of any kind.
- Any live vendor documentation, live research, provider call or external network access.
- Any real client data.

## 4. Required interfaces and dependencies

- Input: `SpecialistTask` built by the AI-2 task builder, with an explicit operator selection.
- Context: read-only `SpecialistContext` (project, requirements keyed by Foundation requirement ID,
  evidence lookup). The lookup is scoped by project and allowed collections.
- Output: `SpecialistInvestigationResult` (shared contract).
- Execution: AI-2 wrapper `run_specialist`.
- Registry: `AGENT_REGISTRY.yaml` entries for both capabilities (status `proposed`).

## 5. Deliverables (implemented)

| Item | Location |
|---|---|
| Shared investigation builder | `ai_engine/src/ai_engine/applications/common.py` |
| Standalone specialist and profile | `ai_engine/src/ai_engine/applications/standalone.py` |
| Middleware specialist and profile | `ai_engine/src/ai_engine/applications/middleware.py` |
| Synthetic placeholder evidence (two collections) | `ai_engine/src/ai_engine/applications/synthetic_evidence.py` |
| Regression and adversarial tests (130) | `ai_engine/tests/test_ai_s05_application_specialists.py` |

## 6. Security requirements

- Every claim is `unverified` or `conflicting`. Nothing is verified.
- Every candidate solution is marked "not selected".
- Evidence is cited only when served by the context, for the project and collections the task allows.
- Stale evidence (older than 365 days relative to the task) is reported as a question and is **not**
  cited as support.
- No import of network, socket, provider or model-client modules (tested).
- Unsupported, wrong-platform, malformed and out-of-scope input is refused with
  `UnsupportedRequestError`, never guessed.

## 7. Human approval boundaries

- The specialist never selects an option, approves a requirement, sets materiality, or accepts scope.
- The specialist never authorises an external write (middleware non-responsibility).
- The operator selects the specialist. Automatic routing is not part of AI-S05.

## 8. Tests and evaluation scenarios

Mapped to the directive's fourteen required test areas:

| Area | Test coverage (file: `test_ai_s05_application_specialists.py`) |
|---|---|
| 1, 2 identity | Result identity for each; registry resolution; cross-category selection refused |
| 3 valid and invalid categories | Out-of-scope refused; mixed task partial |
| 4 missing, stale, conflicting evidence | Missing gives EVIDENCE_UNAVAILABLE with a source question; stale not cited and reported; conflict with both cited and linked back; two groups reported |
| 5 cross-project | Other-project records never cited, for both |
| 6 collection access | Records outside the allowed collection not served; empty allowlist gives EVIDENCE_UNAVAILABLE |
| 7 unsupported | Refusal by each specialist of the other's platform and of out-of-topic requirements; unknown requirement refused |
| 8 citation integrity | Claims and conflicts cite only served evidence; no verified claim; requirement IDs preserved |
| 9 empty and malformed | Empty list refused by the builder; blank statement refused by the contract; malformed statements refused |
| 10 provider independence | No provider imports; both run with every socket blocked; deterministic output |
| 11 unauthorised execution | A mismatched agent is refused by the wrapper; no routing import in the specialist modules |
| 12 compatibility | Each runs through `run_specialist`; output round-trips through the shared contract |
| 13 no network | Socket blocked during runs |
| 14 structured outputs | Risks, assumptions, dependencies, open clarification questions |

Result at this date: **130 passing** in the AI-S05 file. Full gate: 1451 passed, 3 skipped; Ruff check,
format check and strict mypy (124 files) clean.

**Independent QA, first pass (FAIL), and the fixes applied.** The first QA pass reported blockers that were
fixed in this revision: (1) directive topics refused as out of scope, now investigated and tested;
(2) search not restricted to the specialist's own collection, now restricted to the profile collection
intersected with the task allowlist; (3) evidence and conflicts computed per requirement, now per topic;
(4) conflicts over-applied to all claims, now applied only to the claim about the conflicting records;
(5) conflict back-references inconsistent, now checked in both directions; (6) short search terms dropped
silently and empty queries returning everything, now each topic searches a single term longer than three
characters and empty queries are never sent; (7) middleware stale path untested, now reached and tested;
(8) requirements with no current evidence returned COMPLETED, now EVIDENCE_UNAVAILABLE; (9) "retrieve"
matched the retries topic, now fixed; (10) wrong message for requirements missing from the context, now
corrected; (12) multiple contradiction groups in one topic, now all reported. Test weaknesses noted in the
QA report were replaced with assertions that observe the lookup, the claim topic and the conflict links.

Second QA pass (FAIL, three blockers and three majors), and the fixes applied:
- BL-1 keywords: the retries pattern was a non-raw string (`` became a backspace), so "Retries must be
  bounded" was refused. All topic keywords are now raw strings. Added authorise, rate-limit, hourly,
  frequency, mobile and web app, and sign-in variants. Positive tests cover each.
- BL-2 status: a task where any relevant requirement has no current evidence is now PARTIAL, not COMPLETED.
- BL-3 citation attribution: the search term is a substring match, so a monitoring record could support
  the integration claim. Each synthetic record now carries an explicit topic tag, and only tagged records
  are cited for a topic. A test checks that the monitoring record is not cited for integration.
- MA-1: a context record whose ID or project does not match its key is refused with UnsupportedRequestError.
- MA-2: the collection test now plants a record that a leak would cite, and asserts it is not cited.
- MA-3: the wrong-category agent is asserted as FAILED_VALIDATION; the out-of-scope case as UNSUPPORTED_REQUEST.
- Minor: every search term is asserted to be longer than three characters; the monitoring keyword and
  personal-data keyword now match whole words.

Known limits, not fixed: the risk text names only the first two topics (MI-4); a topic with no evidence
still produces hypothesis claims with no citations, labelled as such (MI-5).

Third QA pass (FAIL): two blockers and three majors, and the fixes applied.
- B1: a requirement with one topic that has no current evidence was COMPLETED. Each topic without
  current evidence now raises its own question, and the task is PARTIAL.
- B2 and M1: keyword sets were too narrow (for example "log in", "front end", "web app", "ERP" in
  upper case, "every 15 minutes", "duplicated") and too loose (for example "map", "events", "daily",
  "connect", "available"). Each keyword set is now anchored and lowercase, and both directions are tested.
- M2: the middleware integration topic had no evidence record. Added EVD-MID-SYN-0012, tagged to it.
- M3: a context that belongs to another project is refused.
- m1: the staleness boundary is tested; a record checked exactly at the cutoff is current.
- n1: synthetic records are dated before the task's creation time.
- n5: "operating cost" wording removed.

Fourth QA pass (FAIL on keyword precision, under WDS decision 4 treated as a reproduced correctness
defect for the cases below). Fixes applied and reproduced before and after:
- Middleware accepted pure standalone sentences ("logged in", "personal information", "encrypted at
  rest", "security reviews"): refused now.
- Standalone accepted business sentences ("scale up the sales team", "applications from candidates",
  "key role", "sign in at reception"): refused now.
- Middleware refused in-scope sentences ("send ... to the warehouse system", "map the order fields",
  "every night", "monitored for errors"): accepted now.
- Standalone refused in-scope sentences ("scale to 5,000 concurrent users", "customer portal"): accepted now.
- Non-text statements raised AttributeError: now refused as UnsupportedRequestError.
- Clarification questions contained "approved": reworded to "evidence source".
- The structured risk named only the first two topics: now names every topic of the requirement.
- The no-network forbidden-import list was narrow: widened (http, ftplib, smtplib, ssl).
- The date test skipped two records: replaced by an exact check of the stale set.

Accepted limitations (not fixed; WDS decision 4 permits pattern-based matching for isolated synthetic
engineering, and these are not represented as semantic capability):
- Pattern matching still admits some out-of-scope sentences that share a keyword with a topic, and still
  refuses some in-scope phrasings not in the keyword set (for example "The site must load in under two
  seconds" is refused). Refusal errs on the safe side.
- The same requirement can appear in both specialists' results where the topics overlap by design
  (APIs, integration, credentials).
- A contradiction group that affects several requirements is reported once per requirement.
- The middleware API-access topic term ("scopes") does not appear in its tagged record EVD-MID-SYN-0005; that
  tag is inert and has no effect on output. The record is still cited for its own rate-limit topic.
- Candidate option summaries name only the first two topics of a requirement. Claims, gap questions and
  structured risks name every topic (QA finding F2, minor).
- A non-text statement that bypasses AtomicRequirement validation (for example by model_copy) is not caught
  by the AI-2 wrapper: run_specialist raises pydantic ValidationError from its own task-model validation and
  does not return FAILED_VALIDATION (QA finding F1, major, documentation correction). Through run(), the same
  input is refused with UnsupportedRequestError. The AI-2 wrapper is an accepted contract and is not changed.
  Such an object cannot be built through the validated contract.
- A requirement with a topic that has no evidence still produces hypothesis claims with no citations,
  labelled as unverified.

Engineering acceptance: not recorded. A fresh independent verification of the fix set is required.

## 9. Engineering acceptance criteria

1. All 130 AI-S05 tests pass with the full suite, Ruff check, Ruff format check and strict mypy green.
2. Independent QA, by a reviewer who did not write the code, reports no blocking finding.
3. WDS formally accepts AI-S05 for **isolated engineering scope**.

## 10. External integration acceptance criteria (not claimed)

- Evidence-backed investigation against authorised vendor documentation or platform evidence.
- Foundation-authenticated actor and project permissions in the runtime path.
- Real requirement IDs and revisions from Foundation.

These are a separate full-functional gate. AI-S05 does not pass them and must not be marked as having
passed them.

## 11. Governance decisions still pending (PENDING)

- Whether the standalone and middleware categories are routed by default (C-05 and routing policy).
- Approved evidence sources for each topic (no collection is approved by this sprint).
- The required structure of the eventual Governance Reviewer input (AI-S07).
- Any change to the registry status from `proposed`.

## 12. Definition of Done

- Code, tests and this specification agree.
- Independent QA report is filed.
- WDS acceptance record is filed, or the sprint remains "implemented, acceptance pending".
- No real vendor, client or provider access has occurred.


## 13. Final independent QA on the frozen candidate (FAIL, then remediation)

The frozen candidate (`applications/` source, `tests/test_ai_s05_application_specialists.py`, this
spec) was reviewed independently. Result: FAIL, one blocking contract violation.

- B1: a multi-topic requirement with no evidence for any topic returned EVIDENCE_UNAVAILABLE. The
  directive requires every uncovered topic to give an evidence gap and PARTIAL. Remediation: any
  uncovered topic gives PARTIAL. EVIDENCE_UNAVAILABLE is returned only when the task allows no
  collection that this specialist owns.
- m1: the "approved" wording test now covers gap questions as well.
- Accepted limitations observed by the reviewer (not blocking): eight false refusals from keyword
  gaps, and one overlap acceptance through the external-API topic (standalone accepts a sentence
  that also names the warehouse). Each citation in the sample was topic-tagged.

No commit was made. The remediated candidate requires a new independent QA before any commit.


## 14. Independent QA on the remediated candidate: PASS (no blocker)

Reviewed candidate hashes (code, unchanged by this entry):
- applications/__init__.py fdb87bb5fca5336b429a50946671fb8cc7df9da054bea27b56aa28d3f9c99bb8
- applications/common.py 2012c6fee588931830be
- applications/middleware.py 16a09adf93e73af6c00e622626cb569be43f42664ca405700f9cdd8120198175
- applications/standalone.py 02d9da8a74c5f306fefa583204f235debb7806339a16312f11934f40586568c3
- applications/synthetic_evidence.py 44ac55fd65926e742a945c639ce9241f6c7f9c913dc4f6415db165eb40aefc18
- tests/test_ai_s05_application_specialists.py f6d258cd3f6321258fdc156d0c9e7adceda7ccb2f3f9034385e64edd994cdaf8

Gate on the reviewed candidate: pytest 1451 passed, 3 skipped (the three Foundation-environment skips in
test_ai_s02_s04_acceptance_distinctions.py); AI-S05 130 passed; AI-S01 to AI-S04 subset 926 passed, 3 skipped
(same three); ruff check and format clean; strict mypy clean across 124 files.

Reviewer result: PASS for engineering completion. Checks 1-15 of the review brief passed. Mutations caught:
collection restriction removed, boundary >= changed to >, tag filter removed, context project check removed,
uncovered topic given COMPLETED, empty allowlist given PARTIAL.

Findings after review:
- F1 (major, documentation, corrected in section 'Accepted engineering limitations'): see that section.
- F2 (minor, recorded): candidate option summaries name only the first two topics.
- F3 (minor, corrected): the inert-tag note.
- F4 (info, accepted): a mixed task with one out-of-scope requirement is PARTIAL even when its in-scope topics
  are covered. This is conservative and tested.
- Observed pattern miss (accepted limitation): "login" alone in "web application with login" is not matched as
  an authentication topic.

Post-review change: only the documentation text in this specification was corrected (F1, F3, F2 note, and this
section). No code or test file changed after the reviewed hashes above.
