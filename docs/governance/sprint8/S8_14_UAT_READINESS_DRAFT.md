# S8-14 Sprint 9 UAT readiness package (DRAFT, not a UAT entry recommendation)

**Requirement:** S8-14 (RED in the dependency matrix). The package depends on Sprint 6, Sprint 7 and Sprint 8 completion. **None of those three is complete.**
**Recommendation:** NOT READY. This draft records what exists and what is missing. It does not recommend UAT entry.
**Baseline:** repository state `866b314` and later Sprint 8 commits on `feature/sprint8-hardening-resilience`.

## 1. Supported scope (what the repository actually contains)
- Foundation: authentication through the separate authority process; operation proofs; deny-by-default authorization; projects, memberships and grants; contact change and reset flows; source upload and intake parsing in an isolated child process; durable run and outbox workers; AI read contract `ai-read/v1` (read-only).
- Verified in the Sprint 8 engineering runs: the database security regression (132 tests), unit regression (312 tests), Sprint 8 negative and replay checks (33 passed, 3 BLOCKED).

## 2. Not in scope or not built
- Seven specialists and their integration (S6-INT, not complete).
- Review, approval, estimation, SOW and report export (Sprint 7, not built in this repository).
- Workspace identity (OPEN-11).
- Production deployment, real email transport, production key custody and identity provisioning (`docs/PRODUCTION_BOUNDARY.md`).

## 3. Known limitations (carried forward)
- The three BLOCKED tests: OPEN-11 workspace read; S6-INT specialist path; S6-INT run-level recovery.
- No approved performance SLO. S8-09 and S8-10 are measured baselines only.
- Restore is rehearsed on the current head only (S8-12). The final-schema rehearsal is open (OPEN-18).
- No CI workflow exists in the repository. The S8 gate runs by script (`scripts/s8_qa_gate.sh`).
- Manual monitoring only. No alerting or paging is wired (S8-11 runbook).
- Credential exposure T-31 closed by WDS management attestation. No independent technical evidence in the repository.

## 4. Environment setup (for UAT, not yet provided)
- Dedicated non-production PostgreSQL cluster, with restricted application logins and no superuser grants to application roles.
- Owner-signed installation authorization. Its key custody is open.
- Email transport: capture only. No real delivery is approved.

## 5. Rollback and recovery steps
- Database: restore from the logical dump procedure in `S8_12_RESTORE_REHEARSAL.md`, on the current head only.
- Workers: stop, then restart with a new owner name. Expired leases are reclaimed (`S8_11_OPERATIONS_RUNBOOK.md` §3.1).
- Code: revert to a prior commit on a non-protected branch. No deployment is performed by this repository.

## 6. Blocking defects
- None open in the Sprint 8 engineering scope.
- Blocking for UAT entry: every dependency in §2, plus the final independent QA of the Sprint 8 candidate, plus WDS formal acceptance.

## 7. Explicit UAT entry recommendation
**NOT READY.** Recommended action: keep Sprint 9 UAT entry on hold until Sprint 6 integration, Sprint 7 completion and final Sprint 8 QA are complete, and WDS has accepted them. This is an engineering recommendation only. The decision belongs to WDS.
