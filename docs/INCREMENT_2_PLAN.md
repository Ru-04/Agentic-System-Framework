# Increment 2 Implementation Plan (for approval; no code written)

Baseline: branch `feature/increment-1-foundation`, commit `ce76b32`. 205 tests pass. See
`docs/INCREMENT_1_EVIDENCE.md`. Specification baseline: v0.3.10 approved limited Foundation
(`WebDesk_Agentic_Requirement_Platform_Specs/`), read under the authority order in README.md.
No specification file is changed by this plan.

Out of scope, per GATE1 §Excluded: specialist agents, LLM/model calls, RAG, estimation, SOW output,
live egress, production deployment, production email, retention or purge, SSO.

## 1. Requirement coverage matrix

Status key: COMPLETE (all pass conditions implemented and tested), PARTIAL (some implemented or
tested), DEFERRED (Increment 2 scope, not started), NOT STARTED (no code and no test), BLOCKED
(needs an external decision).

| Requirement | Status | Evidence in repo | Remaining work |
|---|---|---|---|
| EVAL-F01-MATRIX | PARTIAL | `rbac/matrix.py`, `engine.py`, `test_rbac_engine` (55), `test_rbac_sql` | Exhaustive key × role × assigned/unassigned run; run.* keys once runs exist (I-9) |
| EVAL-F02-CLASS | PARTIAL | Project DataClass required (`test_gate1_schema`, `test_projects`) | Source `access_classification`, downgrade refusal, tombstone rules (I-1, I-5) |
| EVAL-F03-UPLOAD | DEFERRED | none | I-2, I-3, I-4, I-5 |
| EVAL-F04-LOCATOR | DEFERRED | none | I-6 |
| EVAL-F05-DTO | PARTIAL | Idempotency and revision at service layer (`test_idempotency`) | No HTTP DTO layer; client-set server fields untested (C-1, I-5) |
| EVAL-F06-JOBS | DEFERRED | none | I-8 |
| EVAL-F07-CONCURRENCY | DEFERRED | none | I-9 |
| EVAL-F08-SOT | PARTIAL | Audited service writes; no checkpoint | I-16 |
| EVAL-F09-TRANSITIONS | PARTIAL | Project create makes no run (`test_projects`) | Run snapshots, state table, R3 archive (I-9, I-10, I-14) |
| EVAL-F10-STALE | DEFERRED | none | I-13 |
| EVAL-F11-SELFGRANT | COMPLETE | `test_projects`, `test_gate1_schema` | none |
| EVAL-F11b-SELFASSIGN | COMPLETE | `test_role_assignment`, `test_gate1_schema` | none |
| EVAL-F11c-ACTIVATION | COMPLETE | `test_auth_lifecycle`, `test_tokens`, `test_install_ceremony` | none |
| EVAL-F11d-CONTACT-APPROVAL | PARTIAL | `test_contact_lifecycle`, `test_gate1_schema` | Replacement create, 24 h expiry sweep, approval-vs-withdrawal concurrency (C-3, C-4, C-5) |
| EVAL-F11e-TOKEN-RATELIMIT | COMPLETE | `test_tokens`, `test_auth_lifecycle`, `test_delivery_and_tokens` | none (login limits covered) |
| EVAL-F11f-CEREMONY-RECOVERY | PARTIAL | `test_install_ceremony`, `test_role_assignment` | 24 h missed-activation release of coverage (C-3) |
| EVAL-F11g-CONTACT-OUTBOX | PARTIAL | `test_outbox_worker` (9), contact_box | Injected-failure atomicity, SMTP-outage-keeps-change, lease-renewal loop, worker entrypoint (C-5, I-15) |
| EVAL-F11h-ADMIN-APPOINTMENT | COMPLETE | `test_role_assignment`, `test_gate1_schema` | none |
| EVAL-F11i-ZERO-ADMIN-OFFLINE-POLICY | PARTIAL | In-app refusal tested | Offline path is specification only; cannot be tested here |
| EVAL-F12-AUDIT | PARTIAL | Append-only, redaction, service denials | Content-read audit, denial-path coverage for every service (I-17, C-2) |
| EVAL-F13-SNAPSHOT | DEFERRED | none | I-10 |
| EVAL-F14-SOURCE-REPARSE | DEFERRED | none | I-11 |
| EVAL-F14b-PARSE-ATOMICITY | DEFERRED | none | I-6, I-7 |
| F-CFG-01 (proposed) | COMPLETE | `test_config` | Needs registering in the spec (C-6) |
| EVAL-DEPLOYMENT-GATE-001 | BLOCKED | Fail-closed config only | Hosting decision D-16 |
| EVAL-LEGACY / later-phase IDs | NOT STARTED | — | Out of Gate 1 |

