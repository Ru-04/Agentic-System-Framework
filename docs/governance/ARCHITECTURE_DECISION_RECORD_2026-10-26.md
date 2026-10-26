# Architecture decision record (26 October 2026)

**Decision (WDS Authorized Approver, reported in chat):** Approve WebDesk as the primary application platform with AI Engine capabilities connected through adapters, as proposed in `ADAPTER_CONTRACT_PROPOSAL_2026-10-26.md`.

## What this decision covers
- The architecture direction: WebDesk owns authentication, authorization, workspace isolation, governance, audit and workflow state. AI Engine provides reusable specialist investigation components. Integration only through explicit, versioned adapters. All specialist execution passes WebDesk security and authority controls.
- Adapter contract version 0.1 as the starting point for design.

## What this decision does NOT cover
- No destructive framework merge or replacement. Both implementations stay in place.
- No decision yet on which implementation keeps each platform, or on removing duplicate platform code. That needs a separate WDS decision.
- No adapter code is authorized for connection to production. Adapters remain non-production until WDS authorizes each step.
- No change to approved security controls, the frozen 4-milestone / 9-sprint baseline, or any acceptance status.
- No Sprint 4 work. No live model. No external retrieval. No Git push (deferred).

## Required before any adapter is connected
1. The adapter contract schema is written in WebDesk and tested (tests must be executed; the current webdesk head is blocked by Application Control error 4551).
2. Each platform's duplicate implementation decision is recorded.
3. Each evidence source is approved under the source register.
4. Independent review by PG, with the declaration completed by PG personally.

## Status
Approved direction. Implementation: not started.
