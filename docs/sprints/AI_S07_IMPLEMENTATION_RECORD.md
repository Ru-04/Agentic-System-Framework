# AI-S07 Implementation Record: Independent Runtime Governance Reviewer

Status: engineering completion candidate. QA history: round 1 FAIL, round 2 PASS WITH FINDINGS, consolidated round 3 FAIL on served-copy consistency (all findings fixed); final independent verification recorded in `AI_S07_QA_FINDINGS_REGISTER.md`. Not committed by this record.
Scope: offline, mocks only. No Foundation calls, no live LLM calls, no specialist execution from governance, no vendor retrieval, no real client data.
Companion documents: `AI_S07_GOVERNANCE_REVIEWER_CONTRACT.md` (contract and authority model), `AI_S07_ACCEPTANCE_MATRIX.md`, `AI_S07_QA_FINDINGS_REGISTER.md`, `AI_S08_HANDOFF_FROM_AI_S07.md`.

## 1. Authority model (summary)

- Specialists cannot self-verify. The specialist output contract refuses a VERIFIED or PARTIALLY_VERIFIED claim status and refuses verified served evidence. Upstream claim status is never treated as proof.
- `EVIDENCE_BACKED` is a reviewer assessment that an admitted record supports a requirement. It is not a verification, approval, materiality decision, execution authorisation, estimate or SOW commitment. Full definition: the contract document.
- Served copies are compared with the admitted record. The specialist validator refuses VERIFIED and PARTIALLY_VERIFIED served evidence. An unverified served status is accepted, and so is a status equal to the admitted status (approved directive, section C). The admitted record is the verification authority. Any other difference is a mismatch and never supports backing.

## 2. Capabilities implemented

| # | Capability | Where |
|---|---|---|
| 1 | Requirement coverage (unrouted requirements, missing investigations, unexpected IDs) | `reviewer.py` `_coverage` |
| 2 | Evidence and citation validation (served, admitted, project, served-copy identity, every served copy checked whether cited or not) | `_citations` |
| 3 | Claim-to-evidence admissibility and relevance (deterministic term screen) | `_citations`, `_backing_citations` |
| 4 | Missing-evidence detection | `_clarification` |
| 5 | Unsupported-claim detection (verified claims without verifiable admitted evidence) | `_claims` |
| 6 | Stale, superseded, cross-project and unauthorised-collection evidence | `_citations`, `_backing_citations` |
| 7 | Contradictory evidence and unreported conflicts | `_claims`, `_statuses` |
| 8 | Cross-specialist feasibility divergence (within and across categories) | `_cross_specialist` |
| 9 | Risk and clarification completeness | `_risks`, `_clarification` |
| 10 | Independent findings (`RVW-NNN`, deterministic, status always `proposed`) | `_Collector`, `contracts.py` |
| 11 | Audit correlation (run ID on every finding; SHA-256 input fingerprint over identifiers and review parameters) | `_fingerprint`, `ReviewReport.input_fingerprint` |
| 12 | Fail-closed malformed input (`ValueError` at `ReviewInput` construction) | `ReviewInput.__post_init__` |
| 13 | AI-S06 orchestration integration (offline) | `governance/adapter.py` `review_orchestration` |
| 14 | Human-review escalation (findings whose action is `human_review`) | `ReviewReport.escalations` |

## 3. Explicit guarantees (tested)

- A specialist returning COMPLETED with no evidence served is `NOT_EVIDENCE_VERIFIED` with a MAJOR finding. Served but unused evidence gives a MINOR `MISSING_EVIDENCE` finding. Where nothing backs, the status is never evidence-verified.
- Backing requires a freshness window (`as_of` and `stale_after`) and an authorised collection set. Without them nothing backs and the review reports `MISSING_REVIEW_PARAMETER`.
- `EVIDENCE_BACKED` requires every gate in the contract document. Mock, unverified, cross-project, unauthorised, superseded, stale, irrelevant, conflicting and mismatched evidence never back a requirement.
- A duplicated served evidence ID is ambiguous: it is reported as a mismatch in either order and never backs.
- A served copy is checked whether or not a claim cites it. A served record that is not admitted is a blocker.
- A staleness window without `as_of` is refused. Naive `as_of` and naive `checked_at` are refused; UTC and offset-aware values are accepted; the freshness limit is inclusive.
- Findings do not depend on specialist execution status (test: identical requirement status and findings across execution statuses).
- `ReviewReport.authorises_anything` is always `False`. Findings are always `proposed`.
- The reviewer core imports no orchestration, specialist or LLM code. Only `adapter.py` imports orchestration (AST test).
- Reviews are deterministic and do not mutate their inputs.
- No rules invented for A-4, C-15, GP-1, D-05, D-06 or D-07.
- R-1 and R-2 are untouched and remain open.

