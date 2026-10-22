# Decision Record — D01 to D11 (effective 22 October 2026)

- **Status:** Recorded from a written management authorization. The decision-maker's name, signature and approval reference were **not** provided and are left blank. See section 3.
- **Effective date:** 22 October 2026. These are new decisions. They are **not retroactive** and must not be presented as historical approvals.
- **Authorizing role:** WDS project decision-maker, as stated in the authorization request dated 22 October 2026.
- **Original Gate 1 authorization:** `WebDesk_Agentic_Requirement_Platform_Specs/GATE1_IMPLEMENTATION_AUTHORIZATION.md`. Preserved unchanged. It does not authorize specialist implementation (its "Excluded from Gate 1" section lists specialist routing, model calls, RAG, and estimation).
- **Companion record:** `docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md` (D03).

## 1. Decisions

| ID | Decision | Effect on development | Not authorized by this record |
|---|---|---|---|
| D01 | Isolated, non-production development of all seven specialists authorized | Development in worktrees and local test PostgreSQL only | Production activation, protected integrations, deployment |
| D02 | Reconcile the seven v0.3.10 drafts against the 16 Oct 2026 decisions and later approved amendments; prepare a **new reconciled version for review** | Reconciliation package in `docs/spec-reconciliation/` (proposed) | Any claim that a historical v2.0 implementation-approved package exists |
| D03 | Gate 1 authorization preserved; separate dated limited amendment for specialist development | See amendment document | Reading Gate 1 as permission for specialist implementation |
| D04 | Independent human QA owner reviews Sprint 1 evidence and signs the acceptance record | Evidence and checklist prepared | Fabricated signatory, signature or approval |
| D05 | Push the specialist feature branch to GitHub and run the full CI workflow | Branch pushed; CI executed | Automatic merge, protected-branch change, production deployment |
| D06 | Canonical name **Shift4Shop (formerly 3dcart)**. Legacy `CAP-3D-CART-SHIFT-SHOPIFY` kept as an internal compatibility alias until a separately approved migration. Distinct eCommerce platform, not a Shopify 3D configurator | Catalog keeps `SHIFT4SHOP` separate from `SHOPIFY` | Removing or renaming the legacy identifier |
| D07 | AI may recommend specialists; an authorized WDS operator must confirm before execution | Routing contracts require operator confirmation (routing itself is Sprint 6) | Automatic specialist execution |
| D08 | Evidence only from approved internal RAG categories and approved official vendor documentation; explicit allowlists and provenance; no unrestricted browsing | Sprint 2 evidence services are allowlist-only | Arbitrary external retrieval; unrestricted agent browsing |
| D09 | Provider-independent model adapter. No live model calls until provider, exact model ID, credentials and usage budget are approved. Synthetic outputs must never be presented as verified investigations | Deterministic and mock adapters for tests only | Live model calls; presenting synthetic output as verified |
| D10 | Isolated local environments and test PostgreSQL initially | Local Docker PostgreSQL for tests | Production hosting, retention policy, production credentials (each needs a separate decision) |
| D11 | Realistic, sanitized WDS scenarios; independent QA; mandatory sprint and milestone reports | Test cases built from sanitized scenarios where available | Acceptance of any specialist on synthetic fixtures alone |

## 2. Conditions and restrictions

- The frozen plan is unchanged: 4 milestones, 9 sprints, scope and order as in `webdesk-specialist-delivery-baseline-v1.0.md`.
- Sprint status may be "Completed" only with QA sign-off. Milestone status may be "Completed" only with separate independent milestone sign-off.
- Security-critical controls from Phase 1 remain in force. No privileged database action is performed without the approved authorization controls.
- Specialists must not execute before operator confirmation (D07).
- No citation or evidence may be manufactured. Unverifiable sources are recorded as unknown.
- Failed tests and critical findings must not be downgraded.

## 3. Items not provided (left blank, not inferred)

- Decision-maker name, signature, and approval reference.
- Approver identity for the reconciled specification package (`docs/spec-reconciliation/approval-record-proposed.md`).
- Human QA signatory for Sprint 1 (D04).
- Approved provider, exact model ID, credentials and budget (D09).
- Approved list of official vendor documentation domains for D08. The Sprint 2 allowlist is therefore a **proposed** configuration until approved.
- Production hosting, retention and production credentials (D10).

## 4. Evidence retention

- This record and the amendment are committed to the feature branch, which is the source of truth for the decision text.
- Approval evidence (signatures, sign-off forms) is stored as a separate file per approval under `docs/governance/approvals/`, referenced here by file name and commit SHA. No approval file has been created by this record.
- Sprint-level evidence lives in `docs/M1_S1_*` and `docs/M1_S2_*` reports, with CI run identifiers recorded from the GitHub Actions API.

## 5. Management answers to open items (22 October 2026)

Recorded from the decision-maker's written answers. These are decisions made by the authorized WDS decision-maker, effective 22 October 2026, not historical approvals.

| # | Item | Answer | Recorded effect |
|---|---|---|---|
| 1 | Shopify vendor allowlist | Lead architect to suggest one | Working allowlist set to `shopify.dev` and `help.shopify.com`, exact hosts, HTTPS, default port. Recorded as a working selection. Not a formal approval of official-domain status under D08 until the decision-maker confirms it. |
| 2 | Where origin is enforced for evidence sources (QA2-07) | Suggest, then get approval before implementing | Proposal written: `docs/governance/PROPOSALS_PENDING_APPROVAL_QA2.md`. No code change until approved. |
| 3 | Proxy policy for vendor fetches (QA2-13) | Suggest, then get approval before implementing | Same proposal file. No code change until approved. |
| 4 | Live retrieval window and real Shopify acceptance | Approved (live retrieval window) | One bounded live fetch of an allowlisted Shopify page was made on 22 Oct 2026. Metadata only is recorded in `docs/evidence/SHOPIFY_LIVE_RETRIEVAL_2026-10-22.md`. Acceptance is NOT granted by this approval. |
| 5 | Shopify real cases | Find them from WDS case studies and portfolio | Four sanitized briefs in `docs/evaluation/SHOPIFY_CASE_BRIEFS_SANITIZED.md`. Client-approval for use of the scenarios is not yet recorded. |
| 6 | Human QA signatory for Sprint 2 | "AS" | Designated signatory: **AS**. No sign-off has been recorded or simulated. The signature and approval reference are to be supplied by AS. |

## 6. Approval of P1, P2 and the specification package (22 October 2026)

- P1 (source origin enforcement) and P2 (vendor proxy policy) are formally approved by the decision-maker, with their implementation, regression tests and commit `2b0cef2`.
- The specification reconciliation package is approved for committing and maintaining in the repository for formal review. This is **not** final approval of any proposed specification.
- Authority: the decision-maker's written authorization of 22 October 2026 under the non-production development authorization (`docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md`).
- Approver identity, role and signature: **not provided in the record**. Left blank, not inferred.
