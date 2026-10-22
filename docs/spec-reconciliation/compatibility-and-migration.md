# Compatibility and Migration — v0.3.10 Drafts to a Proposed Reconciled Version

- **Status:** PROPOSED - NOT APPROVED
- **Version label:** not assigned. The approver assigns the label of the reconciled version. This package does not assume a number that could be mistaken for an approved one.
- **Scope:** Describes what a reconciled version would change, what stays compatible, which legacy identifiers must be preserved, and what Sprint 1 code must align with. It does not edit any draft and does not propose new canonical IDs.

## 1. Principles applied

1. No silent rename or deletion of an ID (draft D-15; management D06; `GOV` L285; `EP` L243 `EVAL-LEGACY-ALIAS-001`).
2. Shift4Shop is a separate eCommerce platform, not Shopify and not a 3D configurator (D01, D06; `GOV` L279).
3. Changes that reduce authority or evidence are applied first; changes that add a field are marked additive.
4. Nothing in the reconciled version may be presented as approved until the approval record is completed by an authorized person.

## 2. What changes from v0.3.10 to the proposed version

| # | Area | Change proposed | Type | Draft location | Register |
|---|---|---|---|---|---|
| 1 | Document status | Keep the draft status text until approval. Add a reconciliation section citing D01–D11, the 22 Oct amendment, and the open items. | Additive | GOV, ARCH, RS, RP, EP headers (L3); SC and AR `status` (L4) | CR-01, CR-02 |
| 2 | Development authority | State that development is authorized only by the 22 Oct amendment (isolated, non-production), and that the drafts are not approved. Remove "not yet implementation-cleared" only on approval. | Additive | GOV L275; ARCH L319–L321, L331 | CR-02 |
| 3 | Shift4Shop display name | Human-readable name becomes "Shift4Shop (formerly 3dcart)". IDs unchanged. | Behaviour change to a display field only | AR L246; SC L67 | CR-06 |
| 4 | Shift4Shop status | Replace "proposed_canonical_name_and_alias_pending" with "legacy ID retained as compatibility alias (D06); canonical ID pending approval". Free text in AR; do not add a value to the SC `status` enum (`proposed`, `verified_pattern`, `deprecated`, `blocked`). | Clarifying | AR L249; SC L115 `status: proposed` | CR-06 |
| 5 | Alias map | Add a documented alias table for every legacy ID (see section 4). Canonical IDs left blank until approved. | Additive | None exists (CR-11) | CR-10, CR-11 |
| 6 | Routing predicates | Keep `machine_routing_enabled: false`. Specify the controlled vocabulary and predicates as a separate versioned contract. | Additive; behaviour unchanged | AR L100–L101 | CR-07 |
| 7 | Operator confirmation | Add routing state "recommended - awaiting operator confirmation" and an audited confirmation step. Permission name to be chosen by WDS. | Additive; narrows execution | ARCH §3, §4; AR L9–L11 | CR-08 |
| 8 | Evidence sources | Limit external evidence to approved official vendor documentation and approved internal categories. Remove "reliable secondary material" as a live-evidence preference; such material is recorded as unverified only. Default allowlist empty (deny-all). | Narrowing | GOV L71; AR L708–L713, L769 | CR-03, CR-15 |
| 9 | Live model calls | Add a configuration gate: no live call unless provider, exact model ID, credential reference and budget are all approved. Until then, mock or deterministic adapters only. | Additive; narrows execution | GOV L282; ARCH L256, L328; AR L722–L766 | CR-12 |
| 10 | Model numbers | Mark timeouts and attempt counts as provisional, or move them to configuration with no default. | Clarifying | AR L722–L745 | CR-25 |
| 11 | Synthetic labelling | Add a mandatory provenance value on specialist outputs and claims (`synthetic`, `mock`, `live_verified`), and forbid `verified` status for synthetic output. | Additive to output contract; new required field for new outputs | RS §4.3.1 (specialist output contract); none in drafts | CR-14 |
| 12 | Evaluation case ROUTE-3DCS-001 | Replace the Shopify co-activation label with the independent Shift4Shop label. Keep the ID and record the change. | Test expectation changes | EP L128; EP L237 | CR-09 |
| 13 | Evaluation data | Keep the synthetic seed for development. Add a separate, approved set of sanitized WDS scenarios for acceptance. | Additive | EP L17, L26, L168, L250; ARCH L271 | CR-13 |
| 14 | Materiality predicates | Add a versioned predicate set, approved separately. Until then, unknown claims in the listed categories are blocking. | Additive | RS §9.1; RP §12 | CR-16 |
| 15 | Registry decision lists | Split "approved policy direction" from "approved detail" under `approved_decisions` / `pending_decisions`. | Restructure of keys | AR L746–L766 | CR-24 |
| 16 | Reporting | Add a sprint and milestone reporting section and a reference to the sign-off record. | Additive | None (CR-28) | CR-28 |
| 17 | Editorial | Correct stale titles in DR and RL; add a track map (Phase 1 security track separate from specialist track). | Editorial | DR L1; RL L1 | CR-33, CR-34 |
| 18 | Approval record | Add the approval record described in `approval-record-proposed.md`, blank until completed. | Additive | None | CR-17 |

