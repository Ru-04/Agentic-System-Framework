# AI-S03 Implementation Plan: RAG and Evidence Retrieval

Authorisation: WDS Decision 3, "Authorize AI-S03 Development". Isolated, non-production implementation and testing.

Branch: `feature/ai-s03`, a new worktree at `.claude/worktrees/webdesk-ai-s03`. Created from `feature/ai-engine`
at `15d660a`, with the AI-S02 changes applied on top as uncommitted work. No commit, push or merge has been made.

Status: **implemented; independent review returned FAIL (nine findings). All nine are fixed with regression tests; re-review requested.** It is not accepted. See section 7.

## 1. Scope mapping (WDS required functionality)

| # | Requirement | Where it is implemented | Tests |
|---|---|---|---|
| 1 | Internal knowledge ingestion interfaces | `rag/ingestion.py`: `IngestionSource` protocol, `SyntheticFixtureSource`, `ingest()` | `test_ai_s03_ingestion_access.py` |
| 2 | Source metadata and version tracking | `rag/contracts.py`: `SourceDocument` (document, source, version, hash, dates, status, supersession); `DocumentStore` keyed by (document, version) | `test_ai_s03_contracts.py`, `test_ai_s03_ingestion_access.py` |
| 3 | Collection-level and project-level authorisation | `rag/access.py`: `CollectionRegistry` (per-project approvals, no default), `AccessPort` (Foundation seam, empty by default), `decide_collections()` | `test_ai_s03_ingestion_access.py`, `test_ai_s03_security.py` |
| 4 | Hybrid keyword and vector retrieval | `rag/index.py`: `HybridIndex` (keyword score, vector cosine, reciprocal-rank fusion, filter before score) | `test_ai_s03_index.py` |
| 5 | pgvector-compatible retrieval contracts | `rag/index.py`: `VectorIndexSpec` (validated identifiers, parameterised `<=>` similarity SQL, not executed) | `test_ai_s03_index.py` |
| 6 | Evidence source references and citation integrity | `rag/contracts.py`: `Citation`; `rag/retrieval.py`: `_validate_hit`, `citation_is_intact` | `test_ai_s03_retrieval.py`, `test_ai_s03_evaluation.py` |
| 7 | Source freshness and version assessment | `rag/retrieval.py`: `assess_freshness()` (superseded, future-dated, no-date, no-policy, stale, current) | `test_ai_s03_retrieval.py` |
| 8 | Evidence verification-status handling | `rag/contracts.py`: documents fixed to `unverified`; `RetrievedEvidence` refuses any non-unverified reference | `test_ai_s03_security.py`, `test_ai_s03_evaluation.py` |
| 9 | Contradictory and missing evidence handling | `rag/retrieval.py`: `_contradictions()` by explicit conflict group; `NO_MATCH` with `missing_evidence` | `test_ai_s03_retrieval.py` |
| 10 | Retrieval-failure classification | `rag/contracts.py`: `FailureClass`; `rag/retrieval.py`: classified, never propagated | `test_ai_s03_retrieval.py`, `test_ai_s03_security.py` |
| 11 | Specialist-compatible retrieval interfaces | `rag/specialist.py`: `RagEvidenceLookup` satisfies the existing `EvidenceLookup` protocol; `SEVEN_SPECIALIST_CATEGORY_IDS` | `test_ai_s03_specialist.py` |
| 12 | Audit and traceability outputs | `rag/contracts.py`: `AuditRecord` (identifiers and query digest, never text); one record per request | `test_ai_s03_retrieval.py`, `test_ai_s03_security.py` |
| 13 | Unit, contract, integration and security regression tests | Eight files, 222 AI-S03 tests plus 7 Y-1 tests (section 5) | all `test_ai_s03_*` |

## 2. Architecture decisions

- **Foundation owns identity and permissions.** `AccessPort` is a seam. The engine asks whether an actor may read a
  collection in a project. It never decides who the actor is. The shipped port is `StaticAccessPort`, empty by default.
- **Default deny.** No collection is readable without a WDS-supplied `CollectionApproval` for that project, and an
  access-port grant for that actor. An approval for another project is refused as cross-project.
- **Authorise before search.** `SVC-EVIDENCE-RETRIEVAL` requires enforcing access before any search. The index is
  never called for a refused request (tested with a spy index).
- **Filter before score.** Chunks outside the request's project and allowed collections are never scored, so they
  cannot be returned by a later step.
- **Validate every hit.** A hit is accepted only if its project, collection, document, availability, span, and hash
  all match the store. A failed hit is excluded and classified. Nothing is repaired.
- **No invented policy.** Freshness uses the caller's `max_age_days`. Without it, freshness is reported as
  "not assessed against a policy". Collection approval and retention are supplied, not defaulted.
- **Synthetic-first.** The only ingestable kind is `synthetic_test`, plus `approved_internal` when a collection's scope
  is approved for it. Live vendor and model-knowledge kinds are not representable. External URLs are refused.
- **No hardcoded provider.** The embedder is a protocol. `DeterministicHashEmbedder` is test-only and has no model.
- **Specialists: one approved AI-1 exception.** The AI-1 Shopify specialist runs over RAG evidence, tested end to end. Its agent (`shopify/agent.py`) and the execution wrapper (`specialists/execution.py`) were changed for project scoping under the WDS Y-1 exception.
- **Identifier convention.** Collection identifiers follow the AI-1 `Slug` pattern, because the AI-1 specialist task
  requires it. One identifier serves both contracts. This was found by probing and is recorded here.
