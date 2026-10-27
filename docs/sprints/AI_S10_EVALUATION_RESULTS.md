# AI-S10 Evaluation Results

Commit under evaluation: `base 3e79d01 plus AI-S10 working tree`

Outcomes are reported per classification. No cross-class percentage is computed.

## Summary

- Total scenarios: 91
- Outcomes: {'blocked': 11, 'delegated': 3, 'open_limitation': 3, 'pass': 74}
- Synthetic (A) executed: 74; passed 74; failed 0

## Results

| ID | Classification | Outcome | Severity | Expected | Actual |
|---|---|---|---|---|---|
| EST-01 | A-isolated-synthetic | pass | critical | sums equal the oracle exactly | project 13.0/20.0/32.0 |
| EST-02 | A-isolated-synthetic | pass | critical | refused | 2 of 2 unordered triples refused |
| EST-03 | A-isolated-synthetic | pass | critical | counted once | likely 12.0; lines 1 |
| EST-04 | A-isolated-synthetic | pass | critical | excluded line listed; complete False | excluded ('LINE-001',) |
| EST-05 | A-isolated-synthetic | pass | major | fingerprint and requirement revisions recorded | fingerprint, revisions and requirement IDs carried |
| EST-06 | A-isolated-synthetic | pass | critical | needs_inputs, no numbers | needs_inputs |
| EST-07 | A-isolated-synthetic | pass | major | needs_inputs (stale) | needs_inputs |
| EST-08 | A-isolated-synthetic | pass | critical | no such field exists | forbidden field names: [] |
| EST-09 | A-isolated-synthetic | pass | critical | draft_status constant; no approved status | statuses ['indicative'] |
| EST-10 | A-isolated-synthetic | pass | major | indicative and complete | status indicative; complete True |
| EVID-01 | A-isolated-synthetic | pass | critical | NOT_EVIDENCE_VERIFIED with MAJOR finding | status not_evidence_verified |
| EVID-02 | A-isolated-synthetic | pass | major | EVIDENCE_BACKED | evidence_backed |
| EVID-03 | A-isolated-synthetic | pass | critical | not backed | not_evidence_verified |
| EVID-04 | A-isolated-synthetic | pass | critical | not backed; MISSING_REVIEW_PARAMETER | not_evidence_verified |
| EVID-05 | A-isolated-synthetic | pass | critical | not backed | not_evidence_verified |
| EVID-06 | A-isolated-synthetic | pass | critical | SERVED_RECORD_MISMATCH; not backed | not_evidence_verified |
| EVID-07 | A-isolated-synthetic | pass | major | STALE_EVIDENCE_CITED; not backed | not_evidence_verified |
| EVID-08 | A-isolated-synthetic | pass | major | SUPERSEDED_EVIDENCE_CITED; not backed | not_evidence_verified |
| EVID-09 | A-isolated-synthetic | pass | critical | CONFLICTED | conflicted |
| EVID-10 | A-isolated-synthetic | pass | critical | not backed | not_evidence_verified |
| EVID-11 | A-isolated-synthetic | pass | critical | CITATION_OUTSIDE_SERVED blocker | blocker reported |
| EVID-12 | A-isolated-synthetic | pass | major | COVERAGE_GAP | classes ['coverage_gap', 'missing_clarification', 'missing_review_parameter', 'not_evidence_verified'] |
| EVID-13 | A-isolated-synthetic | pass | major | MISSING_CLARIFICATION | missing clarification reported |
| EVID-14 | A-isolated-synthetic | pass | critical | output dump unchanged | specialist output unchanged by review |
| EVID-15 | A-isolated-synthetic | pass | critical | blocker present in estimate and SOW | requirement readiness blocked |
| EVID-16 | A-isolated-synthetic | open_limitation | critical | a relevant-sounding but off-topic summary backs; screen is lexical | off-topic summary status evidence_backed |
| EXT-01 | C-real-provider | blocked | major | provider results meet approved thresholds | LLM provider and model decision (D-12) and live-call approval |
| EXT-02 | D-vendor-documentation-or-sandbox | blocked | major | sandbox behaviour matches vendor docs | source-access approval and sandbox credentials; none granted |
| EXT-03 | E-full-platform-human-workflow | blocked | major | human reviewers complete the workflow | Foundation UI and human participants; not available |
| EXT-04 | F-production-security-readiness | blocked | major | penetration and configuration review passes | production environment, configuration decisions and external review |
| EXT-05 | B-foundation-integration | blocked | major | reads return authoritative records | Foundation API not available to the engine |
| EXT-06 | B-foundation-integration | blocked | major | confirmations issued by a Foundation operator session | Foundation-issued operator authorisation not implemented |
| EXT-07 | B-foundation-integration | blocked | major | three tests pass in the Foundation environment | Foundation test environment and approval; tests are skipped, not passed |
| EXT-08 | A-isolated-synthetic | open_limitation | critical | each decision is recorded as open in the governance register | WDS decisions |
| PIPE-01 | A-isolated-synthetic | pass | critical | each stage yields its output; governance fingerprint carried to estimate and SOW | 7 outcomes; fingerprint carried; estimate likely 42.0; SOW pending |
| PIPE-02 | A-isolated-synthetic | pass | critical | blocked readiness in estimate and in SOW risks | line readiness blocked=True; SOW blocker visible=True |
| PIPE-03 | A-isolated-synthetic | pass | critical | reviewer authorises nothing; SOW approval stays pending | status evidence_backed; authorises_anything False |
| PIPE-04 | A-isolated-synthetic | delegated | info | covered by the named accepted test file, which the committed gate runs | not re-executed by AI-S10; see tests/test_requirement_analysis.py |
| PIPE-05 | A-isolated-synthetic | delegated | info | covered by the named accepted test file, which the committed gate runs | not re-executed by AI-S10; see tests/test_ai_s03_retrieval.py |
| REC-01 | A-isolated-synthetic | pass | major | every category makes exactly max_attempts (2) calls and ends transient | attempts [2]; specialist calls 14 |
| REC-02 | A-isolated-synthetic | pass | major | every category makes one call; no retry follows a permanent status | attempts [1]; specialist calls 7 |
| REC-03 | A-isolated-synthetic | pass | critical | the withheld category uses no evidence and reports evidence_unavailable; no other collection is substituted; the other categories run | withheld ['shopify_specialist'] evidence_unavailable, no evidence; others ran=True |
| SEC-01 | A-isolated-synthetic | pass | critical | SOW refuses a requirement from another project | a requirement belongs to another project |
| SEC-02 | A-isolated-synthetic | pass | critical | claim cannot back; unauthorised collection blocker | status unsupported |
| SEC-03 | A-isolated-synthetic | pass | critical | line is needs_inputs with no numbers | status needs_inputs; issues 1 |
| SEC-04 | A-isolated-synthetic | pass | major | stale revision is an integrity issue | stale revision reported |
| SEC-05 | A-isolated-synthetic | pass | critical | ConfirmationRefused | refused: mock confirmation is not permitted on the production path |
| SEC-06 | A-isolated-synthetic | pass | critical | second confirmation refused | second use refused: this run is no longer awaiting confirmation |
| SEC-07 | A-isolated-synthetic | pass | critical | ConfirmationRefused | refused: confirmation has expired |
| SEC-08 | A-isolated-synthetic | pass | critical | ConfirmationRefused | refused: confirmation is bound to another run |
| SEC-09 | A-isolated-synthetic | open_limitation | critical | run_specialist takes no confirmation or actor; limitation present | parameters ['agent', 'clock', 'context', 'execution_id', 'registry', 'task']; gated=False |
| SEC-10 | A-isolated-synthetic | pass | critical | flagged; approval state unchanged | flagged=True; approval pending_human_approval |
| SEC-11 | A-isolated-synthetic | pass | critical | review status and authorisation unchanged | hostile status evidence_backed; benign evidence_backed |
| SEC-12 | A-isolated-synthetic | pass | critical | validation refuses the output | validation refused the contradictory output |
| SEC-13 | A-isolated-synthetic | pass | critical | refused | input refused=True; status refused=True |
| SEC-14 | A-isolated-synthetic | pass | critical | reviewer flags unsupported verified claim | reviewer flagged unsupported verified claim=True |
| SEC-15 | A-isolated-synthetic | pass | critical | no numbers | unauthorised numbers=None; authorised likely=12.0 |
| SEC-16 | A-isolated-synthetic | pass | critical | sentinel absent from messages | 2 messages inspected; sentinel absent=True |
| SEC-17 | A-isolated-synthetic | pass | major | inputs unchanged after execution | reviewer and estimator inputs unchanged |
| SEC-18 | B-foundation-integration | blocked | major | every run and refusal persisted and tamper-evident | Foundation audit and run-state persistence; not implemented |
| SOW-01 | A-isolated-synthetic | pass | major | twelve section identifiers including overview | 12 sections plus overview |
| SOW-02 | A-isolated-synthetic | pass | critical | unrepresented listed; traceability rows | unrepresented ('REQ-SYN-0002',) |
| SOW-03 | A-isolated-synthetic | pass | major | exclusion labelled as proposal requiring confirmation | 1 out-of-scope item(s) |
| SOW-04 | A-isolated-synthetic | pass | critical | explicit not_supported labels | assumptions and milestones explicitly unsupported |
| SOW-05 | A-isolated-synthetic | pass | critical | blocker in risks and deliverable readiness | DLV-2 readiness {'REQ-SYN-0002': 'blocked'} |
| SOW-06 | A-isolated-synthetic | pass | major | provisional readiness shown | {'REQ-SYN-0002': 'provisional'} |
| SOW-07 | A-isolated-synthetic | pass | critical | no number for the line or its deliverable | needs_inputs line LINE-002 carries no numbers |
| SOW-08 | A-isolated-synthetic | pass | critical | banner PARTIAL; complete False | PARTIAL: 1 unresolved line(s). This is not the complete proj |
| SOW-09 | A-isolated-synthetic | pass | critical | no date pattern in output | date-like match: none |
| SOW-10 | A-isolated-synthetic | pass | critical | no price, rate, discount, signature fields | pricing-like property names: [] |
| SOW-11 | A-isolated-synthetic | pass | critical | pending_human_approval; approver None | approval pending_human_approval |
| SOW-12 | A-isolated-synthetic | pass | critical | flagged; approval unchanged | flagged; approval unchanged |
| SOW-13 | E-full-platform-human-workflow | blocked | major | output matches the approved house template and renders to DOCX/PDF | D-10 approved template, section contract and export tests |
| SPEC-01 | A-isolated-synthetic | pass | critical | seven identities; verify_identities passes | 7 identities; verify_identities passed |
| SPEC-02 | A-isolated-synthetic | pass | critical | category three_d_cart_shift_shopify_specialist keeps capability CAP-3D-CART-SHIFT-SHOPIFY | legacy capability CAP-3D-CART-SHIFT-SHOPIFY |
| SPEC-08 | A-isolated-synthetic | pass | critical | execute refuses when no confirmation is recorded | refused: no operator confirmation is in force for this run |
| SPEC-09 | A-isolated-synthetic | pass | major | outcomes cover every confirmed category exactly once | 7 outcomes, one per confirmed category |
| SPEC-10 | A-isolated-synthetic | pass | major | no category is routed for an unsupported platform | categories () |
| SPEC-11 | A-isolated-synthetic | pass | major | both categories are routed and the requirement is listed for each | routed ('bigcommerce_specialist', 'shopify_specialist') |
| SPEC-12 | A-isolated-synthetic | pass | critical | every seeded record is synthetic mock evidence | seeded evidence kinds ['synthetic_mock'] |
| SPEC-13 | A-isolated-synthetic | pass | critical | validation refuses a VERIFIED claim from a specialist | validation refused a specialist VERIFIED claim |
| SPEC-14 | A-isolated-synthetic | delegated | info | covered by the named accepted test file, which the committed gate runs | not re-executed by AI-S10; see tests/test_ai_s06_orchestration.py |
| SPEC-15 | D-vendor-documentation-or-sandbox | blocked | major | each specialist's claims checked against approved official vendor documentation | approved source-access matrix and per-vendor allowlist (D-02); none granted |
| SPEC-16 | E-full-platform-human-workflow | blocked | major | end-to-end run against each approved platform sandbox | platform approval; no sandbox or test store authorised |
| SPEC-R01 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('shopify_specialist',) |
| SPEC-R02 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('wordpress_woocommerce_specialist',) |
| SPEC-R03 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('bigcommerce_specialist',) |
| SPEC-R04 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('three_d_cart_shift_shopify_specialist',) |
| SPEC-R05 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('magento_adobe_commerce_specialist',) |
| SPEC-R06 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('standalone_applications_specialist',) |
| SPEC-R07 | A-isolated-synthetic | pass | critical | the proposal routes exactly the matching category | routed ('middleware_applications_specialist',) |
