# WDS Decision Register — v0.3.7 Foundation Review Candidate

**Recorded:** 2026-10-16. **Status:** D-01 through D-15 stakeholder policy choices confirmed, except D-16 is explicitly DEFERRED; D-12 initial model/provider selection is open. Detailed contracts and configuration remain pending as listed below. The stakeholder choices are NOT equivalent to implementation readiness. This is a decision record, NOT development authorization.

| ID | Status | Decision or choice needed | Implementation constraints / follow-up |
|---|---|---|---|
| D-01 | **CONFIRMED — category correction; naming cleanup pending** | 3dcart/Shift4Shop is an independent eCommerce platform, comparable to Shopify; it is **not** a 3D product visualizer, nor inherently a migration service | Preserve legacy `CAP-3D-CART-SHIFT-SHOPIFY`, `ROUTE-3D-CART-SHIFT-001` and `SVC-3D-CART-SHIFT-SHOPIFY-001` identifiers for compatibility only, with corrected platform semantics. Agree canonical display label/alias and any new stable IDs before coding this specialist (C-01, X-04). |
| D-02 | **CONFIRMED — partial configuration** | Hybrid evidence: internal, access-controlled RAG first; then approved live vendor documentation for gaps/staleness/version sensitivity | Official read-only access; vendor domain allowlist **OPEN** and default-deny (C-06). |
| D-03 | **CONFIRMED — categories only** | WDS standards/guidelines; service catalog/approved solutions; historical client SOWs/proposals; historical development estimates; internal technical documentation | Individual document ingestion needs permission and client-confidentiality/redaction review (C-07). |
| D-04 | **CONFIRMED** | Hour estimates; BA, UI/UX, frontend, backend, QA, PM, DevOps; numeric basis from authorized historical WDS data plus standard WDS reference ranges; AI proposes, authorized reviewer approves | Tasks Low/Likely/High, evidence references and assumptions; concrete reference dataset **not yet provided** (C-08). |
| D-05 | **CONFIRMED — Foundation matrix approved; later-phase action permissions pending** | Four fixed MVP roles: Analyst, Technical Reviewer, Approver, Administrator; no self-approval; fixed RBAC | Foundation roles, action keys and role/assignment checks are approved in GOVERNANCE §11; later-phase action permissions remain pending (H-10). |
| D-06 | **CONFIRMED — predicates to detail** | Deterministic materiality, `unassessed` acts as material; only Technical Reviewer may downgrade with audited rationale; objective criticality triggers for security, privacy, data integrity, payment, access control and fundamental feasibility, unknown not safe | Specific deterministic triggers, non-downgradeable classes, and evidence verification actor policy to detail (C-02). |
| D-07 | **CONFIRMED** | AI-inferred requirements may become committed scope only after explicit authorized WDS reviewer acceptance | Preserve inferred origin, justification, evidence, exact revision and acceptance record (C-04). |
| D-08 | **CONFIRMED — eligibility detail open** | Individual and bulk requirement acceptance, bulk only eligible items; blocked/conflicting/stale/unresolved handled individually | Per-requirement audit events; complete status/role predicates still needed (H-16). |
| D-09 | **CONFIRMED** | Critical governance findings never waivable in MVP; always block final approval until resolved or formally evidence-reclassified | Audited finding disposition, no `accepted_risk` for critical; align H-11/X-08. |
| D-10 | **CONFIRMED — template contract pending** | Existing WDS house SOW structure; generate DOCX and PDF | Obtain approved exemplar/template, section/entity mapping, wording conventions, blocked-draft notices, formatting and export validation; integration to existing SOW-builder remains unspecified (H-18). |
| D-11 | **CONFIRMED — implementation contract pending** | Platform-to-platform migrations are included in MVP | Define standalone `platform_migration` service pattern, source/target assessment, data mapping, SEO/redirect/integration checks and dedicated evaluation cases; do NOT conflate with 3dcart specialist (H-12). |
| D-12 | **CONFIRMED — provider configurable; provider/model undecided** | Maintain configurable LLM provider adapter, with initial provider and model selected later | Initial credentials/provider, per-run budget, latency/token ceilings, failure behavior, model snapshot/pinning and data processing policy **OPEN**, required before LLM execution (M-13). |
| D-13 | **CONFIRMED — periods pending** | Retention policies by data class, controlled deletion and audit tombstones | Periods, legal holds, deletion request authorization, purge jobs, backups, security/privacy retention exceptions, and treatment of immutable records **OPEN** (M-09). |
| D-14 | **CONFIRMED — numeric gates pending** | WDS Technical Lead owns evaluation thresholds and calibration; designated Approver signs off on release thresholds | Named role-holders, minimum test N, numeric release gates and review/recalibration process must be specified before release (H-17). |
| D-15 | **CONFIRMED — alias mappings pending review** | Preserve existing IDs, deprecate obsolete/legacy aliases with documented canonical mappings | No silent deletion/renaming. `CAP-ECOMMERCE`, `CAP-INTEGRATION-SOFTWARE` and the legacy 3dcart-with-Shopify IDs require explicit alias mapping and compatibility checks (M-01/M-02). |
| D-16 | **DEFERRED BY WDS — deployment blocker** | Hosting selection deferred pending deployment requirements review | Hosting target, network egress, allowlist enforcement, secrets, data residency, backup and operational security remain unapproved. No production deployment; live web evidence cannot be claimed operational (C-06). |

