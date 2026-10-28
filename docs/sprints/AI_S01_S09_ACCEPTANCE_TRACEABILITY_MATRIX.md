# AI-S01 to AI-S09 Acceptance Traceability Matrix (Stage 3)

Status: Stage 3. Counts are from the final catalogue (candidate digest in the reproducibility report).

How the columns were produced:

- **Test files** are mapped by file-name prefix and by the commit subjects. The mapping is provisional where
  noted, because each sprint's own record was not re-read for every file.
- **Catalogue** columns count the AI-S10 scenarios whose `references` include the sprint. One scenario can
  count under several sprints, so the columns overlap and must not be added together.
- **Acceptance status** is as recorded in the project's sprint sequence. It is reported, not re-verified here.

| Sprint | Scope (per commit subject / sprint record) | Test files (collected) | Catalogue references (outcomes) | Acceptance status | AI-S10 gap after Stage 3 |
|---|---|---|---|---|---|
| AI-S01 | P0 security remediation (AI-5.1) | `test_ai51_p0_regressions.py` (49), `test_ai51_review2_regressions.py` (13): 62 | 8 pass (`S01-01`..`S01-07`, `STL-04`) | Recorded earlier; not re-verified | Live Foundation enforcement not run (`EXT-05`, `EXT-06`) |
| AI-S01 (earlier AI-1 files) | Earlier AI-1 work | `test_ai1_regressions_and_evidence.py` (20), `test_ai1_y1_conflict_scope.py` (7): 27 | 1 delegated (`AI-1`) | Not stated in this stage | Sprint link not verified |
| AI-S02 | LLM port, guarded structured calls, intake and semantic agents | Committed: 14 `test_ai_s02_*` files, 573 tests. Untracked Foundation files: 67 (64 pass, 3 skip) | 3 pass (`LLM-01`..`LLM-03`); 2 blocked (`EXT-05`, `EXT-07`) | Committed implementation and QA rounds; WDS acceptance not re-verified | Real-provider semantic extraction not run (`EXT-01`) |
| AI-S03 | Evidence index, retrieval, security, specialist | `test_ai_s03_*`: 222 | 1 delegated (`PIPE-05`) | Earlier sprint record; not re-verified | Retrieval is delegated, not re-executed |
| AI-S04 | Specialist ports for four platforms | `test_ai_s04_*`: 67 | 3 pass (`SPEC-01`, `SPEC-02`, `SPEC-12`); 4 blocked (`EXT-02`, `EXT-05`, `EXT-07`, `SPEC-15`) | Earlier sprint record; not re-verified | Real-platform and vendor checks blocked |
| AI-S05 | Application specialists | `test_ai_s05_application_specialists.py`: 130 | 2 pass (`SPEC-01`, `SPEC-12`) | Earlier sprint record | **Thin catalogue coverage** for 130 tests (recorded, not closed) |
| AI-S06 | Orchestration: propose, confirm, execute | `test_ai_s06_orchestration.py`: 58 | 31 pass (incl. replay `RPL-01`..`RPL-07`, `SEC-06`, negative controls, `REC-01`..`REC-05`); 1 delegated (`SPEC-14`); 1 open (`REC-03`, C-15); 2 blocked (`EXT-06`, `SEC-18`) | Earlier sprint record; not re-verified | Replay ledger enforcement proven by mutation (Stage 3) |
| AI-S07 | Governance reviewer | `test_ai_s07_governance.py`: 66 | 28 pass (incl. `XP-02`); 2 open (`EVID-16`, `REC-03`); 1 blocked | WDS accepted for isolated engineering (per sprint record) | Lexical sufficiency is an open limitation (`EVID-16`) |
| AI-S08 | Resource-wise estimation | `test_ai_s08_estimation.py`: 65 | 28 pass (incl. `XP-03`, `XP-04`, `STL-02`); 1 open (`UD-01`, which cites AI-S08 and AI-S09); 1 blocked (`STL-05`) | WDS accepted for isolated offline engineering (per sprint record) | Stale requirement handling is flagged, not rejected (`STL-05`, governance decision) |
| AI-S09 | Draft SOW | `test_ai_s09_sow.py`: 72 | 28 pass (incl. `XP-05`, `XP-06`, `STL-06`); 1 open (`UD-01`, upstream fingerprint gap); 2 blocked (`SOW-13`, `STL-05`) | WDS accepted for isolated offline engineering; qualified QA history (per sprint record) | **Upstream defect `UD-01`** (fingerprint not compared); house template blocked (`SOW-13`) |
| AI-S10 | Integrated evaluation (this sprint) | `test_ai_s10_evaluation.py` (16), `_evaluator_rules.py` (9), `_mutations.py` (4), `_consistency.py` (3): 32 | Self-tests of the runner, rules, mutations and consistency | Stage 3 remediation; Stage 2 re-review pending | Stage 2 re-review; Stage 4 packet |

Shared or earlier files not mapped to a sprint: `test_adapter_registry.py`, `test_ai41_contracts.py`,
`test_contracts_*.py`, `test_demo_end_to_end.py`, `test_operator_selection.py`, `test_prompt_injection.py`,
`test_requirement_analysis.py`, `test_routing_task_builder.py`, `test_shopify_agent.py`,
`test_specialist_execution.py`, `test_specialist_validation_and_isolation.py`. They run in the full suite.

## Findings from this matrix

1. **AI-S01 now has executed coverage** (8 passes). The previous "zero scenarios" finding is closed.
2. **AI-S02 has executed LLM-backed intake coverage** (3 passes, offline) and 2 blocked Foundation rows.
   Requirement extraction in general is covered by the deterministic agent (`REQ-01`..`REQ-08`); the sprint of
   record for that deterministic agent is not stated in its test file, so it is cited as `requirement_analysis`.
3. **AI-S05 remains thin**: 130 accepted tests, 2 catalogue references. Recorded as a limit; not closed here.
4. **AI-S09 carries an upstream defect (`UD-01`)**: the SOW does not compare fingerprints. Recorded as an open
   limitation; not fixed, because AI-S09 is accepted and the fix needs the permitted upstream change.
5. Every executed scenario of AI-S06 to AI-S09 passes. None of these passes is evidence of real-provider,
   real-platform or Foundation behaviour.