## 4. Test results

Final candidate (after the consolidated QA round 3 remediation):
- `pytest -q`: 1575 passed, 3 skipped. The three skips are the Foundation integration tests in `test_ai_s02_s04_acceptance_distinctions.py` (lines 357, 362, 367), visibly skipped and not run offline.
- AI-S07 focused: 66 tests in `test_ai_s07_governance.py`, all passing.
- AI-S05, AI-S06 and AI-S07 focused: 254 passed. AI-S01 to AI-S04 focused subset: 158 passed.
- `ruff check .`: clean. `ruff format --check .`: clean. `mypy --strict src tests`: no issues in 136 files.

## 5. QA history and dispositions

Round 1 (FAIL, no blocker; three MAJOR gaps): verified claims citing unverified records; same-category feasibility divergence; unverified claims citing synthetic mock evidence. All fixed with regression tests. Minor: CONFLICTING feasibility unreported; naive `as_of`; duplicate admitted IDs. All fixed.

Round 2 (PASS WITH FINDINGS, no blocker): EVIDENCE_BACKED ignored claim status (superseded by the authority model above); served copy not reconciled with the admitted record (fixed: `SERVED_RECORD_MISMATCH`); naive `checked_at` on an admitted record (fixed: refused at input).

Consolidated round 3 (FAIL, two MAJOR, plus minor documentation and fail-open findings). All fixed in one pass:
- MAJOR: a duplicated served ID could hide a mismatch depending on order. Fixed: duplicated IDs are a mismatch in any order and cannot back.
- MAJOR: a served copy that no claim cites escaped mismatch checks. Fixed: every served copy is checked; an unadmitted served record is a blocker.
- MINOR (fail-open): a staleness window without `as_of` was silently ignored. Fixed: refused at input.
- MINOR (documentation): the fingerprint docstring overclaimed. Fixed: it states what it covers; the fingerprint now includes the window, collections and supersession inputs.
- MINOR (documentation): the module docstring called all checks policy-independent while the window, collections and supersession are caller inputs. Fixed.

Final verifier, round 4 (FAIL): one MAJOR fail-open default, one MAJOR documentation finding, and minors. All fixed:
- MAJOR: with no collection set or no window, evidence could back. Fixed: backing requires `as_of`, `stale_after` and an authorised set; otherwise nothing backs and `MISSING_REVIEW_PARAMETER` is reported. Tests: `test_evidence_is_not_backed_without_a_window_or_a_collection_set`, `test_evidence_with_an_unknown_collection_fails_closed`.
- MAJOR: the record cited three documents that did not exist. Fixed: `AI_S07_QA_FINDINGS_REGISTER.md`, `AI_S07_ACCEPTANCE_MATRIX.md` and `AI_S08_HANDOFF_FROM_AI_S07.md` now exist.
- MINOR: module docstring wording and the collection caveat; the contract's provenance rule (now per evidence kind); the zero-evidence finding wording; the adapter-only import rule now has a test (`test_only_the_adapter_imports_orchestration`).

The full QA history is in `AI_S07_QA_FINDINGS_REGISTER.md`.

Verifier, round 5 (FAIL, minors only; the round-4 MAJOR fixes held): the package docstring lacked the caller-supplied caveat; the served-status wording omitted that an equal status is also accepted; the adapter-only AST test missed plain `import` statements; and the reviewer trusted a verified record's status without re-checking its provenance. All fixed. Provenance is now re-checked by the reviewer (`_has_provenance`), with the test `test_a_verified_record_without_recorded_provenance_is_not_backed`.

