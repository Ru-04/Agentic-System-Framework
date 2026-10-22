# Authorized AI Read-Only Access Contract — Proposal v0.1

**Status: PROPOSAL, NOT APPROVED.** Owner: Foundation (Track A). Consumer: AI engine (Track B). This document records the
interface the Foundation proposes, the Foundation-owned identifiers and states it would expose, and the decisions WDS
must make before any AI access is implemented. Nothing here is implemented, and nothing here authorizes AI work in
Phase 1. The Foundation does not modify AI-engine files.

## 1. Scope

- **In scope (proposal):** read-only access, by an authorized AI caller, to project metadata, source-version metadata,
  clean source content the caller may read, and run status.
- **Out of scope:** any write, any privileged operation, any operation proof, classification change, membership or grant
  change, contact or account action, and direct database access. AI callers never receive database credentials.

## 2. Principal and authorization (decision required: D-AI-1)

The Foundation proposes that the AI caller is a **service principal** distinct from any human user, with these rules:

1. The principal is issued and validated through the authentication authority, not by the application. It has no
   Administrator role and no membership, and it cannot hold an operation proof for any privileged operation.
2. Read scope is an explicit **project allowlist** granted by an Administrator through a separate, audited grant.
   The grant is per project and per data classification ceiling.
3. Each read is checked in the database under the same rules the human path uses: an active project membership or
   project access grant that permits the read, the data-classification floor, and a restricted-content grant for
   restricted items. Quarantined versions are never readable by any principal.
4. Every read is audited with principal, project, requested object identifier, decision and error class. Refusals are
   audited, and the audit survives the refusal.

*Not decided here:* whether the principal may act on behalf of a human (delegation), its lifetime, its rotation, and
whether restricted content is ever readable by an AI principal. These are D-AI-1 to D-AI-3 below.

## 3. Versioning

- The contract is versioned in the path (`/v1/...`) and by a `contract_version` field in every response.
- Within a major version, changes are additive only: new optional fields and new endpoints. Removing or renaming a field
  or changing a meaning requires a new major version and a WDS decision.
- v0.1 is this proposal. No endpoint below exists in the current API. Current routes are upload, source-content read,
  run start, run control, and reparse; none of them is an AI read surface.

## 4. Proposed read endpoints (v1 candidates)

| Method and path | Returns | Authorization | Notes |
| --- | --- | --- | --- |
| `GET /v1/projects` | Projects the principal may read | Allowlist and membership | Metadata only: `project_id`, `name`, `data_classification`, `status`, `revision` |
| `GET /v1/projects/{project_id}/source-versions` | Source-version metadata | Project read | `source_version_id`, `source_id`, `scan_status`, `parse_status`, `access_classification`, `revision` |
| `GET /v1/source-versions/{source_version_id}/content` | Clean source bytes | Clean scan, classification and grant | Exists today for human callers; an AI variant would add the principal rule |
| `GET /v1/runs/{run_id}` | Run state, status and revision | Project read | `state`, `status`, `revision`, timestamps. No model output in v1 |

Explicitly not proposed for v1: any endpoint returning credentials, sessions, operation proofs, approval details, contact
addresses, audit rows, or other principals' data.

## 5. Foundation-owned identifiers

Every identifier below is a UUID primary key in the Foundation schema (verified against the Phase 1 hardening database at
migration 0026). An AI caller may read these identifiers; it may not infer authority from them.

