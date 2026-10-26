# AI–Foundation Read Contract v1 (`ai-read/v1`)

**Status: APPROVED by WDS for read-only integration (non-production).** This document supersedes the proposal
`docs/AI_ACCESS_CONTRACT_PROPOSAL_v0.1.md`, which remains unchanged as the historical record. WDS approval covers the five
rulings in section 2 and the read-only scope in sections 4 and 11. It does not approve any write, result persistence, or
production deployment.

**Contract identifier:** `ai-read/v1`. **Owner:** Foundation. **Consumer:** AI engine (separate worktree; the Foundation does not
modify AI-engine files). **Baseline:** S0 is commit `82585db` (see `docs/AI_FOUNDATION_S0_MANIFEST.md`).

## 1. Principles

1. The AI engine is a consumer. It holds no database credentials and no human credentials. Every AI request carries one AI
   service credential, and that credential is scoped to one project and one run.
2. Foundation owns every persisted record. In v1 the AI engine writes nothing.
3. Authorization is evaluated in PostgreSQL on every request. An application-layer check is never sufficient on its own.
4. Denials are uniform and neutral to the caller (section 9). Every decision is audited (section 10).

## 2. WDS rulings implemented by this contract

| Ruling | Contract rule |
|---|---|
| **D-AI-1** AI identity | The AI identity is a dedicated **AI service principal**, issued by the trusted authentication authority through an operation-bound proof of the authorizing human (section 3). It is bound to one project and one run, and to the human who authorized the run (`bound_user_id`). It is never an Administrator, never a human user, and holds no operation proofs. Human impersonation is impossible: the bound human is taken only from the proof, never from a client-supplied identifier. |
| **D-AI-2** Restricted content | AI access to content classified `restricted` is **denied in v1**, and a restricted-content grant does not change this. Quarantined content (`scan_status = quarantined`) is never accessible to any principal. A future exception requires separate WDS approval. |
| **D-AI-3** Lifecycle | Credentials are short-lived (15 minutes, section 4), task-scoped (one run), and revocable. Expiry, rotation, cancellation, project permission changes and run termination are enforced on every request (section 4). |
| **D-AI-4** Result persistence | Foundation owns all persisted run and requirement records. AI results are proposals, never approved scope. **No AI write endpoint exists in v1.** The later write contract must specify a Foundation-controlled, independently enforced run/job-scoped authorization boundary. |
| **D-AI-5** Logging | Ordinary logs and audit rows carry minimal metadata: principal identity, bound user, run, resource, decision, outcome, and correlation identifier. They never carry raw documents, credentials, token values, full prompts or full model responses. No retention period is asserted here; retention follows the Foundation retention policy. |

## 3. Principal creation and verification (D-AI-1)

### 3.1 Creation

`POST /v1/runs/{run_id}/ai-principal` (human route, existing session auth).

