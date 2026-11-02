# Production readiness assessment: WebDesk Agentic Requirement Analysis Platform, Foundation Phases 1–7

Read-only assessment. Every observation below comes from `git show`, `git ls-tree`, `git log` or `git grep` against the
refs listed. Nothing was checked out, run, tested or connected to. Secrets under `C:/Users/baps/.webdesk-*` were not read.
The integration branch `feature/foundation-integration-p2-p7` was ignored.

## Refs and ref keys used in citations

| Key | Ref | HEAD |
|---|---|---|
| **P7** | `feature/foundation-phase-7` (contains Phases 5 and 6) | `09d1bdb` |
| **P2** | `feature/foundation-phase-2` | `518ab67` |
| **P3** | `feature/foundation-phase-3` | `6e8f574` |
| **P4** | `feature/foundation-phase-4` | `178a419` |
| **SPEC** | `WebDesk_Agentic_Requirement_Platform_Specs/` (identical on all four refs, checked by `git diff --stat`); cited from P7 | — |

`PB` = `docs/PRODUCTION_BOUNDARY.md`, `DC` = `docs/DEPLOYMENT_CHECKLIST.md`, `HP` = `docs/INCREMENT_3_HARDENING_PLAN.md`,
`GDR` = `docs/GOVERNANCE_DECISION_REGISTER.md`, `DR` = `SPEC/DECISION_REGISTER.md`. All `docs/` files cited without a ref are identical
on P2, P3, P4 and P7, except where a ref is named (`HP` differs on P4 by one status line; `GDR` on P4 has 172 extra lines).

---

## 1. What "production ready" means in this project's documents

The project defines production sign-off in one place:

> PB:91–95 (P7): production sign-off requires an independent Phase 1 review that passed; each blocker in PB closed with evidence;
> `docs/DEPLOYMENT_CHECKLIST.md` completed; and an explicit WDS approval of the production deployment. PB:95 adds: "No item in this
> document is approved." PB:3 states: "Status: production deployment is BLOCKED."

The criteria assessed below are taken from these sources, and only these:

- **PB §1–§7** (PB:21–82): trusted authority deployment, signing-key and secret custody, authenticated transport, separate database
  identities, worker deployment and isolation, approved email transport, operational monitoring and recovery.
- **DC** (DC:6–59): database roles, fail-closed configuration, open decisions, and the PostgreSQL role and privilege setup.
- **SPEC/GATE1_IMPLEMENTATION_AUTHORIZATION.md:34–36**: "Production prerequisites still open".
- **DR**: D-13 retention (DR:19), D-14 release thresholds (DR:20), D-16 hosting as a "deployment blocker" (DR:22), production-blocking
  configuration prerequisites (DR:91), production configuration still open (DR:102).
- **SPEC/ARCHITECTURE.md**: secrets outside code, TLS for deployments, database least privilege and backup/restore, structured
  operational logs (ARCH:262); threat modelling and review of the deployment environment as release prerequisites (ARCH:264);
  production hosting, secrets manager, backups and egress as stakeholder decisions (ARCH:273); retention before production (ARCH:329).
- **SPEC/GOVERNANCE.md**: retention defined before production (GOV:128, GOV:283); D-16 (GOV:286); zero-Administrator offline
  recovery under an approved runbook (GOV:291).
- **SPEC/EVALUATION_PLAN.md**: `EVAL-RETENTION-001` (EVAL:241), `EVAL-RELEASE-OWNER-001` (EVAL:242), `EVAL-DEPLOYMENT-GATE-001`
  "Block production deployment ... until approved hosting/egress configuration exists" (EVAL:244).
- **HP** (P7): §6 security acceptance criteria (HP:270–282), §7 testing and rollback (HP:286–302), §9 decisions H-DEC-1 to H-DEC-12
  (HP:329–346), §10 scope (production deployment, hosting, egress and production email are out of Increment 3, HP:352–358);
  H-22 heartbeat (HP:112); H-26 worker entry point, "A process manager is required in production" (HP:116); H-50 to H-52 (HP:148–150).
- **Phase records**: dependency registers and known limitations of Phases 2–7 (cited per row).

No document in the repository defines numeric availability, latency, capacity or recovery-time targets. Those are not assessed and are
listed as NOT DEFINED where a document names the topic without values.

---

## 2. Criteria table

Status key: **MET** (criterion stated and evidenced), **PARTIAL** (some evidenced, some not), **NOT MET** (stated, not satisfied),
**NOT DEFINED** (named by the documents but without a concrete criterion or value).

### 2.1 Sign-off conditions (PB:91–95)