| Concept | Table | Primary key |
| --- | --- | --- |
| Project | `projects` | `project_id` |
| Source | `sources` | `source_id` |
| Source version | `source_versions` | `source_version_id` |
| Workflow run | `workflow_runs` | `run_id` |
| Run input snapshot | `run_input_snapshots` | `snapshot_id` |
| Workflow job | `workflow_jobs` | `job_id` |
| Workflow checkpoint | `workflow_checkpoints` | `checkpoint_id` |
| Source segment | `source_segments` | `segment_id` |
| Dependency edge | `dependency_edges` | `edge_id` |
| User | `users` | `user_id` |
| Role assignment | `role_assignments` | `assignment_id` |
| Project membership | `project_memberships` | `membership_id` |
| Access grant | `project_access_grants` | `grant_id` |
| Restricted-content grant | `restricted_content_grants` | `grant_id` |
| Contact approval | `user_contact_approvals` | `approval_id` |
| Withdrawal | `user_withdrawals` | `withdrawal_id` |
| Audit event | `audit_events` | `event_id` |
| Outbox notice | `outbox_notices` | `notice_id` |
| Setup ceremony | `setup_trust_ceremonies` | `ceremony_id` |
| Idempotency key | `idempotency_keys` | `key_id` |
| Operation proof (internal, never exposed) | `operation_proofs` | `proof_id` |
| Session (internal, never exposed) | `sessions` | `session_id` |

## 6. Foundation-owned workflow and status states

From the live CHECK constraints (not from memory):

- `workflow_runs.state` (19): `created`, `intake_pending`, `parsing`, `intake_complete`, `requirements_extraction`,
  `clarification_pending`, `routing_pending`, `specialist_investigation`, `evidence_validation`, `scope_drafting`,
  `independent_review`, `changes_required`, `approval_pending`, `approved`, `rejected`, `superseded`,
  `blocked_pending_decision`, `failed`, `cancelled`.
- `workflow_runs.status` (7): `queued`, `running`, `waiting_human`, `blocked_pending_decision`, `completed`, `failed`,
  `cancelled`. A run in `blocked_pending_decision` must have that `state`.
- `workflow_jobs.job_status` (6): `queued`, `leased`, `waiting_human`, `completed`, `failed`, `cancelled`.
- `source_versions.scan_status` (3): `not_scanned`, `clean`, `quarantined`. A quarantined version has `parse_status =
  pending`.
- `source_versions.parse_status` (5): `pending`, `succeeded`, `partial`, `failed`, `unsupported`.
- `projects.status` (2): `active`, `archived`.
- `users.status` (4): `pending_contact_approval`, `pending_activation`, `active`, `disabled`.
- `user_contact_approvals.status` (5): `pending`, `approved`, `rejected`, `cancelled`, `expired`.
- `outbox_notices.status` (4): `queued`, `leased`, `sent`, `dead_letter`.
- `audit_events.outcome` (4): `success`, `denied`, `conflict`, `error`.

These state sets are Foundation-owned. The AI engine may read them. It may not add states, and a state transition may only be
made by the Foundation.

## 7. Result persistence responsibilities (proposed split; decision D-AI-4)

- **Foundation owns:** run records, state transitions, checkpoints, input snapshots, job leases, source and project
  identifiers, audit events, and the revision checks on every write.
- **AI engine owns:** the content of its own analysis. It produces results that are *proposed* to the Foundation.
- **Not proposed in v0.1:** any AI write endpoint. Persisting AI results requires a separate, later write contract and a
  WDS decision on who may write which result types, under which run state, and with which proof.

## 8. Decisions WDS must make (not invented here)

- **D-AI-1:** Principal model: a service principal with an allowlist (proposed) versus delegation from a named human.
- **D-AI-2:** Whether an AI principal may ever read restricted content, and under which restricted grant.
- **D-AI-3:** Principal lifetime, rotation and revocation. Proposal: session-style expiry through the authority, with
  immediate revocation by an Administrator.
- **D-AI-4:** Which side writes AI results, and whether a Foundation-issued proof is required for each result write.
- **D-AI-5:** Retention and redaction of AI request logs. Proposal: audit rows only, with no content in logs.

## 9. Integration readiness

- **Not ready.** No v1 read endpoint exists. The authority-issued principal path does not exist. The proposal needs
  WDS decisions D-AI-1 to D-AI-5 first.
- **Ready to draft once approved:** read-only handlers over the existing authorization functions, contract tests against
  the endpoints above, and negative tests for quarantined, restricted, out-of-allowlist and revoked principals.
