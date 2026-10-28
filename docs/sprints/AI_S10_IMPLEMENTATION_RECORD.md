# AI-S10 Implementation Record (Stage 3 remediation)

Status: Stage 3 remediation of the Stage 2 FAIL on baseline `211d308`. Pending the Stage 2 re-review of the
remediation commit. Not WDS-accepted. No push, merge or deployment.

Authority: `AI_S10_EVALUATION_ACCEPTANCE_SPRINT_SPEC.md` (WDS-approved scope baseline) and the WDS
Stage 3 directive (remediate QA-1 to QA-6 and the minor findings in one cycle).

## 1. Baseline verified before editing

- Branch `integration/ai-s01-s02-s03`, HEAD `211d30824bd1b190c04d4e0f29eeac51e86eda87` (`211d308`), matching the QA baseline.
- Staged: nothing. Modified tracked: nothing.
- Untracked and not part of this work: `tests/test_ai_s02_s04_acceptance_distinctions.py`,
  `tests/test_ai_s02_s04_boundaries.py`, `tests/test_ai_s02_s04_integration.py` (Foundation tests, 67 collected);
  `docs/AI_FOUNDATION_READ_CONTRACT_AND_READINESS_2026-10-26.md`,
  `docs/AI_S02_S04_FOUNDATION_ADAPTER_GAP_AND_DESIGN_PROPOSAL.md`,
  `docs/sprints/AI_S05_*`, `docs/sprints/AI_S05_S10_MASTER_SPRINT_PLAN.md`,
  `docs/sprints/AI_S06_HANDOFF_FROM_AI_S05.md`, `docs/sprints/AI_S10_EVALUATION_ACCEPTANCE_SPRINT_SPEC.md`.
  None of these is modified or staged by this work.
- Upstream engine source (`ai_engine/src`): **unchanged** from `211d308` (verified by `git diff`). No accepted
  AI-S01 to AI-S09 contract was rewritten.

## 2. Initial QA finding list (Stage 2, `211d308`)

| ID | Severity | Finding |
|---|---|---|
| QA-1 | Blocking | `sec_replay` was refused by workflow state before the ledger; removing `consume` left the suite green. |
| QA-2 | Blocking | "Stale input rejected" (spec section 8) is only flagged by the engine. |
| QA-3 | Major | REC-03 expectation was rewritten to fit observed behaviour (C-15). |
| QA-4 | Major | Negative tests accepted any refusal; always-refuse mutation still passed SEC-05/07/08 and SPEC-08. |
| QA-5 | Major | Results not anchored to a candidate; readiness cited 1728 for a 1664 committed tree; untracked provenance unclear. |
| QA-6 | Major | No AI-S01 scenarios; extraction delegated only; cross-project coverage narrow; no pipeline traceability test. |
| Minor | — | EVID-15 (estimate only, SOW claimed), SOW-12 (one field), SOW-09 (dates only), SEC-09 (name-based), REC-01 (no recovery), REC-02 (one variant). |

## 3. Dispositions

### QA-1 — Replay enforcement (resolved; tested and mutation-proven)

- New executors exercise `ConfirmationLedger.consume` directly and through `verify_confirmation`, with a
  shared ledger and `mock=False` synthetic human-shaped confirmations:
  `SEC-06` (same confirmation twice), `RPL-02` (another run), `RPL-03` (another project),
  `RPL-04` (changed selection, reused ID), `RPL-05` (expiry, refused attempt consumes nothing),
  `RPL-06` (direct ledger port), `RPL-07` (fresh ID, reused nonce). `RPL-01` is the positive control.
- Each refusal must be raised by the named enforcement point (`consume` or `verify_confirmation`), found
  from the exception traceback (`evaluation/enforcement.py`). The runner fails a scenario whose refusal
  came from elsewhere.
- Mutation proof (`tests/test_ai_s10_mutations.py`): with `ConfirmationLedger.consume` disabled, `SEC-06`,
  `RPL-04`, `RPL-06` and `RPL-07` fail, and `RPL-01` still passes.
