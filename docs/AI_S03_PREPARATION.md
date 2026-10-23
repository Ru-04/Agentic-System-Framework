# AI-S03 Preparation: RAG and Evidence Retrieval (not started)

Status: **NOT STARTED.** This document prepares the sprint. It contains no implementation, makes no
provider call, and reads no client data. Approval-dependent AI-S03 implementation must not begin until the
specifications and source-access decisions below are confirmed.

## What is confirmed

- AI-S03 is named "RAG & Evidence Retrieval" in the AI-02 Core Intelligence milestone.
- The engine has no retrieval layer today. The AI-S02 contracts and the agents use only segments supplied
  by the caller. They make no retrieval call.
- Evidence status is set by the retrieval layer, not by AI output. This is the AI-S01 governance position 1
  (`AI_ENGINE_AI51_REMEDIATION.md`, section 6). AI-S02 keeps AI output at `proposed_pending_human_review`.
- Retrieval direction, from the decision register (`WebDesk_Agentic_Requirement_Platform_Specs/DECISION_REGISTER.md`,
  D-02, partial configuration): internal, access-controlled RAG first, then approved live vendor documentation
  for gaps, staleness and version-sensitive questions. Official read-only access only.
- Source allowlist C-06 is OPEN, and the default is deny (`AI_ENGINE_IMPLEMENTATION_PLAN.md`).
- The current Shopify evidence is synthetic mock only, typed `synthetic_mock`.
- Production LLM or RAG use is NOT READY (`AI_ENGINE_IMPLEMENTATION_PLAN.md`, the readiness assessment).

## Not confirmed: the master sprint plan

The approved master sprint plan that defines AI-S03 is not in this repository. The searches covered the
repository docs, the specifications folder and the AI Engine plan. The AI-S03 scope above comes from the
WDS acceptance text, not from a plan document I could read.

WDS action: name the master sprint plan file, or supply it. AI-S03 scope, acceptance criteria and gate must
be checked against it before any work starts.

## Decisions required before implementation

1. **Master plan.** Locate or supply the approved master sprint plan (above).
2. **Source allowlist (C-06).** Decide which sources AI-S03 may retrieve from, and confirm default-deny.
3. **Live vendor documentation.** Decide whether live vendor retrieval is in AI-S03 at all. D-02 places it after
   internal RAG. Live retrieval needs official read-only access and its own approval.
4. **Access control for internal retrieval.** Retrieval over client material must honour Foundation
   authorisation. The AI Engine cannot grant that. Foundation must supply the trusted actor and project read
   ports (AI-S01 section 9) before any internal retrieval runs on real data.
5. **Evidence status policy.** Confirm that the retrieval layer sets evidence status and AI output cannot.
   This is AI-S01 governance position 1, still awaiting WDS confirmation.
6. **Provider for any embedding or model step.** Not decided. No provider is approved (AI-S02). Any model step
   in retrieval needs the same approval as real-provider evaluation.
7. **Input and context size.** The AI-S02 input size limit (decision 7) applies to retrieved context as well.
8. **Synthetic-first testing.** Confirm that AI-S03 tests run on synthetic corpora only, as AI-S02 did, until a
   test-access policy is approved.

## Dependencies on current work

- AI-S02 contracts (`contracts/semantic.py`): retrieved text would enter as untrusted segments, with the same
  exact-span provenance rules, so retrieved content can be cited but not treated as instructions.
- AI-S02 unresolved and disposition model (`llm_agents/common.py`): retrieved segments should use the same
  dispositions, so unsupported context is never reported as analysed.
- AI-S01 selection and attribution (`selection/operator.py`): retrieval results that feed a selection must keep
  the operator attribution and fingerprint rules.
- Branch position: AI-S03 work would start from `feature/ai-s02` or `feature/ai-engine` only after the branch
  decision in `AI_BRANCH_RECONCILIATION_AI_S01_AI_S02.md`.

## Explicitly out of scope until approved

- Any real provider call, including embeddings.
- Live vendor retrieval.
- Access to real client data or production Foundation.
- Automatic specialist execution.
- Any bypass of Foundation security controls.
