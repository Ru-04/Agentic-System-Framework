# Independent Specification Review Checklist

- **Status:** PROPOSED - NOT APPROVED. All items are unchecked. Only the independent reviewer may check an item, and only after reading the cited source.
- **Reviewer:** [BLANK - to be named by WDS]. Must not be the author of this package or of the reconciled version.
- **Review date:** [BLANK]
- **Inputs:** the seven v0.3.10 drafts (unmodified), the reconciled version (when it exists), this package, the management decision record and amendment, and the Sprint 1 reports.
- **Result scale:** RESOLVED / PARTIAL / OPEN, per item, with file and location (as REMEDIATION_LOG asks).

## A. Scope and status

- [ ] A1. The reviewer has read `document-status.md` and confirmed each header quote against the file (GOV L3, ARCH L3, RS L3, RP L3, EP L3, SC L4, AR L4).
- [ ] A2. No draft is treated as approved in the reconciled version unless an approval record quotes an approval exactly. (CR-01)
- [ ] A3. G1 is read as preserved unchanged and as excluding specialist work (`## Excluded from Gate 1`). (D03; CR-01, CR-02)
- [ ] A4. The 22 Oct amendment is cited as the development authority for specialist work and is not treated as a specification approval (amendment §4). (D01; CR-02)
- [ ] A5. No claim that a historical v2.0 approved package exists appears in any output. (D02; CR-04)
- [ ] A6. The drafts were not edited. (Brief; compare SHA-256 values in `document-status.md`.)

## B. Management decisions D01–D11

- [ ] B1. D01 development scope and prohibitions are stated without widening them. (`traceability-matrix.md` §1)
- [ ] B2. D02 reconciled version is marked new, proposed and not approved. (CR-04)
- [ ] B3. D06 canonical display name "Shift4Shop (formerly 3dcart)" is applied; IDs unchanged; alias status recorded. (CR-06, CR-11)
- [ ] B4. D07 operator confirmation gate exists in the routing contract and is audited. (CR-08)
- [ ] B5. D08 evidence sources are limited to approved internal categories and approved official vendor documentation; the allowlist is empty until approved. (CR-03, CR-15)
- [ ] B6. D09 live model calls are blocked until provider, exact model ID, credentials and budget are approved. (CR-12)
- [ ] B7. D09 synthetic and mock output cannot be presented as verified. (CR-14)
- [ ] B8. D10 scope limits (local environments and test PostgreSQL) are kept; production items remain separate. (CR-32)
- [ ] B9. D11 acceptance uses approved sanitized WDS scenarios, not synthetic fixtures alone. (CR-13)
- [ ] B10. D04 independent human QA signatory is named by a human, and no signature is generated. (CR-19)
- [ ] B11. D05 push and CI are recorded with run identifiers and head SHA; no merge into a protected branch. (CR-18)
- [ ] B12. Draft `D-xx` and management `Dxx` are never confused in the text. (CR-23)

## C. Frozen plan (brief)

- [ ] C1. The frozen plan document is located, hashed and cited. If it cannot be located, the item is recorded UNRESOLVED. (CR-27)
- [ ] C2. Nine sprints (S1–S9) and four milestones (M1–M4) are mapped in `traceability-matrix.md` §2 without change to scope, order or acceptance criteria.
- [ ] C3. "Six remaining specialist foundations" (S3) is read as the six categories other than Shopify, including Shift4Shop. The reviewer confirms or corrects this reading. (`traceability-matrix.md` §2 note)
- [ ] C4. Sprint and milestone reporting requirements (D11) are added to the reconciled version. (CR-28)

## D. Preserved governance and technical rules

- [ ] D1. Evidence traceability (GOV §4; RS §1) survives unchanged.
- [ ] D2. Reviewer-controlled requirement acceptance (GOV L271–L272; RS §9.4) survives; eligibility predicates are either approved or stated as OPEN. (CR-30)
- [ ] D3. Security-critical materiality (GOV L270; RS §9.1; RP §12) survives; `unassessed` is treated as material; trigger predicates are approved or OPEN. (CR-16)
- [ ] D4. Workspace and project isolation (GOV §8; RS §9.3; ARCH §10; EP §4.8) survives.
- [ ] D5. Human authorization (GOV §9 L209–L214; RP §9) survives: LLM output is never final approval; approver differs from preparer.
- [ ] D6. Phase 1 security controls (GOV §11; RS §3.1; GOV L299–L301; EP Gate 1 suite) are unchanged by specialist work.
- [ ] D7. Specialist limits (GOV §5.3 L86; RP §5) survive: no permission grants, no routing-policy changes, no self-resolution of blockers, no approval of artifacts.
- [ ] D8. Least-privilege allowlists per capability (GOV §10; AR L14) are enforced or the exception is recorded. (CR-20)

## E. Identifiers and compatibility

