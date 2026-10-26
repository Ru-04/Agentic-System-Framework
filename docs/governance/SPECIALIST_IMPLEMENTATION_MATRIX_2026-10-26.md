# Seven-specialist implementation matrix (26 October 2026)

**Heads checked today:** `integration/ai-s01-s02-s03` = `2988913` (local). `claude/webdesk-specialist-baseline-v1-3b21b1` = `72355df` (local; remote `abf13a9`; push deferred). Specialist feature branches `feature/specialist-*` = `5122012` (all six).

**Two frameworks exist and do not share code.** `src/webdesk/specialists/` on the webdesk branch, and `ai_engine/src/ai_engine/` on the integration branch. Nothing is merged between them. A WDS architecture decision is needed before either is chosen.

| # | Specialist | Webdesk branch (`src/webdesk`) | Integration branch (`ai_engine`) | Specialist feature branch | Status |
|---|---|---|---|---|---|
| 1 | Shopify | Investigation implemented (M1 S2). Live retrieval attempted; 0 DIRECT evidence; 55-pair human review not done | Synthetic agent (AI-S01/S02/S03) | none | **Real engineering implementation; not accepted; no reliable real evidence** |
| 2 | Shift4Shop (formerly 3dcart) | Foundation only. No approved source. Legacy alias `CAP-3D-CART-SHIFT-SHOPIFY` kept | Synthetic agent, AI-S04 (`2988913`) | none | **Foundation + synthetic only** |
| 3 | WordPress & WooCommerce | Foundation only. No approved source | Synthetic agent, AI-S04 (`ac1ef7e`) | none | **Foundation + synthetic only** |
| 4 | BigCommerce | Foundation only. No approved source | Synthetic agent, AI-S04 (`ac1ef7e`, wording fix `2988913`) | none | **Foundation + synthetic only** |
| 5 | Magento / Adobe Commerce | Foundation only. No approved source | Synthetic agent, AI-S04 (`2988913`) | none | **Foundation + synthetic only** |
| 6 | Standalone Applications | Foundation only. No approved source | **None** | none | **Foundation only** (no executable agent on either framework) |
| 7 | Middleware Applications | Foundation only. No approved source | **None** | none | **Foundation only** (no executable agent on either framework) |

## Notes
- "Synthetic" means fixture or synthetic evidence only. It is not real platform capability. No real platform investigation exists for any of the six platforms.
- Duplicate development: the same six platforms appear in both frameworks. This is recorded, not merged. Keeping one framework is a WDS decision.
- The integration worktree has **uncommitted changes** to `bigcommerce/agent.py`, `magento/agent.py`, `shift4shop/agent.py` and six more files (9 files, +71/-20). These were not made in this session. They are not committed, not reverted, and not covered by the clean-room run below.
- Clean-room run of `2988913` (full tree export): 1253 tests passed; `ruff check` and `ruff format --check` clean.
