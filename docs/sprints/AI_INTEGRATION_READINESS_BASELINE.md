# AI Integration-Readiness Baseline and Compatibility Matrix (Stage 1A)

Status: Stage 1A record. Read-only inventory; no branch was merged, cherry-picked, reset or pushed.
Recorded: 2026-10-28, after WDS formal acceptance of AI-S10 offline engineering (`54d9867`).

## 1. Current integration branch

- Branch: `integration/ai-s01-s02-s03`. HEAD: `54d9867c6f59976b5d96aac4d883b561c416b58b`.
- Accepted AI-S10 engineering baseline: `4d28648432d9f24180051eb1a20c8ca2d9f4aab9`
  (`54d9867` is documentation only, recording the acceptance).
- All accepted AI-S01 through AI-S10 commits are ancestors of HEAD.
- `5dff462` (AI-S03, on `feature/ai-s03`) is an ancestor of HEAD.

## 2. Accepted sprint commits on this branch (AI-S01 to AI-S10)

| Sprint | Commits (short) |
|---|---|
| AI-1 to AI-4.1 | `aacba1b` `cdf2ed6` `74ec550` `829688e` `c159fac` |
| AI-S01 | `39199d2` `c1a0b15` |
| AI-S02 | `e7cfe43` `c43cda0` `2f16db0` (integration) `16607e6` (approval record) |
| AI-S03 | `5dff462` |
| AI-S04 | `ac1ef7e` `2988913` `6360590` `052d853` `33efaf1` |
| AI-S05 | `84812b0` |
| AI-S06 | `5350649` |
| AI-S07 | `cbec19a` `a0c0de9` |
| AI-S08 | `0a7bfee` `59e6818` `36bc9ec` `f01f76d` `f0fc850` |
| AI-S09 | `70d5906` `4e23c41` `3e79d01` `4d28648` (B-1) |
| AI-S10 | `211d308` `e274cf4` `7476ffa` `7528c53` `a7a83d4` `020e951` `0cb4c0b` `54d9867` |

Foundation increments also on this branch: `83a67d9` to `acd5c51` (Increment 2, phases A to F),
`8f49784` to `e80bf56` (Increment 3, Phase 0), `c78d38c` `740b169` `af37f7b` (Increment 3, Phase 1).

## 3. Foundation code and the AI read API

The Foundation AI read API (`ai-read/v1`) is **not** on this branch. It exists on other branches:

| Branch | `src/webdesk` files | AI read API (`src/webdesk/api/ai.py`) | AI read contract doc |
|---|---|---|---|
| `integration/ai-s01-s02-s03` (HEAD) | 49 | **absent** | absent |
| `feature/foundation-phase-2` (`5ac26a1`) | 57 | present | not checked |
| `feature/foundation-phase-3` (`f1f2a74`) | 64 | present | not checked |
| `feature/foundation-phase-4` (`8d5b039`) | 60 | present | present (`docs/AI_FOUNDATION_READ_CONTRACT_v1.md`) |
| `feature/increment-1-foundation` (`3a38685`) | 57 | present | present |
| `claude/wds-integration-readiness-af19ec` (`e1f0e84`) | 56 | absent | absent |

Consequence: a single integration baseline is not yet established. Bringing the Foundation AI read API onto this
branch requires a WDS integration decision (merge or cherry-pick). None has been made here.

## 4. The documented Foundation read contract (`ai-read/v1`)

Source: `docs/AI_FOUNDATION_READ_CONTRACT_v1.md` on `feature/foundation-phase-4` (read-only).

Available endpoints (all `GET`, header `Authorization: AI-Principal <token>`, header `X-AI-Contract-Version: ai-read/v1`):

1. `/v1/ai/runs/{run_id}` (run metadata)
2. `/v1/ai/runs/{run_id}/project` (project metadata)
3. `/v1/ai/runs/{run_id}/source-versions` (readable source-version metadata, paged; limit 1 to 100)
4. `/v1/ai/runs/{run_id}/source-versions/{id}/segments` (paged; limit 1 to 200; text cut to 4,000 characters with `text_truncated`)
5. `/v1/ai/runs/{run_id}/source-versions/{id}/content` (stored bytes, at most 10 MiB)

Read rules: a version is readable only if the bound human may read it, it is not quarantined, it is not restricted,
and its project equals the principal's project. Cross-scope identifiers return `404`.

Explicitly excluded in v1: every write method; AI result persistence; requirement and evidence IDs; citations;
governance status; restricted and quarantined content; specialist routing; clarification; approval; user, membership
and grant operations; requirement, evidence and analysis-result tables (not in the Foundation schema).

