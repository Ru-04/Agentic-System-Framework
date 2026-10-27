# AI-S01 to AI-S09 Acceptance Traceability Matrix

Status: Stage 1. Counts are from this checkout at base `3e79d01` plus the AI-S10 working tree.

How the columns were produced:

- **Test files** are mapped by file-name prefix. Collected counts come from
  `pytest --collect-only`. The mapping is by name only; it was not checked against each sprint's
  own record, so the link is provisional wherever noted.
- **Catalogue** columns count the AI-S10 scenarios whose `references` include the sprint. One scenario
  can count under several sprints, so the columns overlap and must not be added together.
- **Acceptance status** is as recorded in the project's sprint sequence. The sprint records were not
  re-read in this stage, so these statuses are reported, not verified here.

| Sprint | Scope (per commit subject / sprint record) | Test files (collected) | Catalogue scenarios (outcomes) | Acceptance status | AI-S10 gap |
|---|---|---|---|---|---|
| AI-S01 | P0 security remediation (AI-5.1) | `test_ai51_p0_regressions.py` (49), `test_ai51_review2_regressions.py` (13): 62 | None reference AI-S01 | Recorded earlier; not re-verified | **No catalogue coverage.** Provisional file mapping. |
| AI-S01 (earlier AI-1 files) | Earlier AI-1 work | `test_ai1_regressions_and_evidence.py` (20), `test_ai1_y1_conflict_scope.py` (7): 27 | None | Not stated in this stage | Sprint link not verified |
| AI-S02 | LLM port, guarded structured calls, intake and semantic agents | Committed: 14 `test_ai_s02_*` files, 573 tests. Untracked Foundation files `test_ai_s02_s04_*` (18, 43, 6): 67, excluded from the committed count | 2 blocked (EXT-05, EXT-07: Foundation dependencies); no executed scenario. PIPE-04 (intake and semantic analysis) cites no sprint and is delegated to `test_requirement_analysis.py` (21) | Committed implementation and QA rounds; WDS acceptance not re-verified | **No executed catalogue coverage.** Intake behaviour is covered only by delegation. |
| AI-S03 | Evidence index, retrieval, security, specialist | `test_ai_s03_*` (contracts 19, evaluation 6, index 18, ingestion_access 19, retrieval 21, review_fixes 102, security 20, specialist 17): 222 | 1 delegated (PIPE-05, to `test_ai_s03_retrieval.py`) | Earlier sprint record; not re-verified | Retrieval is delegated, not re-executed |
| AI-S04 | Specialist ports for four platforms (BigCommerce, Magento, Shift4Shop, WooCommerce) | `test_ai_s04_*` (15, 19, 18, 15): 67 | 3 pass (SPEC-01, SPEC-02, SPEC-12); 4 blocked (EXT-02, EXT-05, EXT-07, SPEC-15) | Earlier sprint record; not re-verified | Real-platform checks are blocked (see the platform register) |
| AI-S05 | Application specialists | `test_ai_s05_application_specialists.py`: 130 | 2 pass | Earlier sprint record; `AI_S05_ENGINEERING_CLOSURE_RECORD.md` is untracked | **Thin catalogue coverage** for 130 tests |
| AI-S06 | Orchestration: propose, confirm, execute | `test_ai_s06_orchestration.py`: 58 | 21 pass, 1 delegated (SPEC-14), 1 blocked (SEC-18, Foundation audit) | Earlier sprint record; not re-verified | Retry, partial authorisation and permanent refusal now executed (REC-01 to REC-03) |
| AI-S07 | Governance reviewer | `test_ai_s07_governance.py`: 66 | 27 pass, 1 open limitation (EVID-16) | WDS accepted for isolated engineering (per sprint record) | Lexical sufficiency is an open limitation (EVID-16) |
| AI-S08 | Resource-wise estimation | `test_ai_s08_estimation.py`: 65 | 23 pass | WDS accepted for isolated offline engineering (per sprint record) | None identified in catalogue |
| AI-S09 | Draft SOW | `test_ai_s09_sow.py`: 72 | 21 pass | WDS accepted for isolated offline engineering; qualified QA history (per sprint record) | House template and DOCX/PDF export blocked (SOW-13, D-10) |
| AI-S10 | Integrated evaluation (this sprint) | `test_ai_s10_evaluation.py`: 16 | Self-tests of the runner | Stage 1 checkpoint; not accepted | Stage 2 QA pending |

Shared or earlier files not mapped to a sprint: `test_adapter_registry.py`, `test_ai41_contracts.py`,
`test_contracts_*.py`, `test_demo_end_to_end.py`, `test_operator_selection.py`, `test_prompt_injection.py`,
`test_requirement_analysis.py`, `test_routing_task_builder.py`, `test_shopify_agent.py`,
`test_specialist_execution.py`, `test_specialist_validation_and_isolation.py`. They run in the full suite.

## Findings from this matrix

1. **AI-S01 and AI-S02 have no executed catalogue scenario.** Their behaviour is covered only by the
   test files in the full suite. Closing this needs scenarios that reference them. It is recorded in the
   QA findings register as OBS-2.
2. **AI-S05 has 130 tests and 2 catalogue scenarios.** The breadth is covered by the file, not the
   matrix. OBS-3.
3. Every executed scenario of AI-S06 to AI-S09 passed. None of these passes is evidence of real-provider
   or real-platform behaviour.
