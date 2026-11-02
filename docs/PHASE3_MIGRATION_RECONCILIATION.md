# Phase 3 migration reconciliation procedure

Purpose: join Phase 3 (`0050_durable_execution`) to the Phase 2 remediation migrations (`0044_grant_revocation_lock`,
`0045_change_expiry_on_demand`) without editing any historical migration.

## Current state (this branch, base `46e0e14`)

- Chain head before Phase 3: `0043_phase2_review_fixes`.
- Phase 3 adds `0050_durable_execution`, with `down_revision = "0043_phase2_review_fixes"`.
- The chain is linear with one head on this branch. Verified by `alembic heads` and the head migration test.

## Why reconciliation is needed

Phase 2 remediation has `0044` and `0045` on its own uncommitted branch, both with `down_revision` `0043`. If both
branches are merged as they stand, the chain has two heads. Alembic will refuse to upgrade until they are joined.

## Procedure (run only after the Phase 2 remediation is committed and accepted)

1. Confirm the Phase 2 remediation commit that contains `0044` and `0045`, and that its revision IDs are unchanged.
2. On the Phase 3 branch, set the revision of `0050` to chain after the Phase 2 head: change its `down_revision` from
   `"0043_phase2_review_fixes"` to `"0045_change_expiry_on_demand"`. This edit is to the Phase 3 revision only. It is
   not an edit to a historical revision.
3. Check the chain: `alembic heads` must print exactly one head, `0050_durable_execution`.
4. Check the upgrade on a fresh database from empty: `alembic upgrade head` succeeds.
5. Run the migration cycle test (`tests/committed/test_migration_cycle.py`). Its downgrade target must change from
   `0043_phase2_review_fixes` to `0045_change_expiry_on_demand`, because that is the Phase 3 base once reconciled.
6. Rerun the Phase 3 full regression and the Phase 2 full regression on the joined branch.

## Rules

- Do not renumber a committed revision. Do not change a historical migration's text to resolve a collision.
- Phase 3 reserves `0050` onward. Phase 2 uses `0044` and `0045`. Neither reuses the other's ID.
- A merge of unaccepted Phase 2 code is not done automatically. Reconciliation is a separate, reviewed commit.
- If Phase 2 acceptance changes `0044` or `0045` before commit, repeat step 2 with the new head.

## Phase 3 chain after the final sprint

- Phase 3 revisions: `0050_durable_execution` (committed; `down_revision` `0043_phase2_review_fixes`),
  `0051_worker_fence_diagnostics` (`down_revision` `0050`), `0052_audit_correlation` (`down_revision` `0051`).
- Only `0050`'s `down_revision` changes in the reconciliation. `0051` and `0052` chain on `0050` and need no edit. The
  procedure above (steps 1 to 6) applies unchanged, with the downgrade target in step 5 also reading `0045` for the
  Phase 2 head.
- The reconciliation is a reviewed, separate commit. It is not performed in this branch. Phase 2's `0044` and `0045` are not in
  this branch.
