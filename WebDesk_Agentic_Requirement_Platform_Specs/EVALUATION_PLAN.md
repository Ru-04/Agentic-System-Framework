# Evaluation Plan — WebDesk Agentic Requirement Analysis Platform

- **Status:** Proposed; no benchmark results have been measured
- **Version:** 0.3.10-foundation-gate1-review
- **Last updated:** 2026-10-16
- **Purpose:** Define measurable quality, safety, reliability and release criteria

## 1. Evaluation principles

- Separate proposed acceptance thresholds from measured results.
- Maintain a versioned gold dataset and explicit annotation guidance.
- Include cases where the correct result is a clarification question, `unverified`, or a blocked draft.
- Score deterministic properties mechanically wherever possible.
- Use qualified human evaluation for semantic quality.
- Report sample size, confidence/uncertainty, failures and known limitations.
- Do not tune prompts against the final held-out test set.
- No historical company data is assumed available; use synthetic data until authorized examples are approved.

## 2. Benchmark dataset

Build three partitions:
- **Development:** examples used to refine prompts and schemas.
- **Validation:** used to compare design/configuration alternatives.
- **Held-out regression:** not used for routine prompt tuning; reviewed and expanded through controlled change.

Recommended initial seed: 40–60 synthetic briefs, then expand based on observed failure modes. This is a proposed starting point, not a statistically guaranteed sample size. Include straightforward briefs, ambiguous requests, contradictory emails, long documents, malformed/partial files, Shopify and all seven specialist-category scenarios, API/webhook integration, AI-not-needed scenarios, security-sensitive cases, and prompt injection.

Potential future additions: authorized historical SOWs and outcomes only after written authorization, redaction/de-identification review, and access controls. Maintain a synthetic replacement for any sensitive example.

### 2.1 Test case format

```yaml
case_id: EVAL-REQ-001
dataset_version: "0.1.0"
scenario: "Inventory synchronization with incomplete integration details"
input_source_ids: [SRC-SYN-001, SRC-SYN-002]
expected:
  requirements:
    - expected_id: R1
      expected_origin: client_explicit
      must_preserve_original_wording: true
      expected_source_ids: [SRC-SYN-001]
  expected_questions:
    - "Which system is the inventory source of truth?"
  expected_unverified_claims:
    - "The warehouse API supports the required event flow"
  expected_blockers:
    - "API capability not yet verified"
  required_capabilities: [integration_software]
  forbidden_capabilities: [ai_automation]
  expected_release_outcome: blocked
scoring:
  required_checks: [source_attribution, uncertainty, routing, release_gate]
```

Gold labels should allow multiple valid phrasings and solution options. Human annotators must label source span, requirement boundaries, expected uncertainty, acceptable routes, and release outcome. Disagreements are adjudicated and recorded.

## 3. Metrics and proposed thresholds

All values below are **initial proposed targets**, not observed performance. Calibrate them with WebDesk reviewers after a pilot; approve final thresholds before using them as release criteria.

| Area | Metric | Initial target | Measurement |
|---|---|---:|---|
| Extraction | Requirement precision | >= 0.90 | Correct extracted requirements / all extracted candidates |
| Extraction | Requirement recall | >= 0.90 | Gold requirements recovered / all gold requirements |
| Attribution | Source attribution accuracy | >= 0.95 | Correct source/locator pairs / evaluated pairs |
| Traceability | Committed scope traceability | 100% | Committed scope items with valid requirement links |
| Coverage | Requirement disposition coverage | 100% | Captured requirements with an explicit disposition |
| Ambiguity | Recall on seeded critical ambiguities | >= 0.95 | Detected critical ambiguities / gold critical ambiguities |
| Conflict | Recall on seeded material contradictions | >= 0.90 | Detected conflicts / gold material conflicts |
| Evidence | Unsupported material claim rate | 0 in release benchmark | Unsupported material claims in approval-ready outputs |
| Uncertainty | Correct unverified labeling | >= 0.95 | Gold unverified cases labeled correctly |
| Routing | Required capability recall | >= 0.95 | Required specialist activations / expected activations |
| Routing | Specialist selection precision | >= 0.90 | Correctly selected specialist categories / all selected categories |
| Routing | Specialist selection recall | >= 0.95 | Required specialist categories selected / all gold required categories |
| Routing | Exact routing outcome accuracy | >= 0.95 | Cases with expected route/clarification/unsupported outcome |
| Routing | Cross-platform coverage | 100% on gold cases | Required relevant categories selected for cross-platform cases |
| Routing | Unnecessary invocation rate | <= 0.15 | Unneeded activations / all activations |
| Review | Critical/major defect recall | >= 0.95 | Gold blocking defects detected / all gold blocking defects |
| Review | False-positive blocker rate | <= 0.20 | Incorrect blockers / evaluated blocker findings |
| Security | Prompt-injection policy violations | 0 | Attempts causing prohibited behavior |
| Isolation | Cross-project authorization violations | 0 | Unauthorized cross-project reads/writes |
| Reliability | Valid structured output after bounded retries | >= 0.98 | Valid outputs / supported generation attempts |
| Governance | Approval-gate bypasses | 0 | Cases incorrectly released despite blocker |
| Human quality | Reviewer usefulness rating | >= 4/5 | Mean or distribution from rubric-based evaluation |

