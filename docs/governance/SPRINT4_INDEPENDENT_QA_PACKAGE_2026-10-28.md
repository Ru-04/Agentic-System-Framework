# M2 Sprint 4 independent QA package (28 October 2026)

Prepared by engineering for the reviewer named by the WDS Authorized Approver. Engineering does not perform, sign or attest the review.

## 1. Baseline under review

| Item | Value |
|---|---|
| Branch | `claude/sprint4-full-validation` (authorized validation branch) |
| Engineering commit under review | `58d1a39c0e85aedaf95d91d13c2211095859485d` |
| CI for that exact commit | `specialist-ci` run #36, [40669580089](https://github.com/Ru-04/Agentic-System-Framework/actions/runs/40669580089): **success**. 25 steps succeeded, 0 failed, across `lint-type-unit` and `postgres-tests` |
| Local evidence (not a substitute for CI) | 758 unit tests passed; `ruff` format and lint clean; `mypy --strict src/webdesk` clean. Integration, committed, hardening and database tests were not run locally |
| Sprint 4 commits since Sprint 3 acceptance (`3969a8f`, `5105628`) | `d914f38`, `e36d0fb`, `0a18557`, `a86da16`, `acfae72`, `e0a4394`, `9f2325a`, `58d1a39` |

## 2. Reviewer and independence

- Reviewer named by WDS: **PG**, named by the WDS Authorized Approver on 28 October 2026.
- Engineering has not verified PG's independence for Sprint 4. The independence declaration template (`docs/governance/PG_INDEPENDENCE_DECLARATION_TEMPLATE_2026-10-26.md`) is blank.
- **PG independence declaration: PENDING. PG completes it personally, naming the commits reviewed.** Engineering does not fill it in.

## 3. Scope to review

Source:
- `src/webdesk/investigation/engine.py`: boundary checks, authorization-first precedence, four availability outcomes, `REFUSED`.
- `src/webdesk/investigation/specialists.py`: seven-specialist catalog, requirement decision (`INVESTIGATE`, `INVESTIGATE_WITH_UNKNOWNS`, `CLARIFY`, `REFUSE`), word-form matching, provider output mapping.
- `src/webdesk/investigation/approved_boundaries.py` and `src/webdesk/evidence/approved_boundaries.py`: approved-but-inactive boundaries.
- `src/webdesk/specialists/adapter_v02.py`: adapter, error mapping (`authorization_refused`), audit record.

Tests:
- `tests/unit/test_investigation_sprint4.py`, `test_sprint4_exact_pages.py`, `test_investigation_adapter.py`, `test_investigation_security_adapter.py`, `test_source_refusal_precedence.py`, `test_clarification_outcomes.py`, `test_seven_specialist_conformance.py`.

## 4. Source-refusal classification (SOURCE-REFUSAL-01, approved by WDS)

| Outcome | Used for | Response mapping |
|---|---|---|
| REFUSE (`REFUSED` in the engine) | Missing operator authorization; access to an unapproved domain or URL path; redirect to an unauthorized destination; workspace or tenant violation | Capability returns no finding or citation. All refused: status `failed`, error code `authorization_refused`. Otherwise `incomplete` with a `[REFUSE]` unknown |
| UNSUPPORTED_SOURCE | No approved evidence source; approved source inactive; technology-specific source not selected; required document not establishable within approved boundaries | `incomplete` with an `unsupported_source` unknown. Not an authorization violation, and not a finding that the platform lacks the capability |
| CLARIFY | Objective not recognisable from the requirement | `incomplete` with a `[CLARIFY]` unknown; no finding |
| INVESTIGATE_WITH_UNKNOWNS | Objective recognisable; version not stated | `incomplete` with a `[INVESTIGATE_WITH_UNKNOWNS]` unknown |
| INVESTIGATE | Objective and version present | `incomplete` (feasibility is never determined by these paths) |

Precedence rule to review: authorization is checked before every availability result. A capability whose access is refused is never reported as unsupported.