## 3. Backward compatibility

**Compatible (no change to existing consumers):**
- All seven category IDs and their `SpecialistId` values (`shopify`, `shift4shop`, `wordpress_woocommerce`, `bigcommerce`, `magento_adobe_commerce`, `standalone_applications`, `middleware_applications`).
- All legacy capability, route and service IDs listed in section 4. They stay in place and resolve through the alias table.
- The seven capability entries and their IDs as literal lines of the form `  - id: <ID>` in AGENT_REGISTRY.yaml (see section 5, constraint C-1).
- Enum values in RS §2 and SC `schema.enums`.
- Machine routing stays disabled, so no existing run changes behaviour.
- Gate and permission matrices (GOV §11, RP §7) are unchanged by this list. Only the additions in rows 7 and 9 narrow what can run.

**Not backward compatible (must be planned):**
- Row 8 narrows evidence sources. Any existing draft output that relied on secondary material is re-classified as unverified.
- Row 11 adds a required provenance field to the specialist output contract. Existing outputs (only Sprint 1 mock outputs) must be regenerated or marked `mock`.
- Row 12 changes the expected result of an evaluation case. Earlier results for it, if any, are not comparable.
- Row 15 changes the key structure of the registry lists. No code reads these keys (searched `src/`, `tests/`, `.github/`; the only reference is the path in `tests/unit/test_specialist_contract.py` L14–L15).

## 4. Legacy identifiers preserved

Each must remain resolvable after reconciliation. None is removed or renamed by this package. Canonical IDs are shown as blank because none is approved.

| Legacy identifier | Kind | Where it appears | Preserve as | Canonical ID | Notes |
|---|---|---|---|---|---|
| `CAP-3D-CART-SHIFT-SHOPIFY` | Capability (registry) | AR L245 entry; AR L39, L105, L274, L489, L630; `src/webdesk/specialists/catalog.py` (`SpecialistId.SHIFT4SHOP` mapping); `tests/unit/test_specialist_contract.py` L62–L63 | Compatibility alias for Shift4Shop (D06) | blank (pending) | Name carries "SHOPIFY", which is misleading (CR-06). Name only. |
| `ROUTE-3D-CART-SHIFT-001` | Routing rule | AR L34–L41 | Documentation-only alias; not executable | blank | Keep non-executable (AR L36–L37, L102) |
| `SVC-3D-CART-SHIFT-SHOPIFY-001` | Service pattern | SC L66–L118; SC L940 (`specialist_semantics_pending`) | Compatibility alias | blank | `specialist_category: three_d_cart_shift_shopify_specialist` (SC L69) |
| `CAP-ECOMMERCE` | Capability (registry) | AR L211–L244 (name "Shopify Specialist"); AR L32, L488, L629; `catalog.py` (`SpecialistId.SHOPIFY` mapping) | Compatibility alias for Shopify | blank | Name is generic ("ecommerce") but the capability is Shopify (CR-10) |
| `CAP-INTEGRATION-SOFTWARE` | Capability (compatibility) | AR L501–L534; `ROUTE-INTEGRATION-001` AR L70–L74 | Compatibility route | blank | `status: migration_compatibility`; prefer `CAP-MIDDLEWARE-APPLICATIONS` for new routing |
| `ROUTE-3DCS-001` | Evaluation case ID | EP L128 | Test case ID kept; label corrected (row 12) | n/a | Not a registry ID |
| `three_d_cart_shift_shopify_specialist` | Category string | AR L248; SC L69 | Compatibility string | blank | Keep as alias for the category (GOV §5.3 name: "3dcart / Shift4Shop Specialist") |
| `shopify_specialist` | Category string | AR L215 | Keep | n/a | Not legacy in the sense of D15 but kept unchanged |