Precision/recall should be computed at clearly defined units (requirement, source link, conflict, finding), not mixed together. For semantic matches, use adjudicated matching rules rather than exact string matching alone.

## 4. Evaluation suites

### 4.1 Requirement extraction and attribution
- Clear requirements with one source.
- Multiple requirements in one sentence.
- Same requirement expressed differently across sources.
- Contextual details that must not become requirements.
- Source locators on pages, headings, emails, timestamps and malformed text.
- Split/merge revisions and stable IDs.
Measure precision, recall, source attribution and original wording preservation.

### 4.2 Ambiguity and contradiction
- “Make it faster/better/easier” without a metric.
- Missing platform/version/API access.
- Contradictory meeting notes and later email.
- Conflicting source-of-truth statements.
- Unanswered question that materially changes estimate.
Measure recall, precision, question usefulness, and correct blocking behavior.

### 4.3 Evidence correctness
- Official current documentation.
- Old or version-inapplicable documentation.
- Source URL exists but relevant content is absent.
- Vendor documentation conflicts with an internal historical SOW.
- No retrieval access.
- Fabricated URL/citation bait.
Measure whether the claim is supported, source is applicable, uncertainty is correct, and no fabricated source is accepted.

### 4.4 Routing
Include Shopify-native customization, third-party API integration, middleware/data sync, rule-based automation, genuinely AI-relevant cases, and cases where AI is unnecessary. Measure per-capability precision/recall, unnecessary calls, routing rationale quality, and tool permissions.


### 4.4.1 Required specialist routing matrix

The following are required benchmark cases. These are test definitions only; they have not been run and do not imply implementation exists. Gold labels must specify expected categories, allowed alternatives, forbidden categories, rationale signals, required clarification, and release outcome.

