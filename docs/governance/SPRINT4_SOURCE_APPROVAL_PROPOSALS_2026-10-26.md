# Sprint 4 source-specific approval proposals (26 October 2026)

**Status: PROPOSALS ONLY. Nothing is approved. No domain has been retrieved from.** Each entry must be approved separately by WDS. Default-deny applies to every entry until then.

Required for every proposal: verified official ownership; exact host; exact paths; edition and version; retrieval method; provenance; restrictions; access and availability limits.

## Per-specialist proposals

### 1. Shift4Shop (formerly 3dcart)
- **Owner:** not verified. The search results identify Shift4Shop as the product (formerly 3dcart). No result names the corporate owner. Ownership must be confirmed on Shift4Shop's own official site.
- **Candidate domain:** `developer.3dcart.com` (portal titled "Developer Portal"; lists app building, theme building, REST API reference, front-end API). **Not confirmed as maintained official documentation.**
- **Conflicting secondary information:** third-party guides mention `devportal.3dcart.com` and `apirest.3dcart.com`. These are secondary and conflict with each other. Each must be checked against the official reference before use.
- **Paths:** none authorized. WDS names exact paths after the owner is confirmed.
- **Edition and version:** the Shift4Shop specialist requires the exact platform version. The version must be recorded with each claim.
- **Retrieval method:** named pages only, https only, no crawling, no redirects followed, each fetch recorded with URL, time, status and content hash.
- **Restrictions:** no credential, no store data, no live store access. Read-only documentation only.
- **Limitations:** the portal may be developer-facing and may not describe merchant features. Merchant features need a separate source.
- **Decision for WDS:** confirm the owner, then approve or reject `developer.3dcart.com`, and name the paths.

### 2. WordPress & WooCommerce
- **Owners:** WordPress core (WordPress Foundation documentation) and WooCommerce (Automattic). Candidate domains: `developer.wordpress.org`, `woocommerce.com` documentation. Ownership of each to be confirmed before approval.
- **Paths:** named per page; none authorized yet.
- **Edition and version:** WordPress core version, WooCommerce version, PHP version, and the installed plugin set.
- **Retrieval:** named pages only, with content hashes.
- **Restrictions:** core and plugin claims kept separate. A plugin claim is checked only against that plugin's own documentation.
- **Limitations:** plugin documentation varies by plugin and version.

### 3. BigCommerce
- **Owner:** BigCommerce. Candidate domain: `developer.bigcommerce.com`. Ownership to be confirmed.
- **Paths:** named per page.
- **Edition and version:** store plan, API scopes granted, REST or GraphQL variant.
- **Retrieval:** named pages only, with content hashes.
- **Restrictions:** plan- and scope-dependent claims need the plan and scope recorded.
- **Limitations:** plan availability can change.

### 4. Magento Open Source and Adobe Commerce (two separate sources)
- **Magento Open Source:** candidate `devdocs.magento.com`. Ownership and current maintenance to be confirmed.
- **Adobe Commerce:** candidate `developer.adobe.com/commerce`. Ownership to be confirmed.
- **Edition and version:** each edition is a separate source. Capabilities are not carried between them (MAG-01).
- **Retrieval:** named pages only, per edition, with content hashes.
- **Restrictions:** no cross-edition claims.

### 5. Standalone Applications (technology-specific selection rules, no single source)
- **Rule:** the requirement names the technology. Only then is an official source proposed for that technology.
- **Example rule:** a desktop framework named in the requirement gets its own official documentation source, approved separately.
- **Restrictions:** no universal vendor source. No stack hardcoded (TECH-01).
- **Status:** no technology selected. No source proposed.

### 6. Middleware Applications (technology-specific selection rules, no single source)
- **Rule:** the requirement names the middleware product or technology. Only then is its official documentation proposed.
- **Coverage:** API integrations, webhooks, synchronization, queues, authentication, retry, idempotency, error recovery, observability and transformation (TECH-02).
- **Restrictions:** Node.js is not the only option. No single vendor source.
- **Status:** no product selected. No source proposed.

## Shopify (for completeness)
- Candidates `shopify.dev` and `help.shopify.com`, from the earlier register. Not approved. Plan pages that are blocked, and browser text transcribed by hand, are not evidence (task rule).