- Required: a live human session (`Authorization: Bearer <session>`), and an operation proof for `ai.principal.issue` with
  resource `project_id` (the run's project), obtained through the existing proof route. The project is the resource because the
  database's membership rule is evaluated against the proof's resource project. The run is then checked to belong to that
  project.
- The operation rule is `ai.principal.issue` for role `Analyst` with project membership required. The same holds for
  `ai.principal.revoke` (section 4). An Administrator without
  membership is refused.
- The authority role executes `webdesk_guard.fn_issue_ai_principal_with_proof(proof, run_id, token_hash, ttl_seconds)`, and
  it refuses a run whose project does not equal the proof's resource project. The
  database consumes the proof and derives the bound human from the proof actor. The authority generates the token
  (256-bit random, base64url), stores only its SHA-256 hash, and returns the token **once**.
- Only one live principal exists per run. Issuing a new principal for a run revokes the previous one (rotation).

### 3.2 Verification

Every AI request presents the token in `Authorization: AI-Principal <token>`. The database hashes the token and loads the
principal. The request is authorized only if **all** of the following hold at the moment of the request:

1. The principal is not revoked, and `now() < expires_at`.
2. The run belongs to the principal's project, and the run's `project_id` matches the path.
3. The run's `status` is one of `queued`, `running`, `waiting_human`.
4. The project's `status` is `active`.
5. The bound human is `active`, and still satisfies the human read rule for the resource (section 5). This is the
   enforcement of "the AI may read no more than the human who authorized the run".

An AI principal never inherits membership. Its scope is explicit: one project and one run (the principal row is the
service grant). Membership is not copied to the principal. Under condition 5, the bound human's current membership or
access grant is the basis for every read.

## 4. Credential validity, expiry and revocation (D-AI-3)

| Condition | Effect | Enforced by |
|---|---|---|
| TTL | `expires_at = issued_at + 15 minutes`. The DB rejects a longer TTL. | `CHECK` on `ai_principals`, and the issuance function |
| Rotation | A new principal for the run revokes the old one. | Issuance function |
| Explicit revocation | `POST /v1/runs/{run_id}/ai-principal/revoke` (human, proof `ai.principal.revoke`) sets `revoked_at`. | Revoke function |
| Run cancellation or termination | Run status leaves `queued`/`running`/`waiting_human` (for example `cancelled`, `completed`, `failed`, `blocked_pending_decision`). Requests are refused. | Per-request check (condition 3) |
| Project permission change | Loss of the bound human's membership or access grant, or disable of that human, refuses requests. | Per-request check (condition 5) |
| Project archived | Requests refused. | Per-request check (condition 4) |

Because every condition is checked on every request, there is no stale window beyond the request itself.

## 5. Data classification and read rules

- Effective AI read right for a source version = the bound human's human read right (`fn_can_read_source_version`) **and**
  `scan_status <> 'quarantined'` **and** `access_classification <> 'restricted'` **and** the version's project equals the principal's
  project.
- Restricted content: denied for every principal (D-AI-2). A restricted-content grant does not change this.
- Quarantined: never returned, listed, or acknowledged.

## 6. Endpoints (v1, read-only)

All AI endpoints use the prefix `/v1/ai`. Every request must send `Authorization: AI-Principal <token>` and
`X-AI-Contract-Version: ai-read/v1`. Only `GET` is defined. Any other method returns `405`.

| # | Method and path | Returns | Limits |
|---|---|---|---|
| 1 | `GET /v1/ai/runs/{run_id}` | Run metadata (below) | none |
| 2 | `GET /v1/ai/runs/{run_id}/project` | Project metadata (below) | none |
| 3 | `GET /v1/ai/runs/{run_id}/source-versions?limit=&after=` | Readable source-version metadata, page | `limit` 1–100, default 50 |
| 4 | `GET /v1/ai/runs/{run_id}/source-versions/{source_version_id}/segments?limit=&after=` | Segments of a readable clean version, page | `limit` 1–200, default 100; `text_content` at most 4,000 characters per segment |
| 5 | `GET /v1/ai/runs/{run_id}/source-versions/{source_version_id}/content` | Stored bytes, `Content-Type` = stored MIME | at most 10 MiB; larger returns `413` |

### 6.1 Response schemas

Run (`GET /v1/ai/runs/{run_id}`):
`{"contract":"ai-read/v1","run_id","project_id","state","status","revision","is_stale","failure_class","created_at","updated_at"}`.
`state` is one of the values allowed by the `workflow_runs.state` check constraint (migration 0007 and later). `status` is
one of `queued, running, waiting_human, blocked_pending_decision, completed, failed, cancelled`.

Project (`GET /v1/ai/runs/{run_id}/project`):
`{"contract","project_id","name","data_classification","status","revision"}`. `status` is `active` or `archived`.

Source-version list (`GET .../source-versions`):
`{"contract","items":[{"source_version_id","source_id","version","scan_status","parse_status","access_classification","revision","mime_type","file_size_bytes"}],"next_cursor"}`.
Only versions that satisfy section 5 are listed. `scan_status` is `not_scanned` or `clean` in results, never `quarantined`. `access_classification` is never
`restricted`. `next_cursor` is the last `source_version_id` returned, or `null`. Ordering is by `source_version_id`.
Fields `storage_key`, `content_hash`, `ingested_by_user_id` and `text_content_hash` are never returned.

Segments (`.../segments`):
`{"contract","source_version_id","items":[{"segment_id","locator_type","locator","text_content","text_truncated"}],"next_cursor"}`.
`text_content` is cut to 4,000 characters, and `text_truncated` is `true` when the stored text was longer. A segment
is returned only when its version satisfies section 5.

Content (`.../content`): the stored bytes, with `Content-Type` equal to the stored `mime_type`, and
`X-AI-Contract: ai-read/v1`.

## 7. Authorization of the request path

1. The `AI-Principal` scheme is required. A human session on an AI route is refused as `ai_credential_invalid`, and an AI
   credential on a human route is refused by the existing session check.
2. Every identifier in the path is checked against the principal's scope. A `run_id` other than the principal's run, a
   `source_version_id` outside the run's project, or a version the bound human cannot read all produce `404`, so existence is
   not disclosed.
3. Content reads are performed inside a database read that re-checks section 3.2 and section 5 in the same transaction as the
   read (no separate check-then-read window).

## 8. Explicitly excluded in v1

- Any write, any `POST`, `PUT`, `PATCH` or `DELETE` on an AI route.
- AI result persistence, requirement or evidence ID creation, citation creation, and any governance status.
- Restricted content (D-AI-2). Quarantined content (all principals).
- Direct database access, database roles or credentials for AI callers.
- Session, credential, proof or contact data in any response.
- Specialist routing, clarification, approval, and every operation on users, memberships or grants.
- Requirement, evidence and analysis-result tables. These do not exist in the Foundation schema (section 12).

## 9. Errors and denial behavior

| Status | `error` | When |
|---|---|---|
| 400 | `contract_version_unsupported` | Missing or unknown `X-AI-Contract-Version` |
| 400 | `invalid_request` | Malformed identifier, cursor or limit |
| 401 | `ai_credential_invalid` | Missing scheme, unknown token, revoked, expired, run not active, project archived, bound human not permitted. **One neutral message for all of these.** |
| 404 | `not_found` | Identifier outside the principal's scope, quarantined, restricted (D-AI-2), or not readable by the bound human (`resource_not_readable`, audited only) |
| 405 | `method_not_allowed` | Any method other than `GET` |
| 413 | `response_too_large` | Content above 10 MiB |

Denials never reveal which condition failed. The reason is recorded only in the audit row (section 10).

## 10. Audit and redaction (D-AI-5)

Every AI request, allowed or denied, writes one `audit_events` row in a transaction that survives any refusal (the denial is
recorded after the savepoint rollback, not inside it):

- `event_type`: `ai.read.allowed` or `ai.read.denied`
- `actor_type`: `system`; `actor_id_or_service`: `ai-principal:<principal_id>`, or `ai-principal:unresolved` when
  the presented credential matches no principal (the identity is then unknown and is not guessed)
- `project_id`; `correlation_id` from the request header `X-Correlation-Id` (a UUID, generated when absent)
- `record_refs`: the run identifier and the resource identifier (never content)
- `error_class`: the internal denial reason (for example `classification_restricted`, `token_expired`,
  `bound_user_not_permitted`); `outcome`: `success` or `denied`
- `redacted_details`: `{"contract":"ai-read/v1","route":"<template>","status":<code>,"bound_user_id":"<uuid>"}`

Never recorded: token values, token hashes, content, segment text, prompts, responses, or request bodies.

Limitation: a request refused before any database work (missing or unknown `X-AI-Contract-Version`, a missing
`AI-Principal` scheme, or a malformed identifier or limit) has no principal and no project, so it is answered without an
audit row. Those refusals reveal nothing about project data.

## 11. Pagination and response limits

Cursor pagination is keyset on `source_version_id` (or `segment_id`), with the cursor being the last identifier returned.
Limits are in section 6. Any `limit` outside its range is refused as `invalid_request`.

## 12. Ownership of persisted records

| Record | Owner | Written by | v1 |
|---|---|---|---|
| Projects, sources, source versions, segments | Foundation | Foundation services | read by AI |
| Workflow runs and jobs | Foundation | Foundation worker and services | read by AI |
| AI principals and their revocations | Foundation (authority-issued) | Authority and Foundation guard functions | created by human route |
| Audit events | Foundation | Foundation only | written for every AI request |
| Requirements, evidence IDs, citations, analysis results | **Not present in the Foundation schema** | none in v1 | **gap**; a later write contract is required (D-AI-4) |

## 13. Version compatibility

- The contract identifier is `ai-read/v1`. Every AI request and response carries it.
- Additive changes (new optional response fields, new error codes documented as additive) are allowed within v1.
- Removing or renaming a field, changing a status code, or changing the meaning of a state is a breaking change and requires
  `ai-read/v2`.
- A server that receives an unknown version refuses the request with `contract_version_unsupported`. It never falls back.

## 13A. Scan status, eligibility and transmission scope (WDS ruling, post-baseline clarification)

WDS ruling (recorded in `docs/GOVERNANCE_DECISION_REGISTER.md`, P-INC3-AI-SCAN-07). Three different questions are separated:

1. **Gate 1 source eligibility (approved specification, unchanged).** `scan_status = not_scanned` remains eligible for authorized
   Foundation processing (`REQUIREMENT_SCHEMA.md`: `RunInputSnapshot` selects versions with `scan_status != quarantined`; R1 first-run
   rule). `ARCHITECTURE.md` quarantines failed malware scans "when scanning is available". No Gate 1 component produces `clean`.
2. **Foundation-to-AI read authorization (this contract).** An AI principal may read a source version only if the version is not
   quarantined, not restricted (D-AI-2), and readable by the bound human under the existing rules, within the principal's
   project and run, and while the credential is valid. `not_scanned` versions satisfy this. Metadata and run-status reads are
   governed by the same credential checks.
3. **External model transmission (not part of v1).** Sending any source content to an external AI provider is not authorized by
   this contract. A `not_scanned` status does not authorize it. That requires a separately accepted content-safety, disclosure and
   deployment policy. v1 content reads are for the AI engine inside the Foundation boundary and for non-production testing with
   synthetic fixtures.

Quarantined and restricted content remain denied for every principal. This clarification changes no approved specification text.

## 14. Governance statement

No AI output creates verified, approved, accepted or governance status. v1 has no AI output path. Governance status is owned
by Foundation human workflows only.
