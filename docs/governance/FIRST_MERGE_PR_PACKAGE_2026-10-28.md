# First development PR: review and merge-authorization package (28 October 2026)

**Status: PR NOT OPENED. Merge NOT executed.** No GitHub write credential is available to the assistant, so no pull request could be created. The complete PR content is below. Opening the PR and the merge both need explicit WDS authorization.

## 1. Exact SHAs
| Role | Ref | SHA |
|---|---|---|
| Source (frozen candidate) | `claude/pr-candidate-m1-s4-no-r4` | `79c90bc9055224622723bacb3766ad9130024020` |
| Target | `feature/increment-1-foundation` | `740b1695555303b29323a58df3e2345663d9821d` |
| Governance record (validation branch) | `claude/sprint4-full-validation` | `29439fc6c461a1a7e054573f3ce30dea00bcb71a` |

- Target is an ancestor of the candidate. Merge base equals the target. A fast-forward merge is possible.
- Candidate-only commits: 83 (82 engineering and documentation commits, plus one format-only commit).
- Target-only commits: 0.
- Diff: 177 files, +17,333 / −6 lines.

## 2. Exclusions and dependency checks
- **R4 chain excluded.** `af37f7b` through `89634a8` (11 commits, migrations `0020` to `0027`, Increment 3 Phase 1 R4 work) are not in the candidate. The handoff verdict "NOT READY FOR INDEPENDENT PHASE 1 REVIEW" still applies (`docs/PHASE1_INDEPENDENT_REVIEW_HANDOFF.md`).
- **Migrations in the diff:** none. Single head is `0019_least_privilege_intake_and_workflow`, identical to the target.
- **Scan false positive:** `src/webdesk/specialists/authority.py` matched an "authority" scan. It is the Milestone 1 Sprint 1 specialist action contract, not the R4 authority work. Its history is `41835b9` and `dd03118`, both before the R4 chain.
- **Configuration change:** `.github/workflows/specialist-ci.yml` is added. The target has no CI workflow.
- **Deletions (6 lines):** formatter reflow of one SQL string in `src/webdesk/intake/reassess.py` and two test files. AST-identical. The SQL function `webdesk_guard.fn_reassess_classification` is defined by migration `0013`, which is before the R4 chain.
- **No change to** `pyproject.toml`, `uv.lock`, `alembic.ini`, `docker-compose.yml` or `infra/`.

## 3. Proposed PR title and description

**Title:** `M1 Sprint 1–3 foundation and M2 Sprint 4 engineering (R4 chain excluded)`

**Description:**
- Includes the Milestone 1 specialist foundation, the adapter v0.2 and synthetic vertical slice, the Shopify and platform specialists, the Sprint 2 evidence services, the Sprint 4 investigation engine (synthetic), the controlled retrieval infrastructure, and the approved WooCommerce and BigCommerce pilot.
- Excludes the Increment 3 Phase 1 R4 authority and proof work (migrations `0020` to `0027`). It is not ready for independent review (`MERGE-SCOPE-01`).
- No live LLM calls. Production integration is not enabled (QA-07). Default-deny source access: only the two pilot boundaries are active. No retrieval runs without a configured transport.
- Review status: CI passes. Independent QA is not complete (see the blocker matrix).

## 4. CI evidence
| Run | Commit | Result | Scope |
|---|---|---|---|
| #49 | `79c90bc` (candidate head) | SUCCESS | Lint, format, mypy strict, unit tests, Postgres migrations, integration, committed and hardening tests |
| #47 | `30243a3` | SUCCESS | Same workflow on the validation branch. That tree includes the R4 commits, so it is not the PR tree |

Local results on `79c90bc`: 876 unit tests pass; ruff check and format pass on `src` and `tests`; strict mypy passes on `src/webdesk`.

Run #49 covers the candidate's own tree. The target's protection rules cannot be read without authentication, and the target has no CI workflow. The required-check configuration is therefore unverified.

