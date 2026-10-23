# Master Sprint Status Register: AI-02 Core Intelligence

Status date: after the WDS decision "Close AI-S01 and Start AI-S03". Authoritative scope: WebDesk Framework v2.0
(16 October 2026). Master plan: AI-01 through AI-07 and AI-S01 through AI-S10.

This register separates accepted engineering work from uncompleted production and integration requirements.

## Sprint status

| Sprint | Scope | Status | Baseline | Gate evidence |
|---|---|---|---|---|
| AI-S01 | P0 security remediation (AI-5.1), trust boundaries, evidence isolation, operator selection integrity | **Engineering APPROVED / CLOSED** (limited; isolated engineering implementation; not production authorisation or production-security certification) | `feature/ai-engine` `15d660a` (review fix `c1a0b15`) | 388 passed; ruff and strict mypy clean |
| AI-S02 | LLM port, guarded structured calls, LLM-backed intake and semantic agents, typing remediation | **Engineering APPROVED** (engineering implementation only; not production authorisation). Real-provider evaluation **PENDING** | `feature/ai-s02` `c43cda0` | 958 passed at acceptance; ruff and strict mypy clean |
| AI-S03 | RAG and evidence retrieval (shared infrastructure for all seven specialist categories) | **IN DEVELOPMENT** (isolated, non-production). **Not accepted.** Independent review FAIL (nine findings) fixed with regression tests; re-review requested | `feature/ai-s03` (new worktree), on `feature/ai-engine` `15d660a` plus AI-S02 changes, uncommitted | 1190 passed (388 AI-1 and AI-S01, 573 AI-S02, 222 AI-S03, 7 Y-1 regression); ruff and strict mypy clean |
| AI-S04 | Not started | **NOT STARTED.** May not start before AI-S03 acceptance | none | none |

## Accepted engineering work versus outstanding requirements

**Accepted engineering work.** AI-S01 (limited engineering closure) and AI-S02 (engineering approval). Both are
engineering acceptances on the evidence recorded in their records.

**Not accepted, and not implemented.**
- Foundation-authenticated operator identity and authorisation (AI-S01 dependency 1; AI-S02 approval authority).
- Trusted project and lifecycle status, and Foundation-controlled permission and approval services (AI-S01 dependencies 2 and 3).
- Untrusted specialist process isolation (AI-S01 F2 and F10; AI-S02 section 5). Required before any untrusted code runs.
- Pending governance rulings: A-4, C-15, and governance position 1 (AI output may not assert verified status).
- Real LLM provider evaluation (AI-S02). No provider is approved; no provider call has been made.
- Real WDS documents and real client data for retrieval. Each needs collection-level approval.
- Live vendor research. Needs an approved domain allowlist, which is currently empty.
- Production deployment, persistence of retrieval data, and the pgvector index. AI-S03 describes the contract only.
- Source approval, retention and lifecycle policies. These must be supplied by WDS and not invented.

## WDS decisions recorded

1. AI-S01 Engineering: APPROVED / CLOSED (limited), baseline `15d660a`.
2. AI-S02 Engineering: APPROVED, baseline `c43cda0`. Real-provider functional evaluation: PENDING.
3. AI-S03 development: AUTHORISED for isolated non-production implementation and testing. Scope: the 13 required
   functions, the synthetic-only source boundary, and seven-specialist compatibility.

## Milestone register (AI-02 Core Intelligence)

| Milestone item | Status |
|---|---|
| AI-S01 Engineering | APPROVED / CLOSED (limited) |
| AI-S01 production-security certification | NOT CLAIMED |
| AI-S02 Engineering | APPROVED |
| AI-S02 Real-provider evaluation | PENDING |
| AI-S03 development | IN PROGRESS (isolated) |
| AI-S03 acceptance | NOT ACCEPTED |
| AI-S04 | NOT STARTED |

## Remaining blockers

Foundation (not closable by the AI Engine): operator identity and authorisation; trusted project and lifecycle status;
permission and approval services; the persistence and audit store; the authoritative document-access port; source
collection approvals for real data.

Governance (WDS rulings): A-4; C-15; governance position 1; the source allowlist for live research (C-06, default deny);
retention and lifecycle policies for sources; the authoritative v2.0 scope document, or confirmation of the seven
specifications to reconcile; and the approved master sprint plan file. That file is not present in this repository. See
`AI_S03_PREPARATION.md`.

Engineering (open, in later sprints): a real embedding adapter (needs approval) and recalibration of the vector threshold
for it; pgvector execution (needs a database under approval); process isolation for untrusted specialists.

## Next authorised tasks

1. Independent re-review of AI-S03 after the nine fixes (requested). Read its verdict, then update QA plan section 6.
2. A local commit of the AI-S03 work, only on separate WDS authorisation.
3. AI-S03 acceptance, only on a WDS decision after review.

Not authorised: push or merge of any branch; real client documents; unrestricted vendor research; real LLM providers;
production deployment; AI-S04 before AI-S03 acceptance.
