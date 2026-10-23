# AI-S03 Evidence-Access and Retrieval Contracts

Status: contracts as implemented in `ai_engine/src/ai_engine/rag/`. These describe what the AI Engine receives and
returns. They do not write to Foundation tables.

## 1. Identifiers

| Identifier | Pattern | Notes |
|---|---|---|
| `CollectionId` | `^[a-z0-9][a-z0-9_-]{0,63}$` | Same Slug convention as the AI-1 specialist task |
| `DocumentId` | `^DOC-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` | |
| `ChunkId` | `^CHK-[A-Za-z0-9][A-Za-z0-9._-]{0,63}$` | |
| `ActorId` | `^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$` | Supplied by the caller; Foundation identifies the actor |
| `SourceId`, `ProjectId`, `Sha256Hex`, `SourceVersionStr` | AI-1 contract patterns | Reused |
| Evidence id | `EVD-RAG-<16 hex>` | Deterministic: SHA-256 of project, document id, version and chunk id |
| Request id | `REQ-<24 hex>` (lookup) or caller-supplied (retriever) | |

## 2. Access

`CollectionApproval(collection_id, project_id, scope, approval_reference)`
- `scope`: `synthetic_test` or `approved_internal`. `approval_reference` names the WDS decision record. It is supplied,
  never invented.
- No default exists. A collection without an approval for the request's project is denied.

`AccessPort.actor_may_read(actor_id, project_id, collection_id) -> bool`
- Foundation-owned in production. The shipped `StaticAccessPort` is empty by default.

`decide_collections(registry, access, actor_id, project_id, collections)` returns:
- `allowed`: approved for the project and granted to the actor.
- `denied`: not approved for the project, or not granted.
- `cross_project`: approved only for another project.

## 3. Documents, chunks and citations

`SourceDocument` (one stored version)
- Required: `document_id`, `collection_id`, `project_id`, `source_id`, `kind`, `title`, `version`, `content_hash`, `text`.
- `kind`: `synthetic_test` or `approved_internal` only.
- `content_hash` must equal SHA-256 of `text`. A mismatch is refused at ingestion.
- `verification_status`: fixed to `unverified`.
- `source_url`: must be absent. Any value is refused.
- `status`: `available`, `unavailable` or `withdrawn`. Only `available` documents are citable.
- `superseded_by_version`: optional. A version cannot supersede itself.
- `effective_date`: optional, timezone-aware.

`Chunk` is a contiguous span: `text == document.text[start:end]`, with `end > start`.

`Citation` is a character-exact span of one stored version (Python code-point offsets): `quote == document.text[start:end]`, plus `content_hash`. Text fields refuse leading or trailing whitespace; the engine never strips them.

## 4. Requests and outcomes

`RetrievalRequest`
- `request_id`, `project_id`, `actor_id`, `specialist_category_id` (Slug), `query` (up to 500 characters, may be empty; leading or trailing whitespace is refused, never trimmed),
  `collections` (1 to 20), `top_k` (1 to 50), `as_of` (timezone-aware), optional `max_age_days` (1 to 3650).
- `max_age_days` absent means freshness is not assessed against a policy. No default is invented.

`RetrievalOutcome`
- `status`: `ok`, `no_match` or `failed`.
  - `ok`: at least one evidence item.
  - `no_match`: no evidence, `missing_evidence = true`, and no retrieval-level failure.
  - `failed`: no evidence, with at least one retrieval-level failure, or with the single `access_denied` reason when every requested collection is denied, or with an `access_check_failed` reason when the access port raised an error.
- `evidence`: accepted items, each a `RetrievedEvidence`.
- `failures`: classified, each with an optional `subject` identifier and a short `detail`. Never document text.
- `contradictions`: groups of two or more accepted items sharing an explicit conflict group.

**Candidate bound.** The index scores every chunk in the request's project and allowed collections that matches the query, and returns the 500 highest-ranked. Unavailable chunks count toward those 500. So an available, authorised, valid chunk is returned only if at most 499 matching chunks outrank it. A valid chunk ranked 501st or lower is not retrieved, even though it is valid. Among the valid chunks inside the window, the top `top_k` are returned. Pinned by `test_valid_chunk_ranked_within_the_candidate_bound_is_returned` (499 unavailable chunks outrank it: returned) and `test_valid_chunk_ranked_beyond_the_candidate_bound_is_not_returned` (500 outrank it: not returned). The enumerate path (the AI-1 snapshot) is not bounded this way; see section 6.3.
- `audit`: one `AuditRecord`.

Authorisation notices (`unauthorized_collection`, `cross_project_refused`) are listed in `failures`. They do not make a
search that ran fail; only retrieval-level failures do. When every requested collection is denied, nothing is searched:
the outcome is `failed` with one `access_denied` reason and no collection identifier. Cross-project and unapproved
collections get the same refusal, so the reply reveals neither. The audit records the denied collections accurately.