| # | Criterion | Source | Evidence found | Status |
|---|---|---|---|---|
| S-1 | Independent Phase 1 review passed | PB:93 (P7) | Last recorded verdict: "READY FOR INDEPENDENT PHASE 1 RE-REVIEW (non-production scope). This is not acceptance." (`docs/PHASE1_INDEPENDENT_REVIEW_HANDOFF.md:252`, P7). Open items before acceptance: historical migration exception verification, R-F2 scope, remote-history question (same line; GDR:368, GDR:373–376, GDR:402–403). P3 register: "D-1e Phase 1 independent acceptance — Not recorded" (`docs/PHASE3_DEPENDENCY_REGISTER.md:15`, P3). No later acceptance record found by `git grep` on any ref. | NOT MET |
| S-2 | Each PB blocker closed with evidence | PB:19, PB:93 (P7) | See §2.2. None of PB §1–§7 is closed. PB:82 "none of these procedures is written or rehearsed". | NOT MET |
| S-3 | Deployment checklist completed | PB:94; DC:6–59 (P7) | All 16 checkbox items in DC (lines 8, 10, 12, 14, 15, 19, 20, 21, 22, 24, 26, 31, 32, 33, 34, 35) are `[ ]`. DC:3–4: "It does not authorize one. Hosting is deferred (D-16)". | NOT MET |
| S-4 | Explicit WDS approval of production deployment | PB:94–95 (P7) | PB:95 "No item in this document is approved." GDR:271 "No production service was deployed. No readiness claim is made." No approval record found on any ref. | NOT MET |

### 2.2 Production boundary blockers (PB §1–§7)

| # | Criterion | Source | Evidence found | Status |
|---|---|---|---|---|
| B-1 | Trusted authority deployed under its own OS identity, reachable only from the application tier | PB:21–27 (P7) | `src/webdesk/authority/server.py:7–15` (P7): "for local, non-production integration only ... not a production authentication service". `server.py:353–354` refuses any non-loopback bind; `server.py:362–363` refuses `WEBDESK_ENV=production`. PB:27 "the authority and the application run on one development machine". | NOT MET |
| B-2 | Signing-key and secret custody: KMS or hardware store, documented rotation and revocation, separate keys per environment | PB:29–35; DC:22–23, DC:26–27; DR:91 (P7) | Secrets are environment values: `config.py:43–44` (DB URLs), `config.py:65` (outbox key), `server.py:10` (authority bearer secret). `.env.example:29–30` placeholder only. `.gitignore:11–12` ignores `.env.hardening.local`, `.env.integration.local`. No key-management integration found in `src` (P7). PB:35 "no key custody, no rotation procedure, no revocation procedure". | NOT MET |
| B-3 | Mutually authenticated, encrypted transport app↔authority (e.g. mTLS); TLS for deployments | PB:37–43; ARCH:262 (P7) | Authority is `ThreadingHTTPServer` plain HTTP (`server.py:26`, `server.py:170`) with a bearer secret. `git grep` for `sslmode|tls|https|certfile` in `src`, `migrations`, `docker-compose.yml` (P7) finds only SMTP STARTTLS (`delivery/smtp.py:36`, `:58–59`, `:87`, default on). No TLS for the HTTP API or the database connection. | NOT MET |
| B-4 | Separate DB identities provisioned by deployment (app, authority, intake worker, outbox worker logins; non-superuser migration owner) | PB:45–55; DC:8–15, DC:48–59 (P7) | Role model implemented and tested in non-production: privilege audit (GDR:112–183, GDR:294), worker login (`tests/committed/test_worker_login.py`, GDR:273–281), outbox identity (GDR:242–249), ceremony narrowing (GDR:251–264). Phase 7 QA confirms privileges as intended (`docs/PHASE7_ENGINEERING.md:87–90`, P7). Production logins not provisioned (by design: "migrations do not hold secrets", PB:47–48). Local compose uses superuser `webdesk_owner` (`docker-compose.yml:6–7`, P7; PB:54–55 "must not be copied"). Migration 0011 grants `webdesk_guard_owner` to `CURRENT_USER` (`docs/PHASE5_X7_QA_CLOSURE.md:81–84`, P7), so the migration owner choice affects least privilege. | PARTIAL (code and tests MET; production provisioning NOT MET) |
| B-5 | Each worker in its own process, own login, restart policy; lease and retry parameters documented | PB:57–63; HP:116; P3 register D-4, D-5 (`docs/PHASE3_DEPENDENCY_REGISTER.md:23–24`, P3) | P7 has no `src/webdesk/worker/` (`git ls-tree`, P7). Phase 6 entry points are one-shot (`docs/PHASE6_X8_ENGINEERING.md:17`, `:58`, P7). On P3, `python -m webdesk.worker` exists (`src/webdesk/worker/__main__.py:1–17`, P3) with SIGTERM stop (`:92–98`), stall exit 70 and `--report-stuck`; H-26 "done for the Phase 3 interface ... non-production behaviour" (`docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md:20`, P3); lease 120 s and heartbeat documented (`docs/PHASE3_JOB_LEASE_LIFECYCLE.md:28–40`, P3). Process manager and production worker login: "Production only", deployment (P3 register:23–24). Phase 3 is not accepted or merged. | NOT MET |
| B-6 | Approved email transport, delivery test to an approved contact, then `WEBDESK_RESET_DELIVERY=smtp`, `WEBDESK_SMTP_VERIFIED=true` | PB:65–73; DC:20 (P7) | `delivery/smtp.py:72–88` (P7): disabled unless every gate is set. `.env.example:18` uses `capture`. PB:73 "no real delivery is enabled". GDR:221 same. Settings allow only `email_transport: Literal["capture","none"]` (`config.py:53`). | NOT MET |
| B-7a | Monitoring: alerts on `ops.alert.delivery_failed`, `authority.proof.refused`, `source.content.denied` volumes, failed authentication | PB:77–78 (P7) | PB:78 "None is wired to an alerting system". `git grep` for `logging|getLogger` in `src` (P7) returns no hits. `in_app_alerts` table exists (migration 0044) but "No read path or UI for `in_app_alerts` exists" (`docs/PHASE6_X8_ENGINEERING.md:59`, P7). `/health` returns a static `{"status":"ok"}` with no dependency check (`src/webdesk/api/app.py:40–42`, P7). No metrics/alerting library in `src` (P3 grep for prometheus/sentry/opentelemetry/metric: none). | NOT MET |
| B-7b | Backup and restore of the database, tested | PB:79; ARCH:262; DR:22 (P7) | No backup or restore artefact, script or document found (`git grep` for `backup|restore|pg_dump|pg_basebackup` in `src`, `migrations`, `docker-compose.yml`, `docs` on all four refs: only unrelated hits). PB:82 "none ... written or rehearsed". | NOT MET |
| B-7c | Zero-Administrator recovery (GD-002) rehearsed with the approved owner signing ceremony; approved offline recovery runbook | PB:79–80; DC:33; GATE1:36; GOV:291 (P7) | GD-002 policy implemented as a refusal only (GDR:23–29). No runbook in `docs/` on any ref (`git grep runbook`). GATE1:32 excludes "execution of the offline restore runbook" from Gate 1. | NOT MET |
| B-7d | Incident response for compromised authority, compromised worker, leaked read grant | PB:80–81 (P7) | No incident-response document on any ref (`git grep incident` returns only a test-harness incident note, `docs/INCREMENT_3_EVIDENCE.md:829`). | NOT MET |