- Not claimed: Foundation-issued replay protection. This is an in-memory, offline enforcement test.

### QA-2 — Stale input rejection (resolved as a classification; governance decision recorded)

The accepted contracts define stale-input behaviour, and it is not rejection of the operation:

| Source | Stale input behaviour (accepted) |
|---|---|
| AI-S05 spec | Stale evidence is reported as a question and is not cited. |
| AI-S07 contract | Stale evidence never backs; a missing window or collection set is `MISSING_REVIEW_PARAMETER`; "does not refuse the review". |
| AI-S08 contract | A changed requirement revision makes the line `needs_inputs`; no numbers. |
| AI-S09 contract | A stale revision is an integrity issue; the draft is still produced. |

The only refusal in the accepted chain is at input validation (for example a window without `as_of`, AI-S07),
and for an operator decision made against an earlier project revision (`StaleSelectionError`, AI-S01).

Dispositions:

- `STL-04` (executed, pass): the stale operator selection is genuinely rejected at `run_investigation`, and
  the agent never runs.
- `STL-01`, `STL-02`, `STL-03`, `STL-06` (executed, pass): current revisions are accepted; a stale revision
  is reported and its deliverable is not complete; a missing revision is reported; flagged stale input does
  not produce a completed or approved outcome. These prove exclusion and no false completion. They are
  **not** counted as rejection.
- `STL-05` (blocked, governance decision): spec section 8 says stale inputs are rejected; the accepted
  contracts flag, exclude or mark `needs_inputs` and never refuse the operation. Flagging is not counted as
  rejection. This criterion cannot pass until WDS decides which behaviour is required. If refusal is
  required, the change is an upstream AI-S08/AI-S09 correction through the permitted process.

No engine behaviour was changed to produce a pass.

### QA-3 — REC-03 and C-15 (resolved as an open limitation)

- REC-03's acceptance expectation is restored and frozen (`tests/test_ai_s10_evaluator_rules.py`):
  "the withheld category is refused before any specialist attempt; no evidence is used; no other collection
  is substituted".
- Classification: `OPEN_LIMITATION`, linked to C-15 in the dependency and references. It is excluded from
  engineering PASS counts.
- The observed behaviour is recorded as evidence and as the limitation: the category runs with no evidence,
  its specialist reports `evidence_unavailable`, and the execution reports `succeeded`. The producer
  (`workflow.py`, `execution.py`) is unchanged. No new execution policy is asserted on WDS's behalf.

### QA-4 — Negative-test false positives (resolved; exact reasons, positive controls, mutation proof)

| Scenario | Enforcement point | Exact reason asserted | Positive control |
|---|---|---|---|
| SEC-05 forged mock | `verify_confirmation` | mock confirmation is not permitted on the production path | human-shaped confirmation accepted |
| SEC-07 expired | `verify_confirmation` | confirmation has expired | unexpired accepted |
| SEC-08 wrong run | `verify_confirmation` | confirmation is bound to another run | correct run accepted |
| SPEC-08 unconfirmed execution | `execute` | no operator confirmation is in force for this run | confirmed run executes all seven; zero specialist calls when refused |

Mutation: `verify_confirmation` replaced by an always-refuse function. Every gate scenario routed through
verification fails. `RPL-06` and `RPL-07` exercise the ledger port directly and are correctly unaffected
(asserted in the test).

### QA-5 — Traceability and reproducibility (resolved)

- The results are anchored to a **candidate source digest**, not to a label. The digest is SHA-256 over the
  engine source and the AI-S10 test package, with line endings normalised. Current value:
  `62e7226399ddc90a1c2578ad53c4a4805f80ae9815b68401527e0d83a1c7dd86`.
- `test_ai_s10_consistency.py` regenerates the results from the source and requires them to match the
  committed documents byte for byte, and requires every result to agree with its scenario status.
