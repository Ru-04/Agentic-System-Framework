# Independent Review Remediation Log — v0.3.7 Foundation Review Candidate

This log maps the 2026-10-16 independent review against the updates made. **Integrated** means the approved stakeholder policy has been reflected in documents, not that a code-ready contract, independent review finding or original contradiction is closed.

| Finding | State in this working draft | Work remaining / review question |
|---|---|---|
| C-01 | **PARTIAL** | D-01 clarified 3dcart/Shift4Shop as independent eCommerce platform; registry and catalog corrected, but legacy IDs/canonical alias policy and other old 3D wording need review. |
| C-02 | **PARTIAL** | D-06 materiality and criticality added to governance/schema; enumerate executable rule predicates, waiver/disposition safeguards. |
| C-03 | **PARTIAL** | Claim project_id/subject_refs, solution claim_ids, required scope commitment, project boundaries added; inspect and complete all entity graph FKs and examples. |
| C-04 | **PARTIAL** | ScopeItem.commitment and inferred acceptance policy added; implement actual deterministic validators/selected-solution links. |
| C-05 | **OPEN** | Explicitly DISABLED machine routing over legacy prose; controlled enums, precedence, structured predicates, human overrides pending. |
| C-06 | **PARTIAL** | D-02 hybrid RAG-first strategy recorded; vendor allowlist and live access configuration pending. |
| C-07 | **PARTIAL** | D-03 knowledge categories, document ACL/redaction and conceptual knowledge entities added; chunking, freshness, ranking, ingestion and shared ACL mechanics pending. |
| C-08 | **PARTIAL** | D-04 Task and range fields added; actual WDS reference dataset, aggregation and reviewer permissions pending. |
| H-01 | OPEN | Who validates material claim evidence and by what version/locator predicates? |
| H-02 | FOUNDATION REVISED — awaiting independent re-review | Dependency staleness/re-run transitions after changes. | |
| H-03 | FOUNDATION REVISED — awaiting independent re-review | Active-run concurrency and revision locking. | |
| H-04 | FOUNDATION REVISED — awaiting independent re-review | Durable worker/job execution and checkpoint recovery. | |
| H-05 | FOUNDATION REVISED — awaiting independent re-review | Checkpoint state vs domain table source-of-truth contract. | |
| H-06 | OPEN | Multi-specialist lead/contributors and conflict/handoff handling. |
| H-07 | OPEN | Candidate solution selection/decision model and approval actor. |
| H-08 | OPEN | Enforceable shared security/data/QA/operations checklists. |
| H-09 | OPEN | Independent reviewer retrieval and separation of deterministic gates. |
| H-10 | PARTIAL | D-05 fixed RBAC and no self-approval confirmed; Foundation matrix approved, later-phase matrix pending. |
| H-11 | PARTIAL | D-09 critical waivers disallowed and RiskAcceptance/Reclassification modeled; other waivers and permissions pending. |
| H-12 | PARTIAL | D-11 confirms platform migrations in MVP; separate catalog pattern added, but structured routing, migration contracts and source/target evaluation remain open. |
| H-13 | FOUNDATION REVISED — awaiting independent re-review | Canonical state-transition table needed; existing workflow depictions disagree. | |
| H-14 | OPEN | One consistent SpecialistOutput contract needed; legacy fields differ. |
| H-15 | OPEN | Registry DTOs need precise definitions. |
| H-16 | PARTIAL | D-08 acceptance and D-07 origin controls added; missing complete lifecycle and actor transitions. |
| H-17 | PARTIAL | D-14 appoints WDS Technical Lead as threshold owner and Approver as signoff; numerical thresholds, minimum dataset N and metrics remain open. |
| H-18 | PARTIAL | D-10 selects existing WDS house template and DOCX/PDF; exemplar, section-to-entity mapping, format contract and tests remain open. |
| X-01..X-15 | **NOT CLOSED** | All fifteen original contradiction IDs remain to be rechecked and reconciled. See original independent review. This is deliberately NOT an empty contradiction log. |
| M/L items | **NOT CLOSED** | D-12 provider selection remains open; D-13 retention periods open; D-15 ID compatibility policy chosen; D-16 hosting deferred. Recheck other M/L findings independently. |

### Re-review request

Check the original eight updated files and this register. (1) Verify each approved D-02..D-09 rule has a consistent representation, (2) flag conflicts left by the original 0.2.0 prose and new addenda, (3) distinguish a policy decision documented from an implementable predicate, (4) determine whether any subset can be approved for development without inventing business rules, (5) do not issue blanket approval when C-05, H-13–H-15 and other contractual gaps remain. Return each finding as RESOLVED / PARTIAL / OPEN with file and location. Do not edit files. 

### Decisions D-01 and D-10–D-16 update (2026-10-16)

