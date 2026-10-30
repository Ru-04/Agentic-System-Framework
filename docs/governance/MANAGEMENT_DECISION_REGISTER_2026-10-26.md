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

## M2 Sprint 4 engineering acceptance with conditions (28 October 2026, chat)
Source: WDS Authorized Approver, chat, 28 October 2026. Bound to engineering commit `58d1a39` and CI run #36 (`specialist-ci`, SUCCESS). Full record: `SPRINT4_ACCEPTANCE_RECORD_2026-10-28.md`.
- **S4-ACCEPT-01 APPROVED WITH CONDITIONS:** M2 Sprint 4 engineering accepted at `58d1a39`: shared investigation engine, adapter v0.2 integration, seven-specialist synthetic investigation paths, deterministic classification and clarification, source-boundary and edition controls, workspace and authorization security tests, verified automated engineering baseline. Recognises the implemented and tested foundation only. Does not establish real evidence-backed investigation by any of the seven specialists.
- **Status recorded:** M2 SPRINT 4 — ENGINEERING ACCEPTED WITH CONDITIONS; FORMAL GATE CLOSURE PENDING.
- **Conditions open:** (1) PG personal independence declaration, review record and attestation; (2) frozen Sprint 4 acceptance criteria located and reconciled; (3) real documentation-backed investigations; (4) source activation through the applicable authorization process; (5) Shopify 55-pair human evaluation; (6) independent remediation clearance pending PG verification.
- **S4-QA-01 (cross-reference):** PG QA reported PASS, no defects, confirmed by WDS management. PG personal evidence PENDING VERIFICATION.
- **Sprint 5:** WDS authorizes preparation for M2 Sprint 5 — Specialist Evaluations. Formal Sprint 5 commencement is not claimed until the applicable transition gates are satisfied.
- Standing: no live LLM; production blocked (QA-07); no unapproved retrieval; no source active; no protected-branch merge.

## S4-SOURCE-OWNERSHIP-01 and controlled retrieval pilot (28 October 2026, chat)
Source: WDS Authorized Approver, chat, 28 October 2026.
- **S4-SOURCE-OWNERSHIP-01 APPROVED:** read-only, browser-based publisher-control checks of WooCommerce, BigCommerce, Adobe Commerce exact pages and the Magento Open Source release notes. Recorded in `SOURCE_OWNERSHIP_VERIFICATION_2026-10-28.md`. Result: publisher control shown for WooCommerce, BigCommerce and Magento release notes, and for one Adobe page. No owner statement found.
- **PILOT APPROVED:** controlled read-only retrieval pilot for two sources only: WooCommerce docs (`/docs/*`, within the approved boundary) and the BigCommerce exact product page. Activated in `ACTIVE_BOUNDARIES`. Results in `SOURCE_PILOT_RESULTS_2026-10-28.json`.
- **Pilot outcome, recorded as observed:** WooCommerce Store API products page fetched; outcome UNKNOWN (no version stated on the page). BigCommerce product page fetched; outcome VERIFIED for "product catalog read" as a single-product read, version `v3` taken from the page path.
- **Not activated:** Adobe Commerce, Magento Open Source release notes, shared PHP, Shopify, Shift4Shop, WordPress core, Standalone, Middleware.
- **Not granted:** PG review, frozen acceptance criteria, Shopify human labels, any expansion of approved boundaries.

