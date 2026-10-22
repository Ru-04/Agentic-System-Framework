# Shopify live retrieval record — 22 October 2026 (metadata only)

Purpose: evidence that one allowlisted live retrieval was performed through `fetch_vendor_document`. The retrieved page text is held outside the repository (copyright and size), and only metadata is recorded here.

| Field | Value |
|---|---|
| URL requested | `https://shopify.dev/docs/api/storefront/latest` |
| Allowlist | `PROPOSED_SHOPIFY_ALLOWLIST` (`shopify.dev`, `help.shopify.com`) |
| Retrieved at (UTC) | 2026-10-22T15:01:30Z |
| Result | Success |
| Characters of extracted text | 32,212 |
| SHA-256 of extracted text | `34a565281e9fc1dd7ac5505039437197af251690e9afa89a1db46e998e25e13f` |
| Redirect handling | The URL `https://shopify.dev/docs/api/storefront` returns HTTP 302 to `/docs/api/storefront/latest` on the same host. The fetch refuses redirects, so the canonical `/latest` URL was requested directly. |

Other attempts:
- `https://help.shopify.com/en/manual/products` returned HTTP 403 to a plain client, with and without a browser-style user agent. No bypass was attempted. It is not counted as retrieved.

Specialist run on this text (structure only):
- Three tasks run through the shared harness. Each returned `incomplete` with cited findings and the standard "not performed" unknown.
- Findings are topic mentions, not an investigation. No plan or version wording was found for these tasks.

Limits:
- This is one page, not a corpus. It is not a test of plan-specific or version-sensitive claims.
- Acceptance under D11 is not granted by this record.

## Addendum: Sprint 2 run corpus

A further 16 allowlisted fetches were made for the Sprint 2 run on the same day. Their metadata is in `docs/evaluation/SHOPIFY_REAL_INVESTIGATION_2026-10-22.md`, section 1. The scope of these fetches is pending the decision-maker's confirmation (`DECISION_RECORD_2026-10-22.md`, section 7).
