# Conflict and Decision Register

- **Status:** PROPOSED - NOT APPROVED
- **Rule:** Nothing here is resolved by editing a draft. Items are resolved by the named owner, in a reconciled version that is itself approved.
- **Severity:** Critical = blocks any approval or development claim, or creates a security or scope-validity risk. High = blocks approval of the affected scope. Medium = must be resolved before the affected sprint closes. Low = editorial or naming.
- **Status values:** OPEN = conflict or gap with a known owner. UNRESOLVED = a reference that could not be verified in the repository; its content is not reconstructed.
- **Owners** are roles from the drafts or the decision record. No person is named because none is named in the sources (see CR-17).

**Totals:** 35 items. Critical 3. High 18. Medium 11. Low 3.

---

## Critical

### CR-01 — Gate 1 "implementation-ready" versus "NOT implementation-approved"
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** `G1` L4 `**Verdict:** READY FOR LIMITED FOUNDATION IMPLEMENTATION`; G1 L6 `**Status:** Foundation implementation-ready`. Drafts: GOV L3, ARCH L3, RS L3, RP L3 `NOT implementation-approved`; SC L4 and AR L4 `working_draft_unapproved`; EP L3 `Proposed`. `README.md` L1 and L4 (`APPROVED LIMITED FOUNDATION BASELINE`, `READY ...`), but README L22 says "Gate 1 Foundation contracts have passed independent review" and README L35 says `This version is still **NOT READY FOR IMPLEMENTATION**`. `DR` L84 `implementation authorization remains blocked pending independent reviewer verdict`. `CHANGELOG_v0.3.10_FINAL_REVIEW.md` L8 `not implementation authorization`. `VALIDATION_REPORT_v0.3.10_FINAL_REVIEW.md` `Independent review is required before coding authorization.`
- **Description:** The authorization and the specifications it relies on give opposite statuses. No single record shows an independent verdict that the drafts were approved. The README contradicts itself.
- **Impact:** S1 and S2 (any statement that Foundation or specialist code rests on an approved specification). Sprint 1 reports do not mention this conflict as a defect, although `docs/M1_S1_FINAL_GATE_REPORT.md` §1 does.
- **Proposed owner:** WDS decision-maker, with the independent reviewer named in the approval record.
- **Proposed resolution:** Either approve the drafts in the reconciled version, or amend G1 and README to match the drafts. Do not change either without a dated decision. Until then, state the status as "NOT implementation-approved".

### CR-02 — Specialist development authority versus draft statements that specialists are not implementation-cleared
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** `GOV` §18 L275 `D-01 platform semantics are CONFIRMED; canonical ID mapping and structured routing remain pending, so this specialist is not yet implementation-cleared.` `G1` section `## Excluded from Gate 1` (specialist routing; LLM calls; RAG; estimation; claims, review and SOW outputs). `ARCH` §19.4 L319–L321 ("No code development authorization is implied"). `ARCH` §20 L331 ("only local/specification work is currently authorized by these decisions"). Management: `docs/governance/DECISION_RECORD_2026-10-22.md` D01, D03; `docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md` §1.
- **Description:** D01 authorizes isolated, non-production development of all seven specialists from 22 October 2026. The drafts say that development is not authorized, and G1 excludes specialist work. D03 keeps G1 unchanged. The authority for specialist work is therefore a separate dated amendment, not the drafts or G1. The amendment is not a specification approval (its §4).
- **Impact:** S1 to S9. All specialist code depends on this authority. S1 and S2 are the first affected.
- **Proposed owner:** WDS decision-maker.
- **Proposed resolution:** Reconciled version cites the 22 October amendment as the development authority and states that the drafts remain unapproved. Remove the "not implementation-cleared" wording only when the reconciled version is approved, not by editing the draft.

### CR-03 — Evidence allowlist: no approved vendor domain list; Sprint 2 code carries a proposed list
- **Type:** GAP · **Status:** OPEN
- **Sources:** `AR` L769 `live_domains: []`; L770 `allowlist_state: pending_approval`; `AR` L103 `domain_allowlist_status: pending_D02_configuration_deny_by_default`; `GOV` §18 D-02 L266 (allowlist "currently **OPEN**"; "An empty allowlist is deny-all"). `DR` D-02 L8 (allowlist OPEN, default deny). `docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md` §3 ("Sprint 2 uses a proposed allowlist"). Code: `src/webdesk/evidence/allowlist.py` L40 `PROPOSED_SHOPIFY_ALLOWLIST`; `src/webdesk/evidence/http_vendor.py` L85–L86 (checks the allowlist before any network call; no redirects).
- **Description:** The drafts correctly contain no vendor list, and must not invent one. The Sprint 2 code carries a hard-coded proposed list. Until WDS approves a list, any live retrieval beyond the empty default breaks D08 and the draft rule that an empty allowlist is deny-all.
- **Impact:** S2 (critical). Also S4 (feasibility claims cannot be verified without it).
- **Proposed owner:** WDS decision-maker (approves the domain list and its per-vendor scope). Sprint 2 owner (makes the default empty and marks the list as proposed).
- **Proposed resolution:** The reconciled version states the allowlist as an approved-configuration input, default empty. The code list is loaded from approved configuration only, and no live call is made while it is proposed. No domain is added by the reconciler.

