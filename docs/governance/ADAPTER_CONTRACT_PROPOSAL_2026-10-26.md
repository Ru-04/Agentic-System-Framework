# Minimum viable adapter contract and plan (proposal, 26 October 2026)

**Status: proposal only. Not implemented. Not authorized for migration.** WDS must approve the architecture before any adapter code is written. No existing framework is merged or replaced by this document.

## 1. Proposed architecture (WDS direction)
- WebDesk is the primary application platform. It owns authentication, authorization, workspace isolation, governance, audit and workflow state.
- AI Engine provides reusable specialist investigation components. It is never the authority for access, approval or workflow.
- Integration happens only through explicit, versioned adapters.
- Every specialist execution passes WebDesk security and authority controls before and after the call.
- No duplicate specialist implementations. Each platform has one implementation, chosen by WDS.

## 2. Minimum viable adapter contract (version 0.1)
The adapter is the only path between WebDesk and an AI Engine component. It is versioned, and both sides check the version.

**Request (WebDesk → adapter)**
| Field | Type | Rule |
|---|---|---|
| `adapter_contract_version` | string | Must equal `0.1`; otherwise refuse |
| `request_id` | string | Unique; used for audit |
| `workspace_id` | string | Set by WebDesk from the authenticated session, never by the component |
| `actor_id` | string | The WebDesk user who authorized the run |
| `specialist_id` | enum | One of the seven catalog ids; the legacy Shift4Shop alias is mapped, not accepted as new |
| `requirement_ids` | list | Must exist in the WebDesk workspace |
| `task` | string | Bounded length; treated as data |
| `evidence_refs` | list | Only WebDesk-admitted evidence; origin and workspace checked by WebDesk |
| `allowed_actions` | list | Subset of `read_evidence`, `propose_candidates`, `declare_unknowns` |

**Response (adapter → WebDesk)**
| Field | Type | Rule |
|---|---|---|
| `adapter_contract_version` | string | Must equal `0.1` |
| `request_id` | string | Must match the request |
| `status` | enum | `completed`, `incomplete`, `failed` only |
| `findings` | list | Each cites WebDesk-admitted evidence; statements are unverified proposals |
| `unknowns` | list | Required when status is not `completed` |
| `component_version` | string | Recorded for audit |

**Refused, always:** approve, grant permission, modify routing, accept an inferred requirement, write a requirement, resolve a blocker (the forbidden actions in `authority.py`).

## 3. Controls the adapter must enforce (not delegated to the component)
1. Workspace: the component receives only the workspace WebDesk sends; any output for another workspace is discarded and recorded.
2. Origin: evidence reaches the component only from sources the platform's approved allowlist permits. The stricter rule of the two frameworks applies.
3. Instruction screening: retrieved text is screened before it is used, and instruction-like text is excluded.
4. Authority: actions outside `allowed_actions` are refused before the call.
5. LLM: the LLM port stays disabled (D09). The adapter refuses any request that would enable a provider.
6. Audit: request, response hash, versions and refusals are written to the WebDesk audit trail.
7. Failure: component errors map to `failed`, with no retry that would change the evidence set.

## 4. Implementation plan (for WDS authorization; not started)
1. Write the adapter contract as a versioned schema in WebDesk, with contract tests (no AI Engine code yet).
2. Build a stub component that returns fixed responses; test the adapter with it.
3. Connect one AI Engine capability (proposed: the AI-S04 synthetic commerce agents, for one platform) behind the adapter, with synthetic evidence only.
4. Run the AI Engine tests unchanged, and the WebDesk tests unchanged, after each step.
5. Only after WDS approval: add a second platform, then decide on the duplicate implementations.

## 5. Validation against existing controls and decisions
| Control or decision | Preserved? | How |
|---|---|---|
| WebDesk contract and harness (`src/webdesk/specialists`) | Yes | Adapter sits outside; no change proposed |
| AI-S01 P0-1, P1-2, P1-4 fixes | Yes | No change to `execution.py`, `workflow.py`, `operator.py` proposed |
| AI-S02 ApprovalGuard and LLM port | Yes | Adapter keeps the port disabled |
| AI-S03 retrieval and workspace scoping | Yes | Adapter applies WebDesk origin rule as well |
| Origin allowlist (default deny) | Yes | Adapter refuses unapproved origins |
| D09 (no live model) | Yes | Refused by the adapter |
| D08 (evidence sources approved by WDS) | Yes | No source fetched; default deny |
| Frozen 9-sprint baseline | Yes | No sprint or scope changed |
| Existing tests | Expected unchanged | Not run at the current WebDesk head (blocked; see the test register) |

## 6. Risks
- Two contracts must stay in sync. Mitigation: versioned adapter schema and contract tests on both sides.
- Duplicate platform code. Mitigation: a WDS decision per platform before any adapter is connected.
- Adapter becomes a bypass. Mitigation: all component calls are made only through the adapter, enforced by a test that searches for direct imports.
- Testing is blocked at the current WebDesk head. No adapter can be verified until that is resolved.
