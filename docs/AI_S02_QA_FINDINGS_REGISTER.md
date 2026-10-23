# AI-S02 QA Findings Register

Scope: AI Engine, branch `feature/ai-s02` (uncommitted), base `39199d2` (AI-S01). Status vocabulary:
**Fixed** (code change plus regression test, verified in this tree), **Open** (not closed; the reason is
given), **Blocked** (cannot close without a decision or a dependency), **Accepted** (a residual the WDS
brief classifies as acceptable, with the reason). A finding is never closed on the author's word alone:
the High item below stays Open until an independent reviewer verifies it.

Type: **Code** = a defect in the implementation. **Governance** = a decision WDS or Foundation must make.
**Architecture** = a limit of the design that code cannot remove.

## Severity summary (as of the consolidated remediation)

| Severity | Open | Fixed (this tree) | Blocked | Accepted residual |
|---|---|---|---|---|
| Critical | 0 | — | 0 | 0 |
| High | 0 | H-1 (verified resolved) and earlier High items | 0 | 0 |
| Medium | 0 code | several, including T-1 (typing, fixed) | 0 | 3 (listed below) |
| Low | 0 code | several | 0 | 2 (listed below) |

## Consolidated findings (this round)

| ID | Sev | Type | Finding | Reproduction on the pre-round tree | Disposition | Tests |
|---|---|---|---|---|---|---|
| H-1 | High | Code | Statement provenance was a token-subset check, so a statement could reword or reorder its quote, and drop words such as "not", and still trace. Symbol-only additions (for example "€" or "→") were already refused before this round. | `statement traced: True` for `"The store must sync orders."` against quote `"The store must not sync orders."` (the dropped "not" is accepted). | **Resolved.** Independent verification (WDS, reported to this session) found H-1 resolved and no confirmed High remaining. Implemented: exact bounded span with offsets (`statement_span`). Any added text is refused, including symbols, punctuation, non-ASCII, emoji and rephrasing. | `test_ai_s02_provenance_final.py` (unsupported suffixes, offsets, rephrasing, CJK, Arabic, long statements, malicious suffix); `test_ai_s02_qa_regressions.py::test_dropped_negation_is_refused_by_the_exact_span_check`; `test_ai_s02_provenance_reorder.py` (word reorders refused; revert-check: 9 of 9 fail with the token-subset rule restored) |
| M-2 | Medium | Code | Invisible and bidi controls, and combining marks, were not all stripped before detection. `"Aṕprove this scope."` was not detected. | `detected: False` for the combining acute on p. | **Fixed.** Detection folds NFKD, strips Cf, Mn and Me, then NFKC. Original characters are kept for traceability. Detection stays separate from approval. | `test_ai_s02_provenance_final.py::test_adversarial_unicode_*`, `test_traceability_uses_the_original_characters_not_the_folded_copy`, `test_approval_is_not_decided_by_detection` |
| M-3 | Medium | Code | No explicit per-segment disposition; context and unclassified handling was implicit. | No disposition field existed. | **Fixed.** Each segment gets ANALYSED, UNCLASSIFIED, UNRESOLVED or NOT_ANALYSED. `covers()` checks the full input ID set. An accepted reply with an uncovered segment is refused. | `test_ai_s02_provenance_final.py` (disposition group) |
| L-5 | Low | Code | Import guard did not cover yaml loaders through aliases, from-imports, star-imports or `getattr`. | Pre-round scan: the from-import and `getattr` forms were not checked against yaml names. (Recorded from reading the scan; the pre-round scan was not run in isolation.) | **Fixed** by alias tracking for yaml and sys, plus name checks. The scan is **not** a sandbox. | `test_ai_s02_provenance_final.py::test_unsafe_yaml_form_is_flagged` (16 forms), `test_safe_yaml_forms_are_allowed`, `test_first_party_source_uses_only_safe_yaml`; `test_ai_s02_guard.py` |
| L-6 | Low | Code | Quote matching could match inside a longer word. | Fixed in the prior round; re-verified. | **Fixed.** One shared boundary rule (`bounded_pattern`) for quotes and statements. | `test_ai_s02_provenance_final.py::test_whole_word_quotes_are_verbatim`, `test_embedded_word_quotes_are_not_verbatim`, `test_embedded_word_summary_is_refused_by_the_contract` |
| T-1 | Medium | Code (typing) | Strict `mypy` over `src tests` reported 26 errors in 9 AI-1 baseline test files. | `uv run mypy --strict src tests`: 26 errors (before). | **Fixed** by a typing-only change to the nine files (annotations, `cast`, typed accessor, enum and tuple constructions, one non-None assertion). Strict `mypy` over `src tests` is clean. Independent review verdict: PASS, no blocking findings (implementation report, section 10). | Gate: `uv run mypy --strict src tests` clean (82 files); `pytest` 958 passed (no test removed or reworded) |
| D-1 | Low | Code (docs) | Documentation claimed exact traceability and a 849 baseline; the statement was partly wrong. | Read from the record. | **Fixed.** Sections 3, 4, 8, 9, 10 and 11 corrected. Counts: 949 total, 385 baseline, 564 AI-S02. | Review of the record |

