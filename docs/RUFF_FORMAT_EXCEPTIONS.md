# Ruff formatting exceptions (recorded 2026-10-26; corrected 2026-10-28 in Phase 4; updated in the Phase 2 QA remediation and the Phase 2–7 integration)

`ruff check` is clean for `src`, `tests` and `migrations`. `ruff format --check` reports four files, all of which were
already unformatted when they were committed. They are **not** reformatted, for these reasons:

- Four files are **committed migrations**, and historical migrations are frozen. Rewriting them for formatting alone would
  change their source text and invite the question of whether the applied revision changed. The executed SQL is the same
  either way, but the rule is no rewrite of history for formatting.
- No committed test is an exception any longer. Committed tests are formatted when they are otherwise edited.
  `tests/hardening/test_privilege_hardening.py` was edited and formatted in Phase 2 (QA F-11), and
  `tests/integration/test_reassessment.py` was edited and formatted by Phase 7 H-77. The integration of Phases 2–7 keeps
  both formatted.

| File | Introduced by | Status |
|---|---|---|
| `migrations/versions/0017_least_privilege_column_grants.py` | 740b169 | Frozen migration. Exception. |
| `migrations/versions/0019_least_privilege_intake_and_workflow.py` | 740b169 | Frozen migration. Exception. |
| `migrations/versions/0020_r1_r2_n1_hardening.py` | 740b169 | Frozen migration. Exception. |
| `migrations/versions/0040_last_administrator_lock.py` | 82585db | Committed revision, reverted to its committed text rather than reformatted. Exception. |

Files this work created or edited are formatted (including `tests/hardening/test_privilege_hardening.py`, edited in
Phase 2, and `tests/integration/test_reassessment.py`, edited in Phase 7): `migrations/versions/0041_ai_read_v1.py`, `tests/hardening/test_privilege_audit.py`, and every file under `src/webdesk` and
the new AI tests.

Formatting a migration does not change its SQL. The executed text of each revision is compared with its committed original in
the verification evidence. Changing a frozen migration for formatting alone would need its own WDS governance exception, and no
such exception is requested here.