- D-01: Corrected category semantics. 3dcart/Shift4Shop is standalone; no assumed Shopify dependency, 3D configurator or migration. Legacy identifiers retained but canonical aliases not approved. X-04 requires independent recheck.
- D-10: House SOW + DOCX/PDF confirmed; H-18 remains PARTIAL until a concrete template/export contract exists.
- D-11: Migrations in MVP; new separate catalog pattern, H-12 remains PARTIAL until implementable routing and validation are defined.
- D-12: Configurable LLM gateway confirmed, but initial model/provider and numerical operating budgets remain OPEN.
- D-13: Class-specific retention/deletion/tombstones confirmed, but exact periods and purge rules remain OPEN.
- D-14: Technical Lead owns thresholds; Approver signs off. H-17 remains PARTIAL until quantitative gates/sample sizes defined.
- D-15: Legacy IDs preserved; alias maps and validation still required.
- D-16: Hosting deferred; approval for deployment/live egress explicitly NOT granted.
- This package is **review-only**, not code-ready. Do not mark C-01/H-12/H-17/H-18 or X-01–X-15 closed without independent verification.


## v0.3.1 Foundation remediation status

F-1/F-2 approved; F-3 through F-10 specified as Foundation review candidates, not independently approved. F-3 upload MIME/size choices and F-6 retry/lease values are proposed technical defaults to be checked by the independent reviewer. Architecture §§5,7,13 replace previous ambiguous workflows and upload guidance; older diagrams are illustrative. N-01, N-09, N-13, N-14 addressed in-place. N-18 requires independent line-by-line confirmation. Other critical, high and routing/evidence/estimation issues remain pending their phases.

## v0.3.2 targeted Gate 1 blocker remediation (author-assessed, not independently verified)

| Blocker | Change | Author status |
|---|---|---|
| B-1 | Restored GOV §8 and §11 mandatory safeguards and ARCH §13 audit/threat modelling; rule-preservation check documented. | DRAFTED — needs external review |
| B-2 | Rewrote SCHEMA §9.5 to keep D-01 confirmed and Foundation contracts normative. | DRAFTED — needs external review |
| B-3 | Added permission-key matrix with Analyst-run.start only and Administrator run control, grants, downgrade. | DRAFTED — needs external review |
| B-4 | Added User/RoleAssignment/ProjectMembership/ProjectAccessGrant/RestrictedContentGrant schemas and local-auth adapter baseline. | DRAFTED — needs external review |
| B-5 | Defined RunStatus and its JobStatus mapping; parked/failed excluded from active-run constraint. | DRAFTED — needs external review |
| B-6 | Only POST /runs creates run; uploads snapshot and parked-slot behavior defined. | DRAFTED — needs external review |
| B-7 | Admitted-versus-rejected uploads, .eml attachment behavior, scan status and byte store defined. | DRAFTED — needs external review |
| B-8 | SourceSegment has LocatorType and type-specific locator fields. | DRAFTED — needs external review |
| B-9 | Project revision, expected_source_revision and 24h idempotency semantics added. | DRAFTED — needs external review |
| B-10 | DependencyEdge and RFC8785 canonical JSON SHA-256 rules introduced. | DRAFTED — needs external review |
| B-11 | Single-org no organization_id; nullable policy ref; Gate 1 archive only. | DRAFTED — needs external review |
| B-12 | Added EVAL-F01 through EVAL-F10 with explicit Gate 1 assertions. | DRAFTED — needs external review |
| B-13 | Set job lease TTL/renewal; documented WDS-acknowledged engineering defaults. | DRAFTED — needs external review |

### Conflict and regression log

- G-01–G-09: addressed in GOVERNANCE, ARCHITECTURE, and REQUIREMENT_SCHEMA for Foundation, pending independent verification.
- G-10: refreshed decision register; G-11: architecture RBAC link aligned; G-12: registry RBAC marker updated; G-14: job retries distinct from model-level retries; G-15: validation report reports checked assertions; G-16: segment locator wording aligned.
- G-13 reclassifier naming and all non-Foundation C/H/X/N items remain outside Gate 1 and open unless the external reviewer explicitly confirms closure.
- N-18: this table supplies explicit blocker IDs and modified canonical source sections; superseded normative paragraphs are not silently authoritative.

## v0.3.4 targeted Gate 1 remediation (author assessment; awaiting independent reviewer)

R1 pending-source snapshot, R2 no human self-role/membership assignment with approved system exceptions, R3 archive-during-run, and obsolete C-1 parked-resume wording are patched. EVAL-F11b and expanded EVAL-F09/F13 proposed. Independent reviewer must determine readiness; prior-phase items stay open.

## v0.3.5 review follow-up

- **v0.3.4 Blocker 1 (source parse retry):** SPEC PATCHED — Administrator-only `source.reparse` with reason and audit; isolated failures do not fail whole runs; EVAL-F14 specified. Awaiting independent confirmation.
- **v0.3.4 Blocker 2 (credential provisioning bypass):** SPEC PATCHED — `pending_activation`, private short-lived one-use activation and reset tokens, no Administrator-known credentials; EVAL-F11c specified. Awaiting independent confirmation.
- **Non-blocking:** clarified email metadata and deterministic input sort wording. No later-phase blockers are declared resolved.

