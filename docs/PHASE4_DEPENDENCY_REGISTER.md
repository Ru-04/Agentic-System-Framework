# Phase 4 dependency register

Base: `46e0e14`. Branch: `feature/foundation-phase-4`. Migration head on this branch: `0043_phase2_review_fixes` (no Phase 4 migration yet).

| ID | Dependency | Effect | Blocks |
|---|---|---|---|
| D-P2 | Phase 2 remediation (migrations 0044, 0045) uncommitted in its worktree | none on this branch; reconciliation required before merge | merge |
| D-P3 | Phase 3 durable execution (committed `e9d888a` on its branch; migration 0050) | not merged; Phase 4 does not depend on its code | merge; process isolation (H-32) would use the Phase 3 lease |
| D-DEC3 | WDS choice of numeric parse limits (H-DEC-3) | values in `intake/limits.py` are proposals | acceptance |
| D-DEC4 | Windows memory cap (H-DEC-4) | not implemented; process timeout plus size pre-check is the default | H-32 |
| D-DEC5 | DOCX locator fields beyond SCHEMA 4.2 (H-DEC-5) | not implemented | H-33 |
| D-DEC6 | HTML-only email handling (H-DEC-6) | not implemented | H-33, H-64 |
| D-ACC | Phase 1 and AI Read Contract v1 formal acceptance | not recorded | acceptance |