### 2.3 Other stated production criteria

| # | Criterion | Source | Evidence found | Status |
|---|---|---|---|---|
| C-1 | Production hosting, network egress, vendor allowlist approved (`EVAL-DEPLOYMENT-GATE-001`) | DR:22; GOV:286; EVAL:244; DC:34; ARCH:273 (P7) | D-16 "DEFERRED BY WDS — deployment blocker" (DR:22). No hosting artefact (no Dockerfile, no process definition, no CI file; `git ls-tree -r`, P7). `create_app` (`api/app.py:20`) has no caller in `src` and there is no ASGI entry module (`git grep "create_app("`, P7). | NOT MET |
| C-2 | Local development artefacts: pinned dependencies, `.env.example` with placeholders, documented PostgreSQL via compose, Alembic | ARCH:268–272 (§14) (P7) | `pyproject.toml:6–20` exact pins; `.env.example:1` "Placeholders only"; `docker-compose.yml:1–15` PostgreSQL 16.4 on 5433; `migrations/env.py:13–20` refuses to run without `WEBDESK_DATABASE_URL`. | MET (local only; not a production criterion) |
| C-3 | Production profile fails closed; capture sink refused in production | DC:17–27; GATE1:25–26 (P7) | `config.py:133–154` refuses production with any missing item and refuses `capture` (`:146–150`). `delivery/transport.py:49–50` refuses capture in production. However: (a) `email_transport` can only be `capture` or `none` (`config.py:53`), and `none` is reported missing (`config.py:106–107`, added to production missing at `:143`), so no production configuration can currently pass `validate_for_profile`; (b) `validate_for_profile` is called only from `cli/install.py:65` (`git grep`, P7), not by the HTTP application factory. | PARTIAL |
| C-4 | Domain allowlist and alias denylist set to WDS-approved values | DC:21; DR:91; GATE1:36 (P7) | `.env.example:13–14` empty. No approved values recorded. | NOT MET |
| C-5 | Owner identity, signing-key custody, independent verification procedure (BOOTSTRAP-02) | DC:22–23, DC:32; DR:91; GATE1:36 (P7) | Install and recovery CLIs exist and verify Ed25519 signatures (`cli/install.py:1–13`, `ceremony/install.py`; H-74 digest uniqueness and operator/verifier binding, `docs/PHASE7_ENGINEERING.md:28`, `:36`, P7). No signing tool in `src` (no private-key code by `git grep`). Owner identity, key custody and verification procedure undecided (DC:32). Operator and verifier IDs are "declared, not authenticated" (GDR:263–264, GDR:301, GDR:406). Artifacts signed before H-50/H-74 are refused and must be re-signed (`docs/PHASE6_X8_ENGINEERING.md:61`; `docs/PHASE7_ENGINEERING.md:65`, P7). The production install path is also blocked by C-3(a). | NOT MET |
| C-6 | Recovery CLI with refusals before insert, audited, verifier from the artifact (H-50) | HP:148 (P7) | Implemented and QA-passed: `docs/PHASE6_X8_ENGINEERING.md:13–16`, `:77` (P7). Phase 6 WDS formal acceptance "PENDING" (`:83`, `:100`). | PARTIAL |
| C-7 | Sweep and outbox entry points, scheduled by the worker (H-51, H-26) | HP:149, HP:116 (P7) | One-shot CLIs `cli/sweep.py`, `cli/outbox.py` (P7; `docs/PHASE6_X8_ENGINEERING.md:17`). "Repeated passes need the Phase 3 worker (H-26), which is not in this branch" (`:58`). Scheduling exists only on P3 (`worker/maintenance.py`; `docs/PHASE3_DECISION_EVIDENCE.md:127–134`, P3). | PARTIAL |
| C-8 | Outbox: every transport error audited, dead-letter real, in-app alert (H-52, H-DEC-8); heartbeat renewal (H-22) | HP:150, HP:112 (P7) | Catch-all, dead-letter and `in_app_alerts` complete (`docs/PHASE6_X8_ENGINEERING.md:19`, `:21–22`, P7). Periodic heartbeat "Partial: periodic heartbeat is a Phase 3 dependency" (`:20`, `:57`). Heartbeat implemented on P3 (`docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md:16`, P3), not merged. | PARTIAL |
| C-9 | Outbox dead-letter threshold approved | DC:24–25, DC:35; GATE1:36; DR:102 (P7) | `config.py:62` setting exists; `.env.example:28` unset; no approved value. | NOT MET |
| C-10 | Final rate limits approved and set | DC:24–25, DC:35; GATE1:36 (P7) | Authority limits are code constants: reset 5/contact and 100/IP per 15 min, login 10/account-IP and 200/IP per 15 min (`authority/server.py:50–57`, P7). `WEBDESK_RL_*` settings are required by `config.py:88–97`, but `git grep` finds no use of `settings.rl_*` outside `config.py` (P7). `.env.example:22–27` unset. H-72 atomic limits implemented (`docs/PHASE7_ENGINEERING.md:26`). Login limiter is per client address and stored in the database (GDR:302–303). | NOT MET |
| C-11 | Password minimum and session lifetime confirmed (C-8, H-DEC-10) | DC:31; HP:344 (P7) | `auth/service.py:13–14` (P7): `SESSION_TTL` 8 hours "is a placeholder ... must be approved before production use". No confirmation recorded. | NOT MET |
| C-12 | Outbox encryption key generated per environment, in an approved secrets store; custody and rotation decided (C-9) | DC:26–27; HP:344 (P7) | AES-256-GCM sealing implemented (`crypto/contact_box.py:19`, `:43–47`, P7). Custody and rotation "not decided" (DC:27; `docs/INCREMENT_2_PLAN.md:177`). | NOT MET |
| C-13 | Database privilege setup: non-superuser migration owner, `webdesk_guard_owner` NOLOGIN, PUBLIC CREATE/TEMP revoked, pinned `search_path` | DC:43–56 (P7) | Verified in tests on fresh non-production databases (DC:45–46; GDR:294 "No PUBLIC EXECUTE on any guard, authority or public function"; `docs/PHASE7_ENGINEERING.md:57`). `REVOKE CREATE ON SCHEMA public` is an operator step for databases created outside migrations (DC:54–55). Not performed on any production database (none exists). | PARTIAL |
| C-14 | Migration procedure and rollback: each phase `upgrade head`, `downgrade -1`, `upgrade head` on a fresh database; tested downgrades | HP:296–302 (P7) | Per-branch round trips recorded: P7 `docs/PHASE7_ENGINEERING.md:57` and QA `:87–90`; P6 `docs/PHASE6_X8_ENGINEERING.md:45`; P3 `docs/PHASE3_QA_RETEST_DELTA.md:18–21`, `:137–138`. Limits: full downgrade to base unsupported on a shared cluster (0001 drops roles, `migrations/versions/0001_gate1_foundation_schema.py:589–590`, P7; GDR:304). The four refs fork at `0041_ai_read_v1`: P7 `0042_x7_staleness_archive` and P2/P3/P4 `0042_phase2_identity_controls` both have `down_revision = "0041_ai_read_v1"`; P2 `0044`–`0046` and P7 `0044`–`0049` share numeric prefixes; P3 `0050` has `down_revision = "0043_phase2_review_fixes"` (checked with `git show`). "Reconcile into one linear chain before any merge" (`docs/PHASE7_ENGINEERING.md:73`, `:135–137`). No production migration runbook (operator procedure, backup before migrate, maintenance window) in any document. | PARTIAL (per-branch MET; integrated chain NOT MET; production procedure NOT DEFINED) |
| C-15 | Content safety and scanning | ARCH:260 ("when scanning is available"); GDR:408–420 (P7) | No scanner is approved (HP:89; `docs/INCREMENT_2_PLAN.md:187–188`). `quarantined → clean` refused by the database (HP:89). `not_scanned` remains eligible for authorized Foundation processing (GDR:413–414). External transmission of client content to an AI provider "needs a separately accepted content-safety, disclosure and deployment policy" (GDR:417–418); "Production integration remains blocked" (GDR:420). No such policy exists in the repository. | NOT DEFINED |
| C-16 | Parser resource limits and isolation approved for production (H-31, H-32; H-DEC-3, H-DEC-4) | HP:122–129, HP:337–338; GDR (P4):441–444, :465–472, :577–580 | Implemented on P4 (`docs/PHASE4_H_DEC_LIMITS_REGISTER.md:8–20`, P4). Values "provisional ... not approved as production values" (GDR P4:444); Windows child has "no memory cap" (GDR P4 H-DEC-4, line 465 onward); "Production parser limits require separate capacity and security validation" (GDR P4:577–578); Windows production needs a separate decision (GDR P4:472, :579–580). P4 not on P7 (P7 has no `intake/limits.py` or `parser_child.py`). | NOT MET |
| C-17 | Data retention: class-specific periods, controlled deletion, tombstones, backup purge (D-13, `EVAL-RETENTION-001`) | DR:19, DR:39; GOV:128, GOV:283; ARCH:329; EVAL:241 (P7) | "CONFIRMED — periods pending" (DR:19). B-11: archive only, "no physical deletion/purge until retention policy approval" (DR:60). Tombstone schema exists (audit_tombstones INSERT, GDR:117). No purge or retention code in `src` (`git grep retention|purge|tombstone`: one idempotency docstring only, P7). | NOT MET |
| C-18 | Privacy in logs and audit: no secrets or client content in logs or audit details | ARCH:262; PB:33 (P7) | `config.py:9` secrets are `SecretStr`; withdrawal audit no longer carries the reason (`docs/PHASE7_ENGINEERING.md:27`, H-73); worker logs carry identifiers and classes only (`docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md:40`, P3); CLI prints identifiers only (`cli/install.py:12`, P7). Evidence is per-path and test-based; no production log pipeline exists to assess. | PARTIAL |
| C-19 | Structured operational logs with IDs, stage, latency, normalized error | ARCH:262 (P7) | P3 worker prints JSON event lines (`src/webdesk/worker/loop.py:141–146`, P3) with `correlation_id` (`docs/PHASE3_REQUIREMENTS_GAP_MATRIX.md:38`). The HTTP API and authority on P7 have no logging (no `logging` import in `src`, P7); authority writes one start line to stdout (`server.py:374`). | PARTIAL |
| C-20 | Threat modelling and review of the deployment environment | ARCH:264 (P7) | No threat model document in `docs/` on any ref (`git grep -l "threat model"` matches only SPEC files). No deployment environment exists to review (D-16). | NOT MET |
| C-21 | Numeric release thresholds, named role-holders and release sign-off (D-14, `EVAL-RELEASE-OWNER-001`) | DR:20; EVAL:233, EVAL:242 (P7) | "numeric gates pending"; "Named role-holders, minimum test N, numeric release gates ... must be specified before release" (DR:20). | NOT DEFINED |
| C-22 | Security acceptance criteria HP §6 (1–11) | HP:270–282 (P7) | Per-phase evidence exists (e.g. restricted-login suite, GDR:286, GDR:390; P7 QA 733 passed, `docs/PHASE7_ENGINEERING.md:87`). Criterion 6 depends on Phase 3 fencing; Phase 5 Finding 5 is open: `fn_worker_mark_inputs_changed(p_run uuid)` has no lease or owner check, "Not declared safe" (`docs/PHASE5_X7_QA_CLOSURE.md:59–75`, `:96`, P7); its P7 definition still takes only `p_run` (`migrations/versions/0049_p7_run_audit_project_id.py:97`, P7). Criterion 7 depends on P4 containment (C-16). No combined-branch run exists (`docs/PHASE7_ENGINEERING.md:133`, `:141`). | PARTIAL |
| C-23 | Production delivery of activation (application activation path has a production caller) | PB:71–72 (P7) | "The application's activation path has no production caller in `src`. The activation flows are exercised by tests only." (`docs/PHASE1_INDEPENDENT_REVIEW_HANDOFF.md:244`, P7). | NOT MET |