## Earlier decision follow-ups (not silently decided)

1. Approved per-platform and per-vendor domain allowlist, source freshness thresholds and identity/version matching for evidence (D-02/D-06).
2. Later-phase role-by-action matrix still pending; Gate 1 permissions and preparer/submitter attribution are approved (D-05/F-1/B-3).
3. Deterministic materiality/criticality predicates and evidence verification authority, including reclassification authority (D-06/D-09).
4. Bulk acceptance eligibility and partial-success transaction semantics (D-08).
5. Approved WDS numeric estimation ranges and permissible historical sources (D-04).
6. Open unresolved independent review findings listed in `REMEDIATION_LOG.md`.

## Follow-up specification and configuration register (not approved by inference)

1. **D-01 / D-15**: Final canonical display name and canonical ID for the standalone 3dcart/Shift4Shop specialist, while retaining backwards-compatible legacy IDs. Confirm exact supported versions and documentary evidence before making platform capability claims.
2. **D-10**: Supply approved WDS house SOW template/example, sections and wording requirements, DOCX/PDF export acceptance tests, and the relationship to the existing WDS SOW-builder.
3. **D-11**: Define supported migration source/target pairs, included/excluded data types, validation, SEO and redirects, migration limitations and test fixtures.
4. **D-12**: Pick the initial LLM vendor/model, numeric token/latency/cost budgets, permitted data sharing, fallback/error behavior and model-version pinning before executing AI workflows.
5. **D-13**: Establish data-class retention durations, ownership, deletion/tombstone semantics, legal holds and backup-purge timelines.
6. **D-14**: Name accountable role-holders, approve numeric metrics/minimum samples and release criteria; keep unapproved thresholds non-gating except existing safety blockers.
7. **D-15**: Publish ID alias-to-canonical mapping and ensure registry/catalog/evaluation cross-reference tests cover legacy IDs.
8. **D-16 / D-02**: Decide hosting, outbound network policy and vendor-domain allowlist before real live evidence reads or deployment.
9. **Earlier decisions**: D-02 allowlist and source freshness; D-03 document authorization and redaction; D-04 approved historical datasets and numeric reference ranges; D-05 later-phase action-level RBAC; D-06 deterministic predicates and evidence verification authority; D-08 eligibility transitions and batch failure semantics remain outstanding.
10. **Independent review**: Existing critical/high findings and contradictions remain open unless specifically reverified; no implementation approval is implied by this register.


## v0.3.1 Foundation decisions