- **Empty-query enumeration.** AI-1 builds an authorised snapshot by searching with an empty query. RAG refuses an empty
  query as a search. The lookup therefore routes an empty query to `enumerate_authorised()`, which applies the same
  authorisation and validation and does not rank. This was found by probing the end-to-end run and is recorded here.

## 3. Files

Source (new): `src/ai_engine/rag/__init__.py`, `contracts.py`, `access.py`, `ingestion.py`, `index.py`, `retrieval.py`,
`specialist.py`.

Fixture (new): `fixtures/rag/synthetic_rag_corpus.json` (synthetic, `"synthetic": true`, 10 documents, 3 approvals).

Tests (new): `tests/ai_s03_support.py` (shared helpers) and `tests/test_ai_s03_*.py` (eight files), plus the Y-1 file `tests/test_ai1_y1_conflict_scope.py` (7 tests).

Three AI-1 production files were changed, by the approved Y-1 correction only: `ai_engine/src/ai_engine/evidence/lookup.py`, `ai_engine/src/ai_engine/specialists/execution.py` and `ai_engine/src/ai_engine/shopify/agent.py`. No other AI-1 or AI-S01 production file was changed. The AI-S02 changes were applied to this branch unchanged, except that the
four AI-1 test files whose typing overlapped with AI-S01 keep the AI-S01 versions (section 4).

## 4. Reconciliation performed

- Base: `feature/ai-engine` at `15d660a` (AI-S01 APPROVED / CLOSED for isolated engineering implementation; not production authorisation). Not modified.
- AI-S02 applied as uncommitted changes (`git cherry-pick --no-commit`, no commit created): `e7cfe43` then `c43cda0`.
- Overlap: four AI-1 test files were changed differently on both lines. `test_ai41_contracts.py`,
  `test_ai51_p0_regressions.py`, `test_shopify_agent.py`, `test_specialist_execution.py`. Resolved by keeping the
  AI-S01 version (`git checkout --ours`), which already passes strict typing. No accepted fix was discarded: the other
  five typing hunks from `c43cda0` applied cleanly.
- Verification: the combined tree passes the AI-1 and AI-S02 suites (961 tests before AI-S03) and strict mypy. Recorded in
  the reconciliation report. No material contract change was needed.

## 5. Tests (222 new)

| File | Tests | Covers |
|---|---|---|
| `test_ai_s03_contracts.py` | 19 | Document hash integrity, verified status refused, external URL refused, chunk and citation spans, request validation, outcome consistency, synthetic-never-verified |
| `test_ai_s03_ingestion_access.py` | 19 | Default deny, approvals per project, cross-project refusal, unapproved collections, ingestion refusal reasons, scope and kind matching, duplicate versions, refusal messages do not echo text |
| `test_ai_s03_index.py` | 18 | Exact chunk spans, deterministic chunking and embedding, filter before score, fusion, top-k, pgvector SQL shape and identifier validation |
| `test_ai_s03_retrieval.py` | 21 | Exact citations, contradictions, superseded and stale citations, freshness, no-match, empty query, unavailable documents, index exception, malformed and forged hits, missing citation, partial success, audit |
| `test_ai_s03_security.py` | 20 | Unauthorised collection, index never searched without grant, cross-project leakage (including a leaking index), no automatic verification, injected instructions as data, audit holds no text, out-of-allowlist hit refused |
| `test_ai_s03_specialist.py` | 17 | Seven category ids match the registry, unregistered category refused, protocol compatibility, empty-query enumeration, conflict groups, end-to-end unchanged Shopify run, no evidence without grant |
| `test_ai_s03_evaluation.py` | 6 | Fixed query set (status and expected documents), citation integrity, contradiction and staleness detection, unavailable never returned, no reference verified, grant matrix (the fixed twelve actor × project × collection combinations: 2 × 2 × 3) leaks zero |
| `test_ai_s03_review_fixes.py` | 102 | Regression for the independent reviews and remediations |

## 6. Known limits (documented, not closed by AI-S03)

- Keyword scoring is term-frequency only. Vector scoring uses a test-only feature-hashing embedder.
  `MIN_VECTOR_SIMILARITY = 0.2` is calibrated for that embedder only and must be recalibrated for any real one.
- Contradictions are detected from explicit conflict-group metadata, not by reading meaning.
- Superseded versions are returned, flagged, and reported as superseded. A caller that wants only current versions must
  filter on the reported flags. This is a deliberate choice: silently hiding them would lose traceability.
- The document store, audit log and index are in memory. Nothing is persisted. The pgvector contract is described, not
  executed.
- `enumerate_authorised()` scans the store and is linear in corpus size. It is suitable for the synthetic corpus only.
- Retrieval is bounded to 500 candidates per request (`_CANDIDATE_LIMIT`), accepted by WDS on 2026-10-23. A valid chunk ranked 501st or lower among matching chunks is not retrieved; unavailable chunks count toward the 500. It does not guarantee complete retrieval on larger datasets; that needs a measured bound and approval.
- Approvals and grants in tests are explicit fixtures. Real approvals and grants come from WDS and Foundation.

## 7. Status

- Implemented in the isolated worktree. Gate: see section 4 of the QA and evaluation plan (222 AI-S03 tests, plus 7 Y-1 tests).
- Independent review: FAIL with nine findings. All nine are fixed with regression tests (QA and evaluation plan, section 6). Re-review requested; its verdict must be read before any closure claim.
- Not accepted. AI-S03 is not closed. AI-S04 has not started and may not start before AI-S03 acceptance.
