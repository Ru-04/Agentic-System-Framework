# Specialist integration evidence (26 October 2026, uncommitted)

Baseline: `SPECIALIST_INTEGRATION_REPORT_2026-10-26.md`. Documented findings there are not re-verified here unless marked **[verified today]**.

**Scope rule:** no live research, no vendor retrieval, no real client data, no registry migration, no commit, no push, no unauthorized execution.

## A. Current-head test evidence or execution blocker

### A1. What was checked today (metadata only; nothing executed)
| File in the webdesk `.venv` | Size (bytes) | Result |
|---|---|---|
| `Scripts/pytest.exe` | 47,104 | Denied (error 4551) |
| `Scripts/mypy.exe` | 47,104 | Denied (error 4551) |
| `Scripts/ruff.exe` | 26,103,296 | Ran successfully at `2630ab6` and later |
| `Scripts/python.exe` | 274,424 | Not run. It is the interpreter behind `uv run`; running it to get around the block would be a bypass, so it was not used |

The integration worktree `.venv` contains a `pytest.exe` and `mypy.exe` of the same size (47,104). They ran successfully there.

### A2. Diagnosis
- **Denied operation:** launching `pytest.exe` and `mypy.exe` from the webdesk `.venv`. The error is Windows Application Control error 4551 ("An Application Control policy has blocked this file").
- **Classification:** environment policy. Not filesystem access (the files exist and are readable). Not test configuration (the tests have not started). Not a subprocess restriction in the repository (the same class of launcher runs elsewhere).
- **Unverified cause:** the policy appears to block specific launcher files by path, hash or publisher. The identical-size launcher in the integration worktree ran. The exact rule is not visible to this session, so no further conclusion is made.
- **Not done:** no bypass, no alternative interpreter, no policy change, no copied binary, and no retry of the blocked executables (per your decision QA-01 and the 26 Oct decision not to retry).

### A3. Current-head execution status
- Webdesk `pytest tests/unit` and `mypy src/webdesk` at `2630ab6` or later: **NOT EXECUTED — APPLICATION CONTROL ERROR 4551.**
- Historical results are not current-head evidence: 536 unit tests and strict mypy were last verified at `e3ba3b7`.

### A4. Exact commands for an authorized environment
Run from the webdesk worktree at the commit being accepted (`git rev-parse HEAD` must be recorded first):
```bash
uv sync --extra dev
uv run --extra dev pytest tests/unit -q
uv run --extra dev mypy src/webdesk
uv run --extra dev ruff check src tests migrations
uv run --extra dev ruff format --check src tests
```
Integration and committed tests need a scratch database, which must be created and dropped by the operator:
```bash
uv run --extra dev pytest tests/integration tests/committed -q -p no:warnings
```
Record the commit hash, the output and the environment used for each run.

### A5. Authorized alternative
- None is available to this session.
- The GitHub `specialist-ci` workflow runs `ruff`, `mypy` and `pytest tests/unit` on a pushed commit. This is the first authorized route. It needs the push, which is deferred.

## B. Specialist contract compatibility proposal (v0.2, proposal only)

### B1. Audit: WebDesk contract vs AI Engine contract (interfaces read only)
| Element | WebDesk (`src/webdesk/specialists/contract.py`) | AI Engine (`ai_engine/src/ai_engine/specialists/base.py`, `contracts/specialist.py`) |
|---|---|---|
| Versioning | `CONTRACT_VERSION = "1.0.0"` in every output | No version field in the base protocol; output models carry schema fields |
| Input | `SpecialistInput`: request id, workspace, specialist id, requirement ids, evidence refs, task. `extra="forbid"` | `SpecialistTask` and `SpecialistContext` (project, requirements, evidence lookup) |
| Output | `SpecialistOutput`: status (`completed`, `incomplete`, `failed`), findings with citations, unknowns | `SpecialistInvestigationResult`: requirement ids, claims, candidate solutions, evidence, conflicts, review state |
| Evidence | `EvidenceRef` with workspace, source id and locator | Evidence records with `evidence_id`, `evidence_kind` (for example `synthetic_mock`) |
| Authority | `Action` allowlist; forbidden actions refused | `PermissionDeniedError`; per-task evidence allowlist |
| Confidence | None | Evidence status (`UNVERIFIED`, `CONFLICTING`, …) |