Remaining Gate 1 functionality with no tests yet: source intake and parsing, the full run state
machine, jobs and leases, snapshots, staleness hashing, reparse, archive-with-runs, and content-read
audit. Remaining Increment 1 gaps are in §3.

## 2. Increment 2 tasks (ordered)

Each task lists governing spec, dependencies, and exact EVAL-F IDs. Pass conditions are in the
EVAL-F rows of `EVALUATION_PLAN.md` and are not restated here.

**Phase A: corrections to Increment 1 (C-tasks, §3). Do first.**

**Phase B: data foundation**

- **I-1 Source, run and checkpoint schema** (migration `0006`). Tables: `projects` (unchanged),
  `sources`, `source_versions`, `source_segments`, `run_input_snapshots`, `workflow_runs`,
  `workflow_jobs`, `workflow_checkpoints`, `dependency_edges`. Constraints per SCHEMA §3.1, §4.2,
  ARCH §7, §13. Spec: SCHEMA §4.2, §3.1 (RunInputSnapshot, WorkflowRun), ARCH §7, §13. Depends on
  T3 roles. EVAL: F02 (source part), F04 (uniqueness), F08 (checkpoint holds IDs only), F10
  (DependencyEdge no cycles), F07 (partial unique active-slot index).
- **I-2 Content-addressed byte store.** Local volume, project-isolated, behind a replaceable adapter;
  path-traversal refused; hash recorded. Spec: ARCH §13, GOV §8. Depends on I-1. EVAL: F03
  (storage and hash), F03 quarantine path.

**Phase C: intake**

- **I-3 Upload validation.** Extension, MIME signature and structure, 20 MiB limit, 50 admitted
  versions per project including superseded, UTF-8 for TXT/MD, archives/executables/encrypted and
  `.msg`/images rejected. 415/413 with no Source row; 422 for corrupt files; audit each refusal.
  Spec: ARCH §13. Depends on I-2 and the HTTP layer (C-1). EVAL: F03 (upload clauses), F02.
- **I-4 Quarantine and scan status.** `scan_status` not_scanned/clean/quarantined. Restricted sources
  quarantined until a clean scan; quarantined sources never parsed, snapshotted, read or supplied to
  a model. No reviewer exception. Spec: ARCH §13, GOV §8. Depends on I-3. EVAL: F03 (quarantine
  clauses), F13 (exclusion).
- **I-5 Source ingest service.** `SourceIngestRequest`: expected project revision, optional
  supersession with expected source revision, idempotency, server-derived uploader, size, MIME, hash
  and storage. Client may not supply trusted storage URI. Spec: SCHEMA §3 DTOs, §3.1 R1. Depends on
  I-3, I-4, C-1. EVAL: F05 (source), F02 (classification set by the request, not lowered), F03.
- **I-6 Parsers and typed locators.** PDF (page), DOCX (paragraph), MD (heading+paragraph), TXT
  (line range), EML (subject/body only; attachments listed as `unprocessed_attachment`, never
  ingested). Deterministic segment IDs per (source, version, extraction_version); reuse on re-run.
  Spec: SCHEMA §4.2, ARCH §13. Depends on I-5 and library approval (D-1). EVAL: F04 (all), F03 (EML
  attachments), F14b (a, b, c).
- **I-7 Atomic parse per source version.** Each parse stages segments and commits only on success.
  Exception → failed with zero new segments and other sources preserved. Declared unextractable
  regions → partial. Image-only valid document → unsupported. Spec: ARCH §7, SCHEMA §3.1. Depends on
  I-6. EVAL: F14b (a, b, c).

**Phase D: durable execution**

- **I-8 Durable workflow jobs.** `workflow_jobs` with `SELECT … FOR UPDATE SKIP LOCKED`, lease 120 s,
  renew every 30 s, reclaim after expiry, 3 attempts maximum, backoff capped at 5 min, no retry on
  authorization or schema errors, parked run has no leased job. Single worker. Spec: ARCH §7 (F-6).
  Depends on I-1. EVAL: F06 (all), F07 (lease part).