- **F-1 — APPROVED**: Foundation role×action matrix and project-assignment model, defined normatively in GOVERNANCE §11 and REQUIREMENT_SCHEMA §3.1. Remaining later-phase action matrix requires further specification.
- **F-2 — APPROVED**: Internal, Confidential Client, Restricted data classes and AuditTombstone record, in GOVERNANCE §8 and REQUIREMENT_SCHEMA §3.1. Retention durations/backup purge remain pending D-13.
- **D-01 — CONFIRMED semantics**: independent 3dcart/Shift4Shop platform; canonical ID and alias map pending D-15; do not label D-01 open.

## v0.3.2 Foundation decisions — WDS confirmed

| Decision | Confirmed policy | Status |
|---|---|---|
| B-3 | Administrator controls all run cancellation, retry authorization, resume, grants and classification downgrades. Analysts may only start runs on assigned projects. | CONFIRMED |
| B-6 | `blocked_pending_decision` parked runs release active project slot, history retained; new run cannot silently mutate prior snapshot. | CONFIRMED |
| B-7 | `.eml` subject/body parsed, attachments itemized but attachment bytes not ingested. | CONFIRMED |
| B-11 | Archive only for Gate 1; tombstone schema exists for later, no physical deletion/purge until retention policy approval. | CONFIRMED |

**Engineering defaults acknowledged for Gate 1 specification and verification (not production security authorization):** MIME types PDF/DOCX/TXT/MD/EML, maximum 20 MiB each, maximum 50 admitted source versions per project, no OCR, PostgreSQL single worker, 3 job attempts, 5-minute max backoff, 120-second lease TTL and 30-second renewal, 24-hour idempotency retention and isolated local content-addressed byte store. Security scanning availability and Restricted-content ingestion remain gated by ARCHITECTURE §13. D-13 retention periods remain open; D-16 production hosting remains deferred.

## v0.3.3 — WDS-approved C-1 and corrective contracts

**v0.3.4 decisions (WDS CONFIRMED):** R2 prohibits human Administrator self-assignment for roles and memberships; only audited `system:bootstrap` (one-time initial Administrator) and `system:project_create` (authorized project creator membership) are exceptions. R3 returns 409 on project archival while any run is queued/running/waiting_human; on archived projects run.cancel remains permitted if otherwise applicable, run.retry denied, and no unarchive. R1 adds pending source versions to the first-run snapshot; stale parked-resume qualification removed. Hosting, retention durations, and later-phase authorization remain pending.

- **C-1 CONFIRMED:** `run.start` is assigned Analyst only, including a new run after a parked one. Administrator needs a separate Analyst role and project membership to start. Administrator exclusively controls cancel, retry and resume. `blocked_pending_decision` cannot resume in Gate 1; `run.resume` is only for `waiting_human` where available.
- **C-2–C-9:** Technical contract remediations for security grants, authorization terminology, audit, snapshots, segment stability, quarantine, deterministic hash and archival. These are specification changes for independent approval, not application execution.
- **B-7 clarification:** EML requirement content is subject and body; minimal message-id metadata may be retained for provenance, not used as requirement content. Attachments remain unprocessed.
- **Further pending:** data-class retention durations, later-phase RBAC/approval actions, routing predicates and evidence allowlist, actual LLM provider, hosting.

## v0.3.5 — WDS-confirmed Foundation choices

- **Failed-source recovery — CONFIRMED:** Only Administrators may invoke `source.reparse`, with a nonempty reason and audit trail, to transition an individual failed source version to pending for the next Analyst-started run. Single-source parse failures do not fail the whole run. `run.retry` remains only for failed runs caused by system-level failures.
- **Credential provisioning — CONFIRMED:** Administrators never set, see, or choose user credentials. Newly created users require approved contact first (`pending_contact_approval`), then enter `pending_activation` (v0.3.7 supersedes this v0.3.5 creation-stage wording); a private, single-use expiring activation token delivered to the registered contact is required. Reset uses the same path. Creation, invitation, activation and reset are audited. Delivery provider/transport must be operational and tested before account onboarding, and cannot be silently replaced with admin-issued credentials.
- **Not approved by these decisions:** production hosting, deletion/retention durations, later-phase routing, initial LLM provider, or app deployment. v0.3.5 is a specification review candidate only.