---

## High

### CR-04 — Sprint 1 blocker depends on an "approved v2.0 specification" that does not exist
- **Type:** CONFLICT (superseded) · **Status:** OPEN
- **Sources:** `docs/M1_S1_QA_CLOSURE_REPORT.md` §1 and §5 item 1 ("Blocks Sprint 1 closure"); `docs/M1_S1_FINAL_GATE_REPORT.md` §1, §5 item 1 and §6 item 1; management `DECISION_RECORD` D02 ("Do not claim a historical v2.0 implementation-approved package exists") and §3.
- **Description:** The Sprint 1 reports list the v2.0 package and its approval record as the first blocker. D02 supersedes that requirement by directing a new reconciled version. The reports have not been updated.
- **Impact:** S1 closure status. Also S2 start, which the final gate report ties to Sprint 1 closure.
- **Proposed owner:** Sprint 1 owner, with WDS decision-maker to confirm the re-scoped blocker.
- **Proposed resolution:** Replace the v2.0 blocker with "approval of the reconciled package (this PROPOSED package, once approved)". Do not change the Sprint 1 status until the human QA sign-off and CI items are closed (CR-18, CR-19).

### CR-05 — Sprint 1 cites a README and a zip package that are not in the repository
- **Type:** UNRESOLVED · **Status:** OPEN
- **Sources:** `docs/M1_S1_QA_CLOSURE_REPORT.md` §1 quotes `WebDesk_Agentic_Requirement_Platform_Specs_v0.3.10_FINAL_INDEPENDENT_REVIEW.zip` and its README `FOR INDEPENDENT RE-REVIEW ONLY — NOT APPROVED FOR IMPLEMENTATION`. The repository README L1 reads `v0.3.10 APPROVED LIMITED FOUNDATION BASELINE`. The zip was not found in the repository.
- **Description:** The quoted README text cannot be verified and differs from the repository copy.
- **Impact:** S1 evidence accuracy.
- **Proposed owner:** Independent reviewer.
- **Proposed resolution:** Either supply the zip with its hash, or correct the Sprint 1 report to cite the repository README. Do not reconstruct the zip's contents.

### CR-06 — Shift4Shop canonical name and alias status conflict with D06
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** Management D06 (canonical name "Shift4Shop (formerly 3dcart)"; legacy ID an internal compatibility alias). `AR` L246 `name: 3dcart / Shift4Shop Platform Specialist (legacy identifier)`; L248 `specialist_category: three_d_cart_shift_shopify_specialist`; L249 `status: proposed_canonical_name_and_alias_pending`; L291 `version: 0.3.0`. `SC` L67 `name: 3dcart / Shift4Shop eCommerce platform investigation (legacy identifier)`; L69 `specialist_category: three_d_cart_shift_shopify_specialist`; L943 `d01: ... legacy specialist ID retained`. `DR` D-01 L7 and D-15 L21 ("canonical display name and canonical ID" pending). `src/webdesk/specialists/catalog.py` docstring (lines 1–7) ("canonical display name and ID pending ... not a final name").
- **Description:** D06 decides the canonical display name and the alias status. The drafts still show the legacy name as the entry name and the naming as pending. D06 decides the display name but not a new canonical ID, so the ID question remains open.
- **Impact:** S1 (catalog naming), S3 (Shift4Shop entry), S5 (evaluation labels).
- **Proposed owner:** WDS decision-maker (confirms display name and any canonical ID); spec reconciler (applies it in the reconciled version).
- **Proposed resolution:** Display name: "Shift4Shop (formerly 3dcart)". Identifiers stay as they are until a canonical ID is approved (see CR-11). No new ID is invented in this package.