- **I-9 Run lifecycle and slot.** `run.start` (Analyst with assignment only; Administrator alone
  denied), `run.cancel/retry/resume` (Administrator only). RunStatus vocabulary, job-status mapping,
  one queued/running/waiting_human run per project (partial unique index), parked
  `blocked_pending_decision` releases the slot, `run.resume` 409 for parked runs, revisions with
  409 on stale. Spec: ARCH §7 (B-5, B-6, F-7), GOV §11 (C-1), SCHEMA §3.1. Depends on I-8, I-1. EVAL:
  F01 (run keys), F07 (all), F09 (run states).
- **I-10 Intake run and snapshot.** Stages `intake_pending → parsing → intake_complete` or
  `blocked_pending_decision`. Snapshot from latest non-superseded, non-quarantined versions,
  including new `pending` versions; never empty when an eligible pending source exists. Uploads
  during a run belong to the next snapshot. Run marked stale on completion if inputs changed.
  Spec: ARCH §5, §7, SCHEMA §3.1 (R1). Depends on I-6, I-7, I-9. EVAL: F09 (snapshot and
  transitions), F13 (all), F07 (uploads during run).
- **I-11 `source.reparse`.** Administrator only; nonempty reason; revision check; only failed,
  non-superseded, non-quarantined versions of active projects; atomic reset to pending; audited; no
  snapshot or segment mutation; 403, 409 as specified; not a whole-run retry. Spec: GOV §11,
  SCHEMA §3.1, ARCH §7. Depends on I-10. EVAL: F14 (all), F13 (mixed batch).
- **I-12 Run retry for system failures.** `run.retry` only for failed runs caused by system-level
  errors; Administrator may requeue only when no newer run exists; never repairs one file. Spec:
  ARCH §7, GOV §14. Depends on I-8, I-9. EVAL: F07, F14 (retry scope).

**Phase E: staleness and archive**

- **I-13 Canonical hashing and staleness.** RFC 8785 canonical JSON; inputs sorted by UTF-8 bytes of
  (entity_type, entity_id) with integer revision tiebreak; `config_versions` contains exactly
  `extraction_version` and `parser_library_version`. Transitive invalidation over `dependency_edges`
  in the same transaction. Stale data cannot pass a gate. Spec: ARCH §7 (F-10), SCHEMA §3.1.
  Depends on I-1, I-7, I-10. EVAL: F10 (golden digest
  `5df52f543349fa88dd4a96d4f1f1f6183384adc754b477f65960b62e9b926da9`; reordering or config change
  must alter or fail), F09 (stale).
- **I-14 Archive with active runs (R3).** `project.archive` 409 while any run is queued, running or
  waiting_human; `run.cancel` allowed on archived projects; `run.retry` and `run.start` 409; no
  unarchive. Closes the gap in Increment 1. Spec: GOV §11 (R3), SCHEMA §3.1. Depends on I-9. EVAL:
  F09 (archive clauses).

**Phase F: notification outbox and audit completion**

- **I-15 Outbox worker completion.** Injected-failure atomicity test (contact update, notice and
  revocations commit or roll back together); SMTP outage leaves the contact change effective and
  raises an in-app alert; kill-after-lease reclaim and single send; lease-renewal loop; a single
  worker entrypoint with the dead-letter threshold from configuration. Spec: SCHEMA §3.1
  (OutboxNotice), ARCH §7, F11g. Depends on Increment 1 worker and C-5. EVAL: F11g (all pass
  conditions).
- **I-16 Checkpoint skeleton.** `workflow_checkpoints` holds domain IDs, revision hashes, node
  identifiers and flags only; resume re-reads domain tables and revalidates revisions; no bypass of
  project authorization. No LangGraph in Increment 2 (D-5). Spec: ARCH §7 (F-8), §5. Depends on I-8,
  I-10. EVAL: F08 (all).
- **I-17 Content-read audit and denial coverage.** Every client-content read through a service writes
  one audit event; every denial path has a test; redaction covers restricted titles and excerpts.
  Spec: GOV §11, ARCH §13, SCHEMA §4.10. Depends on I-5, I-10. EVAL: F12 (all).

**Phase G: gate evidence**

- **I-18 Evidence run and report.** Run every EVAL-F test ID listed in §1 for Increment 2 scope;
  record for each: inputs, expected status, actual status, spec section. Update
  `docs/INCREMENT_2_EVIDENCE.md`. Gate 1 completion is claimed only if every release-blocking
  test in §1 is COMPLETE, or is explicitly recorded as BLOCKED by a named decision. Depends on all.

## 3. Gaps from Increment 1 to correct before Increment 2

