# AI-S10 Evaluation Results

Candidate: `base 211d308; evaluated source sha256 c1de7a7fcd09b10176b7d1f040f0a2d5c782f7844a7860499880261022c0fdc5`

Outcomes are reported per classification. No cross-class percentage is computed.

## Summary

- Total scenarios: 136
- Outcomes: {'blocked': 12, 'delegated': 3, 'open_limitation': 5, 'pass': 116}
- Synthetic (A) executed: 116; passed 116; failed 0

## Results

| ID | Classification | Outcome | Severity | Enforced by | Expected | Actual |
|---|---|---|---|---|---|---|
| EST-01 | A-isolated-synthetic | pass | critical | - | sums equal the oracle exactly | project 13.0/20.0/32.0 |
| EST-02 | A-isolated-synthetic | pass | critical | ThreePoint | refused | unordered triples refused at ['ThreePoint', 'ThreePoint'] |
| EST-03 | A-isolated-synthetic | pass | critical | - | counted once | likely 12.0; lines 1 |
| EST-04 | A-isolated-synthetic | pass | critical | - | excluded line listed; complete False | excluded ('LINE-001',) |
| EST-05 | A-isolated-synthetic | pass | major | - | fingerprint and requirement revisions recorded | fingerprint, revisions and requirement IDs carried |
| EST-06 | A-isolated-synthetic | pass | critical | - | needs_inputs, no numbers | needs_inputs |
| EST-07 | A-isolated-synthetic | pass | major | - | needs_inputs (stale) | needs_inputs |
| EST-08 | A-isolated-synthetic | pass | critical | - | no such field exists | forbidden field names: [] |
| EST-09 | A-isolated-synthetic | pass | critical | - | draft_status constant; no approved status | statuses ['indicative'] |
| EST-10 | A-isolated-synthetic | pass | major | - | indicative and complete | status indicative; complete True |
| EVID-01 | A-isolated-synthetic | pass | critical | - | NOT_EVIDENCE_VERIFIED with MAJOR finding | status not_evidence_verified |
| EVID-02 | A-isolated-synthetic | pass | major | - | EVIDENCE_BACKED | evidence_backed |
| EVID-03 | A-isolated-synthetic | pass | critical | - | not backed | not_evidence_verified |
| EVID-04 | A-isolated-synthetic | pass | critical | - | not backed; MISSING_REVIEW_PARAMETER | not_evidence_verified |
| EVID-05 | A-isolated-synthetic | pass | critical | - | not backed | not_evidence_verified |
| EVID-06 | A-isolated-synthetic | pass | critical | - | SERVED_RECORD_MISMATCH; not backed | not_evidence_verified |
| EVID-07 | A-isolated-synthetic | pass | major | - | STALE_EVIDENCE_CITED; not backed | not_evidence_verified |
| EVID-08 | A-isolated-synthetic | pass | major | - | SUPERSEDED_EVIDENCE_CITED; not backed | not_evidence_verified |
| EVID-09 | A-isolated-synthetic | pass | critical | - | CONFLICTED | conflicted |
| EVID-10 | A-isolated-synthetic | pass | critical | - | not backed | not_evidence_verified |
| EVID-11 | A-isolated-synthetic | pass | critical | - | CITATION_OUTSIDE_SERVED blocker | blocker reported |
| EVID-12 | A-isolated-synthetic | pass | major | - | COVERAGE_GAP | classes ['coverage_gap', 'missing_clarification', 'missing_review_parameter', 'not_evidence_verified'] |
| EVID-13 | A-isolated-synthetic | pass | major | - | MISSING_CLARIFICATION | missing clarification reported |
| EVID-14 | A-isolated-synthetic | pass | critical | - | output dump unchanged | specialist output unchanged by review |
| EVID-15 | A-isolated-synthetic | pass | critical | - | blocker present in estimate and SOW | estimate readiness blocked=True; SOW deliverable and risk blocked=True |
| EVID-16 | A-isolated-synthetic | open_limitation | critical | - | a relevant-sounding but off-topic summary backs; screen is lexical | off-topic summary status evidence_backed |
| EXT-01 | C-real-provider | blocked | major | - | provider results meet approved thresholds | LLM provider and model decision (D-12) and live-call approval |
| EXT-02 | D-vendor-documentation-or-sandbox | blocked | major | - | sandbox behaviour matches vendor docs | source-access approval and sandbox credentials; none granted |
| EXT-03 | E-full-platform-human-workflow | blocked | major | - | human reviewers complete the workflow | Foundation UI and human participants; not available |
| EXT-04 | F-production-security-readiness | blocked | major | - | penetration and configuration review passes | production environment, configuration decisions and external review |
| EXT-05 | B-foundation-integration | blocked | major | - | reads return authoritative records | Foundation API not available to the engine |
| EXT-06 | B-foundation-integration | blocked | major | - | confirmations issued by a Foundation operator session | Foundation-issued operator authorisation not implemented |
| EXT-07 | B-foundation-integration | blocked | major | - | three tests pass in the Foundation environment | Foundation test environment and approval; tests are skipped, not passed |
| EXT-08 | A-isolated-synthetic | open_limitation | critical | - | each decision is recorded as open in the governance register | WDS decisions |
| FP-01 | A-isolated-synthetic | open_limitation | critical | - | a null-fingerprint estimate supplies values with no fingerprint finding; gap present | values without a fingerprint=True; no fingerprint finding=True |
| LLM-01 | A-isolated-synthetic | pass | major | - | status accepted with a successful call | status accepted; call success |
| LLM-02 | A-isolated-synthetic | pass | critical | - | status failed; no result; call INVALID_REPLY_EXHAUSTED; no segment analysed | status failed; call invalid_reply_exhausted; segments not analysed 3 of 3 |
| LLM-03 | A-isolated-synthetic | pass | critical | - | no segment text in the system prompt; the system prompt is the registered prompt | segments leaked into the system prompt: [] |
| PIPE-01 | A-isolated-synthetic | pass | critical | - | each stage yields its output; governance fingerprint carried to estimate and SOW | 7 outcomes; fingerprint carried; estimate likely 42.0; SOW pending |
| PIPE-02 | A-isolated-synthetic | pass | critical | - | blocked readiness in estimate and in SOW risks | line readiness blocked=True; SOW blocker visible=True |
| PIPE-03 | A-isolated-synthetic | pass | critical | - | reviewer authorises nothing; SOW approval stays pending | status evidence_backed; authorises_anything False |
| PIPE-04 | A-isolated-synthetic | delegated | info | - | covered by the named accepted test file, which the committed gate runs | not re-executed by AI-S10; see tests/test_requirement_analysis.py |
| PIPE-05 | A-isolated-synthetic | delegated | info | - | covered by the named accepted test file, which the committed gate runs | not re-executed by AI-S10; see tests/test_ai_s03_retrieval.py |
| RAG-01 | A-isolated-synthetic | pass | critical | - | each project receives only its own chunk | project A returned ['CHK-A-1']; project B returned ['CHK-B-1'] |
| REC-01 | A-isolated-synthetic | pass | major | - | every category makes exactly max_attempts (2) calls and ends transient | attempts [2]; specialist calls 14 |
| REC-02 | A-isolated-synthetic | pass | major | - | for each permanent variant (validation, permission, unsupported) every category makes one call and no retry follows | failed_validation:[1]/7; permission_denied:[1]/7; unsupported_request:[1]/7 |
| REC-03 | A-isolated-synthetic | open_limitation | critical | - | the withheld category is refused before any specialist attempt; no evidence is used; no other collection is substituted | withheld ['shopify_specialist']: attempted=True no_evidence=True specialist=evidence_unavailable=True execution=succeeded=True; others ran=True |
| REC-04 | A-isolated-synthetic | pass | major | - | that category succeeds on its second attempt; every category ends succeeded; eight specialist calls in total (seven categories, one retried) | retried outcomes 1 end succeeded; all succeeded=True; calls 8 |
| REC-05 | A-isolated-synthetic | pass | major | - | every category makes one call and its outcome records 'specialist raised RuntimeError' as the failure | attempts [1]; calls 7; refusals ['specialist raised RuntimeError'] |
| REQ-01 | A-isolated-synthetic | pass | major | - | six client requirements; each original wording is an exact substring of its segment | client requirements 6; each wording exact in its segment=True |
| REQ-02 | A-isolated-synthetic | pass | major | - | questions for 'faster' and 'immediately' exist and all are open | vague-term questions present=True; all open=True |
| REQ-03 | A-isolated-synthetic | pass | major | analyze | refused at analyze | empty input refused True enforced by analyze |
| REQ-04 | A-isolated-synthetic | pass | critical | analyze | refused with 'outside project' at analyze | foreign segment refused: 'segment SEG-SYN-0001-A is outside project PRJ-SYN-0001' enforced by analyze |
| REQ-05 | A-isolated-synthetic | pass | major | - | proposal keys unique and identical across runs; every client requirement has a source | unique keys=True; deterministic=True; client requirements sourced=True |
| REQ-06 | A-isolated-synthetic | pass | critical | - | evidence UNVERIFIED; no requirement IDs; human review required; scope not committed | unverified=True; no REQ id=True; review=True |
| REQ-07 | A-isolated-synthetic | pass | critical | - | no requirement is accepted for scope; scope not committed; no requirement IDs | accepted=0; scope committed=False=True |
| REQ-08 | A-isolated-synthetic | pass | critical | - | inferred requirements exist and none is accepted for scope | inferred requirements 3; none accepted=True |
| RPL-01 | A-isolated-synthetic | pass | critical | - | verification accepts the first use | first valid use accepted: True |
| RPL-02 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with 'confirmation is bound to another run' at verify_confirmation; a later valid use is still accepted | reason 'confirmation is bound to another run' enforced by verify_confirmation; later valid use accepted=True |
| RPL-03 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with 'confirmation is bound to another project' at verify_confirmation; a later valid use is still accepted | reason 'confirmation is bound to another project' enforced by verify_confirmation; later valid use accepted=True |
| RPL-04 | A-isolated-synthetic | pass | critical | consume | refused with 'confirmation ID was already used' at consume | changed selection with reused ID: 'confirmation ID was already used' enforced by consume |
| RPL-05 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with 'confirmation has expired' at verify_confirmation; the valid confirmation is then accepted | reason 'confirmation has expired' enforced by verify_confirmation; refused attempt consumed nothing=True |
| RPL-06 | A-isolated-synthetic | pass | critical | consume | second consume refused with 'confirmation ID was already used' at consume | direct second consume: 'confirmation ID was already used' enforced by consume |
| RPL-07 | A-isolated-synthetic | pass | critical | consume | refused with 'confirmation nonce was already used (replay)' at consume | fresh ID, reused nonce: 'confirmation nonce was already used (replay)' enforced by consume |
| S01-01 | A-isolated-synthetic | pass | critical | build_operator_selection | SelectionError at build_operator_selection for each identity | invisible identities refused at ['build_operator_selection'] |
| S01-02 | A-isolated-synthetic | pass | critical | - | PERMISSION_DENIED with no output | status permission_denied; output withheld=True |
| S01-03 | A-isolated-synthetic | pass | critical | - | PERMISSION_DENIED with no output | status permission_denied |
| S01-04 | A-isolated-synthetic | pass | major | - | the caller's requirement is unchanged | caller's requirement unchanged=True |
| S01-05 | A-isolated-synthetic | pass | critical | SpecialistInvestigationResult | ValidationError naming the verified-candidate rule | model-constructed verified candidate refused by SpecialistInvestigationResult |
| S01-06 | A-isolated-synthetic | pass | critical | - | FAILED_VALIDATION with the reason 'was not served to this run' (the served-record check) | status failed_validation; reasons ['evidence EVD-FAKE-0002 was not served to this run'] |
| S01-07 | A-isolated-synthetic | pass | critical | verify_selection | StaleSelectionError raised at verify_selection | stale selection refused True enforced by verify_selection |
| SEC-01 | A-isolated-synthetic | pass | critical | generate | SOW refuses a requirement from another project | refused 'a requirement belongs to another project' enforced by generate |
| SEC-02 | A-isolated-synthetic | pass | critical | - | claim cannot back; unauthorised collection blocker | status unsupported |
| SEC-03 | A-isolated-synthetic | pass | critical | - | line is needs_inputs with no numbers | status needs_inputs; issues 1 |
| SEC-04 | A-isolated-synthetic | pass | major | - | stale revision is an integrity issue | stale revision reported |
| SEC-05 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with reason 'mock confirmation is not permitted on the production path' at verify_confirmation; a valid human-shaped confirmation is accepted | forged 'mock confirmation is not permitted on the production path' enforced by verify_confirmation; valid human-shaped confirmation accepted=True |
| SEC-06 | A-isolated-synthetic | pass | critical | consume | second use refused with 'confirmation ID was already used' at the ledger (consume) | first accepted=True; second 'confirmation ID was already used' enforced by consume |
| SEC-07 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with reason 'confirmation has expired' at verify_confirmation; an unexpired confirmation is accepted | expired 'confirmation has expired' enforced by verify_confirmation; unexpired accepted=True |
| SEC-08 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with reason 'confirmation is bound to another run' at verify_confirmation; the correct run is accepted | other run 'confirmation is bound to another run' enforced by verify_confirmation; correct run accepted=True |
| SEC-09 | A-isolated-synthetic | open_limitation | critical | - | a direct call to run_specialist with no confirmation, actor or proposal returns an execution status; the limitation is still present | direct call with no confirmation, actor or proposal returned succeeded |
| SEC-10 | A-isolated-synthetic | pass | critical | - | flagged; approval state unchanged | flagged=True; approval pending_human_approval |
| SEC-11 | A-isolated-synthetic | pass | critical | - | review status and authorisation unchanged | hostile status evidence_backed; benign evidence_backed |
| SEC-12 | A-isolated-synthetic | pass | critical | Claim | refused by the Claim contract at construction (the Claim model is the enforcement point) | VERIFIED claim without evidence refused by Claim |
| SEC-13 | A-isolated-synthetic | pass | critical | build_request | refused | approval input refused at build_request; 'approved' is not an estimate status=True |
| SEC-14 | A-isolated-synthetic | pass | critical | - | reviewer flags unsupported verified claim | reviewer flagged unsupported verified claim=True |
| SEC-15 | A-isolated-synthetic | pass | critical | - | no numbers | unauthorised numbers=None; authorised likely=12.0 |
| SEC-16 | A-isolated-synthetic | pass | critical | - | sentinel absent from messages | 2 messages inspected; sentinel absent=True |
| SEC-17 | A-isolated-synthetic | pass | major | - | inputs unchanged after execution | reviewer and estimator inputs unchanged |
| SEC-18 | B-foundation-integration | blocked | major | - | every run and refusal persisted and tamper-evident | Foundation audit and run-state persistence; not implemented |
| SEC-19 | A-isolated-synthetic | pass | critical | verify_confirmation | refused with 'confirmation selects categories that were not proposed' at verify_confirmation; a proposed selection is accepted | unproposed category 'confirmation selects categories that were not proposed' enforced by verify_confirmation; proposed selection accepted=True |
| SOW-01 | A-isolated-synthetic | pass | major | - | twelve section identifiers including overview | 12 sections plus overview |
| SOW-02 | A-isolated-synthetic | pass | critical | - | unrepresented listed; traceability rows | unrepresented ('REQ-SYN-0002',) |
| SOW-03 | A-isolated-synthetic | pass | major | - | exclusion labelled as proposal requiring confirmation | 1 out-of-scope item(s) |
| SOW-04 | A-isolated-synthetic | pass | critical | - | explicit not_supported labels | assumptions and milestones explicitly unsupported |
| SOW-05 | A-isolated-synthetic | pass | critical | - | blocker in risks and deliverable readiness | DLV-2 readiness {'REQ-SYN-0002': 'blocked'} |
| SOW-06 | A-isolated-synthetic | pass | major | - | provisional readiness shown | {'REQ-SYN-0002': 'provisional'} |
| SOW-07 | A-isolated-synthetic | pass | critical | - | no number for the line or its deliverable | needs_inputs line LINE-002 carries no numbers |
| SOW-08 | A-isolated-synthetic | pass | critical | - | banner PARTIAL; complete False | PARTIAL: 1 unresolved line(s). This is not the complete proj |
| SOW-09 | A-isolated-synthetic | pass | critical | - | no date pattern in output | dates 0; numeric durations 0 |
| SOW-10 | A-isolated-synthetic | pass | critical | - | no price, rate, discount, signature fields | pricing-like property names: [] |
| SOW-11 | A-isolated-synthetic | pass | critical | - | pending_human_approval; approver None | approval pending_human_approval |
| SOW-12 | A-isolated-synthetic | pass | critical | - | flagged; approval unchanged | flagged 5/5; unflagged []; approval unchanged=True |
| SOW-13 | E-full-platform-human-workflow | blocked | major | - | output matches the approved house template and renders to DOCX/PDF | D-10 approved template, section contract and export tests |
| SPEC-01 | A-isolated-synthetic | pass | critical | - | seven identities; verify_identities passes | 7 identities; verify_identities passed |
| SPEC-02 | A-isolated-synthetic | pass | critical | - | category three_d_cart_shift_shopify_specialist keeps capability CAP-3D-CART-SHIFT-SHOPIFY | legacy capability CAP-3D-CART-SHIFT-SHOPIFY |
| SPEC-08 | A-isolated-synthetic | pass | critical | execute | execute refused with 'no operator confirmation is in force for this run' at execute; no specialist runs; a confirmed run executes all seven | unconfirmed 'no operator confirmation is in force for this run' enforced by execute; specialist calls=0; confirmed run outcomes=7 |
| SPEC-09 | A-isolated-synthetic | pass | major | - | outcomes cover every confirmed category exactly once | 7 outcomes, one per confirmed category |
| SPEC-10 | A-isolated-synthetic | pass | major | - | no category is routed for an unsupported platform | categories () |
| SPEC-11 | A-isolated-synthetic | pass | major | - | both categories are routed and the requirement is listed for each | routed ('bigcommerce_specialist', 'shopify_specialist') |
| SPEC-12 | A-isolated-synthetic | pass | critical | - | every seeded record is synthetic mock evidence | seeded evidence kinds ['synthetic_mock'] |
| SPEC-13 | A-isolated-synthetic | pass | critical | SpecialistInvestigationResult | validation refuses a VERIFIED claim from a specialist | VERIFIED claim with a citation refused by SpecialistInvestigationResult |
| SPEC-14 | A-isolated-synthetic | delegated | info | - | covered by the named accepted test file, which the committed gate runs | not re-executed by AI-S10; see tests/test_ai_s06_orchestration.py |
| SPEC-15 | D-vendor-documentation-or-sandbox | blocked | major | - | each specialist's claims checked against approved official vendor documentation | approved source-access matrix and per-vendor allowlist (D-02); none granted |
| SPEC-16 | E-full-platform-human-workflow | blocked | major | - | end-to-end run against each approved platform sandbox | platform approval; no sandbox or test store authorised |
| SPEC-R01 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('shopify_specialist',) |
| SPEC-R02 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('wordpress_woocommerce_specialist',) |
| SPEC-R03 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('bigcommerce_specialist',) |
| SPEC-R04 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('three_d_cart_shift_shopify_specialist',) |
| SPEC-R05 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('magento_adobe_commerce_specialist',) |
| SPEC-R06 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('standalone_applications_specialist',) |
| SPEC-R07 | A-isolated-synthetic | pass | critical | - | the proposal routes exactly the matching category | routed ('middleware_applications_specialist',) |
| STL-01 | A-isolated-synthetic | pass | major | - | no stale-revision integrity issue | current revisions: stale issues [] |
| STL-02 | A-isolated-synthetic | pass | critical | - | reported as an integrity issue for the requirement; its deliverable is not complete | reported=True; deliverable complete=False; likely=None |
| STL-03 | A-isolated-synthetic | pass | major | - | integrity issue reported; the SOW is still produced | missing revision reported as an integrity issue; SOW still produced |
| STL-04 | A-isolated-synthetic | pass | critical | run_investigation | StaleSelectionError raised at run_investigation; the agent never runs | refused 'analysis is for project revision 3 but the project is at revision 4; analyse and decide again' enforced by run_investigation; agent calls 0 |
| STL-05 | A-isolated-synthetic | pass | critical | - | no authoritative numbers from the stale input; stale evidence does not back; the stale requirement is named in an integrity finding; the approval stays pending | no numbers=True; traced=True; stale evidence flagged=True not backed=True; SOW flagged=True; approval pending=True |
| STL-06 | A-isolated-synthetic | pass | critical | - | approval stays pending_human_approval; the draft is not approved; project totals stay incomplete | approval pending_human_approval; draft draft_not_approved; project complete False |
| TRC-01 | A-isolated-synthetic | pass | critical | - | specialist outcomes, estimate revisions and the governance fingerprint agree | specialist covers requirements=True; estimate covers=True; fingerprint carried=True |
| TRC-02 | B-foundation-integration | blocked | major | - | a Foundation-fed run reaches a SOW through the integrated adapter | no integrated Foundation adapter path exists; the offline pipeline uses synthetic fixtures; Foundation approval required |
| UD-01 | A-isolated-synthetic | pass | critical | - | matched fingerprints give no finding; a mismatched estimate is reported as an integrity finding, its values are excluded, and the SOW is not complete or approved | matched clean=True; mismatch flagged=True; values excluded=True; not complete=True; approval pending=True |
| XP-01 | A-isolated-synthetic | pass | critical | - | no outcome cites a record of the other project | evidence used 14; foreign-project records used 0 |
| XP-02 | A-isolated-synthetic | pass | critical | - | CROSS_PROJECT_CITATION is reported and the requirement is not backed | cross-project citation flagged=True; status not backed=True |
| XP-03 | A-isolated-synthetic | pass | critical | estimate | refused with 'governance review belongs to another project' at estimate | refused 'governance review belongs to another project' enforced by estimate |
| XP-04 | A-isolated-synthetic | pass | critical | estimate | refused with 'a requirement snapshot belongs to another project' at estimate | refused 'a requirement snapshot belongs to another project' enforced by estimate |
| XP-05 | A-isolated-synthetic | pass | critical | _require_governance | refused with 'governance review belongs to another project' at _require_governance | refused 'governance review belongs to another project' enforced by _require_governance |
| XP-06 | A-isolated-synthetic | pass | critical | generate | refused with 'estimate belongs to another project' at generate | refused 'estimate belongs to another project' enforced by generate |