### 2.4 Governance decisions (HP §9) and cross-phase dependencies

| # | Criterion | Source | Evidence found | Status |
|---|---|---|---|---|
| G-1 | H-DEC-1 parked-run cancel | HP:335 | No ruling on any ref (`git grep`). H-68 not implemented (`docs/PHASE7_ENGINEERING.md:22`, P7). | NOT MET |
| G-2 | H-DEC-2 late reclassification | HP:336 | No ruling. H-67 "Blocked by H-DEC-2" (`docs/PHASE7_ENGINEERING.md:21`, P7). | NOT MET |
| G-3 | H-DEC-3 parse limits | HP:337 | Non-production only, provisional; provenance incomplete (GDR P4:424–444, :561–590; `docs/PHASE4_GOVERNANCE_PROVENANCE_MATRIX.md:15`, `:47`, P4). | NOT MET (for production) |
| G-4 | H-DEC-4 Windows memory cap | HP:338 | Non-production only; production needs a separate decision (GDR P4:472, :579–580; provenance matrix:46, P4). | NOT MET (for production) |
| G-5 | H-DEC-5 DOCX table locators; H-DEC-6 HTML-only email | HP:339–340 | Relayed rulings with amendments (GDR P4:506–537, :538–560); approver identity and channel missing (provenance matrix:42, P4). H-64 not implemented on P7 (`docs/PHASE7_ENGINEERING.md:18`). | PARTIAL |
| G-6 | H-DEC-7 deployment gate is production only | HP:341 | No explicit ruling recorded on any ref. SPEC is consistent with "production only" (EVAL:244). | NOT DEFINED (no ruling) |
| G-7 | H-DEC-8 operational alert | HP:342 | Option 1 selected (`docs/PHASE6_X8_ENGINEERING.md:26`, P7). Phase 6 acceptance pending (`:83`). | PARTIAL |
| G-8 | H-DEC-9 test DB owner | HP:343 | No ruling recorded. Test-only. | NOT DEFINED |
| G-9 | H-DEC-10 password, session, outbox key custody | HP:344 | No ruling. See C-11, C-12. | NOT MET |
| G-10 | H-DEC-11 HTTP login and administration endpoints | HP:345 | No ruling recorded. | NOT DEFINED |
| G-11 | H-DEC-12 `created` run state | HP:346 | No ruling recorded. | NOT DEFINED |
| G-12 | H-65 Markdown MIME alternatives | `docs/PHASE7_ENGINEERING.md:19` (P7) | "Blocked. ... WDS must name them". | NOT MET |
| G-13 | Phase 3 dependencies: H-21/H-76 time source, H-25/H-68 lock order, H-22/H-26 worker, Finding 5 fencing | `docs/PHASE7_ENGINEERING.md:22`, `:30`, `:74–76`; `docs/PHASE6_X8_ENGINEERING.md:67–71`; `docs/PHASE5_X7_QA_CLOSURE.md:96–98` (P7) | Implemented on P3 except Finding 5; none merged into P7. | NOT MET |
| G-14 | Phase 4 dependencies: H-64 parser, parse timeout below the lease | `docs/PHASE7_ENGINEERING.md:77`; `docs/PHASE4_DEPENDENCY_REGISTER.md:10`, P4 | `PARSER_TIMEOUT_SECONDS` 30 s versus 120 s lease "Confirm the lease ordering when D-P3 merges". | NOT MET |
| G-15 | Cross-phase integration verified (single migration chain, merged `jobs.py`, full suite and privilege audit on the combined branch) | `docs/PHASE7_ENGINEERING.md:131–141` (P7) | "Integration is **not verified**." | NOT MET |
| G-16 | Approval provenance (approver identity, channel, signature, artifact digests) | `docs/PHASE7_ENGINEERING.md:124–126`; `docs/PHASE5_X7_QA_CLOSURE.md:111–112`; `docs/PHASE3_GOVERNANCE_RECORD.md:62–73`; GDR P4:424–431 | Missing for every phase decision and acceptance. | NOT MET |