### CR-07 — Shift4Shop routing rule is not executable; routing predicates are OPEN (C-05)
- **Type:** GAP · **Status:** OPEN
- **Sources:** `AR` L34–L41 `ROUTE-3D-CART-SHIFT-001` ("legacy rule text only; NOT executable until structured router is approved"); L100 `structured_rules_status: pending_controlled_vocab_and_predicates_C05`; L101 `machine_routing_enabled: false`; L102 `legacy_when_fields: documentation_only_not_machine_executable`; L104–L105 `unresolved_specialist_ids: - CAP-3D-CART-SHIFT-SHOPIFY`. `RL` C-05 L11 `OPEN`. `RS` §9.5 L424–L426.
- **Description:** The routing rules are prose and disabled. No controlled vocabulary or structured predicates exist for any category. The Shift4Shop identifier is listed as unresolved.
- **Impact:** S6 (critical path), and S2 and S3 for any automatic activation.
- **Proposed owner:** Spec reconciler to draft predicates; WDS Technical Lead and designated Approver to approve.
- **Proposed resolution:** Specify the vocabulary and predicates as a separate versioned contract. Keep `machine_routing_enabled: false` until approval.

### CR-08 — No operator-confirmation step before specialist execution (D07)
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** Management D07 (AI recommends; authorized WDS operator confirms before execution). `ARCH` §3 L49–L52 and §4 L70 (deterministic capability router activates specialists); `AR` L9–L11 (`activate only relevant specialist categories`); `ROUTE-*` `activate:` fields L28–L99; `GOV` §5.3 L86 (specialist outputs are proposals). `AR` L241 `human_approval: No autonomous approval` (approval only).
- **Description:** The drafts route to specialists without an operator step. Machine routing is off, but the target design has no confirmation gate and no record of operator selection.
- **Impact:** S6. Also S2 (Shopify investigation must not start automatically).
- **Proposed owner:** WDS decision-maker (defines the operator role and its permission); spec reconciler (adds the gate and its audit record).
- **Proposed resolution:** Add a selection state "recommended - awaiting operator confirmation" to the routing contract, with an audited confirmation by an authorized operator. The permission key is for WDS to name; none is invented here.

### CR-09 — Evaluation case ROUTE-3DCS-001 expects Shopify co-activation for Shift4Shop
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** `EP` L128 `ROUTE-3DCS-001 | Explicit 3D Cart Shift for Shopify requirement | 3D Cart Shift Specialist and Shopify Specialist when platform-specific behavior is relevant`. Against: `GOV` §5.3 L82 (no presumption from the name); `GOV` L289 (the "3D Cart Shift for Shopify" narrative is a stale defect); `RP` §4.5 L77 (remains distinct from Shopify); `EP` L237 `EVAL-3DCART-INDEPENDENT-001` (does not trigger Shopify); management D06.
- **Description:** The gold label for this case contradicts the policy and the test that sits beside it in the same document. The case is a stale-narrative defect of the kind GOV L289 names.
- **Impact:** S5 (the case gates acceptance) and S6.
- **Proposed owner:** Spec reconciler; WDS QA owner to approve the corrected gold label.
- **Proposed resolution:** Replace the label with: Shift4Shop specialist only; Shopify specialist only when a Shopify requirement is present; unknown product capabilities remain unverified. Keep the case ID or record its supersession (EVAL-LEGACY-ALIAS-001).

### CR-10 — Legacy identifiers CAP-ECOMMERCE and CAP-INTEGRATION-SOFTWARE have misleading names and no approved mapping
- **Type:** GAP · **Status:** OPEN
- **Sources:** `AR` L211–L212 `id: CAP-ECOMMERCE` / `name: Shopify Specialist`; `AR` L501 `CAP-INTEGRATION-SOFTWARE` and L70–L74 `ROUTE-INTEGRATION-001` (`migration_compatibility`); `DR` D-15 L21 (`CAP-ECOMMERCE`, `CAP-INTEGRATION-SOFTWARE` and legacy 3dcart IDs require explicit alias mapping); `EP` L243 `EVAL-LEGACY-ALIAS-001`. `src/webdesk/specialists/catalog.py` maps `SHOPIFY` to `CAP-ECOMMERCE`.
- **Description:** CAP-ECOMMERCE is the Shopify capability, and its name says "ecommerce". The drafts give no canonical Shopify ID and no mapping. CAP-INTEGRATION-SOFTWARE is a compatibility route with no catalog entry.
- **Impact:** S1 (catalog mapping), S2 (Shopify investigation records).
- **Proposed owner:** WDS decision-maker (approves the alias mapping under D15).
- **Proposed resolution:** Keep both IDs. Record them as compatibility aliases in the alias map (CR-11). Do not rename.

