# Shift4Shop Registry Identifier Migration: Proposal (not performed)

Status: **proposal only. No migration performed.** WDS approval is required before any change.

Canonical display name confirmed by WDS: **Shift4Shop (formerly 3dcart)**. Registry identifier retained for now:
**`CAP-3D-CART-SHIFT-SHOPIFY`**, with specialist category **`three_d_cart_shift_shopify_specialist`**.
Related pending decisions in `DECISION_REGISTER.md`: D-01 (naming cleanup pending) and D-15 (alias mappings pending review).

## 1. Current references (inventory)

Registry and specifications (`WebDesk_Agentic_Requirement_Platform_Specs/`):
- `AGENT_REGISTRY.yaml`: routing rule `ROUTE-3D-CART-SHIFT-001` (line ~35, marked not executable); capability entry
  `CAP-3D-CART-SHIFT-SHOPIFY` (line ~245, status `proposed_canonical_name_and_alias_pending`); references at lines ~105,
  ~489 and ~630; category `three_d_cart_shift_shopify_specialist` (line ~248).
- `ARCHITECTURE.md` lines ~72 and ~325 (diagram label and routing statement).
- `DECISION_REGISTER.md` D-01, D-11 and D-15.

Code and tests (`ai_engine/`):
- `src/ai_engine/shift4shop/agent.py` lines 40-41: `CAPABILITY_ID`, `SPECIALIST_CATEGORY_ID`.
- `src/ai_engine/rag/specialist.py` line 26: the category identifier in `SEVEN_SPECIALIST_CATEGORY_IDS`.
- `tests/test_ai_s04_shift4shop.py` lines 44-45 and 259-260.

Stored identifiers:
- No stored records carrying this identifier exist in this repository. Evidence, task and audit records are in-memory
  and synthetic. Any stored records elsewhere (Foundation or a database) are unknown and must be inventoried first.

## 2. Proposed approach

1. Keep `CAP-3D-CART-SHIFT-SHOPIFY` as the authoritative ID until WDS approves a canonical replacement (for example
   `CAP-SHIFT4SHOP`; the name itself is a WDS decision).
2. Introduce the new ID as an alias, not a rename. Both IDs resolve to the same specialist for lookup and validation.
3. Registry: add the new ID with `status: proposed` beside the legacy entry. Keep the legacy entry until the deprecation
   window closes.
4. Routing and selection: the legacy rule text stays non-executable. The alias applies to operator selection only.
5. Stored identifiers: a one-time inventory, then a rewrite of references only under an approved change record. Old
   identifiers stay readable.
6. Deprecation: the legacy identifier is removed only after WDS confirms no references remain.

## 3. Tests the migration needs

- Both identifiers resolve to the same specialist and category.
- Validation rejects an unknown identifier.
- A task built with either identifier produces the same output for the same requirement.
- The registry loader accepts both entries and rejects duplicates.
- Existing AI-S04 tests still pass unchanged.

## 4. Rollback

- Remove the alias entry and restore the legacy-only registry. The code keeps the legacy constants, so nothing else changes.
- Any rewritten stored identifiers must have a recorded mapping (new to old) so they can be reversed.
- Rollback is tested before the migration is applied to any shared branch.

## 5. Decisions WDS must make

1. Approve the canonical replacement identifier.
2. Approve the deprecation window and removal condition.
3. Confirm whether stored records exist outside this repository, and who inventories them.
4. Approve the migration as a separate change, after D-01 and D-15 are resolved.