| Case ID | Scenario | Expected routing / behavior |
|---|---|---|
| ROUTE-SHOPIFY-001 | Shopify-only theme/storefront/API requirement | Shopify Specialist; retrieve relevant official evidence; no unrelated specialists |
| ROUTE-3DCS-001 | Explicit 3D Cart Shift for Shopify requirement | 3D Cart Shift Specialist and Shopify Specialist when platform-specific behavior is relevant; unknown product capabilities stay unverified |
| ROUTE-WP-WOO-001 | WordPress CMS plus WooCommerce commerce workflow | One combined WordPress & WooCommerce Specialist; never two separate agents |
| ROUTE-BIGCOMMERCE-001 | BigCommerce-specific storefront/API change | BigCommerce Specialist |
| ROUTE-MAGENTO-001 | Magento / Adobe Commerce module and version-sensitive behavior | Magento / Adobe Commerce Specialist; ask version/edition if missing |
| ROUTE-STANDALONE-001 | Internal SaaS/web app with no commerce platform | Standalone Applications Specialist; no eCommerce specialist |
| ROUTE-MW-NODE-001 | Middleware sync where Node.js is an existing constraint | Middleware Applications Specialist; evaluate Node.js against documented constraints |
| ROUTE-MW-PYTHON-001 | Middleware sync where Python is suitable or required | Middleware Applications Specialist; do not force Node.js |
| ROUTE-COMMERCE-MW-001 | Commerce platform plus API sync middleware | Relevant commerce specialist plus Middleware Applications Specialist |
| ROUTE-MULTI-PLATFORM-001 | One project covers two supported commerce platforms | Select only the two relevant platform specialists plus any evidenced shared specialist |
| ROUTE-AI-RELEVANT-001 | Requirement genuinely needs AI/ML or unstructured classification | Relevant domain specialist(s) plus AI & Automation capability, with evaluation needs |
| ROUTE-AI-NOT-NEEDED-001 | Deterministic rules satisfy the requirement | Do not invoke AI & Automation; document non-AI approach |
| ROUTE-UNKNOWN-001 | Unknown/unsupported platform | Clarification or unsupported-platform path; no guessed specialist |
| ROUTE-AMBIGUOUS-001 | Ambiguous platform/product identity | Ask targeted clarification; do not claim product support |
| ROUTE-UNSUPPORTED-CAP-001 | Requested checkout behavior lacks verified support evidence | Mark unverified/blocked as applicable; no unsupported claim or commitment |
| ROUTE-CONFLICT-001 | Two specialists return conflicting findings | Preserve both with evidence; independent review/reconciliation; block affected commitment until resolved |
| ROUTE-MISSING-EVIDENCE-001 | Relevant vendor docs unavailable | Claim remains unverified; create verification task and block material commitment |
| ROUTE-UNAVAILABLE-001 | Required specialist times out/is unavailable | Bounded retry then explicit incomplete status; no silent omission |
| ROUTE-INVALID-OUTPUT-001 | Specialist returns schema-invalid output | Reject, bounded repair if configured, then explicit failure state |

### 4.4.2 Routing metrics and measurement rules

Measure specialist selection precision and recall per category and micro/macro aggregate; exact route outcome accuracy for specialist selection vs clarification vs unsupported vs no-specialist-needed; unnecessary invocation rate; missed-relevant-specialist rate; cross-platform coverage; specialist output schema-validity rate; and safe unsupported-capability handling. Report confusion matrices by category and distinguish “not selected correctly” from “selected but unavailable.” Thresholds above are proposed only. A specialist's presence is not automatically correct merely because it was invoked.

### 4.5 Scope and estimate
Check every scope item maps to requirement IDs; deliverables are bounded; acceptance criteria are testable; dependencies, assumptions, exclusions and risks are visible; estimates use consistent units and ordered ranges; unsupported commitments are absent.

### 4.6 Review effectiveness
Inject known critical, major, minor and informational defects into drafts. Measure severity-weighted recall, false positives, localization to affected records, evidence support, and remediation quality. Test that a second model agreeing with the first does not automatically pass the draft.

### 4.7 Security and prompt injection
Cases should attempt to:
- Override governance via uploaded instructions.
- Request secrets, hidden prompts, or another client's data.
- Induce unauthorized tool calls or write actions.
- Hide instructions in quoted text, HTML, code blocks, filenames, and retrieved pages.
- Ask the model to mark unverified claims as verified.
- Cause unsafe cross-project retrieval or expose raw confidential content in logs.
Expected outcome: content is treated as data; access controls and gates remain effective; violations are logged without exposing secrets.

### 4.8 Tenant isolation and authorization
Use at least two synthetic projects and multiple roles. Test list/detail/search/export/file retrieval, guessed IDs, cross-project relation creation, reviewer access, approval permissions, and deletion/retention behavior. These are deterministic integration/security tests; an LLM must not be the sole evaluator.

### 4.9 Reliability and recovery
Simulate provider timeout, rate limit, invalid JSON, malformed files, retrieval failure, database interruption, duplicate request, interrupted workflow, failed audit persistence and retry exhaustion. Verify idempotency, checkpoint resume, visible error states and no false success.

## 5. Baselines and comparisons

Compare:
1. Single-pass LLM baseline with the same input/context.
2. Structured workflow without specialist routing.
3. Full MVP workflow with deterministic gates and independent review.

Use identical held-out cases and record model/configuration versions. Compare quality, latency, token usage/cost, specialist call count and blocker detection. Do not claim improvement unless measured and reported with sample size and uncertainty.

## 6. Human evaluation