### CR-11 — No canonical ID alias map exists
- **Type:** MISSING · **Status:** OPEN
- **Sources:** `DR` D-15 L21 ("alias mappings pending review"); `DR` L41 (item 7); `GOV` L285 (D-15 "add documented canonical alias mapping before deprecation"); `EP` L243 (`EVAL-LEGACY-ALIAS-001` requires a documented alias map). No alias-map file exists in the repository (searched all spec files).
- **Description:** Every legacy ID is preserved, but no document maps legacy IDs to canonical IDs or names. Any future rename would be silent.
- **Impact:** S1 and S2 (records and tests use the IDs), S6 (routing logs).
- **Proposed owner:** WDS decision-maker; spec reconciler drafts.
- **Proposed resolution:** Alias map with columns `legacy_id`, `kind`, `display_name`, `canonical_id` (blank until approved), `status`, `approval_ref` (blank). Draft layout is in `compatibility-and-migration.md`. No canonical ID is proposed.

### CR-12 — No explicit "no live model call until approved" gate; provider, model and budget open
- **Type:** CONFLICT (gap) · **Status:** OPEN
- **Sources:** Management D09. `DR` D-12 L18 (provider and model undecided; budget open); `GOV` L282 (draft D-12, "do not presume an initial vendor/model, budget, or production credentials"); `ARCH` L256 ("Model choice and cost limits require stakeholder configuration"); `ARCH` L328 (no implicit defaults for deployment); `AR` L722–L745 (`model_id: environment_configured`); `AR` L762–L766 (`D-12-initial-model` pending); `AR` L795 (`d12_llm_provider: configurable_initial_provider_tbd`).
- **Description:** The drafts keep the provider open, which matches D09, but they contain no gate that blocks live calls until the four items are approved. The registry does list D-12 among its "approved_decisions" (see CR-24).
- **Impact:** S2 (first LLM use), S3 to S7 (all LLM-dependent specialists).
- **Proposed owner:** WDS decision-maker (provider, exact model ID, credentials, budget).
- **Proposed resolution:** Add a configuration gate: live calls disabled unless an approved provider, model ID, credential reference and budget are all present in approved configuration. Mock and deterministic adapters only until then.

### CR-13 — Synthetic evaluation seed versus D11 "realistic sanitized WDS scenarios"
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** Management D11. `EP` L17 ("use synthetic data until authorized examples are approved"); `EP` L26 ("40–60 synthetic briefs"); `EP` L168 ("two synthetic projects"); `EP` L250 ("isolated synthetic projects, roles and sources"); `ARCH` L271 ("seed only synthetic fixtures"). `docs/governance/DECISION_RECORD_2026-10-22.md` D11 ("No specialist accepted on synthetic fixtures alone").
- **Description:** D11 requires realistic, sanitized WDS scenarios and forbids acceptance on synthetic fixtures alone. The drafts specify a synthetic seed and do not require sanitized WDS scenarios. Sanitized scenarios need their own approved source and sanitization process, which is not in the repository.
- **Impact:** S5 (acceptance), S9 (release validation).
- **Proposed owner:** WDS decision-maker (approves the source of sanitized scenarios); WDS QA owner.
- **Proposed resolution:** Keep synthetic cases as development and regression fixtures. Add a separate acceptance set of sanitized WDS scenarios, approved and versioned. Do not generate those scenarios from any historical client record without authorization (GOV §8 L127).

### CR-14 — No rule that synthetic or mock output must be labelled as such
- **Type:** GAP · **Status:** OPEN
- **Sources:** Management D09 ("Synthetic outputs must never be presented as verified investigations"). `GOV` §5.2 L73 (never imply browsing or testing occurred); `GOV` §6 L93 (confidence cannot substitute evidence). No labelling rule for synthetic or mock output in any draft. `src/webdesk/specialists/mock.py` default output is `status: incomplete` with unknowns, which is the honest default.
- **Description:** The rule is implied, not stated. The mock adapter already follows an honest default, but the spec does not require it.
- **Impact:** S1 (mock harness), S2 (evidence records), S5 (reports).
- **Proposed owner:** Spec reconciler; WDS decision-maker to approve.
- **Proposed resolution:** Add a provenance value (for example `origin: synthetic | mock | live_verified`) that is mandatory on every specialist output and claim, and a rule that synthetic output cannot carry `verified` status.

### CR-15 — Web-read tool and secondary-source preference go beyond D08
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** Management D08 ("no unrestricted browsing"). `GOV` §5.2 L71 (prefers, in order, official vendor documentation, official API references, changelogs, internal standards, "reliable secondary material; unverified notes"). `AR` L708–L713 `TOOL-APPROVED-WEB-READ`: "Retrieve public vendor documentation when deployed environment and policy permit"; permissions "Read-only allowlisted domains". `ARCH` L226 (examples of shopify.dev URLs; these are examples, not an allowlist).
- **Description:** D08 limits external evidence to approved official vendor documentation, with an explicit allowlist. GOV L71 lists secondary material and unverified notes as acceptable preference categories. The tool wording depends on deployment policy rather than on an approved list.
- **Impact:** S2.
- **Proposed owner:** WDS decision-maker.
- **Proposed resolution:** Limit the source preference list to approved internal categories and approved official vendor documentation. Secondary material and unverified notes are recorded as unverified and cannot support committed claims.