- [ ] E1. Every legacy ID in `compatibility-and-migration.md` §4 resolves through the alias table. (EP L243)
- [ ] E2. No legacy ID is removed or renamed. (D06; GOV L285)
- [ ] E3. Canonical IDs are blank unless approved; no new canonical ID is invented. (CR-11)
- [ ] E4. `SpecialistId` values and REGISTRY_CAPABILITY_IDS match the seven categories. (`tests/unit/test_specialist_contract.py` L47–L63)
- [ ] E5. AGENT_REGISTRY entries keep the `  - id: <ID>` line form for the seven capability IDs. (test L62–L63)
- [ ] E6. The CAP-3D-CART-SHIFT-SHOPIFY name is corrected to display semantics without changing the ID. (CR-06)
- [ ] E7. ROUTE-3D-CART-SHIFT-001 remains non-executable until its predicates are approved. (AR L36–L37, L100–L102; CR-07)

## F. Routing and categories

- [ ] F1. Routing predicates (C-05) are either specified in a separate approved contract or recorded as OPEN with `machine_routing_enabled: false`. (CR-07)
- [ ] F2. The Shopify, Shift4Shop, WordPress/WooCommerce (combined), BigCommerce, Magento, Standalone and Middleware categories each have a single entry. (GOV §5.3)
- [ ] F3. Middleware technology is not fixed to Node.js. (AR L69; EP ROUTE-MW-PYTHON-001)
- [ ] F4. Standalone applications are analysable without an eCommerce specialist. (EP ROUTE-STANDALONE-001)
- [ ] F5. ROUTE-3DCS-001 is relabelled so that Shopify is not co-activated by default; EVAL-3DCART-INDEPENDENT-001 agrees. (CR-09)
- [ ] F6. Migration is a separate service pattern (SVC-PLATFORM-MIGRATION-001; draft D-11, DR L17). (SC L860)

## G. Evidence and evaluation

- [ ] G1. No vendor domain appears in any approved configuration unless WDS has approved it. (CR-03)
- [ ] G2. Retrieval order (RAG first, then approved live read) and the deny-all default are stated. (GOV §18 D-02; RS §9.3)
- [ ] G3. Claims without approved evidence are unverified and cannot support committed scope. (GOV §7; RP §7 Gate C)
- [ ] G4. EP metrics are labelled as proposed targets; no metric is presented as measured. (EP §3 L58–L60)
- [ ] G5. Numeric thresholds are owned by the WDS Technical Lead and signed off by a designated Approver. (D14; EP §9; CR-31)
- [ ] G6. Synthetic development data and sanitized acceptance data are separate. (CR-13)

## H. Model and provider

- [ ] H1. Provider adapter is provider-independent (ARCH §12).
- [ ] H2. No provider, model ID, budget or credential is hard-coded or presumed. (GOV L282; AR L722–L745; CR-12)
- [ ] H3. Timeouts, attempts and temperature in AR L722–L745 are marked provisional or moved to configuration. (CR-25)

## I. Estimation and reporting

- [ ] I1. Estimates are `needs_inputs` where no approved basis exists. (GOV §12; RS §9.2; CR-26)
- [ ] I2. Estimate units are hours and disciplines match RS §9.2.
- [ ] I3. No delivery date is inferred from effort. (GOV §12)

## J. Approval and audit

- [ ] J1. Approver, role, date and decision are blank in the template and are not filled in by the reviewer or author. (`approval-record-proposed.md`; CR-17)
- [ ] J2. Each open item in the register is listed with its owner in the approval record. (CR-01 to CR-35)
- [ ] J3. UNRESOLVED references are not reconstructed. (CR-05, CR-21, CR-27)
- [ ] J4. Document hashes are recorded at approval time, not before. (`approval-record-proposed.md`)

## K. Sprint 1 evidence

- [ ] K1. The Sprint 1 blocker is re-scoped from the v2.0 package to the reconciled package. (CR-04)
- [ ] K2. Commit-status statements in the Sprint 1 reports match git history. (CR-22)
- [ ] K3. The README quoted in the QA closure report is located or the quote is corrected. (CR-05)
- [ ] K4. QA-07 is recorded as an accepted, time-bound exception. (CR-20)
- [ ] K5. The human QA sign-off record exists and is signed by a human. (CR-19)
- [ ] K6. The CI run on GitHub is recorded with run identifier and head SHA. (CR-18)
- [ ] K7. `catalog.py` docstring cites D06. (CR-29)
- [ ] K8. Sprint 2 evidence code does not perform live retrieval with the proposed allowlist. (CR-03, CR-35)

## L. Conclusion (reviewer to complete)

- [ ] L1. Reviewer's overall result: [BLANK]
- [ ] L2. Items marked OPEN at review: [BLANK]
- [ ] L3. Items marked UNRESOLVED at review: [BLANK]
