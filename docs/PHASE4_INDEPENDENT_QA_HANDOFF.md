# Phase 4 independent QA handoff

Branch: `feature/foundation-phase-4`. Base: `46e0e14`. Sprint start: `85315a1`.

**Status (updated 2026-10-28): PHASE 4 ENGINEERING COMPLETE — READY FOR INDEPENDENT QA.** Not accepted by WDS. Not merged.
Not pushed. Current evidence, commits and gate results are in `docs/PHASE4_CLOSURE_EVIDENCE.md`. The 2026-10-28 final
gate: 13 steps, all passing except the documented format exceptions (step 12). Full regression: **739 passed, exit 0**.
Commits: `cb93047` (defects D1 to D4, EML offsets) and `69aa9e8` (committed-row tests, `.gitignore`).

Open items for QA and WDS, not closed by engineering: (1) the approver's identity, approval date and exact wording
for the relayed governance decisions in `docs/GOVERNANCE_DECISION_REGISTER.md` (`P4-GOV-2026-10-28`) are not recorded;
(2) H-DEC-3 numeric limits are provisional; (3) H-DEC-4 Windows memory containment is accepted for non-production only;
(4) merge dependencies on Phase 3 (`0050`, lease) and Phase 2 remediation (`0044`, `0045`), recorded in §9 of the closure
evidence, are not integrated.

The earlier status below (ENGINEERING INCOMPLETE, 714 passed) describes the superseded `a3f39d6` baseline. It is kept
for history.

## Final verification (this sprint)

| Check | Command | Result |
|---|---|---|
| Full suite | `pytest tests -q -p no:cacheprovider` (sequential, `webdesk_p4_integration` and `webdesk_p4_hardening`) | **714 passed, 1 warning, exit 0** (783.75 s) |
| Unit subset after fixes | `pytest tests/unit -q` | 194 passed |
| Demonstration | `pytest tests/committed/test_parse_demonstration.py -s -q` | 1 passed, exit 0 |
| Lint | `ruff check src tests` | All checks passed |
| Format | `ruff format --check src tests` | Two files would reformat: `tests/hardening/test_privilege_hardening.py` and `tests/integration/test_reassessment.py`. Both are documented exceptions in `docs/RUFF_FORMAT_EXCEPTIONS.md`, which this sprint did not touch. |
| Strict types | `mypy --strict src/webdesk` | Success: no issues in 60 source files |

The full-suite run came after all code changes and fixes. An earlier run (`p4_full2.txt`) had two failures in
`tests/unit/test_intake_unit.py`. They were expectations that predated this sprint's behaviour: a fake PDF page
without `get_contents`, and a TXT locator without character offsets. Both fixes were test updates, not code
changes to the assertions' intent. Those fixes are in the final run.

## Requirement status

| ID | Status | Note |
|---|---|---|
| H-30 | done | every failure isolated per version and audited |
| H-31 | partial | limits implemented; numeric values await H-DEC-3 |
| H-32 | done for timeout and crash on Windows; partial for memory cap | Windows memory cap is H-DEC-4 |
| H-33 | partial | EML character offsets open (basis undefined); H-DEC-5 and H-DEC-6 proposed defaults in use |
| H-34 | done | partial reasons persisted and not reparseable |
| H-35 | partial | committed-row variant covers race and reparse only |

Full matrix: `docs/PHASE4_REQUIREMENTS_GAP_MATRIX.md`.

## What QA should re-test

1. Isolation: `tests/unit/test_parse_isolation.py`. Confirm the child environment carries no database URL, the fault
   switch is ignored outside `WEBDESK_ENV=test`, and the hang test returns within 20 s.
2. Locators: TXT offsets satisfy `text[char_start:char_end] == segment`; DOCX table cell locators; image-only PDF
   pages are partial.
3. Reparse and concurrency: `tests/integration/test_parse_reparse.py` and `tests/committed/test_parse_concurrency.py`.
   The race tests assert invariants that hold in either ordering.
4. Corpus: `tests/unit/test_parse_corpus_manifest.py` fails if a generator's bytes change. Re-pinning requires a new
   `CORPUS_VERSION`.
5. Demonstration output: `docs/PHASE4_DEMONSTRATION_OUTPUT.md`.

## Open items (blocking acceptance)

- H-DEC-3: approve or replace each numeric limit (`docs/PHASE4_H_DEC_LIMITS_REGISTER.md`).
- H-DEC-4: Windows memory cap (not enforced).
- H-DEC-5 and H-DEC-6: confirm the proposed defaults.
- EML character offsets: the plan does not state the basis.
- Migration `0013` named in the plan does not exist on this branch. No migration was added. WDS to confirm.
- Committed-row variant of H-35 for the partial and failed paths other than race and reparse.
- Phase 3 durable execution is not merged here. Its lease must be confirmed against the 30 s parser timeout.
- Phase 2 remediation (`0044`, `0045`) is uncommitted in its worktree and not on this branch.

Dependencies: `docs/PHASE4_DEPENDENCY_REGISTER.md`. Evidence: `docs/PHASE4_ENGINEERING_EVIDENCE.md`. Corpus:
`docs/PHASE4_SYNTHETIC_CORPUS.md`.

## Verdict

**PHASE 4 ENGINEERING INCOMPLETE — BLOCKERS REMAIN.** Blockers: the WDS decisions above, the EML offset basis, and
the committed-row H-35 gap. The engineering that could be done without those decisions is complete and passes.