### CR-16 — Materiality and criticality trigger predicates are OPEN
- **Type:** GAP · **Status:** OPEN
- **Sources:** Management D08 and D-06 materiality (draft D-06 requires deterministic predicates). `DR` D-06 L12 ("Specific deterministic triggers ... to detail"); `RS` §9.1 (`CriticalityAssessment`: "Trigger predicates ... field-level conditions remain **OPEN**"); `RL` C-02 L8 (`enumerate executable rule predicates`); `RP` §12 Gate C (`Criticality is determined by deterministic criteria, with unknown treated as unsafe`) with no criteria listed.
- **Description:** The rule that unknown is material is stated. The predicates that decide materiality and criticality are not. Gate C therefore cannot be executed deterministically.
- **Impact:** S5, S7 and S9 (gates), S2 (claims).
- **Proposed owner:** WDS decision-maker and WDS Technical Lead.
- **Proposed resolution:** Specify a versioned predicate set for security, privacy, data integrity, payments, access control and fundamental feasibility, approved separately. Until approved, all claims in those categories are treated as material and blocking.

### CR-17 — No approver, owner or QA signatory is named in any source
- **Type:** MISSING · **Status:** OPEN
- **Sources:** `GOV` L6 `**Owner:** WebDesk stakeholder to be assigned`; `SC` L6 `owner: stakeholder_to_assign`; `RP` §9 L160–L162 (`Stakeholders must name the approver and risk owner roles before production`); `RS` `Approver` role, D-05; `DECISION_RECORD` §3 (approver for the reconciled package left blank); FINAL_GATE_REPORT §3 (sign-off fields blank).
- **Description:** Approval needs a named approver with a role. None exists in the sources. This package does not supply one.
- **Impact:** All approval and sign-off items (S1 to S9).
- **Proposed owner:** WDS decision-maker.
- **Proposed resolution:** Name the approver, role, and risk owner in the approval record (`approval-record-proposed.md`). Do not infer names.

### CR-18 — D05 (push and CI) conflicts with the deferred push in the Sprint 1 report
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** Management D05 ("Push the specialist feature branch to GitHub and run the full CI workflow"). `docs/M1_S1_FINAL_GATE_REPORT.md` §5 item 6 ("Push of the branch. Deferred by your decision"); §4 ("The workflow has not run on a GitHub runner"); §6 items 4–5. `ARCH` §14 L272 (CI content only).
- **Description:** The report records the push as deferred; D05 requires it. The CI run on GitHub has not happened. The workflow file was committed in `5122012`.
- **Impact:** S1 closure evidence.
- **Proposed owner:** WDS decision-maker; Sprint 1 owner.
- **Proposed resolution:** Push and run CI, then record the run identifier and head SHA in the sprint report. No merge into a protected branch (D05).

### CR-19 — No Sprint 1 human QA sign-off record
- **Type:** MISSING · **Status:** OPEN
- **Sources:** Management D04 (independent human QA owner signs the Sprint 1 acceptance record). `docs/M1_S1_FINAL_GATE_REPORT.md` §3 and §5 item 4 (the sign-off file `docs/M1_S1_HUMAN_QA_SIGNOFF.md` is not present); `docs/M1_S1_QA_CLOSURE_REPORT.md` §5 item 6; `docs/M1_S1_HUMAN_QA_CHECKLIST.md` (fields blank).
- **Description:** The checklist is prepared. No signatory, role, date or decision is recorded. D04 forbids fabricating one.
- **Impact:** S1 closure.
- **Proposed owner:** WDS QA owner (human).
- **Proposed resolution:** A human QA owner completes the checklist and signs a separate record. The reconciler and the AI agent must not fill it in.

### CR-20 — Declaration-only authority in Sprint 1 versus draft requirements for least privilege and runtime allowlists
- **Type:** CONFLICT · **Status:** OPEN
- **Sources:** `docs/M1_S1_QA_CLOSURE_REPORT.md` §2 QA-07 (authority is a self-declaration; run-time enforcement deferred to M3 S6 "by decision (user, Sprint 1)"); `src/webdesk/specialists/authority.py` L38 (same base allowlist for every category). Drafts: `GOV` §9 L137 (tool calls "MUST be selected by application-controlled routing and allowlists"); `GOV` §10 L145 (every tool declares permissions and audit); `GOV` §5.3 L80 (least privilege inherited); `AR` L14 (explicit allowlist per capability).
- **Description:** The drafts require least-privilege enforcement. Sprint 1 enforces a declaration check only, and the deferral is a user decision recorded in the QA report, not an amendment to the drafts. The residual risk (a provider can act outside its declaration until M3 S6) is outside any draft.
- **Impact:** S1, S6 (orchestrator), P7 and P8.
- **Proposed owner:** WDS decision-maker (accepts the interim risk in writing or requires earlier enforcement).
- **Proposed resolution:** Record the deferral as a documented, time-bound exception under GOV §16, approved by the policy owner. Note that no critical finding can be accepted as risk (D09), so this item must not be classed as critical.

