# AI-S03 Implementation Report: RAG and Evidence Retrieval

Status: **implemented in isolated, non-production form. Not accepted.** Independent QA and formal WDS acceptance are
pending. This report does not mark AI-S03 accepted.

Authorisation: WDS Decision 3 (AI-S03 development, isolated and non-production), and the WDS final execution directive
for this cycle. Branch `feature/ai-s03`, worktree `.claude/worktrees/webdesk-ai-s03`, based on `feature/ai-engine` at
`15d660a`.

## 1. What is implemented

The 13 required functions (see `AI_S03_IMPLEMENTATION_PLAN.md`, section 1):

- Ingestion interfaces (`rag/ingestion.py`): a synthetic fixture source, with refusal reasons that never echo text.
- Source metadata and version tracking (`rag/contracts.py`, `rag/ingestion.py`).
- Collection and project authorisation (`rag/access.py`): default deny, approvals per project, an access-port seam.
- Hybrid keyword and vector retrieval (`rag/index.py`): filter before score, reciprocal-rank fusion.
- pgvector-compatible contract (`rag/index.py`, `VectorIndexSpec`): SQL text with named placeholders. Not executed.
- Evidence references and citation integrity (`rag/contracts.py`, `rag/retrieval.py`): character-exact spans.
- Freshness and version assessment (`rag/retrieval.py`, `assess_freshness`).
- Verification status handling: every reference is `unverified`; synthetic evidence can never be verified.
- Contradictory and missing evidence (`rag/retrieval.py`): explicit conflict groups; `no_match` with `missing_evidence`.
- Retrieval-failure classification (`rag/contracts.py`, `FailureClass`).
- Specialist-compatible interface (`rag/specialist.py`, `RagEvidenceLookup`), satisfying the existing `EvidenceLookup`.
- Audit and traceability (`rag/contracts.py`, `AuditRecord`): identifiers and a query digest, never text.
- Tests: unit, contract, integration and security regression tests.

Seven specialist categories (`SEVEN_SPECIALIST_CATEGORY_IDS`) are supported by the shared infrastructure. No specialist
logic is implemented in AI-S03.

## 2. Files

Source (new): `ai_engine/src/ai_engine/rag/` (`__init__.py`, `contracts.py`, `access.py`, `ingestion.py`, `index.py`,
`retrieval.py`, `specialist.py`).

Fixture (new): `ai_engine/fixtures/rag/synthetic_rag_corpus.json` (synthetic; `"synthetic": true`).

Tests (new): `ai_engine/tests/ai_s03_support.py` and `ai_engine/tests/test_ai_s03_*.py` (eight files).

Documentation: `docs/AI_S03_IMPLEMENTATION_PLAN.md`, `docs/AI_S03_EVIDENCE_ACCESS_AND_RETRIEVAL_CONTRACTS.md`,
`docs/AI_S03_QA_AND_EVALUATION_PLAN.md`, `docs/AI_S03_QA_FINDINGS_REGISTER.md`, `docs/AI_S03_IMPLEMENTATION_REPORT.md`,
`docs/AI_S02_ACCEPTANCE_REGISTER.md`, `docs/AI_S01_CLOSURE_RECORD.md`, `docs/AI_SPRINT_STATUS_AI02.md`.

Three AI-1 production files were changed, by the approved Y-1 correction only: `ai_engine/src/ai_engine/evidence/lookup.py`, `ai_engine/src/ai_engine/specialists/execution.py` and `ai_engine/src/ai_engine/shopify/agent.py`. No other AI-1 or AI-S01 production file was changed. The AI-S02 changes carried onto this branch are unchanged in function.

## 3. Decisions applied (WDS final execution directive)

