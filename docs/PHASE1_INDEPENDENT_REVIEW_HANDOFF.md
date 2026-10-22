# Phase 1 Independent Review Handoff — Increment 3 (R4 Option A)

**Verdict at handoff: NOT READY FOR INDEPENDENT PHASE 1 REVIEW.** The blockers in section 7 must be resolved or
explicitly accepted by WDS first. Passing tests do not establish security approval. Nothing here is pushed, merged or
deployed.

## 1. Baseline and governance

- Approved baseline: v0.3.10 limited Foundation, with Amendment A1 (decisions P-INC3-LAST-ADMIN-04 and
  P-INC3-TEST-CLOCK-05) and Amendment A2 (decision P-INC3-ACTOR-SESSION-06, R4 Option A).
- Normative contract: `WebDesk_Agentic_Requirement_Platform_Specs/PHASE1_R4_OPTION_A_IMPLEMENTATION_CONTRACT.md`.
- Decision decisions recorded: Decision 1 (authority-issued, DB-recorded single-use operation proofs, no PostgreSQL
  Ed25519) and Decision 2 (authority may create, update and revoke credentials; the application login has no direct
  credential or session access).
- Historical migrations 0001–0020 are not edited. The R4 work is forward-only, in revisions 0021–0027.
- Foundation scope: Phase 1 only. No Phase 2, no AI integration, and no AI-engine file was modified.
  `docs/AI_ACCESS_CONTRACT_PROPOSAL_v0.1.md` is PROPOSED, not approved.

## 2. Commits (branch `feature/increment-1-foundation`, local, not pushed)

| Commit | Content |
| --- | --- |
| b126ed8 | R4 stage 1: authority role, operation-proof table (0021) |
| 98231e7 | M1: authority privileges (0022), authority entry points |
| 735ff15 | M2: authority process, write boundary for credentials and sessions (0023), N26 converted |
| 17d6649 | M3a: proof-bound account state; proof-guarded writes (0024, 0025) |
| 9c4e9da | M3b: proof-guarded contacts (0026); EVAL-F11j module |
| b0d5df8 | lint follow-up |
| d49f6b7 | evidence status; AI access proposal |
| 267c934 | closure: proof-gated token issuance (0027); rollback and extended EVAL-F11j tests |

Migration sequence: 0021 authority proofs; 0022 authority privileges; 0023 authority boundary (credentials and sessions
restricted); 0024 proof enforcement (epoch and revision bound proofs, Administrator gate); 0025 proof-guarded
membership, grants and archive; 0026 proof-guarded contacts; 0027 proof-gated token issuance.

## 3. Security invariants

1. A session is valid only while unrevoked, unexpired, active and matched to the account's current session epoch.
2. Only `webdesk_authority` writes credentials and sessions and issues proofs. The application login has no such privilege.
3. A proof is bound to one operation, one resource, one live session, the session epoch and contact revision at issue,
   and is spent at most once (committed effect). An Administrator-only operation is issued only to an Administrator.
4. The actor of a privileged mutation is the proof's actor, never a caller-supplied ID, for every mutation covered by
   section 5.
5. A refusal is audited, and the audit persists through the transaction runner.
6. Reset-token issuance requires an Administrator-issued proof for the target account.

## 4. Attack-test evidence (restricted login `webdesk_app_login`, authority as a separate process)

- `tests/hardening/test_app_role_negative.py`: N1–N32, including N26 (forged session refused) as an ordinary test.
- `tests/hardening/test_eval_f11j.py`: 17 cases (forged session and credentials, forged or caller-supplied actor, random
  proof, impersonation, wrong resource, wrong operation, replay, concurrent use, revoked session, expiry after 31 s,
  self-approval, non-administrator approval, direct approval and membership writes, legitimate disable).
- `tests/hardening/test_eval_f11j_extended.py`: 20 cases (unprotected guard entry points refused with 42501, wrapper with a
  made-up proof refused, reset without proof refused and audited, reset from a non-administrator refused, legitimate reset
  issuance, epoch change invalidates an earlier proof, stale session cannot be validated, role assumption refused, authority
  login membership limited to `webdesk_authority`).