**Gaps:**
1. The output shapes do not match. A bridge is needed in both directions.
2. WebDesk has no confidence field. AI Engine has evidence status but no numeric confidence.
3. The AI Engine uses `evidence_status` values that WebDesk does not define.
4. Shift4Shop legacy identifiers are handled differently (WebDesk alias; registry legacy name).

### B2. Proposed compatibility contract (v0.2)
- **Versioned envelope:** `specialist_contract_version` (currently 1.0.0 in WebDesk) plus `adapter_contract_version` (ARCH-02, v0.1).
- **Seven canonical categories:** `shopify`, `shift4shop`, `wordpress_woocommerce`, `bigcommerce`, `magento_adobe_commerce`, `standalone_applications`, `middleware_applications`. Exactly seven. Keep all seven in every matrix.
- **Capability IDs and registry version:** each output carries `capability_id` (for example `CAP-SHOPIFY`, `CAP-3D-CART-SHIFT-SHOPIFY` as a legacy alias for `shift4shop`) and `registry_version` (the registry file version). The alias maps to the canonical id; the alias is never emitted as a new id.
- **Requirement and evidence references:** `requirement_ids` (from the workspace) and `evidence_refs` (workspace, source id, locator, content hash). Output cites only admitted evidence.
- **Investigation status:** `completed` only with DIRECT evidence for each claim. `incomplete` for partial or unknown coverage. `failed` for retrieval or contract errors. No `feasible` status is emitted (feasibility is not determined).
- **Confidence and unknowns:** each finding carries `evidence_grade` (DIRECT, PARTIAL). Confidence is not numeric; unknowns are explicit strings. No finding without a grade.
- **Unsupported-source handling:** source not approved → `incomplete`, with the unknown "no approved evidence source". Source out of origin scope → excluded and counted. Instruction-like text → excluded and counted.
- **Provenance and citation:** each citation has source id, origin, retrieved-at, content hash and locator. A citation without a verifiable hash is rejected.
- **Authority:** the output never contains approval, permission, routing or requirement-acceptance actions. Those are refused (forbidden actions).

### B3. Migration rule
No migration without WDS approval. Both contracts stay in place until an adapter (ARCH-02) passes conformance tests.

## C. Seven-category readiness matrix

| # | Category | Canonical ID | Profile or agent | Real investigation | Readiness | Blocker |
|---|---|---|---|---|---|---|
| 1 | Shopify | `shopify` | WebDesk investigation (M1 S2); AI Engine synthetic agent | No (0 DIRECT evidence; no approved live source) | Engineering only | Approved source; human review 0/55 |
| 2 | Shift4Shop | `shift4shop` (legacy alias `CAP-3D-CART-SHIFT-SHOPIFY`) | WebDesk profile; AI Engine synthetic agent (`2988913`) | No | Foundation + synthetic | Official source (SRC-02) |
| 3 | WordPress & WooCommerce | `wordpress_woocommerce` | WebDesk profile; AI Engine synthetic agent (`ac1ef7e`) | No | Foundation + synthetic | Official source (SRC-01) |
| 4 | BigCommerce | `bigcommerce` | WebDesk profile; AI Engine synthetic agent (`ac1ef7e`) | No | Foundation + synthetic | Official source (SRC-01) |
| 5 | Magento / Adobe Commerce | `magento_adobe_commerce` | WebDesk profile; AI Engine synthetic agent (`2988913`) | No | Foundation + synthetic | Official source per edition (MAG-01) |
| 6 | Standalone Applications | `standalone_applications` | WebDesk profile and shared base only | No | Technology-neutral foundation | Technology not authorized (TECH-01) |
| 7 | Middleware Applications | `middleware_applications` | WebDesk profile and shared base only | No | Technology-neutral foundation | Product not authorized (TECH-02) |

No category is functional in the sense of real platform investigation. Profiles and synthetic agents are not evidence of capability.

## D. Official-source approval proposal (for WDS approval; nothing fetched)

Each row is a candidate. Ownership, domains and paths must be verified by WDS before approval. Default-deny stays in force.