### 2.5 Formal acceptance status by phase

| Phase | Source | Recorded status | Status |
|---|---|---|---|
| 1 (X1–X3, decisions 1–8, R4) | `docs/PHASE1_INDEPENDENT_REVIEW_HANDOFF.md:250–252` (P7); `docs/PHASE3_DEPENDENCY_REGISTER.md:15` (P3) | Ready for re-review; "This is not acceptance." Acceptance not recorded. | NOT MET |
| 2 (identity correctness) | `docs/PHASE2_RECONCILIATION_AND_CLOSURE.md:71–79` (P2) | "PHASE 2 ENGINEERING INCOMPLETE — SPECIFIC BLOCKERS REMAIN": Windows authority-child start failure `0xC0000142` unresolved (`:43–49`, `:75`); F-09 acknowledgement missing (`:76`); independent QA not run on the final SHA (`:78`); no WDS acceptance (`:79`). | NOT MET |
| 3 (durable execution) | `docs/PHASE3_GOVERNANCE_RECORD.md:103–112` (P3); `docs/PHASE3_QA_RETEST_DELTA.md:7–8`, `:127–134` (P3) | QA passed on `4829386` only; commits `e3c2929`..`db844ed` await independent re-test; "Final WDS acceptance ... has not been granted." | NOT MET |
| 4 (parse robustness) | `docs/PHASE4_QA_REMEDIATION.md:213–217`, `:229–234` (P4) | "ENGINEERING REMEDIATION COMPLETE — READY FOR INDEPENDENT QA ... not independent QA and not WDS acceptance." Developer gate on `f416716` only. | NOT MET |
| 5 (X7) | `docs/PHASE5_X7_QA_CLOSURE.md:101–115` (P7) | QA passed on `f001b9d`; WDS acceptance "GRANTED for the standalone X7 scope", 30 Oct 2026; "not verified against an authoritative register"; cross-phase integration "PENDING". | PARTIAL (standalone accepted; provenance unverified) |
| 6 (X8) | `docs/PHASE6_X8_ENGINEERING.md:73–106` (P7) | QA passed on `9a9e8d3`; "WDS formal acceptance: **PENDING**" (`:83`, `:100`). | NOT MET |
| 7 (H-60–H-77) | `docs/PHASE7_ENGINEERING.md:80–129` (P7) | QA passed on `ae032a2` (`:91`); WDS formal acceptance "GRANTED", 2 Nov 2026, chat statement; approver identity, signature, channel and digests "not in this repository" (`:124–126`). F-1 test commit `89d6ef2` awaits independent re-check (`:127–129`). Five items not implemented (`:62`). | PARTIAL (standalone accepted; provenance incomplete) |