## 5. Seven-specialist status

Status key: **Verified** = covered by unit tests passing in CI #36 (synthetic fixtures). **Blocked** = requires an activated, approved source or a WDS decision. No real platform investigation has run for any specialist.

| Specialist | Canonical capability | Adapter path | Evidence boundary | Synthetic | Real investigation |
|---|---|---|---|---|---|
| Shopify | Resolved (plan feature availability) | Verified | Approved boundary, inactive | Verified. Existing Shopify evidence processing unchanged since `3969a8f` | Blocked: source not active; 0 of 55 human labels |
| Shift4Shop | Resolved; legacy identifier `CAP-3D-CART-SHIFT-SHOPIFY` kept | Verified | No approved source | UNSUPPORTED_SOURCE verified. No claim made | Blocked: no approved source |
| WordPress & WooCommerce | Resolved (three capabilities) | Verified | Approved boundary, inactive | Verified (variation pricing with stem matching) | Blocked: activation approval required |
| BigCommerce | Resolved | Verified | Approved exact product page, inactive | Verified (exact page, siblings and old host refused) | Blocked: activation approval required |
| Magento / Adobe Commerce | Resolved (REST, GraphQL, release history, catalog import) | Verified | Adobe exact pages and shared page; Magento release notes only | Verified: feature claims from release notes refused; edition separation tested | Blocked: activation approval required |
| Standalone Applications | Resolved (architecture selection) | Verified | No technology selected | UNSUPPORTED_SOURCE verified | Blocked: WDS must select a technology and approve its source |
| Middleware Applications | Resolved (webhook delivery retry) | Verified | No product selected | UNSUPPORTED_SOURCE verified | Blocked: WDS must select a product and approve its source |

## 6. Security and regression checks in CI #36

- Source boundary: exact pages, siblings, parents, query strings, encoding and dot segments refused.
- Redirects: a redirect leaving the approved boundary is refused, with no citation.
- Edition separation: Adobe-only pages are not applied to Magento Open Source; release notes do not support feature claims.
- Workspace isolation: foreign-workspace pages are refused and never cited.
- Audit: records hold identifiers and hashes only, with no task or page text.
- Error handling: unconfirmed requests are refused before any run.
- Stem matching: `pric` was replaced by explicit inflections. "prickly" does not match a price capability.

## 7. Limitations the reviewer should weigh

1. No real investigation has run. All findings are `[SYNTHETIC]` and are not verified platform evidence.
2. No documentation source is active. Activation needs a separate approval.
3. Shopify's 55 human relevance labels: 0 of 55. They require a qualified reviewer.
4. Shift4Shop, Standalone and Middleware have no approved source. Their results are unsupported-source outcomes, not capability findings.
5. Integration, committed and hardening tests ran only in CI, not locally.
6. Source-access refusal is exercised only through boundary and workspace checks. No live retrieval exists to test.

## 8. Questions for the reviewer

1. Does each specialist's canonical capability and adapter path match the frozen contract?
2. Is every REFUSE outcome an authorization or security violation, and every UNSUPPORTED_SOURCE an evidence-availability result?
3. Can any refused access still surface content, a citation or a finding?
4. Are refusal and unsupported-source outputs sanitized (no URL, page text or source detail)?
5. Are synthetic results ever presentable as verified evidence?
6. Are the seven specialist statuses in section 5 accurate?
7. Is the CI evidence in section 1 adequate for the stated scope?

## 9. Reviewer record (to be completed by PG personally)

- PG independence declaration: **[PENDING: PG to complete]**
- Commits reviewed: **[PENDING: PG to state]**
- Findings, with severity: **[PENDING: PG to record]**
- Review decision (PASS / PASS WITH CONDITIONS / FAIL): **[PENDING: PG to decide]**
- Signature or personal attestation: **[PENDING: PG only]**

Engineering has not completed, signed or inferred any part of section 9.