- Test-count separation is in the reproducibility report, section 5.
- The 1728 figure is no longer used as a committed-tree baseline. Committed and untracked tests are counted
  separately.
- The sprint spec and master plan remain untracked. They are read, not committed, and are named as such in
  every record that cites them.

### QA-6 — Coverage (resolved for the offline scope)

- **AI-S01 security (8 executed):** operator identity with invisible characters (`S01-01`); unallowed
  collection denied by the wrapper (`S01-02`); foreign-project request denied (`S01-03`); the agent cannot
  change the requirements it was given (`S01-04`); a model-constructed verified candidate is refused at the
  contract (`S01-05`); fabricated evidence outside the authorised set fails validation (`S01-06`); a reviewed
  content change makes an operator selection stale (`S01-07`); and the stale-decision rejection (`STL-04`).
  Live Foundation enforcement is not run (EXT-05, EXT-06).
- **Requirement extraction, deterministic (8 executed):** `REQ-01`..`REQ-08`: valid extraction with exact
  source quotes; ambiguity becomes open questions; malformed and foreign input refused at `analyze`;
  identifiers unique and deterministic; no verified status or requirement IDs; instruction-like source text
  is data; inferred requirements never accepted.
- **Requirement extraction, LLM-backed intake, AI-S02 (3 executed, offline):** `LLM-01` correct reply accepted;
  `LLM-02` hallucinated quote refused after retries; `LLM-03` untrusted text stays out of the system prompt.
  Real-provider semantic extraction is not run (EXT-01).
- **Cross-project isolation (6 executed):** specialist evidence access (`XP-01`); reviewer refuses a cross-project
  citation (`XP-02`); estimate refuses foreign governance (`XP-03`) and foreign snapshot (`XP-04`); SOW
  refuses foreign governance (`XP-05`) and foreign estimate (`XP-06`). Plus `SEC-01` (foreign requirement).
- **Full pipeline traceability (1 executed):** `TRC-01` correlates requirement identifiers across the
  specialist outcomes, the estimate revisions and the governance fingerprint.
- **Integrated adapter (blocked):** `TRC-02` records that no Foundation-fed requirement-to-SOW path exists.

### Minor findings

| Finding | Disposition |
|---|---|
| EVID-15 expected estate and SOW, executor checked the estimate only | Executor now checks both: the estimate readiness and the SOW deliverable and risk text (`evid_blocker_not_erased`). |
| SOW-12 expected several fields, executor tested one | Executor tests five positions: requirement statement, deliverable description, deliverable title, acceptance criterion, milestone title. |
| SOW-09 expected no durations, regex covered dates only | Executor checks calendar dates and schedule durations (days, weeks, months, years). Effort values in hours are AI-S08 estimate figures and are not schedule durations; the check excludes them deliberately. |
| SEC-09 checked only parameter names (absence of a confirmation-like name) | Behavioural: a direct call to `run_specialist` with no confirmation, actor or proposal returns an execution status. The limitation is still present (`open_limitation`). |
| REC-01 tested the initial failure only | `REC-04`: a transient first attempt is retried and succeeds; eight calls in total. |
| REC-02 tested one permanent variant | `REC-02` covers `failed_validation`, `permission_denied` and `unsupported_request`. `REC-05`: a raised exception is recorded and never retried. |

## 4. Evaluator rules (implemented and regression-tested)

