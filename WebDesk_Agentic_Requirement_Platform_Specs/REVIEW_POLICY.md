# Independent Review and Release Policy

- **Status:** Working draft for independent re-review; NOT implementation-approved
- **Version:** 0.3.10-foundation-gate1-review
- **Last updated:** 2026-10-16
- **Authority:** Review execution, severity, findings, remediation and release gates

## 1. Purpose and independence

The reviewer determines whether the proposed scope is traceable, adequately evidenced, technically plausible within the stated context, bounded, and suitable for human decision. It must be able to reject the scope.

The reviewer MUST receive access to:
- Original source materials and locators (subject to authorization).
- Canonical requirements and revision history.
- Evidence records and source versions.
- Candidate solutions, dependencies, assumptions, estimates and exclusions.
- Draft SOW and traceability mapping.
- Prior review findings and changes.

The reviewer MUST NOT rely exclusively on the first agent's summary. A separate model may help, but model diversity is not proof of independence or correctness. Deterministic checks and human review remain required.

## 2. Review stages

1. **Input integrity:** project boundary, source versions, parse errors, authorization, provenance.
2. **Requirement completeness:** atomicity, source attribution, original wording preservation, classifications, ambiguity, omissions, duplicates and contradictions.
3. **Technical investigation:** platform-specific capability, relevant API version, authentication/scopes, prerequisites, third-party dependency, feasibility status and evidence quality.
4. **Architecture/integration:** data flows, source of truth, mapping, idempotency, retries, rate limiting, reconciliation, observability and failure handling where applicable.
5. **Security/privacy/operations:** least privilege, data exposure, retention, secrets, auditability, availability, monitoring, rollback and operational ownership as relevant.
6. **Scope integrity:** every scope item maps to requirements; deliverables, boundaries, assumptions, exclusions, dependencies and acceptance criteria are present.
7. **Estimation:** units, basis, assumptions, uncertainty, dependencies, exclusions and no false precision.
8. **SOW consistency:** no unsupported promise, contradiction, unapproved commitment, or unresolved blocker hidden in polished prose.
9. **Release gate:** deterministic validators pass, no blocking finding remains, and authorized human decision is recorded.

## 3. Severity definitions

- **critical:** material security/privacy/authorization issue; cross-project exposure; fabricated critical capability; missing/contradictory requirement that makes scope unsafe or fundamentally invalid; bypassed approval gate. Blocks release.
- **major:** material requirement omission, unsupported feasibility, unbounded integration risk, missing dependency/acceptance criterion, invalid estimate basis, or material scope contradiction. Blocks approval until resolved or handled by an explicitly permitted, authorized decision.
- **minor:** localized quality issue that does not materially alter feasibility, security, scope, cost, or acceptance. May be resolved or documented before finalization according to stakeholder policy.
- **informational:** improvement suggestion or non-blocking note.

Findings must be evidence-backed. The severity is based on impact, not how confident or forceful the reviewer sounds.

## 4. Required checks

### 4.1 Source and requirement checks
- Every client-derived requirement has a source reference and original wording.
- Source locators resolve to the correct source version where technically possible.
- Inferences and recommendations are not represented as explicit client requests.
- Requirement coverage includes an explicit disposition for every captured requirement.
- Ambiguities, conflicts and missing details have questions or an authorized documented disposition.
- No requirement was silently dropped, merged, or changed during synthesis.

### 4.2 Evidence and feasibility checks
- Material technical claims have adequate evidence or remain visibly unverified.
- Evidence is applicable to the platform/version/context and sufficiently current.
- Official vendor evidence is preferred for vendor capabilities and constraints.
- Conflicting evidence is preserved and blocks affected commitments.
- A proposed approach distinguishes native capability, extension, third-party product, integration, custom service and AI/automation.
- Unsupported assumptions about pricing, quotas, access, subscription, permissions, credentials or vendor behavior are flagged.

### 4.3 Integration and data-flow checks
When relevant, verify system ownership, direction of data flow, field mapping, identity matching, authentication/scopes, triggers, retries, idempotency, error queues/manual recovery, reconciliation, rate limits, observability and data protection. Missing details become questions or assumptions, not invented design facts.