## 5. Compatibility matrix for the integration-readiness items

| Directive item | Foundation surface (ai-read/v1) | Status |
|---|---|---|
| Operator identity | Human session on Foundation; AI principal issued per run (human route) | Available (Foundation side); engine receives only the AI principal |
| Project access | `GET /v1/ai/runs/{id}/project` | Available (read only) |
| Source and collection authorisation | Source-version list applies read rules; no explicit collection-authorisation object | Partial: read rules available; explicit collection allowlist not in contract |
| Requirement revisions | No requirement tables in the Foundation schema (contract section 12) | **Unavailable** |
| Authoritative specialist selection confirmation | Specialist routing and approval excluded in v1 | **Unavailable** |
| Execution grants | Not in contract | **Unavailable** |
| Durable run references | `GET /v1/ai/runs/{id}` (run id, revision, state, is_stale) | Available (read) |
| Audit events | Written by Foundation on AI routes; not exposed to the engine | Unavailable to engine |
| Review and approval persistence | Excluded in v1 | **Unavailable** |
| Verified source provenance | Not in contract; `content_hash` is never returned | **Unavailable** (fail closed) |

## 6. Missing or unavailable Foundation routes (to coordinate with the Foundation owner)

- Requirement read and revision routes.
- Collection-authorisation read route.
- Specialist-selection confirmation and execution-grant routes (authoritative).
- Approval and review persistence routes.
- Verified-provenance route (source hash or verified-evidence reference suitable for `EVIDENCE_BACKED`).
- Audit-event read route for the engine (if the engine is to reference durable audit).

None of these is invented in this repository. The engine treats each as unavailable and fails closed.

## 7. Separate branches (not integrated; not assessed for merge)

- `claude/ai-engine-contract-alignment-834e49` (`967d895`): a separate `src/webdesk_ai` increment-2 package
  (`a8188b9` and follow-ups). It does not contain B-1 or the SOW fingerprint change.
- `claude/webdesk-ai-engine-af7c07` (tip `af37f7b`, Increment 3 Phase 1 A2): **already an ancestor of HEAD** (integrated earlier).
- `feature/specialist-*` (M1 sprint, `5122012`): specialist branches; not on HEAD.
- `claude/p2-independent-qa-e1b03d`, `feature/foundation-phase-2`: Phase 2 cluster evidence.

These are recorded for WDS integration decisions. None is treated as accepted engineering for this baseline.

## 8. Unrelated untracked files (preserved, not committed)

- `ai_engine/tests/test_ai_s02_s04_acceptance_distinctions.py`, `_boundaries.py`, `_integration.py` (Foundation tests, 67 collected).
- `docs/AI_FOUNDATION_READ_CONTRACT_AND_READINESS_2026-10-26.md`, `docs/AI_S02_S04_FOUNDATION_ADAPTER_GAP_AND_DESIGN_PROPOSAL.md`.
- `docs/sprints/AI_S05_ENGINEERING_CLOSURE_RECORD.md`, `AI_S05_S10_MASTER_SPRINT_PLAN.md`, `AI_S06_HANDOFF_FROM_AI_S05.md`.
- `docs/sprints/AI_S10_EVALUATION_ACCEPTANCE_SPRINT_SPEC.md` (governing spec; untracked; amended in place 2026-10-28).

## 9. Governance-fingerprint gap (FP-01, added at QA re-review of `3f6f66d`)

- Gap: an estimate with no `governance_fingerprint` is still used as authoritative by the draft SOW, supplies
  values, and raises no integrity finding. B-1 (`4d28648`) closed only the case where the fingerprint names a
  different governance review.
- Evaluation: `FP-01` is an **open limitation** (`fp01_null_fingerprint_is_authoritative`). It passes only while the
  gap is present. When the gap is closed, the scenario reports FAIL and must be reclassified; it is not a PASS.
- Required live behaviour (WDS confirmed): an estimate without an authoritative fingerprint must not be treated as
  current or authoritative in a draft SOW; it may be kept only as provisional or diagnostic data with explicit
  unresolved status.
- Status: **not fixed**. Live integration acceptance stays blocked until enforcement is independently demonstrated.
  Smallest compatible upstream correction: the AI-S09 SOW path must withhold authoritative values when the estimate
  has no fingerprint, and raise an integrity finding. Requires WDS approval because it changes AI-S08/AI-S09 behaviour.