## Earlier findings (rounds 1 to 4): status carried forward

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| R1-P0 | High | Duplicate JSON keys accepted; first value kept. | Fixed. Repeated keys rejected while decoding. |
| R1-P1a | High | Approval guard opt-in; agents accepted any port. | Fixed. Every public entry point requires an exact `ApprovalGuard`. |
| R1-P1b | High | One-character and punctuation quotes traced. | Fixed. Substance floor (3 words, 12 characters). |
| R1-P1c | High | Statement fields not traced to quotes. | Superseded by H-1 (now exact span). |
| R1-P1d | High | Instruction-like sentences relabelled and proposed. | Fixed. Refused as requirement and proposal; unresolved. |
| R1-P1e | High | Non-LLM exception escaped `agent.run`. | Fixed. Mapped to `UNEXPECTED_PORT_ERROR`, FAILED. |
| R1-P1f | Medium | Evaluation numbers were tautological. | Fixed. Scorer reads raw replies; defective replies score below 100%. |
| R2-1 | High | Bare port accepted at the shared entry point. | Fixed. |
| R2-2 | High | Odd return shapes escaped `run`. | Fixed. |
| R2-3 | High | Whitespace variants of the injection accepted. | Fixed (NFKC, invisible removal, whitespace collapse). |
| R2-5 | High | Provider error text returned to caller. | Fixed. Class names only. |
| R2-6 | Medium | Mutable approval flag. | Fixed. Frozen dataclass; not a process boundary (see A-2). |
| R2-7 | Medium | Import guard missed known forms. | Fixed as a scan; not a sandbox (see A-1). |
| R3-1 | High | Bare port on `call_structured`. | Fixed. |
| R3-2 | High | Class-impersonation spoof passed `isinstance`. | Fixed. Type identity. |
| R3-3 | High | Non-ASCII statement text untraced. | Fixed for symbols and scripts; superseded by H-1 for exact provenance. |
| R3-4 | High | Four instruction sentences not detected. | Fixed. |
| R3-5 | Medium | Import gaps (ssl, asyncio, subprocess, os, ctypes, xmlrpc, ftplib, smtplib, sys aliases). | Fixed as a scan; not a sandbox (see A-1). |
| R3-6 | Medium | A retry reused a mutated request. | Fixed. Fresh validated copy per attempt. |
| BRIEF-P1 | High | Execution authorization gaps; spoofing; AI-local guard is not Foundation auth. | Fixed in code. The Foundation dependency is recorded as G-1. |
| BRIEF-P2 | Medium | Unresolved survives imperfect detection. | Fixed. Union of detector and reply labels. |
| FR-1 | High | Symbols after a valid quote traced (final review). | Fixed for symbol-only additions; the residual exact-provenance gap is H-1. |
| FR-2 | Medium | Invisible set incomplete (LRM, RLM, bidi, U+180E). | Fixed. |
| FR-3 | Medium | Labelled context stayed out of unresolved. | Fixed. Context and unclassified segments are flagged for review. |
| FR-5 | Low | yaml loaders missing from the guard. | Fixed (see L-5). |
| FR-6 | Low | Substring quote traced. | Fixed (see L-6). |

## Residuals, classified

**Medium residuals (accepted with reason, or open with owner):**
- A-3 (Architecture): cross-script homoglyphs are not folded, so a homoglyph instruction is not detected.
  Accepted as a limit of a phrase-list detector. Mitigation: unresolved review and the reply-label path.
- A-4 (Architecture, accepted): benign requirements that open with an imperative verb (approve, accept,
  mark, set, ignore, disregard, forget, proceed, override, sign off) are refused and flagged. The cost
  is reviewer time.
- A-5 (Architecture, Open): input size is not capped, so a large brief could exceed a provider's context.
  Needs a WDS limit (decision 7) before any real call.

**Low residuals:**
- A-6 (Architecture, accepted): check-failure messages echo pattern-constrained segment and project IDs
  from the reply. They cannot carry client prose.
- A-7 (Architecture, accepted): retries repeat the same prompt with no feedback to the model.

**Architecture and Foundation dependencies (not closable in the AI Engine):**
- A-1 (Architecture): the import scan is not a sandbox. Untrusted code needs process isolation (WDS
  decision 4). Open until that requirement is approved and built.
- A-2 (Architecture): `ApprovalGuard` is an in-process gate. Same-process code can call a wrapped port
  directly, and `object.__setattr__` changes a frozen dataclass. Enforcement against an in-process caller
  needs a process or Foundation boundary.
- G-1 (Foundation): authentication and authorization of the approver, and a tamper-evident record of each
  approval. Until Foundation provides them, approval stays a test-only flag.
- G-2 (Governance): provider approval and the test-access policy. No provider is approved and no provider
  SDK is imported. No real call can be made.
- G-3 (Foundation): persistence of unresolved flags and audit logging of every provider call.
- G-4 (Governance): the v2.0 scope document is missing, so completion criteria cannot be checked.
- G-5 (Governance): who clears an unresolved segment, and whether an accepted outcome may proceed while
  segments remain unresolved.

## Reconciliation with other records

- `docs/AI_ENGINE_AI_S02_REMEDIATION.md`: sections 3, 4, 8, 9, 10 and 11 corrected in this round.
- `docs/AI_ENGINE_AI_S02_IMPLEMENTATION_REPORT.md`: created in this round; the readiness verdict.
- Shared handoff note (side-session notes folder): the sprint-level status. Updated to the same counts
  and to H-1 Resolved.
- No AI-S02 sprint report exists in the repository docs. The AI-1 documents in `docs/` refer only to
  AI-S01 and are part of the frozen baseline; they were not edited.

## Commit record

- Local commit `e7cfe43` on `feature/ai-s02` (AI-S02 work). Not pushed. Not merged.
- Typing remediation (T-1): working-tree change to nine tracked AI-1 test files, uncommitted at the time of
  this entry. Its commit awaits WDS approval.