## S4-PILOT-EVIDENCE-01 (28 October 2026, chat)
Source: WDS Authorized Approver, chat, 28 October 2026. Pilot engineering commit `8c65b88` (CI run #45, SUCCESS). Implementation of the decision: see the report and the commit that records this entry.
- **Decision A APPROVED (BigCommerce coverage):** capability `CAP-BIGCOMMERCE` and its definition are preserved. Single-product retrieval through the documented v3 product endpoint: VERIFIED BY APPROVED PILOT EVIDENCE. Broader product catalog reading: PARTIALLY VERIFIED. Product listing and searching: UNKNOWN. Other catalog operations: UNKNOWN. Engine and provider scope cited statements to the verified operation; regression tests added.
- **Decision B APPROVED (WooCommerce):** Store API products page retained within the pilot boundary. Version applicability: UNKNOWN. No version inferred from another page. Variation pricing not reported as verified. The Page Not Found response (HTTP 200) is excluded from evidence.
- **Activation:** only WooCommerce docs and the BigCommerce product page are active. No boundary was expanded.
- **Not granted:** PG review, frozen acceptance criteria, Shopify human labels, live LLM use, production integration.

## M2 Sprint 4 management acceptance with conditions (28 October 2026, chat)
Source: WDS Authorized Approver, chat, 28 October 2026. Bound to engineering commit `30243a3`, CI run #47 (`specialist-ci`, SUCCESS on `30243a3`). Prior CI: run #46 SUCCESS on `5e07783`, run #45 SUCCESS on `8c65b88`.
- **S4-MGMT-ACCEPT-01 APPROVED:** M2 Sprint 4 formally accepted by management with conditions. Scope: shared investigation engine; seven-specialist adapter integration and conformance; specialist specification packages and knowledge assets; controlled retrieval infrastructure; approved WooCommerce and BigCommerce pilot; source-boundary and workspace enforcement; deterministic clarification, unknown and refusal handling; capability-scoped evidence; passage-level citations and provenance metadata; regression, security and conformance tests.
- **Status recorded:** M2 SPRINT 4 — MANAGEMENT ACCEPTED WITH CONDITIONS.
- **S4-QA-02 (management-confirmed, not PG's personal record):** PG reported successful functionality and no defects. WDS management confirms the report. PG personal independence declaration, detailed review record and attestation: NOT IN REPOSITORY, PENDING.
- **Remediation:** NO DEFECT REMEDIATION REQUIRED based on the reported QA findings. Independent closure pending verification of PG's actual record.
- **Conditions open:** (1) PG personal independence and QA attestation evidence; (2) verify final CI against the accepted engineering SHA (verified: run #47 on `30243a3`); (3) approve the proposed acceptance-criteria reconciliation, not represented as the original frozen document; (4) preserve platform-documentation and capability-coverage limits; (5) real investigations only within separately approved boundaries; (6) Shopify 55-pair human relevance evaluation, 0 of 55, and other historical gates.
- **Sprint 5:** readiness and transition preparation authorized. Formal commencement remains subject to the mandatory transition gates and a reconciled scope.
- Standing: no live LLM; production blocked (QA-07); no source expansion; frozen four-milestone, nine-sprint baseline preserved.

## First merge scope: R4 chain held out (28 October 2026, chat)
Source: WDS Authorized Approver, chat, 28 October 2026.
- **MERGE-SCOPE-01 APPROVED:** the R4 migration chain (`af37f7b` through `89634a8`, migrations `0020` to `0027`, Increment 3 Phase 1 R4 work) is held out of the first merge. Its handoff verdict remains "NOT READY FOR INDEPENDENT PHASE 1 REVIEW" with release-blocking findings open. Nothing in the R4 chain is accepted by this decision.
- **Candidate for the first PR:** branch `claude/pr-candidate-m1-s4-no-r4` at `79c90bc`, the target `feature/increment-1-foundation` (`740b169`) plus 82 commits. CI run #49 on `79c90bc`: SUCCESS. Single migration head `0019`.
- **Not merged:** no protected-branch merge has been executed. The PR is awaiting explicit approval.
- **Open:** PG's personal review; Milestone 1 controls; R4 release-blocking findings for any later merge of the R4 chain.

## QA-07 ruling on the first merge (28 October 2026, chat)
Source: WDS Authorized Approver, chat, 28 October 2026.
- **QA-07-MERGE-01 RULED:** the QA-07 run-time authority enforcement gate ("make run-time enforcement a hard gate before any integration", `AS_REVIEW_PACKET_2026-10-23.md` Q7) **BLOCKS** the merge of the first development PR into the integration branch.
- **Consequence:** the first PR for candidate `79c90bc` is HELD. It cannot merge until run-time authority enforcement is in place and verified, or until WDS rules otherwise in writing.
- Not a ruling on production integration, which remains blocked by QA-07 under the standing restriction.

## M2 Sprint 4 management closure (30 October 2026, chat)
Source: WDS Authorized Approver, chat, 30 October 2026. Record: `SPRINT4_CLOSURE_RECORD_2026-10-30.md`.
- **S4-CLOSE-01 APPROVED:** M2 Sprint 4 management closure, bound to `e907861` (specialist-ci run #52, success). Commencement of M2 Sprint 5 authorized.
- **Status recorded:** SPRINT 4 MANAGEMENT CLOSED — CARRIED-FORWARD EVIDENCE AND INDEPENDENT QA RECORDS REMAIN TRACEABLE.
- **Not evidence of:** PG's personal review (not supplied, not backdated), Shopify 55-pair human labels (0 of 55), or real investigations beyond the two active pilot sources.
- **Carried forward:** O1–O7 as listed in the closure record. Sprint 5 plan: `SPRINT5_PLAN_2026-10-30.md`.
- **Proposed reconciliation:** `SPRINT4_5_ACCEPTANCE_RECONCILIATION_PROPOSED_2026-10-28.md` remains a proposed amended baseline, not the original frozen document. WDS did not review every clause of an unidentified revision.