- **C-1 No HTTP layer.** Upload, DTO validation (F05), and neutral responses need a FastAPI
  application. Add a minimal app with error mapping, request models, and a single place where denial
  audits are committed. Spec: ARCH §2, §11; SCHEMA §3 DTOs. Needed for I-3, I-5.
- **C-2 Denial audit commit.** Services write denial events then raise. A caller rollback discards
  them. The HTTP layer must commit denial audits in their own transaction. Needed for F12.
- **C-3 Expiry sweep.** Pending create and change requests expire at 24 h, and missed install and
  recovery activations must release reserved coverage (F11d, F11f). Add a sweep that writes an
  audit event per expiry. Spec: SCHEMA §3.1, GOV §11 (P-GATE1-CONTACT-01, BOOTSTRAP-02).
- **C-4 Replacement create request.** Not implemented (SCHEMA §3.1: a replacement create may follow
  expiry or rejection, with the reservation retained). Add it and test F11d's replacement clause.
- **C-5 Missing F11d and F11g tests.** Approval versus withdrawal serialization (one side returns
  409); SMTP outage leaves change effective; lease-renewal loop. Add tests against committed rows.
- **C-6 Test-ID registration.** `F-CFG-01` and the CLI, migration and config test IDs are proposals.
  Register them in the spec only with approval (`EVALUATION_PLAN` change), or record them as
  project-local IDs in the evidence report.
- **C-7 F01 exhaustive test.** Run every key × every role × assigned/unassigned against the SQL store,
  not only the fake store. Spec: EVAL-F01.
- **C-8 Placeholders.** Password minimum 12 characters and session lifetime 8 hours are not in the
  Gate 1 contracts. Confirm or change them before any production configuration.
- **C-9 Key custody.** `WEBDESK_OUTBOX_ENCRYPTION_KEY` custody, rotation and storage are undecided.
  Decision needed before any real prior-contact notice is sent.
- **C-10 Owner role.** Local Docker runs the owner as a superuser. Production must use a
  non-superuser owner and separate login roles. Record in the deployment checklist; no code change
  in Increment 2.

## 4. Decisions needed before coding

- **D-1** Parser libraries: `pypdf` (PDF), `python-docx` (DOCX). Markdown and TXT need no library;
  EML uses the standard library. Versions must be at least two weeks old and pinned.
- **D-2** Scanner: none is approved. Under the Gate 1 rule, restricted sources stay quarantined,
  and non-restricted sources proceed with a visible `not_scanned` warning. Confirm this reading.
- **D-3** Canonical JSON: use the `rfc8785` package, or implement the subset needed and test it
  against the golden digest. Recommend the package.
- **D-4** Single worker process (Gate 1 states PostgreSQL single worker). Confirm.
- **D-5** LangGraph is not introduced in Increment 2. Checkpoints are domain-ID rows. Routing stays
  disabled. Confirm.
- **D-6** FastAPI is introduced for the upload and DTO layer (C-1). ARCH §2 names it.
- **D-7** Storage root: a local directory from configuration, outside the repository. The path is
  not hardcoded.
- **D-8** Confirm C-8 and C-9 values before Increment 2 starts, as in §3.

## 5. Completion criteria and evidence

A task is complete only when all of the following hold:

1. Its listed EVAL-F tests exist and pass against PostgreSQL, with the database created from
   migrations.
2. Migrations upgrade, downgrade one step, and upgrade again.
3. Ruff lint, Ruff format check and mypy strict pass.
4. Every mutation, denial and client-content read it adds writes one audit event (tested).
5. `docs/INCREMENT_2_EVIDENCE.md` records each test with inputs, expected status, actual status
   and the spec section.
6. No EVAL-F test is marked COMPLETE on the basis of a unit test that only uses a fake store, where
   the spec requires database enforcement.

Gate 1 is complete only when §1 has no PARTIAL, DEFERRED or NOT STARTED rows, except rows marked
BLOCKED by a named decision (EVAL-DEPLOYMENT-GATE-001 by D-16, EVAL-F11i offline recovery by
P-GATE1-ZERO-ADMIN-RECOVERY-03 runbook).

## 6. Approval requested

1. Approve Phase A (C-1 to C-10) and Phase B to G (I-1 to I-18) in this order.
2. Decide D-1 to D-8. Each affects code choices.
3. Confirm the Gate 1 completion rule in §5.
4. Confirm that the spec baseline stays unchanged for Increment 2. Any spec change needs your
   explicit approval.
