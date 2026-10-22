# Document Status — Seven Draft Specifications and Related Status Records

- **Status:** PROPOSED - NOT APPROVED
- **Method:** Header lines quoted verbatim from the files as read on 2026-10-22. SHA-256 computed over each file as read. Searches covered the repository only.

## 1. Authority finding

**None of the seven documents is authoritative.** No approval record was found that names any of them. The search covered the repository working tree, the documents' own headers and change logs, and the recent commit history (`git log`, 43 commits across all refs). It did not cover the zip packages or the Downloads folder named in the Sprint 1 reports. The Sprint 1 final gate report reports the same absence of approval (`docs/M1_S1_FINAL_GATE_REPORT.md` §1 and §2). The only dated approval-type record for the v0.3.10 package is `GATE1_IMPLEMENTATION_AUTHORIZATION.md`. It is scoped to Foundation implementation, excludes specialist work, and conflicts with the drafts' own headers (see CR-01 and CR-02).

## 2. The seven drafts

All seven are at version `0.3.10-foundation-gate1-review`, location `WebDesk_Agentic_Requirement_Platform_Specs/`.

| # | File | Version (as written) | Header status (verbatim) | Authoritative? | Covers | SHA-256 (as read) |
|---|---|---|---|---|---|---|
| 1 | `GOVERNANCE.md` | `- **Version:** 0.3.10-foundation-gate1-review` (L4) | `- **Status:** Working draft for independent re-review; NOT implementation-approved` (L3) | No | Top-level policy (§1–§19): precedence, terminology, traceability, evidence, specialist-layer rules (§5.3), uncertainty, data isolation (§8), prompt injection (§9), tools (§10), human review and permissions matrix (§11), estimation (§12), audit (§13), failure handling (§14), blockers (§15), D-01–D-16 decision controls (§18–§19), Gate 1 contact/bootstrap/recovery policies, Amendment A1 and A2 | 7398e8006f2b4b888eef7b2f5ae5a2a525dd1e2ed758334bf6657334de2b8f21 |
| 2 | `ARCHITECTURE.md` | `- **Version:** 0.3.10-foundation-gate1-review` (L4) | `- **Status:** Working draft for independent re-review; NOT implementation-approved` (L3) | No | Goals and non-goals, stack, logical components, routing diagram (§4), workflow and state contract (§5–§7), deterministic versus LLM work (§8), data model (§9), evidence ingestion (§10), API boundaries (§11), model provider adapter (§12), upload and security contract (§13), local deployment (§14), specialist registry contract (§17), open decisions (§18), D-decision constraints (§19–§20), Amendment A2 boundary | 562cdee7702c7ff11ad7214571cd41498a9046a5c5cd751f2518c57052a1a074 |
| 3 | `SERVICE_CATALOG.yaml` | `  version: 0.3.10-foundation-gate1-review` (L3) | `  status: working_draft_unapproved` (L4) | No | Catalog schema and enums (L8–L64); 14 service patterns including the 3dcart/Shift4Shop pattern `SVC-3D-CART-SHIFT-SHOPIFY-001` (L66), Shopify patterns (L407, L457), platform migration `SVC-PLATFORM-MIGRATION-001` (L860), knowledge categories (L914), estimation policy (L920) | b52b8ee887ac9630e6286e4c52d2c350d6be1792457714a7cd11958cdd6b74bb |
| 4 | `AGENT_REGISTRY.yaml` | `  version: 0.3.10-foundation-gate1-review` (L3) | `  status: working_draft_unapproved` (L4) | No | Routing policy and rules (L8–L104), agents (L107–L210), seven capability entries (L211–L534), evidence service (L568), scope and governance agents (L600–L678), tools (L679–L721), model configuration (L722–L745), approved and pending decisions (L746–L766), access and governance policy (L767–L801) | d294f5d98520ba5275cbe6f9aa8e6eef85af3699f47f331680ec660209db8eb4 |
| 5 | `REQUIREMENT_SCHEMA.md` | `- **Version:** 0.3.10-foundation-gate1-review` (L4) | `- **Status:** Working draft for independent re-review; NOT implementation-approved` (L3) | No | Canonical enums (§2), identifiers (§3), Foundation contracts including permissions, data classes, ceremonies, tokens, outbox, sessions, jobs (§3.1), entities (§4), routing metadata (§4.3.1), lifecycle (§5), validation (§6), examples (§7), later-phase contracts D-02–D-09 (§9), Amendment A1 and A2 | 3e549f1fc57fa8b08ed3db4f0454e9e157b4cde462daa27ba0583f85a3a0c0ee |
| 6 | `REVIEW_POLICY.md` | `- **Version:** 0.3.10-foundation-gate1-review` (L4) | `- **Status:** Working draft for independent re-review; NOT implementation-approved` (L3) | No | Reviewer independence (§1), review stages (§2), severities (§3), required checks including routing (§4), deterministic versus LLM checks (§5), finding lifecycle (§6), release gates A–F (§7), review result contract (§8), approval and accepted risk (§9), audit (§10), block conditions (§11), D-05–D-09 enforcement (§12), D-09/D-14 policy (§13) | f12757eb2f8325f9eb15952eab3d7fff376ef578722ff6521e7ecd3f4a558659 |
| 7 | `EVALUATION_PLAN.md` | `- **Version:** 0.3.10-foundation-gate1-review` (L4) | `- **Status:** Proposed; no benchmark results have been measured` (L3) | No | Principles (§1), synthetic benchmark seed (§2), proposed thresholds (§3), suites including the required routing matrix (§4.4.1), security and isolation (§4.7–§4.8), reliability (§4.9), baselines (§5), human evaluation (§6), release-blocking criteria (§7), regression procedure (§8), threshold ownership (§9), D-decision test obligations (§10–§11), Gate 1 Foundation suite (L248–L312) | ba28d621e067f9ca7c735a48cb7f8319cea7c6482aebd93ab1cc31255e1e7282 |