## v0.3.6 — Proposed final Gate 1 contact-security decision (WDS SIGN-OFF REQUIRED)

- **P-GATE1-CONTACT-01 — HISTORICAL PROPOSAL; WDS CONFIRMED IN v0.3.7 BELOW:** Close v0.3.5's Administrator-controlled delivery-address bypass with WDS-domain allowlist, lowercase/unique/no-plus emails, creator-independent Administrator `user.approve`, independently verified ownership, two-person contact changes and old-contact notice. Neither Administrator may provision or redirect another person's credentials alone. No tokens until approval; no resets during pending contact change.
- **P-GATE1-BOOTSTRAP-02 — HISTORICAL PROPOSAL; WDS CONFIRMED IN v0.3.7 BELOW:** One-time organization-owner-witnessed installation process provisions a second independently verified Administrator, then closes its privileged path. Does NOT grant an additional regular `system:bootstrap` role exception or allow a human Administrator to self-approve. If WDS does not authorize this mechanism, Gate 1 onboarding stays blocked until an alternative approved independent verifier exists.
- **v0.3.6 engineering proposals — SUPERSEDED BY v0.3.7:** One live token per user/purpose; resend without secret disclosure; 5 attempts/15min per account and per IP; non-production capture mailbox only; parse failures persist no partial segments; `UserContactApproval` and `UserContactChangeRequest` contracts and EVAL-F11d/F11e/F14b. Actual WDS email domain(s), second-approver operator, external identity-verification procedure and production delivery provider are configuration prerequisites, not invented facts.
- **Gate 1 status:** SPECIFICATION REVIEW CANDIDATE; implementation authorization remains blocked pending independent reviewer verdict AND explicit WDS approval of the two proposed contact/setup policies. Previous approved decisions remain unchanged.

## v0.3.7 — WDS-approved security policies and remediation

- **P-GATE1-CONTACT-01 — CONFIRMED:** two-human-Administrator identity/contact approvals, domain allowlist and independent proof, unique email/current-change reservations, auditable contact changes, no token to unapproved contacts. Outbox notice failure is asynchronous and alerted, never a rollback of approved change.
- **P-GATE1-BOOTSTRAP-02 — CONFIRMED:** signed owner-authorized initial two-Administrator installation and bounded recovery ceremony exclusively when active Administrator count is below two; dedicated CLI/DB role, signed owner authorization, independent verifier, permanent closure of initial setup path, audited private activation.
- **Residual risks — ACKNOWLEDGED BY WDS (2026-10-16):** Two colluding Administrators or an Administrator with WDS mail-domain control could defeat some identity assurances. Out-of-band independent verification and reviewed owner-signature procedures are mandatory compensating controls. Approval is not a claim of absolute technical prevention.
- **Configuration prerequisites — OPEN / PRODUCTION-BLOCKING:** exact WDS-controlled email-domain allowlist and alias denylist, identified trusted WDS owner and signing key/authority, approved independent mailbox/identity verification procedure, and production private email delivery provider. Values MUST be provided and security reviewed before production activation.
- **Gate 1 status:** v0.3.7 specification candidate; no development authorization and no production security approval implied by remediation.

## v0.3.8 remediation (foundation review candidate)