### 4.4 Scope and estimate checks
- Every committed scope item maps to requirements.
- Acceptance criteria are observable and testable or marked as needing agreement.
- Assumptions, dependencies, exclusions, risks and client responsibilities are explicit.
- Estimates have a unit and rationale and are not represented as guaranteed.
- Out-of-scope items are stated where needed to avoid implied commitment.
- No optional recommendation is silently converted into a committed deliverable.


### 4.5 Specialist routing and cross-platform checks
- The selected specialist categories match the original requirements, platform/application context, dependencies, and service catalog; routing rationale is recorded.
- Detect missed relevant specialists and unnecessary specialist invocations. Do not require every specialist to run for every project.
- WordPress and WooCommerce must route to one combined specialist category, not two agents.
- 3dcart / Shift4Shop remains distinct from the general Shopify Specialist; product identity and actual capabilities are verified or explicitly marked unverified.
- Standalone applications can proceed without an eCommerce specialist when none is relevant.
- Cross-platform requirements may be assigned to multiple specialists; overlapping and conflicting findings are reconciled rather than silently merged.
- Middleware specialist analysis is technology-neutral; Node.js must not be treated as the only permitted backend. Review technology selection against requirements, existing systems, constraints, and evidence.
- Unknown/ambiguous platforms must lead to clarification or an explicitly unsupported outcome, not a guessed route.
- Specialist outputs pass schema and reference validation before they can influence scope. Timeout/unavailable/invalid specialist output must remain visible as incomplete; no silent skip.
- Independent review compares specialist findings to original requirements and source/evidence records; it must not merely accept the specialists' conclusions.

## 5. Deterministic checks versus LLM judgment

**Deterministic checks:** schema validation; foreign keys; project boundary; valid lifecycle transitions; required source mappings; scope-to-requirement mapping; enum validity; estimate arithmetic; required evidence status; required review fields; open blocker count; actor permissions; artifact version/hash; approval/audit record.

**LLM-assisted checks:** semantic omissions, ambiguity, contradiction candidates, plausibility, unclear acceptance criteria, scope overreach, technical reasoning quality and readability. LLM findings must include affected record IDs and evidence references when possible.

Human reviewers decide disputed interpretation, business trade-offs, exception approval, estimates, and final approval.

## 6. Finding lifecycle and remediation

A finding contains: `finding_id`, `severity`, `status`, `category`, description, affected requirement/scope IDs, evidence refs, required action, owner if assigned, creation time, and resolution note/time.

- `open -> in_progress -> resolved`
- `open | in_progress -> accepted_risk` is permitted ONLY for non-critical findings with an authorized decision. `critical` findings cannot transition to `accepted_risk`; a Technical Reviewer may separately record evidence-backed reclassification with original and new severity, actor and evidence.
- `open | in_progress -> not_applicable` only with rationale and reviewer confirmation.
- A finding cannot be marked resolved merely because prose was rewritten; its underlying defect must be addressed.
- After remediation, rerun deterministic checks and re-review affected areas.
- Any material scope, evidence, estimate, or requirement change creates a new artifact version and triggers re-review.
- Previously approved artifacts are not overwritten.

## 7. Release gates

### Gate A — Input integrity
Required sources are readable or parse limitations are visible; project access and provenance are valid.

### Gate B — Requirement integrity
All captured requirements are accounted for. Critical ambiguity/conflict has a question or explicit disposition. Source attribution passes.

### Gate C — Technical evidence
Material feasibility claims are supported or marked unverified and excluded from commitments. Relevant security and integration dependencies are documented.

### Gate D — Scope integrity
All committed scope items trace to requirements; acceptance criteria, assumptions, dependencies, exclusions and estimate basis are present as applicable.

### Gate E — Independent review
No open critical or major blocker remains. Deterministic checks pass. Review result and finding dispositions are persisted.

### Gate F — Human decision
A user authorized for internal approval explicitly approves the exact artifact version. Client release is a separate permission/action and is disabled in the MVP by default.

`pass_with_conditions` MUST NOT bypass any open blocker. A draft can be exported for discussion with visible warnings only if clearly marked `NOT APPROVAL-READY` and the export action is permitted.

## 8. Structured review-result contract