### CR-21 — Referenced review findings and contradictions cannot be verified
- **Type:** UNRESOLVED · **Status:** OPEN
- **Sources:** `RL` L5–L34 (C-01 to C-08, H-01 to H-18, X-01 to X-15, M/L items; "See original independent review"); `RL` L38 (re-review request); `README.md` L28 (`original 29-page assessment`); `DR` D-01 L7 (`X-04`), D-05 L11 (`H-10`), D-06 L12 (`C-02`), D-08 L14 (`H-16`), D-09 L15 (`H-11`, `X-08`), D-10 L16 (`H-18`), D-11 L17 (`H-12`), D-12 L18 (`M-13`), D-13 L19 (`M-09`), D-14 L20 (`H-17`), D-15 L21 (`M-01`, `M-02`). `RL` N-18 and G-01 to G-16 are referenced in the logs.
- **Description:** The register of findings that the drafts say must be checked is not in the repository. Their closure status is therefore unverifiable. Several are marked OPEN (C-05, H-01, H-06 to H-09, H-14, H-15, X-01 to X-15).
- **Impact:** S1 to S9 (any item that cites them). Specifically C-05, H-14, H-15 gate routing and specialist output contracts (S6).
- **Proposed owner:** Independent reviewer (supplies the original review and rechecks each ID).
- **Proposed resolution:** Do not treat any cited finding as closed. Record each as RESOLVED, PARTIAL or OPEN only after it is read from the original document.

---

## Medium

### CR-22 — Sprint 1 final gate report commit status is stale
- **Type:** CONFLICT (report) · **Status:** OPEN
- **Sources:** `docs/M1_S1_FINAL_GATE_REPORT.md` header: `Last commit: 84bc7db`; `Uncommitted: .github/workflows/specialist-ci.yml, docs/M1_S1_FINAL_GATE_REPORT.md, docs/M1_S1_HUMAN_QA_CHECKLIST.md`. `docs/M1_S1_QA_CLOSURE_REPORT.md` §6 ("Fixes and regression tests: **uncommitted**"). Git history: `5122012` (add PostgreSQL CI job and final gate report) and `a9482d2` (fix independent QA findings and add closure report; includes `tests/unit/test_specialist_qa_regressions.py`).
- **Description:** Both reports describe work as uncommitted that is committed in the branch history.
- **Impact:** S1 evidence accuracy.
- **Proposed owner:** Sprint 1 owner.
- **Proposed resolution:** Correct both reports with commit SHAs; no change to the test results.

### CR-23 — Draft decision IDs D-01 to D-16 collide with management IDs D01 to D11
- **Type:** GAP (naming) · **Status:** OPEN
- **Sources:** Draft: `DR` D-01 to D-16. Management: `DECISION_RECORD` D01 to D11. Examples: draft D-07 (inferred-requirement acceptance; `GOV` L271) versus management D07 (operator confirmation); draft D-10 (SOW DOCX/PDF; `DR` L16) versus management D10 (isolated local environments); draft D-02 (evidence) versus management D02 (reconcile); draft D-06 (materiality) versus management D06 (name).
- **Description:** The same ID means different things in the two sets. Any citation of "D-07" or "D07" is ambiguous without a prefix.
- **Impact:** All items.
- **Proposed owner:** Spec reconciler.
- **Proposed resolution:** Always write `draft D-xx` or `D01`–`D11` in full (as this package does). Do not renumber either set.

### CR-24 — Registry lists draft decisions as "approved" while the register leaves them open
- **Type:** CONFLICT (internal) · **Status:** OPEN
- **Sources:** `AR` L746–L761 `approved_decisions:` lists D-01 to D-15 including D-12 and D-13; `AR` L762–L766 `pending_decisions:` lists `D-12-initial-model`, `D-16-hosting`, `D-02-domain-allowlist`, `D-01-canonical-alias`. `DR` D-12 L18 ("provider/model undecided"); `DR` D-13 L19 ("periods pending").
- **Description:** The registry marks D-12 and D-13 as approved and also lists parts of them as pending. The register states the detail is open.
- **Impact:** S2 and S6 (registry-driven behaviour).
- **Proposed owner:** Spec reconciler.
- **Proposed resolution:** Split "approved policy direction" from "approved detail" in the reconciled registry.

