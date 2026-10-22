# Proposals pending approval — Sprint 2 QA2-07 and QA2-13

**Status:** PROPOSED. No code change has been made. Each item needs the decision-maker's approval before implementation (management answers 2 and 3, 22 October 2026).

## P1 — QA2-07: where the approved-source rule is enforced

**Problem:** the specialist trusts any `SourceRecord` with kind `VENDOR_DOC`. The allowlist applies only inside `fetch_vendor_document`. A record built from any origin is therefore treated as approved vendor evidence.

**Options:**
- A. Check origin in `SourceRecord` itself. A `VENDOR_DOC` record must have an `https` origin on an allowlisted host. `INTERNAL_RAG` records must use an `internal:` origin. Test fixtures use a separate test-only constructor that is not importable from production code.
- B. Check origin in the retriever interface only. Every production retriever must enforce it. Lighter, but it relies on each retriever being correct.
- C. Leave as is and document. Not recommended.

**Recommendation:** A, because it puts the rule where every record is created, so no retriever can bypass it. The fixture escape hatch must be explicit and test-only.

**Effect on tests:** fixtures move to the test-only constructor. Existing tests that use `fixture://` origins are updated. No change to the shared contract.

## P2 — QA2-13: environment proxies on vendor fetches

**Problem:** urllib honours `HTTP_PROXY` and `HTTPS_PROXY`. A permitted request can then be routed through a proxy host that the allowlist did not approve. The allowlist is therefore not enforced at the network hop.

**Options:**
- A. Disable environment proxies for vendor fetches (ignore `*_PROXY` variables). Simplest, and the allowlist controls the destination directly.
- B. Allow only an explicitly configured, approved proxy URL. Requires a proxy approval and its own record.
- C. Keep the default and document the risk. Not recommended.

**Recommendation:** A, now. Revisit B only if an approved corporate proxy is required, with its own decision.

**Effect on tests:** one test asserts that a proxy variable does not change the opener's handlers.

## Approval needed

- [ ] P1 option: ______ (A recommended)
- [ ] P2 option: ______ (A recommended)
- Approver: ______________________  Date: ____________