## 6. Governance decisions (open; not invented by the reviewer)

1. **Served-status interpretation (D-EVB-1), approved by WDS for isolated engineering.** The specialist validator refuses verified served statuses, while the directive's MAJOR-2 wording says a verification-metadata mismatch must never support backing. Read literally, those two make EVIDENCE_BACKED unreachable from any validated output. The implementation resolves this by treating the served status as a forced, non-authoritative projection and the admitted record as the verification authority. A served status other than unverified or equal to the admitted status remains a mismatch. This is an interpretation, not a contract amendment. WDS approved it for isolated engineering (see the contract document, section 5, and `AI_S07_D06_D09_RECONCILIATION.md`).
2. **Evidence verification authority (D-06 and D-09, open).** The reviewer does not establish verification. It relies on the admitted record's recorded verification provenance, supplied by the caller. Who may set that provenance is not yet decided.
3. **Semantic relevance.** The relevance check is a deterministic term screen, not semantic relevance. Real relevance remains a human decision.
4. A-4 and C-15 (lifecycle and blocked versus clarification): not implemented.
5. GP-1: not implemented.
6. D-05 (who may accept a finding): not implemented. Findings remain `proposed`.
7. D-06 (materiality) and D-07 (acceptance of inferred requirements): not implemented.
8. R-1 (`run_specialist` ungated) and R-2 (unsigned confirmations): open blockers, unchanged.

## 7. Accepted limitations

- Offline and mock-only. Mock evidence validation is not production source verification.
- Durable run, review and audit persistence is not implemented in AI-S07; it requires Foundation integration. The fingerprint is a correlation key, not a persisted audit record.
- `UNSUPPORTED_VERIFIED_CLAIM` cannot fire from a contract-valid specialist output (the contract refuses verified claims). It is detected for defective or tampered output only.
- Collection and supersession data are supplied by the caller; the reviewer does not look them up.
- The fingerprint covers identifiers and review parameters, not claim or evidence content.

## 8. Foundation services required for real authority

- Authoritative requirement and source reads (approved requirement records; admitted source versions).
- Admitted evidence with verified provenance (content hash, source version, verification record) and the authority that sets it.
- Collection authorisation for the requesting actor and project.
- Supersession and conflict records as authoritative data, not caller assertions.
- Durable, tamper-evident review and audit persistence keyed by the run and the input fingerprint.

## 9. Proposed commit files (not committed; requires separate authorisation)

Include:
- `ai_engine/src/ai_engine/governance/__init__.py`
- `ai_engine/src/ai_engine/governance/contracts.py`
- `ai_engine/src/ai_engine/governance/reviewer.py`
- `ai_engine/src/ai_engine/governance/adapter.py`
- `ai_engine/tests/test_ai_s07_governance.py`
- `docs/sprints/AI_S07_RUNTIME_GOVERNANCE_REVIEWER_SPRINT_SPEC.md`
- `docs/sprints/AI_S07_HANDOFF_FROM_AI_S06.md`
- `docs/sprints/AI_S07_IMPLEMENTATION_RECORD.md`
- `docs/sprints/AI_S07_GOVERNANCE_REVIEWER_CONTRACT.md`
- `docs/sprints/AI_S07_ACCEPTANCE_MATRIX.md`
- `docs/sprints/AI_S07_D06_D09_RECONCILIATION.md`
- `docs/sprints/AI_S07_QA_FINDINGS_REGISTER.md`
- `docs/sprints/AI_S08_HANDOFF_FROM_AI_S07.md`

Exclude (unrelated untracked work, preserve as-is): the `test_ai_s02_s04_*` test files, the Foundation read-contract and adapter-gap documents, the AI-S05 closure record and AI-S05/S06 handoffs, the master sprint plan, and the AI-S08/S09/S10 specs (other than the AI-S08 handoff named above).

## 10. Engineering acceptance readiness

See `AI_S07_ACCEPTANCE_MATRIX.md` for the criterion-by-criterion status and the commit decision.