- **B1 — Option A spec resolution:** one system bootstrap Administrator role grant only; first activated Administrator makes an ordinary audited non-self role assignment to separately activated second user. Survivor grants role after ceremony recovery with one active Administrator. Does not amend the approved R2 exemption.
- **B1 zero-Administrator recovery — PENDING WDS OPERATIONAL ACCEPTANCE:** no in-system grantor; owner-authorized offline restore/reinstall via independently documented audited runbook. Earlier approved recovery ceremony does not itself authorize this out-of-system process.
- **B2:** effective Administrator coverage counts approved unexpired ceremony-backed pending replacements, preventing serial recovery.
- **B3:** normal approval requires non-null requester and database-trigger-enforced separation/status transitions.
- **B4:** surrogate reservation ID plus active-address partial unique constraint.
- **S1–S8:** outbox leases, create-request TTL, email normalization, parse-boundary evaluation, duplicate removal, session_epoch session binding, clock tests and corrected activation wording.
- Production configuration remains open: WDS domain allowlist, owner/signing authority, verification protocol, email provider, operational restore runbook, outbox dead-letter threshold.


## v0.3.9 Gate 1 cross-contract correction (proposed review baseline)

- C1: restricted install approves two contacts but issues ONLY the first bootstrap Administrator role; the first active Administrator issues the second ordinary role grant. Exactly one active Administrator may grant Administrator role only to an approved, unexpired ceremony-backed appointee; arbitrary staff promotion below two is forbidden. In-system zero-Administrator recovery is refused.
- C2: ordinary approvals need a single non-empty `proof_ref`; no second evidence reference required. Ceremony approvals cannot also carry a human approver.
- C3: disabled users and rejected/expired create approvals KEEP normalized email reservations. Only an audited withdrawal of a never-approved `pending_contact_approval` user can tombstone the email and release its address.
- C4: both install contacts and recovery replacements must activate within 24 hours. Failure of first install contact leaves zero active Administrators; second failure after first activation allows one-Administrator recovery.
- **WDS ACCEPTANCE STILL OPEN:** Zero-active-Administrator recovery through owner-authorized offline restore/reinstall must be explicitly accepted; no application/system-role exception or implementation authorization is inferred.

## v0.3.10 Gate 1 specification corrections (review candidate)

- **R1:** Preserve R2 cardinality; `UserContactApproval` is the single-use ceremony appointment source (`administrator_appointment`, consumed metadata); `RoleAssignment.appointment_approval_id` with DB trigger; owner-signed `request_type=appointment` permits independently verified existing active staff during one-Administrator recovery without a new contact reservation. This is a scoped implementation of approved BOOTSTRAP-02, not a second `system:bootstrap` assignment.
- **R2:** `EVAL-F11d` corrected: never-approved accounts may be withdrawn; approved/previously active and stale requests return 409, unauthorized actor 403; named `UserWithdrawal` and pending-create cancellation are atomic.
- **Still pending WDS acceptance:** zero-active-Administrator owner-authorized offline restore/reinstall and its first-install-contact-missed activation consequence. **No Gate 1 implementation authorization is claimed.**


## v0.3.10 — Final Gate 1 WDS operational decision (CONFIRMED 2026-10-16)

- **P-GATE1-ZERO-ADMIN-RECOVERY-03 — CONFIRMED by WDS:** When there are **zero active Administrators**, there is NO in-application recovery, Administrator-role grant, reopening of the installation ceremony, or new `system:bootstrap` exception. Recovery is exclusively an **owner-authorized, audited offline restore or reinstallation**, performed by an authorized operator under an **approved operational runbook**. This includes the case where the first installation Administrator fails to activate within the 24-hour deadline. The owner-authorization evidence, verified operator, restored state and resulting audit evidence MUST be recorded in the operational recovery record before production access resumes. The offline recovery path does not grant an in-app security exception. The signed owner identity/key, the detailed operational runbook and production environment prerequisites are **configuration/delivery prerequisites still OPEN**, not purported to be supplied or approved by this policy decision.
- **Approval boundary:** This confirms the previously pending *operational policy only*. The v0.3.10 package remains a **Foundation review candidate** until independent Gate 1 approval; application implementation and production deployment are not authorized by this decision alone.
- **Historical corrections:** v0.3.8–v0.3.10 statements marking zero-Administrator recovery as *pending WDS acceptance* are superseded **only for the acceptance status** by `P-GATE1-ZERO-ADMIN-RECOVERY-03`; the no-in-system-bypass rule remains unchanged.