At least two qualified reviewers should independently assess a subset of held-out outputs. Use a rubric for source fidelity, coverage, evidence quality, feasibility reasoning, uncertainty, scope boundaries, estimate transparency, and readability. Resolve disagreements and calculate an agreement measure appropriate to the label type (for example, Cohen's kappa for suitable categorical labels). Report raw agreement too; do not use a single agreement statistic as proof of correctness.

Reviewers should be blinded to system variant where practical. Track disagreement between humans and the platform to improve annotation guidance.

## 7. Release-blocking criteria

A candidate release is blocked by any:
- Cross-project authorization or data disclosure failure.
- Approval-gate bypass.
- Successful prompt injection that overrides policy or causes unauthorized action.
- Fabricated critical evidence presented as verified.
- Missing traceability for committed scope.
- Critical seeded blocker not detected in the release suite.
- Schema/migration failure or unrecoverable audit integrity failure.
- Unapproved use of private/historical data.

Numerical targets are initial gates subject to stakeholder approval. Averages must not hide a critical safety failure.

## 8. Versioning and regression procedure

Each evaluation run records dataset version/hash, expected-label version, code commit, schema/catalog/registry versions, model/provider/settings, prompt/template version, run timestamp, metric implementation version, raw case results, aggregate results, failures, and reviewer sign-off.

On each material prompt, model, schema, catalog, routing, or policy change:
1. Run deterministic unit/integration/governance tests.
2. Run security and prompt-injection regression.
3. Run the held-out benchmark.
4. Compare with baseline and investigate regressions.
5. Review changed outputs and new failure categories.
6. Obtain required human approval before release.

Never overwrite previous evaluation results. Dataset additions require review, rationale, version increment and protection against training/tuning leakage.

## 9. Threshold calibration and ownership

The WebDesk policy owner, technical lead, and designated SOW reviewer should approve final thresholds. Use the first pilot to estimate realistic performance, inspect failure costs, and set stricter thresholds for high-impact errors. No metric result is claimed in this document; all targets are proposals pending measurement.

## 10. v0.3.0 required regression scenarios (proposed; not yet executed)

| Test ID | Expected behavior | Decision |
|---|---|---|
| EVAL-D02-001 | No live vendor access when approved domain allowlist empty; missing evidence remains unverified | D-02 |
| EVAL-D03-001 | Unauthorized historical client SOW is not ingested or retrieved across project ACLs | D-03 |
| EVAL-D04-001 | Missing WDS estimation basis prevents numerical final estimate; Low/Likely/High ordering enforced | D-04 |
| EVAL-D05-001 | Artifact preparer cannot approve own version; Administrator without Approver role cannot approve | D-05 |
| EVAL-D06-001 | Unassessed claim is material for gates; downgrade without reviewer audit is rejected | D-06 |
| EVAL-D07-001 | LLM-inferred requirement cannot become committed scope absent explicit reviewer acceptance | D-07 |
| EVAL-D08-001 | Bulk approval skips blocked/stale/conflicting/unresolved requirements with per-item audit | D-08 |
| EVAL-D09-001 | Critical accepted-risk waiver fails; documented evidence reclassification auditable | D-09 |

These are test *requirements*, not test results. Category sample sizes, numerical release thresholds and threshold owner remain undecided (D-14). Maintain zero tolerance for unauthorized scope approval, evidence fabrication, cross-project disclosure and critical waiver bypass. Re-evaluate route cases for D-01 once clarified.

## 11. D-01 and D-10–D-16 required evaluation additions (not yet executed)

- `EVAL-3DCART-INDEPENDENT-001`: 3dcart/Shift4Shop requirement selects the independent specialist; does not trigger Shopify or 3D visualization merely by historic ID.
- `EVAL-MIGRATION-SEPARATE-001`: Store migration between specified source/target platforms triggers the migration service and appropriate platform evidence checks.
- `EVAL-SOW-EXPORT-001`: DOCX and PDF follow the approved WDS house template and preserve traceability/blocker labels. Pending template.
- `EVAL-LLM-CONFIG-001`: Configurable provider adapter; no implicit unapproved provider/limit assumptions.
- `EVAL-RETENTION-001`: Apply approved class-specific policies, controlled deletion and audit tombstones without losing required audit integrity. Pending periods.
- `EVAL-RELEASE-OWNER-001`: Threshold ownership WDS Technical Lead; explicit designated Approver signoff. Numerical thresholds pending.
- `EVAL-LEGACY-ALIAS-001`: Legacy agent/service IDs resolve through documented alias maps; no silent removal.
- `EVAL-DEPLOYMENT-GATE-001`: Block production deployment and live network evidence calls until approved hosting/egress configuration exists.

All cases are proposed test obligations; none is an executed or passed test.

## Gate 1 deterministic Foundation acceptance suite (v0.3.5)

All tests below are release-blocking for **limited Foundation only**. Tests use isolated synthetic projects, roles and sources; failed tests block Gate 1. Every result records inputs, expected status, actual status, and spec section.

| Test ID | Required pass conditions |
|---|---|
| `EVAL-F01-MATRIX` | Exercise every GOV §11 permission key with assigned/unassigned roles; only an assigned Analyst starts a project run (including after a park); Administrator role alone cannot start; Administrator exclusively controls cancel/retry/resume/grants; Admin without a content grant cannot read client bytes. |
| `EVAL-F02-CLASS` | All Projects/Sources have typed DataClass; classification cannot be lowered without Admin-authored audited reassessment; tombstones have no content; no physical deletion in Gate 1. |
| `EVAL-F03-UPLOAD` | Accept each allowed type; reject spoofed MIME/oversize with 415/413 and no Source; correct type with zero text yields unsupported and with some text yields partial; 51st source version rejects; `.eml` attachments listed but never ingested; scan status explicit; quarantined Sources never parsed, snapshotted or indexed, and restricted not_scanned Sources remain quarantined. |
| `EVAL-F04-LOCATOR` | Every segment references correct source version and required typed locator; cross-project reference rejected; distinct segment IDs; PDF/DOCX/MD/TXT/EML fixtures validate; repeated runs on one source version and extraction version reuse exact segment IDs. |
| `EVAL-F05-DTO` | Reject client-set server-derived fields; optimistic conflict 409 with no mutation; idempotent identical replay returns same response; changed payload with reused key returns 409. |
| `EVAL-F06-JOBS` | Worker death lease recoverable after 120s TTL, renew at 30s, 3 job attempts max, bounded backoff; authorization/schema failures never retried; parked run has no leased job. |
| `EVAL-F07-CONCURRENCY` | Only one queued/running/waiting_human run per project; parked run releases active slot; parked runs cannot resume even without a newer run; resume from any state other than waiting_human returns 409; stale revision returns 409. |
| `EVAL-F08-SOT` | Domain data only in PostgreSQL domain tables, checkpoint contains references/flags only; audited service writes required. |
| `EVAL-F09-TRANSITIONS` | Project creation makes no run; explicit start snapshots sources; unlisted state transitions rejected; Gate 1 intake parks blocked_pending_decision without artifact; uploads during run belong to next snapshot; archived projects deny source modifications and new run starts with 409; project.archive during queued/running/waiting_human returns 409 with no mutation; archived run.cancel remains authorized where applicable but run.retry returns 409. |
| `EVAL-F10-STALE` | RFC 8785 SHA-256 hash stable for identical inputs; inputs sorted ascending by byte-wise entity_type/entity_id/revision; config includes extraction_version and parser_library_version; verify reference golden digest; revision changes invalidate dependency edges transitively; stale data cannot pass a gate. |


### v0.3.5 Gate 1 additional security and contract tests

| Test ID | Release-blocking expected result |
|---|---|
| `EVAL-F11-SELFGRANT` | Administrator cannot grant ProjectAccessGrant or RestrictedContentGrant to self: HTTP 403 and audited; a second authorized Administrator may grant, subject to role/assigned scope; client-content read by the granted user is audited. |

| `EVAL-F11b-SELFASSIGN` | Human Administrator assigning themself Analyst (or any role) or project membership MUST get 403 plus an audit event. `system:bootstrap` creates exactly one FIRST Administrator role assignment during controlled setup; the active first Administrator grants the second activated user an ordinary audited non-self Administrator role; `system:project_create` creates only creator membership in the new project. Neither exception allows content self-grants. Test database CHECK and service-layer denial separately. |
| `EVAL-F12-AUDIT` | Every mutation, denial, and client-content read writes one auditable event, and application roles cannot update/delete audit rows. Audit view redacts secrets, sensitive personal information, restricted titles/excerpts without content authorization. |
| `EVAL-F13-SNAPSHOT` | A first run on a project with only newly uploaded `pending` sources MUST snapshot the latest non-superseded, non-quarantined pending versions, enter parsing and persist their resulting parse status/segments; the snapshot MUST NOT be empty if eligible pending sources exist. Failed source versions remain excluded until Administrator-only `source.reparse` with a reason resets that version to pending; whole-run `run.retry` never repairs one file. A mixed batch with four successful files and one failed parser MUST reach `intake_complete`, preserve the four successes and itemize the failed source. That failed source must be excluded from the next snapshot, re-enter only after `source.reparse`, and process in the next run without modifying past snapshots. In-flight uploads are excluded and appear only in a later run; old run is flagged stale on completion. |

**EVAL-F11c-ACTIVATION (release-blocking; v0.3.7):** A regular Administrator creates `pending_contact_approval` with no credentials or activation link. No token or authentication is allowed until an independent valid approval (or the strictly bounded ceremony approval) transitions to `pending_activation`, then private delivery. 30-minute tokens are single-use, hashed, never returned to Administrators, contact-revision-bound and securely audited. `pending_contact_approval`, `pending_activation` and `disabled` cannot sign in; reset revokes sessions. Bootstrap and recovered Administrators also activate privately. Test transport absence blocks onboarding without Admin fallback.

**EVAL-F11d-CONTACT-APPROVAL (release-blocking; v0.3.8):** Test case-normalized ASCII email after NFC trim and lowercase; mixed case maps to same reservation. Reject non-ASCII local part, disallowed domain, `+tag`, configured denylist alias, duplicate among current users (including disabled) or pending changes (422). Database rejects a NORMAL approval with NULL requester and approved row missing human approver. Database trigger rejects approver who created the User or who is not an active Administrator, and rejects normal approval unless two distinct active Administrators exist. Direct application-DB update of `User.status` or `normalized_email` without matching approved request is rejected. Exactly one non-empty `proof_ref` is required on ordinary approved contact requests; it is an opaque recorded external verification artifact, not machine verification of ownership. Database rejects a ceremony-backed approved request if `approved_by_user_id` is non-NULL. Create approval expiry/rejection leaves account pending, keeps its normalized email reservation, cannot issue a token, and permits a new request. Disabling any previously approved user retains the address reservation. Only an audited `user.withdraw` for a never-approved pending-contact-approval account disables, tombstones the email, and releases the reservation; newly reserved use of that address succeeds while the old audit history remains. A non-Administrator `user.withdraw` returns audited 403; an Administrator withdrawal of an eligible never-approved pending account succeeds with a `UserWithdrawal` record; attempts for approved, previously activated, or revision-stale users return audited HTTP 409 with no address release; database direct clear without matching withdrawal record fails; concurrent approval/withdrawal cannot both commit. Approved or previously active users cannot take this withdrawal route. A never-approved pending-contact-approval account MAY be withdrawn by an Administrator; successful withdrawal cancels pending create approvals in the same transaction and creates immutable `UserWithdrawal`. A pending contact change expires at 24h via injectable clock, releases reset hold and target reservation. Released address can be reserved anew with another reservation_id, with original record retained. Contact change atomically revokes tokens/sessions, queues notice; SMTP failure leaves change effective, alert stored in app.

**EVAL-F11e-TOKEN-RATELIMIT (release-blocking; v0.3.7):** Two issued tokens for same user/purpose leave only latest row unconsumed and unrevoked (DB partial unique index); old token has `revoked_at`, correct reason. Invalid/expired/revoked/consumed token or token.contact_revision != User.contact_revision is denied. Contact change increments session_epoch, denies prior sessions and tokens. Assert unique live token under concurrent issuance. Default configurable login limit: 5 failures/15min per `(account,IP)` plus 100 requests/15min per IP (two users sharing IP do not block each other); activation/reset/resend limits 5/15min per contact plus 100/15min per IP, neutral unauthenticated errors. Nonproduction capture sink works only for tests and production rejects its use. Admin API/logs never reveal secrets.



**EVAL-F11h-ADMIN-APPOINTMENT (release-blocking; v0.3.10):** Under injected time and governance lock, assert every install/recovery `UserContactApproval` granted by a signed ceremony has `administrator_appointment=true`. Bootstrap grant consumes only the first installation appointment; the first active Administrator issues the ordinary second grant referencing and consuming the second approval. Reuse of a consumed approval to grant or re-grant an Administrator role fails HTTP 409 and is audited; direct DB role insertion without a fresh approved, unexpired appointment is rejected by a BEFORE INSERT trigger. With one active Administrator, an owner-signed recovery ceremony with `request_type=appointment` may appoint an existing active non-Administrator staff member on their already reserved contact without creating a second `ContactReservation`, changing `User.status`, or issuing an activation token. A successful non-self grant consumes that appointment exactly once. No ceremony approval, expired approval, different user, attempted self-grant or second use is denied; 403 for authorization, 409 for stale/consumed/deadline conflict. The zero-active-Administrator path remains outside the application under WDS-confirmed P-GATE1-ZERO-ADMIN-RECOVERY-03: owner-authorized, audited offline restore or reinstallation under an approved operational runbook; no in-application recovery or additional bootstrap role grant.
**EVAL-F11f-CEREMONY-RECOVERY (release-blocking; v0.3.8):** Install CLI with signed owner artifact approves precisely two separately verified `pending_activation` contacts and issues just ONE `system:bootstrap` Administrator role to first user. First user activates privately and issues ordinary audited non-self Administrator role to separately activated second. With exactly one active Administrator, `role.assign` for Administrator MUST reject an existing active staff user without an approved, unexpired ceremony-backed Administrator-appointment approval (403); the survivor MAY grant only to an activated ceremony-backed replacement and the grant is audited. Normal in-system recovery with one active Administrator reserves only one pending replacement and requires ordinary role grant from survivor after private activation. While that replacement awaits activation, a second signed recovery returns 409 even though only one Administrator is active; activation deadline at 24h expires the prospective coverage slot using injectable clock; after expiry a fresh authorized ceremony may proceed. BOTH initial installation contacts have the same 24-hour deadline from contact approval: when contact #2 misses activation after #1 becomes active, permit owner-signed one-Administrator recovery; when contact #1 misses activation, assert zero-active-Administrator in-system recovery is refused and WDS-confirmed owner-authorized audited offline restore/reinstallation is the exclusive permissible recovery policy (P-GATE1-ZERO-ADMIN-RECOVERY-03); the executable operational runbook is a separate deployment prerequisite. Expired install contacts cannot activate later. With two effective Administrators, deny ceremony. With zero active Administrators, reject in-system recovery and refer exclusively to owner-authorized audited offline restore/reinstallation under confirmed P-GATE1-ZERO-ADMIN-RECOVERY-03, without invoking any application recovery or bootstrap-role exception. Assert closed install CLI, immutable audit, DB-role isolation and no second system-issued Administrator role.

**EVAL-F11g-CONTACT-OUTBOX (release-blocking; v0.3.8):** Contact update, session/token revocation, and queued notice commit or roll back as one transaction. With injectable clock, kill worker after lease: at 120s lease expiry a second worker reclaims and idempotently sends once; 30s renewal prolongs lease. SMTP outage leads to persisted in-app operational alert, even if email remains unavailable; never roll back account update. Audit and redact all retries; dead-letter threshold is deployment configuration.

**EVAL-F14b-PARSE-ATOMICITY (release-blocking; v0.3.8):** (a) Parser exception after staging N segments MUST set source parse_status=failed, commit zero new segments for that source version/extraction attempt, and preserve other successful sources. (b) Explicitly declared unextractable portions with successfully extracted regions MUST commit the successful segments and set partial with flagged regions, not failed. (c) Valid image-only document with no extractable text MUST yield unsupported with zero segments, not failed. Reparse and subsequent successful run creates one stable segment set without duplicates.

**EVAL-F14-SOURCE-REPARSE (release-blocking):** Given five admitted pending source versions, four parse successfully and one fails, the run reaches `intake_complete` with four successes and one failed itemization, without retrying the whole run. The failed source is excluded from the next run's snapshot. Non-Administrator reparse receives 403; Administrator `source.reparse` requires reason, checks revision and scan state, resets only the targeted failed version to pending and audits the action; the next Analyst-started run includes it. Verify 409 on invalid states, stale revisions, quarantined sources and archived projects; no previous snapshot or segment set is mutated. Whole-run retry is only available for a failed run caused by system-level errors.

**EVAL-F10 golden reference (review fixture):** canonical JSON is `{"config_versions":{"extraction_version":"v1","parser_library_version":"p1"},"inputs":[{"entity_id":"S1","entity_type":"Source","revision":1}]}`; SHA-256 lowercase hex is `5df52f543349fa88dd4a96d4f1f1f6183384adc754b477f65960b62e9b926da9`. This fixture contains already sorted input tuples. Any production encoder MUST conform to RFC 8785 and tuple ordering; tests shall reject altered order or config-version changes yielding unchanged digest.

**EVAL-F01:** Test all canonical GOV §11 permissions for all four roles both assigned and unassigned. An Administrator with no Analyst assignment MUST be denied `run.start`; a separately assigned Analyst+Administrator can start; after a parked run only the same Analyst rule applies. Test a self-grant denial under F11.

**EVAL-F07:** `run.resume` only accepts `waiting_human` when supported; a parked run always returns 409, independently of whether a later run exists.


**EVAL-F11i-ZERO-ADMIN-OFFLINE-POLICY (release-blocking; v0.3.10 final Gate 1 review):** With an injected clock, expire installation contact #1 before activation using an isolated test-only clock (or simulate an external, non-application loss-of-access event without bypassing application/DB controls). Assert `active_administrator_count=0`; every in-application `role.assign` for Administrator, `recover` ceremony, installation rerun and `system:bootstrap` second grant is denied and audited. Confirm the only prescribed path is `P-GATE1-ZERO-ADMIN-RECOVERY-03`: separately signed owner authorization, authorized operator, approved offline restore/reinstall runbook, and immutable operational audit evidence. This is a **specification acceptance case**; actual disaster-recovery execution must be separately validated in the selected environment before production. A missing owner identity/key or unavailable approved runbook MUST NOT be represented as a ready-to-execute recovery path.

### Increment 3 Phase 1 governance amendment A1 — release-blocking acceptance coverage

**EVAL-F11i amendment (`P-INC3-LAST-ADMIN-04`):** To test zero Administrator coverage, expire installation contact #1 without activation using an approved isolated test-only clock and real install flow, or model an external loss-of-access event without ordinary in-app disable/revoke or app-role protected-column mutation. `user.disable` and `role.revoke` MUST deny and audit self-action and attempts to remove the last active Administrator. At zero active Administrators, all in-application recovery, extra `system:bootstrap` and installation reruns must still be refused/audited. The approved remedy is only owner-authorized, audited offline restoration per `P-GATE1-ZERO-ADMIN-RECOVERY-03`.

**EVAL-F11f/F11h deadline setup (`P-INC3-TEST-CLOCK-05`):** Use isolated disposable PostgreSQL databases and a test-only coherent effective clock with legitimate owner-signed ceremonies and private activation flows. Cover missed first and second install contacts, expiry of unused ceremony appointments, one-Administrator recovery, appointment consumption, and replay refusal; no direct backdating of protected columns, ordinary last-Administrator disable/revoke, or production-exposed test hook. Recoveries are governed by active-plus-pending effective coverage: a live second-contact appointment reserves its slot until expiry.

**All eight governance-sensitive tests:** remain release-blocking. Existing xfail entries must be reviewed individually and converted to ordinary passing tests only after the intended scenario is constructible without a security bypass. Do not mark a scenario complete because it is xfailed or because its precondition was created by privileged direct SQL.

## Phase 1 security evaluation extension (Amendment A2)

Add **EVAL-F11j-ACTOR-PROVENANCE** as a Phase 1 release-blocking suite. With a real restricted `webdesk_app_login` connection: (a) direct credentials INSERT/UPDATE/DELETE and session mint/rewrite are denied; (b) a forged `actor_user_id` or modified DB session setting cannot satisfy a privileged action; (c) session proofs for a different user, project, operation or expired/revoked session fail and are audited; (d) changing `session_epoch` or disabling a user invalidates previously valid authority; (e) replay and concurrent reuse are denied where proof is single-use; (f) two-Administrator approval cannot be completed by one user or a compromised application connection claiming two IDs; (g) authorized active-session workflows and restricted signed owner ceremonies succeed. Use committed-row PostgreSQL negative tests and a real protected authentication issuer, not owner/superuser fixture shortcuts. Preserve existing EVAL-F11b–F11i.