Canonical identifiers, if any, are approved and recorded in the alias table. Until then the canonical column stays blank and the display name carries the change.

## 5. Sprint 1 code alignment

File: `src/webdesk/specialists/catalog.py` and related modules. Constraints C-1 to C-6 are derived from the current code and tests.

| Constraint | Source | Requirement |
|---|---|---|
| C-1 | `tests/unit/test_specialist_contract.py` L62–L63 | Every ID in `REGISTRY_CAPABILITY_IDS` must appear in AGENT_REGISTRY.yaml as the exact line `  - id: <ID>` followed by a newline. The reconciled registry must keep this format for the seven entries. |
| C-2 | `tests/unit/test_specialist_contract.py` L47–L57 | `SpecialistId` values must equal exactly the seven values listed. No value may be added or renamed in this package. |
| C-3 | `catalog.py` lines 1–7 (docstring) | Update the docstring to cite D06 and the display name "Shift4Shop (formerly 3dcart)". Keep the legacy ID mapping as it is. (CR-29) |
| C-4 | `catalog.py` mapping | `SpecialistId.SHIFT4SHOP` maps to `CAP-3D-CART-SHIFT-SHOPIFY`. Do not map `SHIFT4SHOP` to `CAP-ECOMMERCE`, and do not map `SHOPIFY` to the Shift4Shop ID. Both are asserted by the category contract (GOV §5.3, D01). |
| C-5 | `src/webdesk/specialists/authority.py` L38 and QA-07 | The same base allowlist for every category is correct for Sprint 1 only. The deferral of run-time enforcement to M3 S6 must be recorded as an exception (CR-20). The code must not claim run-time enforcement. |
| C-6 | `src/webdesk/specialists/mock.py` (module docstring; default output) | Keep the honest default (`status: incomplete`, unknowns). Add the provenance label `mock` when CR-14 is adopted. |

Also aligned in Sprint 2 (not Sprint 1 code, but the same contract):
- `src/webdesk/evidence/allowlist.py` L40 `PROPOSED_SHOPIFY_ALLOWLIST`: load from approved configuration with an empty default (deny-all). The proposed list must not be used for live retrieval until approved (CR-03). `src/webdesk/evidence/http_vendor.py` already checks the allowlist before any network call and does not follow redirects (L85–L86); keep that behaviour.

Suggested order for code changes, after the blocking items are decided (no change is authorized by this document):
1. Docstring update (C-3).
2. Alias-resolution test: each row of section 4 resolves to its registry or catalog entry (`EVAL-LEGACY-ALIAS-001`).
3. Provenance label on mock output (C-6), after CR-14 is approved.
4. Allowlist configuration with empty default (Sprint 2, CR-03).

## 6. Migration steps (order, not dates)

1. Decide CR-01 to CR-03 (approval basis, development authority, allowlist).
2. Decide CR-06 and CR-11 (display name and alias table). Approve the alias table with blank canonical IDs.
3. Decide CR-07, CR-08, CR-12 (routing predicates, operator gate, live-call gate).
4. Produce the reconciled version and its alias table as a PROPOSED draft; route to the independent review (`independent-review-checklist.md`).
5. After approval, update code docstrings and add the alias-resolution test.
6. Keep every legacy ID until a separately approved migration (D06). Removal needs its own decision.
