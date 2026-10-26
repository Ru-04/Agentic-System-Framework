# Shift4Shop Registry Migration: Proposed Amendment (not applied)

Status: **proposal only.** The authoritative registry (`WebDesk_Agentic_Requirement_Platform_Specs/AGENT_REGISTRY.yaml`) is
not modified. This amendment may be applied only after decisions D-01 and D-15 are formally reconciled and the registry
change is approved through the applicable governance process.

WDS approved (AI-S04 acceptance record):
- Canonical name: **Shift4Shop (formerly 3dcart)**.
- Canonical identifier: **`CAP-SHIFT4SHOP`**.
- Legacy compatibility identifier: **`CAP-3D-CART-SHIFT-SHOPIFY`**, which stays supported as an alias during migration.

## 1. Why the registry must change first

The registry is the source of truth for capability IDs. Today the canonical identifier is refused by the existing
binding code, while the legacy identifier is accepted. Probe result on the integration branch:

- `bind_selection` with `CAP-3D-CART-SHIFT-SHOPIFY`: selected.
- `bind_selection` with `CAP-SHIFT4SHOP`: refused, "capability CAP-SHIFT4SHOP is not in the registry".

Nothing else can make the canonical identifier work without a registry entry. Code-side aliasing without a registry entry
would create a second, unauthorised identity, so none is proposed.

## 2. Exact proposed registry amendment

Schema extension (proposed): each capability entry may carry an `aliases` list. An alias is an identifier that resolves to
the same entry and never to a second entry.

Proposed entry, replacing the legacy entry's `id` and keeping every other field unchanged:

```yaml
  - id: CAP-SHIFT4SHOP
    aliases:
      - CAP-3D-CART-SHIFT-SHOPIFY
    name: Shift4Shop (formerly 3dcart) Platform Specialist
    type: llm_capability
    specialist_category: three_d_cart_shift_shopify_specialist
    status: proposed_canonical_name_and_alias_pending   # to be updated on approval
    # all other fields (purpose, responsibilities, non_responsibilities, schemas, allowed_tools,
    # permissions, activation, evidence_requirement, validation, dependencies, handoffs, ...) unchanged
```

Specialist category: the category identifier `three_d_cart_shift_shopify_specialist` is kept in this amendment. Whether a
category rename is also needed is part of D-01 and must be decided separately.

Routing rule `ROUTE-3D-CART-SHIFT-001` (non-executable legacy rule text): its `activate` list gains `CAP-SHIFT4SHOP`. The rule
stays non-executable until the structured router is approved.

## 3. Alias behaviour (required)

- Both identifiers resolve to the same registry entry object.
- Lookup by either identifier returns the same capability and category.
- Duplicate identifiers (an alias equal to another entry's `id`, or two entries claiming one alias) are rejected at load.
- Unknown identifiers are rejected as today.
- A task built with either identifier yields the same `specialist_category_id` and the same specialist behaviour.
- Output records keep the identifier the task was built with (no silent rewrite of historical records).

## 4. Tests required before application

- Loader accepts the alias and resolves it to the canonical entry.
- Loader rejects an alias that duplicates another entry's `id` or another alias.
- `bind_selection` selects with either identifier and returns the same outcome.
- A task built with the legacy identifier and one built with the canonical identifier produce equal specialist output for
  the same requirement, apart from the identifier field.
- Existing AI-S04 Shift4Shop tests pass unchanged.
- Full regression gate passes.

## 5. Stored and external identifiers

- No stored records with this identifier exist in this repository. Any records outside the repository must be inventoried
  before any rewrite (see `AI_S04_SHIFT4SHOP_ID_MIGRATION_PROPOSAL.md`, section 1).
- No persisted identifier is changed by this amendment. Rewrites, if approved later, require a recorded new-to-old mapping.

## 6. Rollback

1. Revert the registry file to the pre-amendment version (the legacy entry, no `aliases` field).
2. Revert the schema extension in the loader; the code path that reads `aliases` becomes unused.
3. Confirm the legacy identifier still binds and the regression gate passes.
4. Any stored-identifier mapping is kept so a reverse rewrite is possible.

## 7. Approvals required before application

1. D-01: final canonical display name and canonical ID, formally reconciled.
2. D-15: alias mapping, reviewed.
3. Governance approval of the registry change under the applicable process.
4. Confirmation whether the category identifier also changes (D-01).
5. Confirmation of the registry's signing or version control requirement, if any, before editing the authoritative file.

Until these are complete the registry remains unchanged and the canonical identifier remains unsupported.