| Platform | Domain (candidate) | Purpose | Collection boundary | Versions / editions | Risks | Approval status |
|---|---|---|---|---|---|---|
| Shopify | `shopify.dev` | Developer and API documentation | Named pages only; no crawling | API version; plan | Plan-dependent claims; API churn | Candidate, not approved |
| Shopify | `help.shopify.com` | Merchant help (plan and feature availability) | Named pages only | Plan tier | Plan pages blocked or transcribed content is not evidence (task rule) | Candidate, not approved |
| WooCommerce | `woocommerce.com` documentation | Plugin and extension documentation | Named documentation paths | WooCommerce version; WordPress; PHP | Extension-specific claims | Candidate, not approved |
| WordPress | `developer.wordpress.org` | Core developer documentation | Named paths | WordPress version | Core vs plugin distinction | Candidate, not approved |
| BigCommerce | `developer.bigcommerce.com` | API and platform documentation | Named paths | Plan; scopes; REST or GraphQL | Plan- and scope-dependent claims | Candidate, not approved |
| Shift4Shop | Not identified | Developer and platform documentation | None | Exact platform version | Source not verified | **Not identified** (SRC-02) |
| Magento Open Source | `devdocs.magento.com` | Developer documentation (Open Source) | Named paths | Open Source version | Not transferable to Adobe Commerce | Candidate, not approved |
| Adobe Commerce | `developer.adobe.com/commerce` | Developer documentation (Adobe Commerce) | Named paths | Adobe Commerce version | Not transferable to Open Source | Candidate, not approved |

Approval steps per source (SRC-01): verify ownership; list domains and paths; record editions and versions; state the retrieval method; record access and provenance limits; then WDS approves that entry.

## E. Developer assignment reconciliation

| Lane | Allocation (23 Oct) | Reported in chat | Status |
|---|---|---|---|
| Shopify agent and shared commerce interfaces | Developer A | — | Allocated |
| Shift4Shop | Developer B | — | Allocated; source missing |
| WordPress & WooCommerce | Developer C | — | Allocated; source missing |
| BigCommerce, then Magento / Adobe Commerce | Developer D | — | Allocated; source missing |
| Standalone Applications | **None** | BD (chat, 23 Oct) | **Proposed, not accepted** |
| Middleware Applications | **None** | BD (chat, 23 Oct) | **Proposed, not accepted** |

- BD is recorded as **proposed, not accepted**, because no acceptance evidence exists for either lane. Acceptance needs a WDS record.
- BD was also named in the 23 Oct management statement as the producer of the Sprint 1–3 work. That makes BD not independent for review purposes.
- Neither lane is counted as complete.

## F. Synthetic Foundation–AI–Specialist vertical slice

### F1. Minimum functionality
1. A WebDesk request built with the v0.2 envelope (synthetic data only).
2. An adapter call (ARCH-02) that passes workspace, actor and allowed actions to the AI Engine.
3. One specialist (Shopify, or one commerce specialist) that returns the WebDesk output shape with citations from a synthetic fixture.
4. Adapter checks: workspace, origin, instruction screening, forbidden actions.
5. A WebDesk-side audit record of the request and response hashes.
6. A conformance test that runs the same request through the stub and the real specialist, and compares output shape.

### F2. Readiness
- Items 1, 4 and 6 can be prepared now. Item 2 needs the adapter, which is not implemented.
- Item 3 needs a synthetic fixture. A fixture is provided in section G.
- No vendor source is involved. The slice is synthetic end to end.
- Not verifiable until the webdesk tests can run (A3).

## G. Human-review worksheet and procedure (55-pair Shopify relevance review)

**Status:** worksheet prepared; **0 of 55 labels returned.** No review results are recorded here.

Procedure:
1. The reviewer is PG, or another independent reviewer named by WDS. The reviewer must not have produced the reviewed work.
2. The reviewer receives the reading file through the approved WDS channel. It is not transferred from this session.
3. The reviewer fills the label CSV: `label` (DIRECT, PARTIAL, IRRELEVANT), `reviewer`, `confidence`, `uncertain`, `comment`.
4. The importer (`webdesk.evidence.evaluation_cli`) refuses duplicate, unknown or malformed rows.
5. Metrics are computed only after all 55 labels are present. A partial set is not evaluated.
6. The reviewer signs the acceptance record personally.

Pass criteria (proposed for WDS approval, not yet approved): precision and recall on DIRECT labels meet the threshold in the evaluation plan. Thresholds are not changed by this document.

## H. Remaining WDS approvals needed
1. Approve or amend each source in section D, one entry at a time.
2. Name the Shift4Shop official source (SRC-02).
3. Name the technology for Standalone Applications and the product for Middleware Applications.
4. Confirm or reject BD for the Standalone and Middleware lanes, with a dated record.
5. Approve the v0.2 compatibility proposal, or revise it.
6. Approve the vertical-slice scope in section F.
7. Name the independent reviewer for the 55-pair review (PG or other).
8. Provide an authorized environment or approve a CI run for current-head tests (A4, A5).