---

## 3. Blockers to production, by severity

Severity reflects the documents' own classification (PB "BLOCKED", DR "deployment blocker", "production-blocking") and the effect on
security. Owners: **ENG** engineering, **GOV** WDS governance, **OWN/OPS** owner or operator, **PHASE-n** another phase.

### Critical (production is impossible or unsafe until closed)

1. **No approved hosting, egress or deployment target (D-16)** — DR:22; EVAL:244; DC:34. No production artefacts exist (C-1).
   Owner: **GOV** (decision), then **OPS** (infrastructure), then **ENG** (artefacts: application entry point, process definitions).
2. **No trusted authority deployment and no authenticated transport** — PB:21–27, PB:37–43; `server.py:353–354`, `:362–363`. The only
   authority refuses production and binds to loopback over plain HTTP. Owner: **ENG** (production authority, mTLS) and **OPS**
   (deployment, certificates).
3. **No key or secret custody** (authority secret, DB passwords, outbox key, owner signing key) — PB:29–35; DC:22–23, DC:26–27, DC:32.
   Owner: **GOV** (custody decision C-9, BOOTSTRAP-02), **OWN/OPS** (key generation and storage), **ENG** (integration).
4. **No approved email transport; production profile cannot pass validation** — PB:65–73; `config.py:53`, `:106–107`, `:143–150`.
   Activation, reset and contact-change notices cannot be delivered, and `validate_for_profile` refuses every production configuration,
   which also blocks the production install CLI (`cli/install.py:65`). Owner: **GOV** (provider approval), **OPS** (credentials and
   delivery test), **ENG** (production transport option in `Settings`).
