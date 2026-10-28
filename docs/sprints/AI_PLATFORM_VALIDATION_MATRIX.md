# Seven-Platform Validation Matrix (Stage 1G, preparation only)

Status: **preparation**. No vendor documentation was retrieved, no sandbox or test store was accessed, and no
approval exists for any row. Every "Candidate" below is a proposal for WDS and Foundation approval, not a source
that has been read. Acceptance for any platform is **not granted** (AI-S10 formal acceptance, section 3).

Scenario identifiers refer to the AI-S10 catalogue. Status reflects the accepted offline synthetic evaluation only.

| Domain (identity) | Specialist category | Offline synthetic scenarios | Candidate official documentation sources (to approve; not read) | Foundation source approval | Version coverage | Sandbox or test store | Access owner | Acceptance criteria (proposed) |
|---|---|---|---|---|---|---|---|---|
| Shopify | `shopify_specialist` | SPEC-R01, SPEC-08, SPEC-12 | Shopify developer and admin documentation, as approved | Required (D-02 allowlist) | To be defined by WDS | Development store (to be approved) | To be assigned | Each claim cites an approved, versioned source; no unapproved claim is `verified` |
| Shift4Shop (legacy identity) | `shift4shop` category identity `three_d_cart_shift_shopify_specialist` | SPEC-R04, SPEC-02 | Shift4Shop documentation, as approved; registry migration D-01/D-15 open | Required; migration decision open | To be defined | To be approved | To be assigned | Identity mapping resolved (D-01/D-15) before any platform acceptance |
| WooCommerce / WordPress | `wordpress_woocommerce_specialist` | SPEC-R02 | WooCommerce and WordPress documentation, as approved | Required | To be defined | Local or hosted test site (to approve) | To be assigned | As Shopify |
| BigCommerce | `bigcommerce_specialist` | SPEC-R03 | BigCommerce developer documentation, as approved | Required | To be defined | Sandbox store (to approve) | To be assigned | As Shopify |
| Magento Open Source / Adobe Commerce | `magento_adobe_commerce_specialist` | SPEC-R05 | Magento and Adobe Commerce documentation, as approved | Required | To be defined (Open Source and Commerce editions) | Test instance (to approve) | To be assigned | As Shopify, per edition |
| Standalone applications | `standalone_applications_specialist` | SPEC-R06 | Vendor documentation per application, as approved | Required per application | To be defined | Per application (to approve) | To be assigned | Per application |
| Middleware applications | `middleware_applications_specialist` | SPEC-R07 | Vendor documentation per middleware product, as approved | Required per product | To be defined | Per product (to approve) | To be assigned | Per product |

Scenario coverage notes:

- `SPEC-R01` to `SPEC-R07` check routing to each category (offline).
- `SPEC-15` (vendor documentation validation) and `SPEC-16` (real-platform acceptance) are **blocked**.
- `EXT-02` (sandbox investigation) is **blocked**. No row above has a sandbox approval.

Gating items before any row can be exercised:

1. WDS approval of each candidate documentation source and of the allowlist (D-02).
2. Foundation approval of each source for ingestion and the admitted provenance (see AI read contract, section 5).
3. Named access owners for each sandbox or test store.
4. Version coverage decided per platform.
5. Human acceptance criteria approved by WDS.

Nothing in this matrix authorises retrieval from a vendor, operation of a sandbox, or real client data.
