# Management decision register (26 October 2026)

**Approval source:** chat approval by the WDS Authorized Approver, 26 October 2026, in reply to the consolidated request that listed ARCH-01 to QA-01. Reply: "I approve all". This is management authorization. It is not QA acceptance, not a signature, and not PG's review.

**Management role:** WDS Authorized Approver (the approver's personal name and signature are not recorded here and are not inferred).

## Approved decisions

| ID | Title | Approved scope (exactly as recommended) | Status |
|---|---|---|---|
| ARCH-01 | Primary framework | WebDesk is the authoritative application, security, governance, workspace and workflow platform. AI Engine components are reused through versioned adapters. Adapters cannot bypass WebDesk authorization or evidence controls. | APPROVED (direction only) |
| ARCH-02 | Adapter contract | Adapter contract v0.1 approved for isolated development and conformance testing. WebDesk owns workspace context, actor identity, allowed actions, routing authorization, evidence admission, security controls and audit boundaries. Live model execution stays disabled. | APPROVED for isolated development and conformance testing only. No production connection |
| ARCH-03 | Duplicate implementations | Both framework implementations are preserved for now. AI Engine components are reused only after functional parity, security verification, regression testing, contract conformance and an approved migration decision. No early deletion. | APPROVED |
| SRC-01 | Official documentation sources | Each source is approved individually, after verifying ownership, domains, paths, editions and versions, retrieval method, and access and provenance limits. Default-deny applies to everything else. | APPROVED as the process. No individual source is approved by this entry |
| SRC-02 | Shift4Shop documentation | Locate and verify Shift4Shop's official developer and platform documentation, then present the verified source and access scope for approval. No domain is authorized by appearance in search results. | APPROVED as the process. No Shift4Shop source is approved yet |
| TECH-01 | Standalone Applications | Technology-neutral specialist. Technology is chosen from each requirement and the approved scenarios. No fixed frontend, backend or database stack. | APPROVED |
| TECH-02 | Middleware Applications | Technology-neutral specialist covering API integrations, webhooks, synchronization, queues, retries, idempotency, security and observability. Node.js may be evaluated but is not the only permitted technology. | APPROVED |
| MAG-01 | Magento evaluation | Initial Magento investigation starts with Magento Open Source. Adobe Commerce is a separate edition with its own evidence and feature validation. Capabilities are not carried between editions. | APPROVED |
| GOV-01 | AI-S04 approval status | The historical AI-S04 statement is preserved. Its approval status is UNVERIFIED until a dated approval record exists. AI-S04 functionality is not accepted by this decision. The reviewed commit, test results, scope mapping and limitations are presented for formal approval. | APPROVED as the process. AI-S04 approval: UNVERIFIED |
| QA-01 | Blocked test execution | Application Control error 4551 is not bypassed. Earlier results are kept with their commits. Current-head pytest and mypy are NOT EXECUTED. An authorized environment is sought. Current-head execution is required before mandatory acceptance. PG's review and sign-off remain pending. | APPROVED |

## Status corrections
- **AI-S04 approval wording:** the uncommitted edit in the integration worktree to `docs/AI_S04_QA_AND_ACCEPTANCE_REGISTER.md` and `docs/AI_SPRINT_STATUS_AI02.md` reads "Synthetic-Scope Engineering APPROVED". That wording is not supported by a dated approval record. It should read "UNVERIFIED pending approval record". That edit belongs to uncommitted work I did not make, so it has not been changed here. It needs correcting by whoever owns that worktree, or by an explicit instruction.
- **Committed status:** `docs/AI_SPRINT_STATUS_AI02.md` at commit `052d853` reads "IN PROGRESS" for AI-S04. That is consistent with this register.

## Not decided here
- Which framework keeps each platform, and removal of duplicates (ARCH-03 defers this).
- Any individual evidence source (SRC-01 and SRC-02 approve the process only).
- Any production activation, live model call, external retrieval, or Git push (deferred).
- Sprint 3 acceptance, PG's independent review, and PG's sign-off.

## Frozen plan
The 4-milestone, 9-sprint baseline is unchanged. Sprint 3 acceptance remains subject to its mandatory gates. Sprint 4 remains unstarted.

## Second chat approval (26 October 2026): implementation authorization
Source: WDS Authorized Approver, chat, 26 October 2026 ("Formal Approval and Continue Seven-Specialist Development"). Management authorization only. Not QA acceptance, not a signature, not PG review.

| ID | Approved scope | Status |
|---|---|---|
| INT-01 | Adapter contract v0.2 implemented and tested. WebDesk authoritative for workspace, actor, execution authorization, evidence admission, audit and approval/routing. No breaking change without versioned tests. No invented confidence. | Approved for implementation and testing. Code uncommitted; tests NOT EXECUTED (see TEST-01) |
| INT-02 | Synthetic vertical slice through the adapter, using the existing fixture. Deterministic test-only specialist. Production integration blocked (QA-07, M3 S6). | Approved. Implemented as a test-only harness |
| DEV-01 | BD assigned to Standalone Applications and Middleware Applications lanes. BD may build, write tests, fix defects and document. BD must not give independent QA acceptance for BD work. | Approved assignment (management decision) |
| TECH-01 | Standalone Applications technology-neutral. Concrete technology only with a verified project scenario and approved sources. | Approved (restates the 26 Oct decision) |
| TECH-02 | Middleware Applications technology-neutral. Node.js not the only option. | Approved (restates the 26 Oct decision) |
| SRC-01 | Verification and configuration preparation only. Default-deny. Exact allowlist prepared for a separate activation approval. No live requests for candidates. | Approved for preparation only |
| SRC-02 | Shift4Shop source discovery only. No invented domain. No retrieval without source-specific authorization. | Approved for discovery only. Discovery candidate recorded; ownership not yet verified |
| QA-01 | PG nominated Independent QA Reviewer and Authorized QA Acceptance Signatory. PG personally confirms independence. Assistant does not fill PG declaration, labels, findings or signature. | Approved (restates the 26 Oct decision). Independence PENDING |
| TEST-01 | Run current-head tests through an authorized environment only. Do not bypass error 4551. Record NOT EXECUTED if unavailable. | Approved. Not achieved: no authorized environment available in this session |

## M2 Sprint 3 engineering approval (26 October 2026, chat)
Source: WDS management approval, chat, 26 October 2026, stated by the approver as "I, AS (Arushi Sharma), acting as WDS Authorized Approver". Recorded as stated. No handwritten or cryptographic signature is recorded or required by this entry. Management authorization only: not QA acceptance, not PG review.

- **Decision:** ENGINEERING ACCEPTED WITH CONDITIONS, FORMAL SPRINT ACCEPTANCE PENDING.
- **Bound to:** implementation `3969a8f`; documentation `5105628`.
- **Approved scope:** six specialist foundations on the shared base; seven-specialist canonical compatibility; adapter v0.2; synthetic non-production vertical slice; associated unit, integration, typing and lint evidence; Sprint 3 engineering and governance documents; preparation for M2 Sprint 4.
- **Not authorized:** unconditional Sprint 3 acceptance; unapproved live retrieval; live model execution; production integration; pushes or protected-branch merges; changes to the frozen 4-milestone, 9-sprint plan.

| Condition | Responsible owner | Status |
|---|---|---|
| PG verifies independence personally, performs independent QA, and signs | PG | PENDING |
| 55-pair Shopify relevance review | Independent qualified reviewer (not yet named for this review) | PENDING, 0 of 55 |
| Required CI and hardening tests performed | Engineering, via authorized CI run on a pushed commit | PENDING (push deferred); hardening not run locally |
| Official evidence sources require separate approval | WDS approver, per source | PENDING; none approved |
| QA-07 runtime authorization implemented before applicable production integration | Engineering (M3 S6) | OPEN; production blocked |
| Milestone 1 acceptance dependencies | WDS and independent reviewers | OPEN |
| No platform declared technically verified from synthetic tests alone | Standing rule | Enforced |

## Decisions of 26 October 2026 (chat): B1-B6, C4, SEC-01
Source: WDS Authorized Approver, chat, 26 October 2026, based on verification report and test commit a69cd50.
- **B1 approved:** BigCommerce boundary `docs.bigcommerce.com/developer/docs/*` replaces `developer.bigcommerce.com/docs/*`; exact page `.../developer/api-reference/rest/admin/catalog/products/get-product` only. Not the `/api-reference/*` tree. Activation pending gates.
- **B2 approved with conditions:** WooCommerce `developer.woocommerce.com/docs/*` and `/guides/*`, for controlled read-only retrieval after Sprint 4 entry and activation gates. Ownership PARTIAL (Automattic via WordPress.org listing). Not conclusively verified.
- **B3 approved for narrowing:** exact-page allowlist to replace Adobe prefixes. Page activation pending; exact URLs need final approval. Shared Adobe Commerce and Magento Open Source content labelled; no edition feature inferred.
- **B4 deferred:** Shift4Shop inactive until vendor REST portal and documentation host relationship is verified.
- **B5 deferred:** Magento Open Source inactive until edition boundaries are established. C4 fetch showed the devdocs host redirects to Adobe.
- **B6 deferred:** WordPress developer documentation inactive pending verification and approval.
- **C4 approved:** limited fetch done (see verification results). Exact Open Source entries not yet proposed for approval.
- **SEC-01 approved and implemented:** duplicate scoped hosts refused with explicit error; exact_paths field added (default empty, existing entries unchanged); redirect and exact-page regression tests added (tests/unit/test_allowlist_sec01.py).
- **Active sources:** none. Inactive approved configuration: src/webdesk/evidence/approved_boundaries.py (WooCommerce, BigCommerce). Every platform profile keeps approved_source None.
- Standing: live LLM calls disabled; production blocked by QA-07; pushes deferred; PG review pending; Sprint 3 formal acceptance pending.

## Decisions ADOBE-01, MAGENTO-01, SOURCE-01 (27 October 2026, chat)
Source: WDS Authorized Approver, chat, "I approve all three", 27 October 2026. Bound to source verification at `40b6746`. Management authorization only.
- **ADOBE-01 approved:** exact URLs only: `https://developer.adobe.com/commerce/php/` (shared, labelled shared); `.../commerce/webapi/rest/`, `.../commerce/webapi/graphql/`, `.../commerce/extensibility/events/` (Adobe Commerce only). `frontend-core` excluded. No directory trees.
- **MAGENTO-01 approved with restrictions:** `https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/magento-open-source/overview` only. Version identification, release history, version applicability. Not proof of general feature support. `devdocs.magento.com` redirects refused; contributor install guide not capability evidence; Open Source feature docs unresolved.
- **SOURCE-01 confirmed:** WooCommerce `developer.woocommerce.com/docs/*`, `/guides/*`; BigCommerce `docs.bigcommerce.com/developer/docs/*` plus the approved product-catalog page. Unchanged. Not unrestricted retrieval.
- **Deferred activation:** all sources inactive. Activation needs source verification, Sprint 4 entry, security gates, and a separate activation approval.
- **Configuration:** exact-page entries added to `src/webdesk/evidence/approved_boundaries.py` under separate edition keys (adobe_commerce, shared_adobe_magento_open_source, magento_open_source_release_notes). Still inactive. No profile reads them.
- **Tests:** `tests/unit/test_sprint4_exact_pages.py` added. Status NOT EXECUTED: pytest and mypy blocked by Application Control error 4551 on 27 October 2026. Ruff format check passes. The configuration and tests are uncommitted until they run.

## Sprint 3 formal management acceptance (27 October 2026, chat)
Source: WDS management decision, chat, 27 October 2026, stated as "I, AS (Arushi Sharma), acting as WDS Authorized Approver". Recorded as stated. No signature recorded.
- **S3-ACCEPT-01 APPROVED:** M2 Sprint 3 engineering deliverables accepted, bound to `3969a8f` and `5105628`, with associated foundations and governance records. Supersedes ENGINEERING ACCEPTED WITH CONDITIONS. Not extended to Sprint 4 changes or to untested working-tree changes.
- **S3-QA-01 REPORTED BY MANAGEMENT:** PG QA completion and PASS (no defects) reported by WDS management. PG personal sign-off: PENDING VERIFICATION. PG independence declaration: PENDING VERIFICATION. No PG-signed record exists in the repository (only the blank template).
- **S3-GATE-01:** formal gate closure PENDING. Current-head tests partly NOT EXECUTED; CI and hardening OPEN; 55-pair review OPEN. See `SPRINT3_ACCEPTANCE_RECONCILIATION_2026-10-27.md`.
- **S4-PREP-01:** uncommitted `approved_boundaries.py` and `test_sprint4_exact_pages.py` preserved. NOT EXECUTED (Application Control 4551). Not claimed as verified or accepted.
- Standing: no push; live LLM disabled; production blocked (QA-07); no unapproved retrieval; Milestone 1 acceptance separate.

## PUSH-01, CI-01, ACCESS-01 (27 October 2026, chat)
Source: WDS Authorized Approver, chat, "I approve all three", 27 October 2026. Verified at HEAD `fab9230`; remote tip `abf13a9` (fast-forward, no divergence).
- **PUSH-01 approved:** normal, non-force push of `claude/webdesk-specialist-baseline-v1-3b21b1` to origin. No protected-branch merge, no deployment, no production activation. Uncommitted changes excluded.
- **CI-01 approved:** run existing CI checks against the pushed committed SHA. Do not claim uncommitted Sprint 4 configuration passed CI.
- **ACCESS-01 approved:** restoration of authorized GitHub write access through normal administration. No credential modification or bypass by the assistant.

## Retrospective and Sprint 3 / Sprint 4 decisions (27 October 2026, chat)
Source: WDS Authorized Approver, chat, 27 October 2026, stated as "I, AS (Arushi Sharma), acting as WDS Authorized Approver". Recorded as stated. No signature recorded.
- **A1 APPROVED RETROSPECTIVELY:** retain `db9e785` (documentation-only, CI run #27 record). Record that the push exceeded its approval scope when made; WDS then authorised retaining it. Commit-specific ratification only. Not blanket approval for future pushes. No revert. No history rewrite.
- **A2 APPROVED AND CONFIRMED:** M2 Sprint 3 formal management acceptance against `3969a8f` and `5105628`, with associated seven-specialist foundation deliverables and governance records. Foundation-level only. Does not claim real evidence-backed platform investigation. Not extended to later Sprint 4 changes.
- **A3:** WDS confirmation of PG QA outcome APPROVED. PG QA result as reported by WDS: PASS, no defects reported. PG personal independence declaration: PENDING VERIFICATION (no PG-completed declaration in repository). PG personal review and sign-off: PENDING VERIFICATION (no PG-signed record in repository). Not treated as verified.
- **A4 AUTHORIZED:** commencement of M2 Sprint 4 engineering within frozen scope, non-production, deterministic investigation development and security testing. Does not authorise bypassing independent QA, unapproved documentation, live LLM calls, or production integration. Sprint 4 formal acceptance and source activation remain separate gates.
