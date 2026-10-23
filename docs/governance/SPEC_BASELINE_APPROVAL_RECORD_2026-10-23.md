# Specification baseline approval record — management decision (recorded 23 October 2026)

**Status:** management decision recorded as reported. **Version binding is NOT yet confirmed** (section 4). This record is not an independent review, and it does not make any specification authoritative on its own.

## 1. Decision as reported

- **Approval date:** 23 October 2026.
- **Approver role:** WDS Authorized Approver.
- **Approver name and signature:** **not provided in this environment** and not recorded here.
- **Approved subject, as reported:** the reconciled seven-document specification package, and Sprint 2 engineering progress.
- **Source of this record:** the decision-maker's written instruction of 23 October 2026. I have not seen a separate approval document, and none is in the repository.

## 2. What the seven-document set is in the repository

| Document (`WebDesk_Agentic_Requirement_Platform_Specs/`) | Version | Header status (as committed) |
|---|---|---|
| GOVERNANCE.md | 0.3.10-foundation-gate1-review | Working draft for independent re-review; NOT implementation-approved |
| ARCHITECTURE.md | 0.3.10-foundation-gate1-review | Working draft for independent re-review; NOT implementation-approved |
| SERVICE_CATALOG.yaml | 0.3.10-foundation-gate1-review | `working_draft_unapproved` |
| AGENT_REGISTRY.yaml | 0.3.10-foundation-gate1-review | `working_draft_unapproved` |
| REQUIREMENT_SCHEMA.md | 0.3.10-foundation-gate1-review | Working draft for independent re-review; NOT implementation-approved |
| REVIEW_POLICY.md | 0.3.10-foundation-gate1-review | Working draft for independent re-review; NOT implementation-approved |
| EVALUATION_PLAN.md | 0.3.10-foundation-gate1-review | Proposed; no benchmark results have been measured |

The seven documents above are unchanged since their last commits (no file in this set was edited for reconciliation). The reconciliation work is held as analysis in `docs/spec-reconciliation/` (last changed in commit `54aef28`) and in `docs/spec-reconciliation/CONSOLIDATED_REVIEW_PACKAGE.md`. **No revised seven-document set exists in the repository.**

## 3. Hashes of the seven documents

Canonical SHA-256 is computed on LF-normalised content. This Windows checkout has `core.autocrlf` enabled, so the working files have CRLF line endings while the committed blobs have LF. The canonical hash is therefore the stable identity. The git blob SHA is the committed identity at commit `54aef28`.

| Document | Canonical SHA-256 (LF-normalised) | Git blob SHA at 54aef28 |
|---|---|---|
| GOVERNANCE.md | `d9ba899d119fe34452e384739bd2594f2cc40b2aaba41da8cb9eadca995f0b8e` | `af6c36b87a8d5d593a2a72d1305a0b67bcbaab47` |
| ARCHITECTURE.md | `585ff589449d40d8de7e8ee581942767d0ef7c3589847b57ef58865b4b218d8d` | `4c7c01ca06e6d04c3d14912a0dbd3185b8cdfe98` |
| SERVICE_CATALOG.yaml | `f37b92b01c7a641ef1650db9cbeb2183f58a19292dcb42ea5416a7a491aa15ee` | `089756d0d9004d3775fd785802cd1ff33a717d9a` |
| AGENT_REGISTRY.yaml | `d517205605ca2c4f71f5ad6a9c7bc65a7e25dd7f53a758be6211048216a70e57` | `13c04e0b8406e1d5607881b6c55986ec4485cf77` |
| REQUIREMENT_SCHEMA.md | `f408ee3ecc7c6d9d152473ac4576b2282889752030ad92ee2108fb92a3657d65` | `add34264d919103b72ca3aee5f996b073e233435` |
| REVIEW_POLICY.md | `d1ed5aa634a933e79a4014db539006ea913621cd47ee1bea4c752f80041ad84f` | `84157bdaf44920a53942b97f139103b0e6481cf9` |
| EVALUATION_PLAN.md | `4f9255293c143e53741a896b89c0fc2240b72e2261e6f552ccfea8b7c8fc5a78` | `6af16fc8ba3c1f6ac78355ad156b0bba461413a9` |

Preserved records (not altered):
- `GATE1_IMPLEMENTATION_AUTHORIZATION.md`: git blob `3112addaf9187030b5a1ade0c35ccc999b7f230b` (last changed in `ce76b32`).
- `docs/governance/SPECIALIST_IMPLEMENTATION_AUTHORIZATION_AMENDMENT_2026-10-22.md`: last changed in `e2bbfb3`.

## 4. Version-binding question (open)

The approval refers to a "reconciled seven-document package". Three candidates exist, and they are not the same thing:

1. **The seven drafts above (0.3.10), as committed.** Their headers say "NOT implementation-approved". An approval of them would contradict those headers unless the approver states that the approval supersedes the headers.
2. **A revised set of seven documents** produced by the reconciliation. **None exists in the repository.**
3. **The reconciliation analysis** (`docs/spec-reconciliation/`). It is a review package with conflicts and proposed corrections. It is not a specification.

**Question for the WDS Authorized Approver:** which artifact does the approval bind to? Options: (a) the seven drafts above by hash, with the stated exception to their headers; (b) a revised set that must be produced, reviewed and hashed before approval; or (c) the analysis package only, with no specification approved. Until this is answered, the approval is **not bound to any specification revision**.

## 5. Scope and limitations of the decision

- The decision authorizes nothing beyond the non-production scope already in the 22 October amendment. It does not authorize production, protected integration, live model calls (D09), or a retroactive v2.0 approval. No historical v2.0 approval exists.
- Sprint 2 engineering progress is recorded as reported. It is not Sprint 2 acceptance.

## 6. Independent review conditions still outstanding

- The consolidated independent review of the seven documents (S2-D22) has **not been performed**. Findings and required corrections are in `docs/spec-reconciliation/CONSOLIDATED_REVIEW_PACKAGE.md`, section 8, and are blank.
- The conflicts in `docs/spec-reconciliation/conflict-and-decision-register.md` remain open, including CR-01 (implementation readiness versus draft headers) and CR-08 (operator confirmation before execution, D07).
- Any specification that is later reviewed must be re-hashed, and this record updated, before it can be referred to as approved.

## 7. Signature fields (human only)

- Approver name: ______________________
- Approver role: WDS Authorized Approver
- Version binding confirmed as option (a), (b) or (c): ______
- Signature or approval reference: **to be completed by the approver only**