- `tests/hardening/test_proof_rollback.py`: 5 cases (failure before the protected operation leaves the proof usable;
  rolled-back mutation has no committed effect and the retry commits once; a committed operation spends the proof;
  concurrent use when the first attempt rolls back commits once; refusal audit committed by the runner).

## 5. Trust boundaries and legitimate exceptions

- **Authority process** (`python -m webdesk.authority.server`): separate OS process, loopback only, shared secret of at
  least 32 characters, refuses `WEBDESK_ENV=production`, login role member of `webdesk_authority` only.
  **Not a production authority.** No production key management or deployment exists.
- **Ceremony role** (`webdesk_ceremony`): installation, recovery and the expiry sweep. It still inserts role assignments
  (bootstrap appointments), inserts and updates users and approvals, and holds column-level UPDATE on `users`. These are
  system flows governed by ceremony tokens, not by actor IDs. Narrowing needs review (blocker 4).
- **Outbox worker**: the application role keeps UPDATE on `outbox_notices` (lease, sent, dead-letter). Not an
  authorization decision. Blocker 3.
- **Activation tokens**: issued by the system after an approved contact approval (`fn_issue_activation_token`), not by an
  actor. Bounded by the database rule that requires a live approved approval.

## 6. Remaining risks

- A rolled-back transaction leaves its proof unspent until expiry (30 s). It cannot produce a second committed effect,
  but WDS must decide whether Amendment A2's "single-use" requires burning a proof on rollback. Burning would need a
  detached commit, which would separate authorization from the mutation; that was not implemented.
- The contact-revision check is exercised only together with the session-epoch change of the same approval, not in
  isolation. Isolating it requires an owner-level fixture.
- Reset initiation is Administrator-only by implementation choice. WDS must confirm it.

## 7. Release-blocking findings (must be resolved or accepted before READY)

1. **Unverified actor on intake and run paths.** Source upload (`ingest_source`), run start and run control (`start_run`,
   controls), reparse (`reparse_source_version`) and source-content reads take a caller-supplied actor. The application role
   can also insert directly into `sources`, `source_versions`, `workflow_runs`, `workflow_jobs`, `workflow_checkpoints`,
   `run_input_snapshots`, `source_segments` and `dependency_edges`. These are privileged mutations under the approved matrix
   and are not yet covered by the proof boundary.
2. **No production authority.** The authority, its key handling and its deployment are not built. Authority isolation is
   verified only for the local integration process.
3. **Outbox delivery writes under the application role** (section 5): needs a narrow worker role or guard functions, or an
   accepted residual.
4. **Ceremony column-level UPDATE on `users`** is broader than the installation and recovery flows need.
5. **Rollback semantics** (section 6): WDS decision.
6. **Reset-initiation policy** (section 6): WDS confirmation.

## 8. Reproduction

Prerequisites: PostgreSQL 16.4 (Docker Compose service `postgres`, host port 5433), roles and databases created by the
migrations. Local environment files (not committed): `.env.integration.local` (owner URLs with CREATEROLE for test
provisioning) and `.env.hardening.local` (owner and application login passwords).

```bash
# fresh databases, then migrate
docker compose up -d postgres
# migrate integration base and hardening databases to head (owner URL from .env.integration.local)
WEBDESK_DATABASE_URL=<integration owner URL> alembic upgrade head
# full suite
WEBDESK_TEST_DATABASE_URL=<integration owner URL> WEBDESK_INTEGRATION_OWNER_URL=<same>
WEBDESK_HARDENING_OWNER_URL=<webdesk_test_owner URL on webdesk_hardening>
WEBDESK_HARDENING_APP_URL=<webdesk_app_login URL on webdesk_hardening>
python -m pytest -q
# lint and types
ruff check src tests migrations
mypy --strict src/webdesk
```

Last verified run on fresh databases at commit 267c934: **464 passed, 0 failed**. Ruff and strict mypy clean.
Do not run other suites against the same databases concurrently; a concurrent run produced 54 spurious failures that
disappeared on a clean run.