## v0.3.6 — Focused remediation, pending independent Gate 1 check

| Review finding | v0.3.6 specification remedy | Gate 1 status |
|---|---|---|
| Contact-controlled stand-in activation | `pending_contact_approval`, independent `user.approve`, verified unique allowlisted contact and no token before approval | PROPOSED — WDS sign-off and re-review |
| Account takeover via changed email | Independently approved staged contact change; all sessions/tokens revoked, old address notified | PROPOSED — WDS sign-off and re-review |
| First/second Administrator setup | Owner-witnessed one-time separate setup trust ceremony with audit and fail-closed normal onboarding | PROPOSED — WDS sign-off and re-review |
| Failed parsing partial segments | Version/attempt transaction rollback, source-only failure, `EVAL-F14b` | DRAFTED — review |
| Multiple live activation/reset tokens | One live token per user and purpose; contact-revision binding; rate limits and `EVAL-F11e` | DRAFTED — review |
| Development/private transport | Local test capture sink allowed nonproduction only; delivery required in production | DRAFTED — review |

## v0.3.7 Gate 1 review queue

T1–T11: **SPECIFICATIONS REMEDIATED; AWAITING INDEPENDENT REVIEW.** See CHANGELOG_v0.3.7.md for finding-to-section mapping. No claim of verified implementation. CONTACT-01 and BOOTSTRAP-02 WDS approval is confirmed in DECISION_REGISTER. Actual production configuration prerequisites remain open.

## v0.3.8 diff-based resolution log

B1: GOV §11, SCHEMA §3.1, EVAL-F11b/F11f, DECISION_REGISTER (role assignment and zero-admin limitation). B2: same ceremony contracts (effective coverage). B3: SCHEMA §3.1, EVAL-F11d (non-null requester, DB triggers). B4: SCHEMA §3.1, EVAL-F11d (surrogate reservation key). S1: SCHEMA OutboxNotice, EVAL-F11g. S2: SCHEMA contact approvals, EVAL-F11d. S3: SCHEMA normalization, EVAL-F11d. S4: EVAL-F14b. S5: duplicate removal in GOV/SCHEMA. S6: SCHEMA User session_epoch (see v0.3.8 addendum). S7: EVAL-F11d injectable clock. S8: GOV wording.


## v0.3.9 C1–C4 traceability

| Finding | In-place correction | Review disposition |
| --- | --- | --- |
| C1 | Architecture §7, Governance §11, Schema §3.1 and EVAL-F11f define one bootstrap role plus permitted ceremony-backed surviving-Administrator grant | Pending independent verification |
| C2 | EVAL-F11d requires single `proof_ref` and tests ceremony approver NULL | Pending independent verification |
| C3 | Governance §11, Schema §3.1, EVAL-F11d align disable/create-rejection reservations and audited withdrawal | Pending independent verification |
| C4 | Governance §11, Schema §3.1, Architecture §7 and EVAL-F11f establish 24h install deadlines and missed activation consequences | Pending independent verification |

- C3 security follow-up: canonical `user.withdraw` authorization in Governance §11 and schema database trigger with negative EVAL-F11d tests.

## v0.3.10 R1/R2 verification mapping

| Finding | Canonical patch | Review state |
|---|---|---|
| R1 | GOV §11, SCHEMA §3.1 appointment marker/consumption, ARCH §7, EVAL-F11h | Corrected; pending independent review |
| R2 | EVAL-F11d precise 403/409, SCHEMA §3.1 named `UserWithdrawal`, GOV §11 atomic withdrawal and cancellation | Corrected; pending independent review |
| N1–N4 | `UserWithdrawal`, pending create approvals cancelled; rejected change reservation release; corrected README and v0.3.8 section history | Corrected; pending independent review |

Zero-active-Administrator out-of-system recovery remains a WDS policy acceptance gate.


## v0.3.10 Final Gate 1 review — WDS acceptance closure

- `P-GATE1-ZERO-ADMIN-RECOVERY-03`: **WDS CONFIRMED 2026-10-16**. Previously pending v0.3.8–v0.3.10 operational acceptance is superseded; in-system zero-Administrator recovery remains prohibited.
- Governing edits: DECISION_REGISTER latest decision; GOVERNANCE §11/decision summary; REQUIREMENT_SCHEMA §3.1 ceremony; ARCHITECTURE §7 installation and recovery; EVALUATION_PLAN EVAL-F11f and new EVAL-F11i; README current status. Earlier review/log notes are immutable historical findings.
- Scope boundary: final independent Gate 1 review pending; signed owner identity/key, independent verification procedure, production mail provider and approved offline recovery runbook remain deployment prerequisites. No application coding performed.
