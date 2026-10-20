# Claude Code handoff — Phase 1 R1–R4 closure

The WDS stakeholder has **approved R4 Option A**, decision P-INC3-ACTOR-SESSION-06. Treat the attached `PHASE1_R4_OPTION_A_IMPLEMENTATION_CONTRACT.md` and Decision Register Amendment A2 as normative post-baseline policy. Do not choose Option B or accept the actor-identity risk.

1. Inspect current branch, code, migrations, `docs/INCREMENT_3_EVIDENCE.md` and full independent review. The ZIP has specifications, **not** the live repository.
2. Propose the security-sensitive R4 trusted-issuer/session-proof architecture and explicitly identify keys, DB roles, signature/proof fields and transactional checks. If choices expose a new business/policy tradeoff, flag for approval; no untrusted mutable session-setting as actor proof.
3. Implement R1 (`search_path`, schema-qualified objects and TEMP restriction), R2 (24-hour ceremony/approval DB bounds, immutable start/created time, test 25h refusal), R3 (restore the missing EVAL-F11f `coverage_sufficient` denial+audit test), R4 verified-session binding plus credential/session DML restrictions, N1 reservation protection and N2 deployment checklist/PG16 role setup. Add new forward Alembic migrations; never edit 0001–0019 historical migrations.
4. Harden only Phase 1. Write tests as actual restricted DB login on committed rows. Include tampering with actor arguments/session context, forged/replayed/revoked session proofs, two-approver impersonation, function name shadowing, arbitrary reservation release and deadline extension.
5. Re-run full suite on fresh DBs, hardening tests, Ruff, strict mypy and down/up migrations. Produce honest evidence with actual inputs/expected/observed/role and note any unverified checks.
6. Stop for independent review before Phase 2. Do not push/merge without instruction.

**Implementation not performed by this document.**