### CR-25 — Model configuration numbers have no recorded source
- **Type:** GAP · **Status:** OPEN
- **Sources:** `AR` L722–L745: `timeout_seconds: 60 / 90`, `max_attempts: 2`, `temperature: environment_configured`. `ARCH` §12 L248–L256 (retry and timeout are configured; no values given). `GOV` §14 L230–L232 (bounded retries).
- **Description:** The timeouts and attempt counts are specific values with no decision or evidence behind them. Under GOV L94 and ARCH L256 they must come from stakeholder configuration.
- **Impact:** S2 onward (LLM use). Also `EP` §4.9 reliability tests.
- **Proposed owner:** WDS Technical Lead.
- **Proposed resolution:** Mark the values as provisional in the reconciled version, or move them to configuration with no default. Do not treat them as approved.

### CR-26 — Estimation reference dataset absent
- **Type:** MISSING · **Status:** OPEN
- **Sources:** `SC` L938 `catalog_reference_ranges_populated: false`; `DR` D-04 L10 ("concrete reference dataset **not yet provided**"); `RS` §9.2 L405–L407 (no basis, no numeric estimate); `GOV` §12 L218–L220.
- **Description:** Estimates require approved historical data or reference ranges. None are in the repository, so any numeric estimate is `needs_inputs` by the drafts' own rule.
- **Impact:** S7.
- **Proposed owner:** WDS decision-maker (supplies authorized reference data).
- **Proposed resolution:** Keep estimates as `needs_inputs` until data is supplied and approved.

### CR-27 — Frozen plan document is not in the repository
- **Type:** UNRESOLVED · **Status:** OPEN
- **Sources:** `docs/governance/DECISION_RECORD_2026-10-22.md` §2 ("webdesk-specialist-delivery-baseline-v1.0.md"); `docs/M1_S1_FINAL_GATE_REPORT.md` §1 (`Downloads`, "Status: FROZEN FOR PLANNING"). Not found in the repository.
- **Description:** The sprint and milestone structure in the brief (4 milestones, 9 sprints) is not verifiable from a repository file. The brief is the only source used here.
- **Impact:** S1 to S9 and M1 to M4.
- **Proposed owner:** WDS decision-maker (supplies the frozen plan with its hash).
- **Proposed resolution:** Add the plan to the repository with its hash, or cite it by hash in the approval record.

### CR-28 — Sprint and milestone reporting not specified in the drafts
- **Type:** MISSING · **Status:** OPEN
- **Sources:** Management D11 (mandatory sprint and milestone reports; separate independent milestone sign-off) and D04. No draft mentions sprints, milestones or milestone reports. `DR` (decision record) §2 (Sprint status "Completed" only with QA sign-off).
- **Description:** The reporting requirement is management policy and is not in the drafts.
- **Impact:** S1 to S9, M1 to M4.
- **Proposed owner:** WDS decision-maker; spec reconciler adds a reporting section.
- **Proposed resolution:** Add a reporting section that references the required sections of each report and its sign-off record.

### CR-29 — catalog.py docstring states the Shift4Shop name is pending
- **Type:** CONFLICT (code) · **Status:** OPEN
- **Sources:** `src/webdesk/specialists/catalog.py` lines 1–7 ("D-01 and C-01 still leave its canonical display name and ID pending, so it is not a final name"). Management D06.
- **Description:** The code comment reflects the status before D06. The mapping in the same file is correct for the legacy ID.
- **Impact:** S1.
- **Proposed owner:** Sprint 1 owner.
- **Proposed resolution:** Update the docstring to cite D06 and the display name. Keep the ID mapping unchanged (see `compatibility-and-migration.md`).

### CR-30 — Later-phase role actions and bulk-acceptance predicates are OPEN
- **Type:** GAP · **Status:** OPEN
- **Sources:** `RS` §9.4 L417–L422 ("action-level role permissions and full status predicates remain **OPEN** (D-08)"); `DR` D-05 L11 and D-08 L14; `GOV` §11 L203 (`sow.approve` later phase); `GOV` §18 L272 (later-phase eligible statuses pending); `RL` H-10 and H-16.
- **Description:** Bulk acceptance and the later-phase permissions are not fully specified.
- **Impact:** S7 and S9.
- **Proposed owner:** WDS decision-maker; spec reconciler.
- **Proposed resolution:** Specify after CR-16 is closed; keep bulk acceptance disabled until then.