| Rule | Mechanism | Test |
|---|---|---|
| A scenario cannot PASS without reaching its enforcement point | `Scenario.enforcement`; `Check.enforced_by`; `runner._judge` | `test_pass_requires_the_declared_enforcement_point`, `test_a_refusal_from_another_layer_cannot_pass` |
| A refusal cannot PASS because an unrelated control rejected it | Enforcement names the innermost refusing function or pydantic model | `test_a_check_that_reached_no_enforcement_point_cannot_pass` |
| Every refusal expectation declares its enforcement point | Catalogue invariant | `test_every_refusal_expectation_declares_its_enforcement_point` |
| A declared limitation cannot count as an executed PASS | `OPEN_LIMITATION` outcome | `test_an_open_limitation_that_disappears_is_not_a_pass`, `test_a_present_open_limitation_is_reported_as_open_not_as_a_pass` |
| Blocked and delegated cannot be successful | Runner | `test_non_synthetic_classes_are_never_reported_as_passed`, `test_delegated_and_open_limitation_rows_are_not_passes` |
| Mutations of mandatory controls are detected | Controlled monkeypatch mutations | `test_ledger_consume_removed_is_detected`, `test_always_refuse_verification_is_detected` |
| Stale input that is only flagged is not classed as rejected | `STL-05` blocked; `STL-04` is the only rejection | `test_stale_input_that_is_only_flagged_is_not_classed_as_rejected` |
| Expected and actual remain independent; REC-03 expectation frozen | Expectations are catalogue literals; frozen-text test | `test_frozen_expectation_for_rec03_is_the_acceptance_contract_not_the_observation` |
| Every result references a reproducible candidate | Source digest | `test_committed_results_match_the_regenerated_output` |
| Scenario results are consistent with their status | Status-to-outcome map | `test_each_result_agrees_with_its_scenario_status` |
| Synthetic outcomes cannot establish live Foundation authority | Foundation and provider rows are blocked; none passes | existing `test_non_synthetic_classes_are_never_reported_as_passed` |

## 5. Gates (development worktree, after remediation)

- Full suite: **1744 passed, 3 skipped**. The 3 skips are the Foundation tests at
  `test_ai_s02_s04_acceptance_distinctions.py` lines 357, 362 and 367, not run offline.
- AI-S10 files: 32 passed (`test_ai_s10_evaluation`, `_evaluator_rules`, `_mutations`, `_consistency`) on the
  final catalogue, plus the full suite above.
- `ruff check .`: clean. `ruff format --check .`: clean. `mypy --strict src tests`: no issues in 157 source files.
- Clean-export counts of the committed remediation commit: recorded in the Stage 4 acceptance packet.

## 6. Catalogue after remediation

- 133 scenarios. Class A: 112 executed and passing, 0 failing; 5 open limitations (`SEC-09`, `EVID-16`,
  `EXT-08`, `REC-03`, `UD-01`); 3 delegated (`PIPE-04`, `PIPE-05`, `SPEC-14`); 1 blocked (`STL-05`).
- Class B: 5 blocked (`EXT-05`, `EXT-06`, `EXT-07`, `SEC-18`, `TRC-02`). Class C: 1 (`EXT-01`).
  Class D: 2 (`EXT-02`, `SPEC-15`). Class E: 3 (`EXT-03`, `SOW-13`, `SPEC-16`). Class F: 1 (`EXT-04`).
- Outcomes: pass 112, open_limitation 5, delegated 3, blocked 13, fail 0.

## 7. Upstream defect recorded, not fixed

- **UD-01 (AI-S09, open limitation):** the SOW does not compare the estimate's governance fingerprint with the
  governance review's. A mismatched estimate is accepted with no integrity issue. The fix is an additive
  integrity check in the accepted AI-S09 engine, outside AI-S10 scope. It needs the permitted upstream change
  and renewed verification. Recorded as `UD-01`; the test asserts the defect is still present.

## 8. Limits of this remediation (stated, not hidden)

- Mutation coverage is two controls: the ledger `consume` and the verification gate. The inline stale-revision
  check and the upstream fingerprint gap are not mutation-tested. `UD-01` shows the gap by observation.
- `STL-05` cannot pass until WDS decides whether stale input must be rejected or flagged.
- `REC-03` and `C-15` remain unresolved policy; the scenario shows the condition rather than resolving it.
- AI-S01 wrapper denials (`S01-02`, `S01-03`) are status-based, not exception-based; their enforcement point is
  recorded as none.
- All evidence, identities and confirmations are synthetic. No Foundation, real-provider, vendor or platform
  evidence is produced.
