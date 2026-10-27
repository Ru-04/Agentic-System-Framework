# Foundation Phase 4: independent QA handoff (partial)

Branch: `feature/foundation-phase-4`. Base: `46e0e14`. Status: **ENGINEERING INCOMPLETE**. Phase 4 is not accepted.

Implemented and verified on this branch:
- H-30: every segment-write failure fails only its version (`parse_service._fail`; test in `tests/integration/test_parse_hardening.py`).
- H-31 (partial): input size, PDF page count, DOCX archive size and inflate ratio, segments per version and characters per segment. Values are proposals (H-DEC-3).
- H-34: `partial` results record their flagged regions in `parse_error`.

Not implemented (see `docs/PHASE4_REQUIREMENTS_GAP_MATRIX.md`): H-32 process isolation and timeout; H-33 locator completions; reparse concurrency and idempotency tests; the versioned synthetic corpus; the synthetic demonstration; the Phase 4 migration and privilege evidence.

Verification: full regression `673 passed, 0 failed` (exit 0) on the Phase 4 database; ruff and strict mypy clean.
