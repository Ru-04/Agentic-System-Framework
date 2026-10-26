# AI-S04 QA and Acceptance Register

Status: **AI-S04 Synthetic-Scope Engineering: APPROVED** (WDS formal approval). **Full functional acceptance: PENDING** (35 of 45 reported criteria satisfied; ten real-platform criteria not waived). Real-platform verification has not started.

Branch: `integration/ai-s01-s02-s03`. Development checkpoint: `ac1ef7e` (WooCommerce, BigCommerce). Nine-file commit:
`2988913` (Shift4Shop, Magento / Adobe Commerce, BigCommerce wording fix). Low-finding corrections: uncommitted.

## 1. Acceptance criteria

There are 45 reported criteria: seven synthetic-scope criteria and two real-platform criteria for each of five specialists.

Synthetic-scope criteria (per specialist):
- S1 Contract: runs through the AI-2 execution wrapper; in-scope tasks succeed; out-of-scope and wrong-platform tasks are refused.
- S2 Evidence status: every claim, solution and risk is unverified or conflicting; no verified status is produced.
- S3 Provenance: claims cite only evidence the context serves; evidence records are SYNTHETIC_MOCK and UNVERIFIED.
- S4 Isolation: records of another project, and of collections not allowed, are never cited.
- S5 No fabrication: outputs are framed as hypotheses; questions ask for versions, editions or official documentation.
- S6 Identity: canonical platform names; registry identifiers preserved where a migration is pending.
- S7 No network and no automatic execution: no network or model-client import; only an operator-built task runs an agent.

Real-platform criteria (per specialist, not met):
- R1 Each platform-specific claim is checked against official vendor documentation for the version in use.
- R2 Each platform's APIs and integrations are exercised against an authorised test instance under an approved access policy.

## 2. Status by specialist

| Specialist | Registry identifier | Synthetic-scope (S1 to S7) | Real-platform (R1, R2) | Where |
|---|---|---|---|---|
| Shopify | `CAP-ECOMMERCE` (AI-1) | QA-confirmed contract conformance | Not met | AI-1, unchanged |
| WordPress / WooCommerce | `CAP-WORDPRESS-WOOCOMMERCE` | Met (QA PASS) | Not met | `ac1ef7e` |
| BigCommerce | `CAP-BIGCOMMERCE` | Met (QA PASS) | Not met | `ac1ef7e`, text fix `2988913` |
| Shift4Shop (formerly 3dcart) | `CAP-3D-CART-SHIFT-SHOPIFY` (legacy, kept) | Met (QA PASS) | Not met | `2988913` |
| Magento / Adobe Commerce | `CAP-MAGENTO-ADOBE-COMMERCE` | Met (QA PASS) | Not met | `2988913` |

Synthetic-scope criteria met: 35 of 35. Real-platform criteria met: 0 of 10. Total: 35 of 45 (about 78%).

## 3. Independent QA

- Synthetic-scope QA on the five specialists (before the Low corrections): PASS. Four Low findings were reported:
  Magento deployment classification, duplicated topic wording, Magento edition-specific hypothesis wording, and a test
  docstring and name.
- The four Low findings are corrected in an uncommitted change and covered by three new regression tests.
  Focused QA of that change: see section 5.

## 4. Test evidence

- Full integration gate after the Low corrections: pytest 1256 passed; ruff check and format clean (115 files);
  mypy --strict src tests clean (115 files).
- AI-S04 suites: WooCommerce 15, BigCommerce 15, Shift4Shop 17, Magento 16 (total 63 at `2988913`, plus three
  regression tests for the Low corrections).

## 5. Low-finding corrections (uncommitted, separate reviewed change)

1. Magento deployment topic: "deployment" maps to "deployment and hosting" in the architecture layer, via a prefix match.
2. Duplicated wording: a phrase that repeats, or sits inside one already chosen, is skipped (all four modules).
3. Magento edition wording: the hypothesis names "Magento Open Source or Adobe Commerce" and states the edition is
   not confirmed.
4. Test docstring and outside-scope test name corrected in the Shift4Shop and Magento test modules.

## 6. Not claimed

- The specialists are not verified against real platform capabilities.
- No vendor documentation was consulted and no platform was accessed.
- No real project, client document or live provider was used.
- AI-S04 is not operator-selectable at runtime (see `AI_S04_ROUTING_READINESS.md`).

## 7. Remaining for full AI-S04 acceptance

- R1 and R2 for each of the five specialists (see `AI_S04_VENDOR_REQUIREMENTS.md`).
- Shift4Shop registry identifier migration, only with WDS approval (see `AI_S04_SHIFT4SHOP_ID_MIGRATION_PROPOSAL.md`).
- Routing readiness gates (see `AI_S04_ROUTING_READINESS.md`).
- WDS acceptance decision. Either full acceptance, or a clearly limited engineering-only closure if WDS separately
  authorises it.

## 8. Supporting documents (preparation, not approval)

- `AI_S04_REGISTRY_MIGRATION_AMENDMENT.md`: proposed registry amendment for D-01 and D-15 (not applied).
- `AI_S04_VENDOR_SOURCE_ACCESS_MATRIX.md`: five-platform source and access approval matrix (nothing approved).
- `AI_S04_ROUTING_READINESS.md`: runtime activation remains blocked.

## 9. Remaining ten real-platform criteria (not waived)

For each of Shopify, WooCommerce, BigCommerce, Shift4Shop and Magento Open Source / Adobe Commerce (evaluated separately):
- R1: each platform-specific claim traced to a checked official source for the version in use.
- R2: each platform's integration path exercised against an authorised test instance, with results recorded as evidence.