```yaml
review_id: REV-EXAMPLE
project_id: PRJ-EXAMPLE
artifact_version: 3
reviewer_type: independent_llm_plus_deterministic
checklist_version: "0.1.0"
outcome: changes_required
summary: "An integration dependency is not verified."
checks:
  - check_id: technical_evidence
    result: fail
    affected_ids: [REQ-EX-003, SCOPE-EX-001]
findings:
  - finding_id: FIND-EX-001
    severity: major
    status: open
    category: evidence
    description: "ERP authentication method and authorized scopes are not established."
    affected_requirement_ids: [REQ-EX-003]
    affected_scope_item_ids: [SCOPE-EX-001]
    evidence_refs: []
    required_action: "Confirm vendor API documentation and client access prerequisites."
blocking_reasons:
  - "Major evidence finding remains open."
reviewed_at: "2026-10-16T00:00:00Z"
```

The example is illustrative, not an actual review result. In implementation, `checks` and `findings` must be validated by Pydantic models. Use a consistent finding category enum maintained in code.

## 9. Human approval and accepted risk

Approval records the actor, role, timestamp, exact artifact version/hash, decision, rationale, and finding dispositions. The server validates that the actor has the relevant permission. No LLM may create or simulate a human decision.

Critical findings cannot be waived in the MVP. Major risk acceptance requires a documented policy permission, designated risk owner, mitigation, rationale, and follow-up date. Stakeholders must name the approver and risk owner roles before production.

## 10. Audit requirements

Persist checklist version, reviewer inputs, output, findings, fixes, rerun results, human edits, decisions, artifact hashes, and relevant registry/catalog/schema versions. Store concise evidence-linked rationale, not hidden chain-of-thought. Review history must remain accessible to authorized auditors.

## 11. Block approval when

- Required sources or traceability records are missing.
- A critical or major blocker remains open.
- A material claim is unverified but presented as a commitment.
- A material contradiction affects scope or feasibility.
- Authorization, tenant isolation, or audit integrity checks fail.
- Estimate assumptions/units are missing where estimates are presented as commitments.
- Scope items lack requirement mapping.
- Required deterministic tests fail.
- Required human approval is absent or applies to a different artifact version.

## 12. v0.3.0 review enforcement — D-05 through D-09

- **Gate B:** A user-authorized, revision-bound acceptance decision is mandatory before an inferred requirement supports committed scope. Bulk acceptance must exclude unresolved, stale, conflicting or blocked requirements and persist per-item audit records. Permission assignment/eligibility enumerations still require completion.
- **Gate C:** Treat `Materiality.unassessed` as material. Material claims in committed scope must have verified, applicable evidence; invalid/stale source linkage is not verification. A downgrade needs a Technical Reviewer decision with justification and audit. Criticality is determined by deterministic criteria, with unknown treated as unsafe until assessed.
- **Gate D:** ScopeItem must carry explicit `commitment`; optional proposals cannot silently be drafted as commitments. Task hours and ranges come from authorized WDS history, approved reference ranges or human estimation, and need final human approval.
- **Gate E:** A critical review finding is **never waivable** in MVP. Reject `accepted_risk` for critical severity. Block final approval until the finding is resolved, or evidence-backed severity reclassification is explicitly approved and logged by an authorized independent reviewer. This replaces any legacy interpretation of §9 suggesting critical waivers.
- **Gate F:** Role-based authorization is fixed and deny-by-default. Approver must not be the same individual as the artifact preparer/submitter. Administrator role alone cannot grant approval or bypass separation of duties.
- Decision D-02 mandates ACL-filtered RAG-first retrieval, followed only by read-only allowlisted live sources where required; pending allowlist = deny all live access, with claims unverified if no sufficient source is available.

**Do not mark any gate implementation-ready until its referenced record, actor permission, and deterministic check are unambiguously specified.**

## 13. v0.3.0 D-09/D-14 release policy

Critical governance findings must not be accepted as risk or waived in the MVP. A critical finding blocks approval until resolved, or formally reclassified with versioned evidence, authorized actor identity, rationale, date, and audit trail. Reclassification is not a bypass of failed security, privacy, data-integrity or permissions checks. The WDS Technical Lead owns proposed evaluation thresholds; the designated Approver signs off accepted release thresholds and artifacts. Until numerical thresholds and adequate sample sizes are approved, do not claim passing evaluation or release readiness.