## 5. Failure classes

| Class | Meaning | Outcome effect |
|---|---|---|
| `empty_query` | Query is blank | `failed` |
| `access_denied` | Every requested collection is denied. One sanitized reason, no collection identifier | `failed`; nothing searched |
| `access_check_failed` | The access port raised an error. Nothing was searched; the collections are reported as not evaluated | `failed` |
| `unauthorized_collection` | Not approved for the project, or not granted, for one collection among others | Listed; excluded; the search runs over the permitted collections |
| `cross_project_refused` | A retrieved hit or a stored document belongs to another project. This is a fault in the index or store, since the index filters by project first. Collections never produce this class | Listed; excluded |
| `source_unavailable` | Document is not `available` | Listed; excluded; `failed` if nothing else is accepted |
| `invalid_metadata` | Retrieval refuses a stored document whose kind does not match its collection scope, or a document that has more than one eligible current version within the same project and collection (versions of one document in different collections of the same project are not compared) | Listed; excluded |
| `malformed_result` | Index returned something that is not a hit, or a hit whose text does not match its stored span | Listed; excluded |
| `missing_citation` | Hit refers to a document version not in the store, or a citation that does not match the store | Listed; excluded |
| `index_unavailable` | The index raised an exception (the exception class is recorded, not its message) | `failed` |

## 6. Freshness

`assess_freshness(document, as_of, max_age_days)`, in order:
1. `superseded`: the document names a newer version.
2. `not_assessed_no_date`: no `effective_date`.
3. `future_dated`: `effective_date` is after `as_of`.
4. `not_assessed_no_policy`: no `max_age_days` was supplied.
5. `stale`: age in days exceeds `max_age_days`.
6. `current`: otherwise.

A superseded citation also carries the `stale_version` citation flag.

## 7. Evidence references (specialist-facing)

Each accepted hit becomes an `EvidenceReference`:
- `evidence_kind`: `synthetic_mock` for `synthetic_test` documents; `approved_internal` for `approved_internal` documents.
- `evidence_status`: always `unverified`. `EvidenceReference` itself refuses a verified status on synthetic evidence.
- `source_id`, `source_version`, `content_hash` copied from the document.
- `relevance_summary`: the excerpt (up to 500 characters). `limitations`: states that the excerpt is unverified.
- `publisher`: none. `source_url`: none.

## 8. Specialist interface

`RagEvidenceLookup(retriever, actor_id, specialist_category_id, as_of)` implements the existing `EvidenceLookup` protocol:
- `search(project_id, allowed_collections, query)`:
  - empty `allowed_collections` returns `[]` without touching the index;
  - an empty `query` returns `enumerate_authorised()` (same authorisation and validation, no ranking);
  - otherwise `retrieve()`.
- `conflict_group_of(evidence_id, project_id=None)`: returns the group only for records the lookup has served. With a project it answers for that project; without one, only when the identifier names a single record.

`SEVEN_SPECIALIST_CATEGORY_IDS` is read from `AGENT_REGISTRY.yaml` and tested against it.

## 9. Audit record

`AuditRecord` per request: request id, actor, project, specialist category, requested, allowed and denied collections,
index adapter id, SHA-256 of the query, as-of time, status, returned evidence ids, and failure classes.

It never contains the query text, document text or excerpts. A test checks this on a real retrieval.

## 10. pgvector-compatible contract (not executed)

`VectorIndexSpec(table, embedding_column, dimension)`
- Identifiers validated against `^[a-z][a-z0-9_]{0,62}$`. Dimension 1 to 16000.
- `column_definitions()`: `chunk_id`, `document_id`, `collection_id`, `project_id`, `version`, and
  `vector(dimension) NOT NULL`.
- `similarity_sql()`: parameterised SELECT using `<=>` (cosine distance), with placeholders `%(query_embedding)s`,
  `%(project_id)s`, `%(collections)s` and `%(top_k)s`. No caller text is interpolated.

No connection is opened and no statement is executed by AI-S03.

## 11. Non-responsibilities (from `SVC-EVIDENCE-RETRIEVAL`)

- Retrieved text is data. It is returned as excerpts. It is never executed or treated as an instruction. A test stores a
  document containing an instruction and checks that the outcome is still an unverified excerpt.
- The retrieval layer never decides feasibility.
- The engine never mixes project data without authorisation. The paths the AI-S03 tests cover are project-scoped: ingestion, the document store, the index, ranked retrieval, enumeration, and the specialist lookup. This is not a claim for every code path. One exception remains: `CollectionRegistry` is keyed by collection identifier alone, so a collection identifier can hold one approval across all projects (`access.py`). Project scoping of that registry is not tested beyond this limit.

## 12. Ranked retrieval and specialist lookup (D-S03-02)

