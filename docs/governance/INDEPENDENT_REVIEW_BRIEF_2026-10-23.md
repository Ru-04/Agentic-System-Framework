# Brief for an independent AI-assisted review (Sprint 1–3, 23 October 2026)

Give this brief to a **new, separate Claude chat**. Do not start it from the working session. The reviewer does not receive the working session's conclusions.

## Goal
Review the code and tests for Sprint 3 platform foundations and Sprint 1 specialist contracts. Report findings only. Do not approve, sign off, or change any file.

## Repository and commits
- Repository: `Ru-04/Agentic-System-Framework`, branch `claude/webdesk-specialist-baseline-v1-3b21b1`.
- Local head `f828a72` plus later local commits. The remote may not hold these commits yet. Use the local worktree if you have access to it.

## Scope
- `src/webdesk/specialists/` (Sprint 1 contract, harness, authority, workspace).
- `src/webdesk/specialists/platforms/generic.py` and the six platform modules.
- `src/webdesk/evidence/` (retrieval, allowlist, untrusted screening, citations, relevance).
- `tests/unit/test_specialist_*.py`, `tests/unit/test_m2_s3_platforms.py`, `tests/unit/test_s2_*.py`.

## Questions to answer, with file and line evidence
1. Can a platform specialist retrieve or cite anything when no approved source is configured?
2. Can a fixture or a non-allowlisted origin be cited as evidence?
3. Can any passage from another workspace reach the output?
4. Can a forbidden action succeed through the shared harness?
5. Does input validation reject extra or malformed fields?
6. Can instruction-like text reach the output unflagged?
7. Are there false matches in topic detection, and what statements would they produce?

## Output format
For each finding: severity (high, medium, low), file and line, a concrete failure scenario, and a minimal fix. Separate confirmed from suspected. Say explicitly where you found nothing.

## Limits
This is an AI-assisted review. It is not human QA and it is not independent QA under decision Q2. Do not state that it is.
