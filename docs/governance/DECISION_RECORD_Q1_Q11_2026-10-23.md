# Decision record Q1–Q11 — WDS Authorized Approver (effective 23 October 2026)

**Approver:** WDS Authorized Approver. **Full name and signature:** not provided in this record. **Decision date:** 23 October 2026.
**Nature:** new management decisions. Not retroactive. Earlier records are preserved, not rewritten.

## Controlling decisions

| ID | Decision (as approved) | Scope and restrictions | Prior records referenced |
|---|---|---|---|
| **Q1** | Specification version: produce a properly reconciled seven-document version. Bind approval only to the exact reviewed version, with its commit SHA and content hashes. Keep v0.3.10 as historical drafts. Track CR-01 and CR-08 until resolved. Do not treat unchanged drafts as an implementation-approved package. Do not bind prior approval to a newly generated version automatically. | **Controlling for future version binding.** Supersedes the earlier "Option A" selection, which is preserved as a historical record. | `SPEC_BASELINE_APPROVAL_RECORD_2026-10-23.md` (section 4); `BLOCKER_RESPONSES_2026-10-23.md` item 1 |
| **Q2** | Independent reviewer: Arushi Sharma (AS), Technical Lead and Project Manager, proposed. May perform the 55-pair review only if independence is verified. | **Conditional.** See the independence finding below. | `AS_REVIEW_PACKET_2026-10-23.md` |
| **Q3** | Canonical name "Shift4Shop (formerly 3dcart)". Legacy identifier `CAP-3D-CART-SHIFT-SHOPIFY` retained as a compatibility alias. No identifier migration without separate approval. | In force. | D06 (22 Oct); DECISION_REGISTER entries on D-01, D-15, C-01 |
| **Q4** | Use 55 independently labelled requirement–passage pairs to validate the deterministic relevance method. Labels: DIRECT, PARTIAL, IRRELEVANT. Labels measure evidence relevance only, not platform feasibility or capability. | Human labels not yet received (0 of 55). | `HUMAN_REVIEW_PROTOCOL.md`; S2-D10, S2-D14 |
| **Q5** | Shopify plan pages returning HTTP 403 are unavailable evidence. No bypass. Plan-specific claims stay unverified unless supported by other authorized sources. | In force. | S2-D08 |
| **Q6** | Manually transcribed browser passages are not verified Sprint 2 evidence. Reconsider only after an approved, auditable capture method exists. | In force. Supersedes the earlier "transcription is not recommended" wording. | S2-D07 (browser access) |
| **Q7** | QA-07 runtime authority enforcement is mandatory and acceptance-blocking before applicable orchestrator execution and protected integration. Planned for M3 Sprint 6. No unprotected agent execution before verified. | In force. Confirms the earlier deferral with an explicit gate. | QA-07 deferral (user decision, Sprint 1) |
| **Q8** | Any production retriever must pass tests for workspace isolation, permission filtering, quarantine and eligibility ordering, ranking and limit behaviour, and citation identity. No production activation without the contract. | In force. Implemented as `tests/support/retriever_contract.py`. | S2-D18, S2-D20 |
| **Q9** | CRA documentation may be used as dated regulatory background. Outputs must distinguish background from professional legal or tax advice. No claim of verified client-specific compliance. | In force. | S2-D09 |
| **Q10** | `www.shopify.com` within S2-D08 only for authorized official plan and feature documentation. No unrestricted crawling. | In force. | S2-D08; S2-R3 |
| **Q11** | Requirements with fewer than three meaningful specific terms trigger a clarification request, not a relevance grade. Preserve handling and regression tests. | In force. | S2-R2 (23 Oct); `test_s2_preserved_decisions.py` |

## Outstanding dependencies

1. **Q1 (version):** the reconciled seven-document version is **not yet produced**. CR-01 and CR-08 remain open.
2. **Q2 (independence):** **not established.** See the independence finding below.
3. **Q4 (labels):** 0 of 55 returned.
4. **Q7:** M3 Sprint 6 implementation. Not started, correctly.
5. **Acceptance:** Sprint 1 and Sprint 2 human QA signatures not given.

## Independence finding (Q2)

- Every commit in the repository, including the Sprint 1 and Sprint 2 implementation, the relevance evaluation tooling (`src/webdesk/evidence/evaluation.py`), the review sheet, the evidence package and the completion report, is authored by `toarushiS <arushi@webdeskinc.com>`.
- That identity is the git account configured on the working machine. It does not by itself prove that AS personally wrote the code. The code was produced in working sessions on this machine.
- Under Q2, AS may perform the review only if independence is verified. The repository shows AS as the author of the artifacts she would review. **Independence cannot be established from the repository.**
- Required action: AS states in writing whether she authored, directed or materially contributed to the implementation, evidence or review tooling under review. If yes, or if the record cannot be confirmed, the decision-maker must appoint another qualified reviewer with documented authorization (Q2).

## Signature fields

- WDS Authorized Approver full name: ______________________ (not entered by the system)
- Signature or approval reference: ______________________ (approver only)