Note on EP: its header status is not the "NOT implementation-approved" wording used by the other Markdown drafts. Its own text says "Proposed; no benchmark results have been measured". Both forms are quoted here as found.

Note on the YAML files: each has `status: working_draft_unapproved` in its top-level block (the catalog block for SC, the registry block for AR), not a Markdown header.

## 3. Related status records (quoted where they bear on status)

| File | Quoted status language | Bearing on reconciliation |
|---|---|---|
| `WebDesk_Agentic_Requirement_Platform_Specs/README.md` L1 | `# WebDesk Agentic Requirement Analysis Platform — v0.3.10 APPROVED LIMITED FOUNDATION BASELINE` | Conflicts with the draft headers (CR-01) |
| same, L4 | `**Status:** READY FOR LIMITED FOUNDATION IMPLEMENTATION per independent Gate 1 review dated 2026-10-16.` | Conflicts with the draft headers (CR-01) |
| same, L35 | `This version is still **NOT READY FOR IMPLEMENTATION** and is intended only for independent review.` | Contradicts README L4 within the same file (CR-01) |
| `GATE1_IMPLEMENTATION_AUTHORIZATION.md` L4, L6 | `**Verdict:** READY FOR LIMITED FOUNDATION IMPLEMENTATION` ; `**Status:** Foundation implementation-ready; ... A separate user request is needed to start coding.` | Foundation scope only; excludes specialist routing, LLM calls, RAG, estimation, SOW outputs (section `## Excluded from Gate 1`). Preserved unchanged under D03. (CR-01, CR-02) |
| `DECISION_REGISTER.md` L1 | `# WDS Decision Register — v0.3.7 Foundation Review Candidate` | Stale title; content runs to v0.3.10 and 2026-10-20 (CR-33) |
| same, L3 | `The stakeholder choices are NOT equivalent to implementation readiness. This is a decision record, NOT development authorization.` | Written 2026-10-16 (CR-01) |
| same, L84 | `**Gate 1 status:** SPECIFICATION REVIEW CANDIDATE; implementation authorization remains blocked pending independent reviewer verdict AND explicit WDS approval ...` | Historical v0.3.6 entry; conflicts with G1 verdict (CR-01) |
| `REMEDIATION_LOG.md` L1 | `# Independent Review Remediation Log — v0.3.7 Foundation Review Candidate` | Stale title (CR-33) |
| same, L50 | `This package is **review-only**, not code-ready.` | Same date as G1 (CR-01) |
| `CHANGELOG_v0.3.10_FINAL_REVIEW.md` L8 | `**Status:** final *independent review candidate*, not a reviewer verdict and not implementation authorization. No application code.` | Conflicts with G1 (CR-01) |
| `VALIDATION_REPORT_v0.3.10_FINAL_REVIEW.md` | `Independent review is required before coding authorization.` | Conflicts with G1 (CR-01) |
| `CHANGELOG_PHASE1_AMENDMENT_A1.md` (2026-10-20, most recent by date) | `Recorded two WDS-confirmed decisions ... No application or test code changed.` | Post-baseline amendment; no status change to the drafts |
| `PHASE1_R4_OPTION_A_IMPLEMENTATION_CONTRACT.md` | `**Status:** NORMATIVE governance contract, NOT an implementation-complete claim.` | Phase 1 track, separate from specialists |
| `INCREMENT_3_PHASE1_WDS_DECISIONS_2026-10-20.md` | `These decisions are authoritative **post-baseline amendment A1** ... not a blanket authorization to modify the older frozen baseline in place.` | Phase 1 track |
| `docs/governance/DECISION_RECORD_2026-10-22.md` | `**Status:** Recorded from a written management authorization. The decision-maker's name, signature and approval reference were **not** provided and are left blank.` | Source of D01–D11; not a specification approval |
| `docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md` | `Amends: nothing. This is a separate, dated, limited authorization.` ; section 4: `Specification approval: not approved. Reconciled package proposed.` | Development authorization only (CR-02) |
| `docs/M1_S1_QA_CLOSURE_REPORT.md` §7 | `**BLOCKED.**` | Sprint 1 status; blocker based on a v2.0 package that does not exist (CR-04) |
| `docs/M1_S1_FINAL_GATE_REPORT.md` header and §1 | `Sprint 1 status: BLOCKED. Sprint 2 not started.` ; `Specification reconciliation result: BLOCKED.` | Same as above (CR-04) |

## 4. Verification notes

- Each draft's version field is the same string. No draft carries version 2.0.
- The seven drafts' own status lines are consistent with one another. They conflict with G1, README L4 and CHANGELOG_v0.3.10_FINAL_REVIEW L8.
- The Sprint 1 reports quote a README `FOR INDEPENDENT RE-REVIEW ONLY — NOT APPROVED FOR IMPLEMENTATION` from a zip file that is not in the repository (`docs/M1_S1_QA_CLOSURE_REPORT.md` §1). The repository README header differs (CR-05).