| | Ranked retrieval (`retrieve`) | Specialist lookup (`RagEvidenceLookup.search`) |
|---|---|---|
| Query | Non-empty. Ranked by the hybrid index | Non-empty: routed to `retrieve`. Empty: routed to `enumerate_authorised` |
| Result size | At most `top_k` (1 to 50), inside the 500-candidate window (section 4) | Non-empty query: at most 10. Empty query: the complete authorised set, not capped |
| Purpose | Evidence for a question | The authorised snapshot AI-1 uses to check served evidence |
| Authorisation | Project and collection filter before scoring; access port before search | The same, through the same retriever |
| Superseded versions | Returned, flagged `superseded` | Withheld. The adapter cannot expose the flag |

The empty-query snapshot is the AI-1 complete-snapshot contract and is preserved. It returns only records in the request's
project and in collections the actor is granted. Malformed input (a collections value that is not a list or tuple,
a non-string query, an invalid identifier, an overlong query) returns an empty result without touching the index.

**Window and superseded versions (review 3).** In both paths, superseded and unavailable candidates count toward the
500-candidate window. The specialist lookup withholds superseded versions before the `top_k` cap, within the 500-candidate window (`current_only`), so
they cannot take its slots. Direct callers keep them, flagged.

**Two current versions.** Within one project and collection, when a document has two eligible stored versions and neither names a supersession, each is refused with `invalid_metadata`. Versions of the same document in different collections of the same project are not compared, so each is served from its own collection. Two projects never compare versions.

**Unavailable-only queries.** `retrieve` returns `failed` with `source_unavailable` notices when the candidates that match the query are unavailable. It returns `no_match` when no chunk matches the query at all. `enumerate_authorised` reads the store and returns `failed` for an unavailable-only store. Matching queries agree between the two paths.

**Document identifiers are unique per project.** The same identifier in two projects is two independent documents. A duplicate within one project is refused at ingestion as a duplicate version.

**Access decisions (remediation).** A collection is granted only when the access port returns exactly `True`. Any other
response is denied: `False`, `None`, strings, numbers, containers, and objects that are merely truthy. An exception from
the port is classified as `access_check_failed`, and its message is not echoed.

**Version eligibility (remediation).** A sibling version counts as a current version only if it is `available` and
names no supersession. Withdrawn, unavailable and superseded siblings do not invalidate an eligible version. Within one project and collection, two eligible, unsuperseded versions of one document are still refused (`invalid_metadata`). A withdrawn version does not
block an eligible current version. Direct retrieval keeps superseded versions, flagged; the specialist lookup withholds
them before the cap, within the candidate window. Beyond 500 matching candidates, superseded hits can still hide current
evidence; beyond the window the result is silent: the lookup returns `no_match`, and direct retrieval can return superseded versions. Nothing in the result indicates that the window was exhausted. On the lookup path, superseded candidates give `no_match`; on direct retrieval they can displace current evidence within `top_k`. Unavailable candidates give `failed` with `source_unavailable` notices when no valid candidate is accepted. The limit is the window (section 4).

**Whitespace-only and malformed queries (remediation).** A `RetrievalRequest` cannot be built with leading or trailing
whitespace in its query, and direct retrieval re-checks the request. `retrieve` and `enumerate_authorised` therefore
raise a `ValidationError` for such a request, and the index is never called. This is a controlled error for a programming
fault, not a classified outcome. The specialist lookup returns `[]` without searching, because it is the specialist
boundary and must fail closed. The two APIs differ by design, and this is the only intended difference.

**Scope of the sibling check (QA finding X-1).** Sibling versions are compared only within the same project and
collection. A version stored for another project or collection never changes this project's evidence.

**Document identity (QA finding X-2).** A stored version is identified by its project, document identifier and version.
Two projects may hold documents with the same identifier and version; neither affects the other. Ingestion refuses a
duplicate only within the same project.

**Index and evidence identity (QA findings X-3, X-4).** Chunk and evidence identifiers include the project. Two projects
with the same document identifier and version have distinct chunks and distinct evidence identifiers. A hybrid index
refuses duplicate chunk identifiers rather than overwriting them.

**Accepted limitation Y-2 (WDS).** Superseded candidates competing within the 500-candidate window can displace valid current evidence on direct retrieval. Unavailable candidates consume positions within the 500-candidate window but do not consume final `top_k` output slots. On the specialist lookup path (`current_only`), superseded candidates inside the window are withheld, and the result is `no_match` when nothing else is eligible. On direct retrieval, superseded versions are returned flagged `superseded` and can occupy `top_k` slots, so a current version can be displaced; a caller that needs only current evidence must use the lookup path or filter the flags. Unavailable candidates inside the window give `failed` with `source_unavailable` notices when no valid candidate is accepted; if a valid candidate is accepted, the result is `ok` with a `source_unavailable` notice. No evidence is invented on either path. This is the approved prototype limit and not a guarantee of complete retrieval.