### CR-31 — No performance or resilience acceptance criteria
- **Type:** GAP · **Status:** OPEN
- **Sources:** `GOV` L94 and L220 (do not invent performance targets or numeric acceptance targets); `EP` §3 (quality metrics only; "initial proposed targets"); `EP` §4.9 L170–L171 (reliability scenarios without measures). No latency, throughput or availability target in any draft.
- **Description:** S8 names performance. No measurable criterion exists, and the drafts forbid inventing one.
- **Impact:** S8 and S9.
- **Proposed owner:** WDS Technical Lead (D14 owns thresholds); designated Approver signs off.
- **Proposed resolution:** Record performance as UNRESOLVED acceptance criteria until WDS supplies them.

### CR-32 — Retention periods and production prerequisites remain OPEN
- **Type:** UNRESOLVED · **Status:** OPEN
- **Sources:** Management D10. `DR` D-13 L19 (periods, legal holds and purge timelines OPEN); `GOV` §8 L115–L128; `RS` §3.1 (`retention_policy_version` nullable pending D-13); `DR` D-16 L22 (hosting deferred); `G1` section `## Production prerequisites still open`.
- **Description:** Production use needs these decisions. D10 keeps them out of scope.
- **Impact:** Any production use. Not on the Sprint 1 or Sprint 2 critical path.
- **Proposed owner:** WDS decision-maker.
- **Proposed resolution:** Track as production-blocking. Do not claim a retention policy is approved.

---

## Low

### CR-33 — Stale headers in DECISION_REGISTER.md and REMEDIATION_LOG.md
- **Type:** GAP (editorial) · **Status:** OPEN
- **Sources:** `DR` L1 `# WDS Decision Register — v0.3.7 Foundation Review Candidate`; `RL` L1 `# Independent Review Remediation Log — v0.3.7 Foundation Review Candidate`. Content runs to v0.3.10 and to 2026-10-20 amendments.
- **Impact:** None on specialist scope; affects audit readability.
- **Proposed owner:** Spec reconciler.
- **Proposed resolution:** Correct the titles in the reconciled version only.

### CR-34 — Terminology collisions across tracks
- **Type:** GAP (naming) · **Status:** OPEN
- **Sources:** "Gate 1" (`G1`), "Phase 1" and "Increment 3" (`INCREMENT_3_PHASE1_WDS_DECISIONS_2026-10-20.md`), "Foundation F-1 to F-10" (`GOV` §8, §11), "Sprint 1 / M1 S1" (`docs/M1_S1_*`), and "Amendment A1 / A2". The drafts do not map the Gate 1 Foundation track to the specialist sprint track.
- **Impact:** Readability; could cause a Phase 1 control to be read as covering specialists or the reverse.
- **Proposed owner:** Spec reconciler.
- **Proposed resolution:** Add a short track map to the reconciled version: Phase 1 security track (Gate 1, A1, A2) and specialist track (M1–M4, S1–S9) are separate, with cross-references.

### CR-35 — Sprint 2 working tree has untracked evidence and platform files with no reconciled reference
- **Type:** GAP (status) · **Status:** OPEN
- **Sources:** Git status in the worktree shows untracked `src/webdesk/evidence/`, `src/webdesk/specialists/platforms/`, `tests/unit/test_evidence_services.py`, `tests/unit/test_shopify_specialist.py`. The amendment §4 says Sprint 2 is "in progress".
- **Description:** Sprint 2 work is in progress before the evidence allowlist (CR-03) and the LLM gate (CR-12) are approved. None of the files is covered by a sprint report.
- **Impact:** S2.
- **Proposed owner:** Sprint 2 owner; WDS decision-maker.
- **Proposed resolution:** No commit or push of Sprint 2 files until the blocking items are closed or the scope is explicitly confined to tests with no live retrieval.

---

## Summary by severity

| Severity | Count | Items |
|---|---|---|
| Critical | 3 | CR-01, CR-02, CR-03 |
| High | 18 | CR-04 to CR-21 |
| Medium | 11 | CR-22 to CR-32 |
| Low | 3 | CR-33 to CR-35 |
| **Total** | **35** | |

## Items the brief asked to see explicitly

| Brief item | Register entry |
|---|---|
| Gate 1 "implementation-ready" versus "NOT implementation-approved" | CR-01 (and CR-02 for specialist scope) |
| ROUTE-3D-CART-SHIFT-001 not executable | CR-07 |
| CAP-3D-CART-SHIFT-SHOPIFY naming | CR-06, CR-11, CR-29 |
| `pending_controlled_vocab_and_predicates_C05` and `machine_routing_enabled: false` | CR-07 |
| LLM model and provider open items | CR-12, CR-25, CR-24 |
| Evidence allowlist and absence of a vendor list | CR-03, CR-15 |
| Others found | CR-04, CR-05, CR-08 to CR-10, CR-13, CR-14, CR-16 to CR-23, CR-26 to CR-35 |