| ID | Decision | Implementation |
|---|---|---|
| D-S03-01 | Retain the 500-candidate maximum for the prototype | `_CANDIDATE_LIMIT = 500`; two boundary tests (499 returned; 500 not) |
| D-S03-02 | Preserve the AI-1 complete-snapshot contract for the empty-query lookup | `enumerate_authorised`, uncapped; authorised records only; malformed input fails closed |
| D-S03-03 | All-denied returns FAILED with a sanitized ACCESS_DENIED reason | `_ACCESS_DENIED` in `retrieval.py`; no collection identifier in the reply |
| D-S03-04 | Reject queries with leading or trailing whitespace | `RetrievalRequest` refuses; re-validated on entry to `retrieve` and `enumerate_authorised` |
| D-S03-05 | Collections not evaluated are never labelled denied | `AuditRecord.not_evaluated_collections`; empty queries report it |

## 4. Accepted limitations (prototype, not guarantees)

- **Candidate window.** Retrieval inspects at most 500 matching candidates per request. Unavailable chunks count toward
  those 500. A valid chunk ranked 501st or lower is not retrieved. This is not a guarantee of complete retrieval on
  larger datasets. Contracts document, section 4.
- **Specialist empty-query snapshot.** Returns the complete authorised set, uncapped, by design. Contracts document,
  section 12.
- **Keyword scoring** is term-frequency only. **Vector scoring** uses a test-only feature-hashing embedder;
  `MIN_VECTOR_SIMILARITY = 0.2` is calibrated to it and must be recalibrated for any real embedder.
- **Contradictions** come from explicit conflict-group metadata, not from reading meaning.
- **Superseded versions** are returned to direct callers flagged `superseded`. The specialist lookup withholds them
  before the `top_k` cap, within the candidate window, because it cannot expose the flag. Within one project and collection, two versions of one document with no supersession between them are refused, since neither is known to be current.
- **In-memory only.** The document store, audit log and index are not persisted. The pgvector contract is described,
  not executed. Audit log and lookup group map grow without bound in a long-lived process.
- **Query digests** are unsalted SHA-256. A digest identifies a query; it does not hide a guessable one.
- **Approvals and grants** in tests are explicit fixtures.

## 5. Test evidence

Full engine gate (from `ai_engine/`, with the pinned mypy 1.11.2 binary because the workstation blocks the uv-managed one):

| Check | Result |
|---|---|
| pytest, commit 097ba44 (AI-S02 tests not included) | 617 passed |
| pytest, AI-1 and AI-S01 (`test_ai*` files outside AI-S02 and AI-S03, plus the AI-1 suites) | 388 passed |
| pytest, AI-S02 (`tests/test_ai_s02_*.py`), not in commit 097ba44; staged in the working tree | 573 passed |
| pytest, AI-S03 and Y-1 in the commit | 229 passed |
| ruff check `src tests` | clean |
| ruff format --check `src tests` | clean (74 files, commit 097ba44) |
| mypy `src` | clean (45 files, commit 097ba44) |
| mypy `--strict src tests` | clean (74 files, commit 097ba44) |

AI-S03 test files and counts: contracts 19, ingestion and access 19, index 18, retrieval 21, security 20, specialist 17,
evaluation 6, review fixes 102.

## 6. Independent QA

Independent QA reports are recorded in `AI_S03_QA_AND_EVALUATION_PLAN.md` (sections 5, 6, 6.1, 6.2 and 6.3) and
classified in `AI_S03_QA_FINDINGS_REGISTER.md`. The consolidated review of the frozen candidate for this cycle is
recorded in section 6.5 of the QA plan.

## 7. Dependencies and gaps

- **Access.** `StaticAccessPort` with explicit test grants. No Foundation port exists.
- **Approvals.** Synthetic fixture approvals only. No real WDS collection approvals.
- **Persistence and index.** In memory. No Foundation tables are written.
- **Governance rulings.** A-4, C-15, governance position 1 (AI output may not assert verified status), and the C-06
  allowlist remain open.
- **Source and retention policy.** Not defined. Synthetic data only.

## 8. Status and recommendation

- Engineering status: implemented and tested locally; not accepted.
- Real-data, live-vendor, real-provider and production use: not authorised and not tested.
- AI-S04: not started. It may not start before AI-S03 acceptance.
- Recommendation to WDS: acceptance may be considered only after an independent QA PASS on the frozen candidate with no
  outstanding blocking findings. The acceptance decision belongs to WDS.
