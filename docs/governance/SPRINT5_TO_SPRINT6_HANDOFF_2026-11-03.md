# Sprint 5 to Sprint 6 handoff (3 November 2026)

## 1. Status handed over

- **Sprint 5:** formally accepted under the WDS-approved revised MVP evaluation scope. See `SPRINT5_FINAL_CLOSURE_RECORD_2026-11-03.md`.
- **Sprint 5 does not authorize Sprint 6 work.** Sprint 6 Step 2 remains gated, for the reasons in Section 4.

## 2. Accepted scope and limitations

Accepted: requirement-level routing and refusal behaviour for the seven registered specialists, on 36 synthetic scenarios (v8). The thresholds accepted are listed in `SPRINT5_SCOPE_AMENDMENT_AND_CLOSURE_2026-11-03.md`, Section 4.

Not accepted, and not to be read as passed:
- Real-citation correctness on real retrieval (not measured by the harness).
- Shopify human relevance and rater agreement (superseded; no human labels exist).
- Feasibility, practical suitability, evidence relevance beyond BigCommerce.
- Vendor accuracy. The results are synthetic fixtures, not platform evidence.

## 3. Exact SHAs

| Line | Ref | SHA | Notes |
|---|---|---|---|
| Specialist, tested code | `claude/sprint5-specialist-evaluations` | `b885ad740aac7a7dccacbc7b250cd919069c7abd` | CI run `41423137005`: success |
| Specialist, governance head | same branch | `74608aaa0a852d52622307429421a75bccd0491b` | Docs only over `b885ad7`. Pushed. CI run `41599741809` pending at time of writing |
| Foundation main | `feature/increment-1-foundation` | `3a38685` | Migration head `0041_ai_read_v1` |
| Foundation integration candidate | `feature/foundation-integration-p2-p7` | `5974d59` | Migration head `0059_int_mark_inputs_fence`. Candidate for D-13 re-QA |
| AI Engine line A (target, D-4) | `claude/ai-engine-contract-alignment-834e49` | `967d895` | Migration head `0041` |

Local-only branch: `integration/sprint6-step2-prep` (worktree `.claude/worktrees/sprint6-step2`) at `c77d0f9`, on base `5974d59`. Not pushed. Holds the Step 2 preparation document and D-13 request.

## 4. Sprint 6 blockers (precise)

| ID | Blocker | Owner | Needed to clear |
|---|---|---|---|
| D-13 | Independent re-QA of candidate `5974d59` (Foundation security requirement) | PG, or a WDS-named independent reviewer with a separate explicit disposition | A personally attributable record: reviewer, independence statement, scope, SHA `5974d59` (or a later SHA PG reviews), findings, decision. Fields in `docs/SPRINT6_D13_REVIEW_REQUEST.md` on `integration/sprint6-step2-prep` |
| D-10 | Ruling 5 approver, date and channel, recorded in the Foundation governance register | Foundation integration team, with the approver they name | A written register entry naming the actual ruling 5 approver. See Section 5 |
| D-1 | Approver, date and channel for `ai-read/v1` (D-AI-1 to D-AI-5) | WDS | Added to `GOVERNANCE_DECISION_REGISTER.md` |
| Step 2 | Foundation read endpoints against AI Engine line A, PostgreSQL integration tests | Engineering, after the above | Starts only after D-13 and D-10 clear |

The Sprint 5 PG exception does **not** clear D-13. D-13 is a separate Foundation security requirement.

## 5. D-10 coordination (for the integration team)

The Foundation register must name the actual approver of ruling 5. This is not the Sprint 5 approver. The WDS Authorized Approver's Sprint 5 decisions do not extend to it.

The earlier Foundation record (commit `c77d0f9`, local) states "AS, as designated by WDS management (chat, 2 November 2026). Not a personally signed approval". That wording is a WDS-reported designation and is not a signed approval. The integration team should confirm or correct it. It should not be copied into the Sprint 5 record.

**Draft message to send to the integration team (not sent by this record):**

> Sprint 6 Step 2 is gated on D-10 and D-13. For D-10, please add to the Foundation governance register the approver, date and channel of ruling 5, as applied to `feature/foundation-integration-p2-p7` at `5974d59`. Please confirm whether the earlier WDS-reported designation of AS is correct. The Sprint 5 approver is a separate decision and should not be used for ruling 5. For D-13, PG must provide a personally attributable re-QA record for `5974d59`, or WDS must make a separate explicit disposition. Step 2 will not start until both are recorded.

## 6. What must not happen

- No protected-branch merge of Foundation, AI Engine or specialist branches under Sprint 5 authority.
- No change to unrelated Foundation or AI Engine code for Sprint 6 without its own approval.
- No migration beyond the frozen head `0059` without its own approval (D-8).
- No production activation (D-11 accepts F-2 for non-production only).