5. **No tested backup and restore, no zero-Administrator offline recovery runbook or rehearsal, no incident runbooks** — PB:79–82;
   GOV:291; GATE1:36. Owner: **OPS** (backup), **GOV/OWN** (runbook approval and rehearsal), **ENG** (supporting procedure).
6. **Phase 1 independent acceptance not recorded** — PB:93; handoff:252; P3 register:15. Owner: **GOV** (independent reviewer and
   WDS).

### High

7. **Cross-phase integration not verified; migration chains diverge at 0041** — `docs/PHASE7_ENGINEERING.md:131–141`; forked
   `down_revision` values (C-14). Owner: **ENG** (integration) and **GOV** (approval of the reconciled chain).
8. **Phases 2, 3, 4 and 6 not accepted; Phase 2 engineering incomplete** (§2.5). Owner: **PHASE-2/3/4/6** owners, independent QA,
   **GOV**.
9. **Worker deployment and supervision absent on the Phase 7 line** — no `src/webdesk/worker/` on P7; P3 worker not merged; no
   process manager (HP:116; P3 register:23–24). Owner: **PHASE-3** (merge), **OPS** (process manager, worker logins), **ENG**.
10. **Phase 5 Finding 5: worker stale mark without lease or owner check** — `docs/PHASE5_X7_QA_CLOSURE.md:59–75`; still
    `fn_worker_mark_inputs_changed(p_run uuid)` at `0049:97` (P7). Owner: **PHASE-3**.
11. **No monitoring or alerting wired** — PB:77–78; no logging in P7 `src`; no alert read path. Owner: **OPS** (alerting system),
    **ENG** (logging, metrics, alert export).
12. **Parser containment and limits not approved for production; no Windows memory cap** — GDR P4:444, :472, :577–580. Owner:
    **GOV** (H-DEC-3, H-DEC-4 production rulings, hosting OS choice), **PHASE-4**.
13. **Ceremony operator and verifier identities are declared, not authenticated** — GDR:263–264, GDR:301, GDR:406. Owner: **ENG**
    (with the production authority) and **OWN/OPS**.

### Medium

14. **Rate limits not final and partly not configurable** — `server.py:50–57` constants; `WEBDESK_RL_*` required but no consumer
    found; DC:24–25. Owner: **GOV** (values), **ENG** (wire the configured values).
15. **Retention periods, deletion and backup purge undecided (D-13)** — DR:19; GOV:128. Owner: **GOV**, then **ENG**.
16. **Domain allowlist, alias denylist, dead-letter threshold, password minimum, session lifetime undecided** — DC:21, DC:24–25, DC:31;
    `auth/service.py:13–14`. Owner: **GOV**, then **OPS** (configuration).
17. **Content-safety policy for `not_scanned` content not defined; no scanner approved** — GDR:417–420; HP:89. Owner: **GOV**.
18. **Threat model and deployment-environment review absent** — ARCH:264. Owner: **ENG** with **GOV**.
19. **Open H-DEC rulings (H-DEC-1, 2, 7, 9, 10, 11, 12) and H-65** — §2.4. Owner: **GOV**.
20. **Approval provenance missing for all phase acceptances and rulings** — G-16. Owner: **GOV** (administrative attestation).
21. **Signed artifacts must be re-issued in the H-50/H-74 format** — `docs/PHASE7_ENGINEERING.md:65`. Owner: **OWN**.

### Low (documentation)

22. Stale or inconsistent records that a reviewer could mistake for evidence (see §6). Owner: **ENG**.

---

## 4. Items only humans or the operator can do

- **WDS governance**
  - Approve hosting, egress and the vendor allowlist (D-16, EVAL-DEPLOYMENT-GATE-001), and say whether Windows hosting is permitted
    (H-DEC-4).
  - Approve the production email provider, the domain allowlist, the alias denylist, final rate limits, the dead-letter threshold,
    the password minimum, the session lifetime, retention periods (D-13), production parser limits (H-DEC-3), the content-safety
    policy for `not_scanned` content, and the numeric release thresholds with named role-holders (D-14).
  - Rule on H-DEC-1, H-DEC-2, H-DEC-7, H-DEC-9, H-DEC-10, H-DEC-11, H-DEC-12 and H-65 (Markdown MIME list).
  - Grant formal acceptance of Phases 1, 2, 3, 4 and 6 after independent QA, and attest approver identity, channel, time, signature and
    artifact digests for every recorded acceptance, Phases 5 and 7 included.
  - Confirm that no shared environment applied migrations 0027 to 0036 before they were edited (GDR:373–376).
  - Give explicit approval of the production deployment (PB:94).