## 5. Reviewer checklist
- [ ] Source SHA `79c90bc` and target SHA `740b169` are as stated above.
- [ ] Diff is the 83 candidate-only commits. No R4 migration or R4 authority file is present.
- [ ] Migration head is `0019`. No migration is added or changed.
- [ ] CI run #49 on `79c90bc` is SUCCESS.
- [ ] Only the two pilot boundaries are active (WooCommerce docs and BigCommerce product page). Test `test_only_the_pilot_boundaries_are_active` covers this.
- [ ] No live LLM dependency and no network call without a configured transport.
- [ ] Default-deny: unlisted domains and redirects are refused before any request.
- [ ] Synthetic and real evidence are labelled separately.
- [ ] Management and QA statuses are stated accurately (see the blocker matrix).

## 6. Merge-blocker matrix

| # | Requirement | Source of the rule | Classification | Current state |
|---|---|---|---|---|
| B1 | Merge needs explicit WDS authorization for the exact PR and reviewed SHA | Standing instruction in WDS directives: no protected-branch merge without explicit authorization; register `PUSH-01` ("No protected-branch merge") | **Mandatory merge blocker** | Not given. Awaiting approval |
| B2 | Successful required checks on the proposed head | Standing instruction: no protected-branch merge without successful required checks; register `CI-01` | **Mandatory merge blocker** | CI #49 on `79c90bc` SUCCESS. The target's required-check configuration could not be read (HTTP 401), so it is unverified |
| B3 | QA-07 run-time authority enforcement: "make run-time enforcement a hard gate before any integration" | `docs/evidence/AS_REVIEW_PACKET_2026-10-23.md` line 30 (Q7); register QA-07-MERGE-01 | **MERGE BLOCKER (WDS ruling, 28 Oct 2026).** Blocks merge into the integration branch | Authority is declared, not enforced at run time. The candidate contains no run-time enforcement |
| B4 | No production integration before QA-07 | Standing restriction, register | **Production-release gate** | Production blocked. This PR does not enable production |
| B5 | PG personal independence, findings and sign-off | Milestone 1 tracker (`MILESTONE1_ACCEPTANCE_TRACKER_2026-10-23.md`); S4 acceptance conditions | **Later sprint acceptance condition** for Sprint 4. Not a written merge requirement in any record found. WDS to confirm whether it blocks this merge | NOT OBTAINED. Management-reported PASS only (S4-QA-02) |
| B6 | Milestone 1 controls: Sprint 1 and 2 human QA, specification approval, independent Milestone 1 testing, final CI | `MILESTONE1_ACCEPTANCE_TRACKER_2026-10-23.md`; decision G9 | **Milestone 1 closure gate.** Not a merge blocker by any written rule found. WDS to rule | Milestone 1 is NOT accepted and NOT closed |
| B7 | Authorship of Sprint 1–3 work verified (BD contribution) | Milestone 1 tracker, section on BD | **Independence condition for review.** Not a merge blocker | Not verified. Git authorship is `toarushiS` only |
| B8 | R4 release-blocking findings resolved before R4 is merged | `PHASE1_INDEPENDENT_REVIEW_HANDOFF.md` section 7 | **Mandatory blocker for the R4 chain only** (excluded here) | Open |
| B9 | Shopify 55-pair human relevance evaluation | Register; S4 conditions | **Later sprint acceptance condition** | 0 of 55 |
| B10 | Frozen Sprint 4 acceptance criteria reconciliation | S4 conditions | **Later sprint acceptance condition** | Proposed document; WDS approval pending |

## 7. Evidence references
- Candidate: `claude/pr-candidate-m1-s4-no-r4` at `79c90bc`.
- CI: run #49 (candidate), run #47 (`30243a3`).
- R4 exclusion: `docs/governance/MANAGEMENT_DECISION_REGISTER_2026-10-26.md`, MERGE-SCOPE-01.
- Pilot scope: `docs/governance/SOURCE_PILOT_RESULTS_2026-10-28.json`, `docs/specialists/REAL_EVIDENCE_COVERAGE_2026-10-28.md`.
- Sprint 4 acceptance: `docs/governance/SPRINT4_ACCEPTANCE_RECORD_2026-10-28.md`.
- Sprint 5 readiness (not started): `docs/governance/SPRINT5_TRANSITION_PACKAGE_2026-10-28.md`.

## 8. Recommendation
**HOLD.** B3 is ruled a merge blocker (QA-07-MERGE-01). Merge waits for run-time enforcement or a written WDS waiver, and for a ruling on B5, and gives explicit merge authorization for the exact PR and SHA `79c90bc`. Technical checks pass. The open items are governance decisions, not failing tests.
