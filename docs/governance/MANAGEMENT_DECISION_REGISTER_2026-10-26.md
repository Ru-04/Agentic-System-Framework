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