- **Owner**
  - Establish the owner identity and generate the Ed25519 signing key under approved custody (DC:22–23, DC:32).
  - Define the independent verification procedure and name the verifier.
  - Re-sign install and recovery artifacts in the current format (`docs/PHASE7_ENGINEERING.md:65`).
  - Authorize and witness the one-time install ceremony and the rehearsal of the zero-Administrator offline recovery (PB:79–80;
    GOV:291).
- **Operator**
  - Provision real infrastructure: hosts, network placement, TLS and mTLS certificates, and a secrets manager or KMS.
  - Create the production logins (app, authority, intake worker, outbox worker, ceremony) and a non-superuser migration owner, run
    `REVOKE CREATE ON SCHEMA public` (DC:54–55), and keep the ceremony credentials (DC:12–13).
  - Generate the outbox encryption key and the authority secret per environment.
  - Run the SMTP delivery test to an approved contact, then set `WEBDESK_SMTP_VERIFIED=true` (PB:69–72).
  - Set up the process manager for the worker, backup and tested restore, the alerting system, and the incident runbooks.
- **Independent QA**
  - Re-test Phase 3 commits `e3c2929`..`db844ed`, Phase 4 `f416716`, Phase 2 `00ec194`, the Phase 7 F-1 commit `89d6ef2`, and the
    combined branch.

---

## 5. Verdict

**PRODUCTION READINESS: NOT VERIFIED.**

Reasons, each observed in the repository:

1. The project's own sign-off definition (PB:91–95) has four conditions. None is met: Phase 1 acceptance is not recorded, no PB
   blocker is closed, all 16 checklist items are unchecked, and no WDS production approval exists. PB:3 records production as
   "BLOCKED".
2. Hosting and egress (D-16) are deferred by WDS and recorded as a deployment blocker (DR:22). No production deployment artefact
   exists.
3. The authority is a development process that refuses production and binds only to loopback over unencrypted HTTP
   (`server.py:7–15`, `:353–363`).
4. No email transport is approved, and the production configuration profile cannot currently validate (`config.py:53`, `:106–107`,
   `:143–150`).
5. Key custody, backup and restore, the offline recovery runbook and rehearsal, incident response and monitoring are not written,
   provisioned or rehearsed (PB:35, PB:78, PB:82).
6. Phases 2, 3, 4 and 6 are not accepted. Phases 5 and 7 are accepted for standalone scope only, with incomplete provenance.
   Cross-phase integration is not verified (`docs/PHASE7_ENGINEERING.md:133`).
7. Open security dependencies remain: Phase 5 Finding 5 fencing, unauthenticated ceremony operator and verifier identities, the
   Windows parser memory cap, and production parser limits.

A VERIFIED verdict is not possible on this evidence. Several defined criteria are NOT MET, and others are NOT DEFINED because the
governing decisions (D-13, D-14, H-DEC-7, H-DEC-9, H-DEC-11, H-DEC-12, the content-safety policy) have not been made.

---

## 6. Record discrepancies observed (documentation, not production criteria)

These do not change the verdict. A reviewer should know about them before relying on the records.

- **Phase 3 hash.** `docs/PHASE3_GOVERNANCE_RECORD.md:54–55` (P3) gives the SHA-256 of `0053_contact_approval_clock.py` "as committed
  in `e3c2929`" as `cab2f6dc...`. Hashing `git show e3c2929:<file>` gives `9a1e5de4...`. `cab2f6dc...` is the hash at `db844ed`
  (which line 100 correctly attributes to `db844ed`). Line 55 misattributes the hash.
- **Phase 1 checklist.** DC:57–59 (P7) still says the R4 finding is open and the verified-session authority "is not yet deployed; do
  not deploy to a shared environment until R4 is closed". Later records describe the authority implementation (GDR:186–282). The
  checklist has not been reconciled with them, and R4's closure status should be confirmed by the reviewer.
- **Checklist grants.** DC:10–11 says `webdesk_app` "holds only the grants in migrations `0001`–`0006`". That predates 0010–0049,
  which changed those grants (GDR:112–183).
- **Production boundary scope.** PB:9 cites "migrations 0001 to 0038". The P7 head is `0049_p7_run_audit_project_id`.
- **Example environment file.** `.env.example:9` gives the app URL as user `webdesk_app`. DC:48–51 and PB:49 name the runtime login
  `webdesk_app_login`.
- **Hardening plan status.** HP:3 (P7) still reads "Proposed. Awaiting approval." P4's copy was changed to point to the relayed
  approval (P4 `HP:3`). The two refs disagree on the plan's approval status.
- **Phase 6 acceptance.** Phase 6 acceptance remains PENDING on both P7 and `feature/foundation-phase-6` (`7943d03`). No later record
  was found.
