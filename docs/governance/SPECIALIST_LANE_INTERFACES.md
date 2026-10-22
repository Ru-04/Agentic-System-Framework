# Specialist Lane Interfaces — Preparation Only (22 October 2026)

**Status:** Preparation. No M2 Sprint 3 implementation is authorized or started. Lanes below contain no specialist code.

## 1. Lanes

| Specialist (canonical) | Worktree | Branch | Base commit |
|---|---|---|---|
| Shopify | `.claude/worktrees/webdesk-specialist-baseline-v1-3b21b1` | `claude/webdesk-specialist-baseline-v1-3b21b1` | Sprint 2 work in progress (uncommitted) |
| Shift4Shop (formerly 3dcart) | `.claude/worktrees/webdesk-lane-shift4shop` | `feature/specialist-shift4shop` | `5122012` |
| WordPress & WooCommerce | `.claude/worktrees/webdesk-lane-wordpress-woocommerce` | `feature/specialist-wordpress-woocommerce` | `5122012` |
| BigCommerce | `.claude/worktrees/webdesk-lane-bigcommerce` | `feature/specialist-bigcommerce` | `5122012` |
| Magento / Adobe Commerce | `.claude/worktrees/webdesk-lane-magento-adobe-commerce` | `feature/specialist-magento-adobe-commerce` | `5122012` |
| Standalone Applications | `.claude/worktrees/webdesk-lane-standalone-applications` | `feature/specialist-standalone-applications` | `5122012` |
| Middleware Applications | `.claude/worktrees/webdesk-lane-middleware-applications` | `feature/specialist-middleware-applications` | `5122012` |

Lane branches are local. They are not pushed (D05 authorizes only the specialist feature branch).

## 2. Shared interfaces each lane consumes (owned by core; not changed by lanes)

- Contract: `webdesk.specialists.contract` (`SpecialistInput`, `SpecialistOutput`, `CONTRACT_VERSION = 1.0.0`).
- Harness: `webdesk.specialists.harness.run_specialist(provider, raw_request)`. Every specialist call goes through it.
- Provider protocol: `webdesk.specialists.harness.SpecialistProvider`:
  - `specialist_id` (a `SpecialistId` member)
  - `declared_actions` (a frozenset of allowlisted action names)
  - `run(request) -> Mapping[str, object]`
- Errors: `webdesk.specialists.errors.SpecialistError`. Provider exceptions are converted to `PROVIDER_FAILURE`.
- Evidence: `webdesk.evidence.retrieval.Retriever` (Sprint 2). Lanes must not call the network directly.
- Citations: `webdesk.evidence.citations` (Sprint 2). Findings are emitted only after a citation check.
- Untrusted text: `webdesk.evidence.untrusted.split_by_trust` (Sprint 2). Required for any retrieved text.

## 3. Lane-owned paths (the only paths a lane may create or change)

- `src/webdesk/specialists/platforms/<platform>.py`
- `tests/unit/platforms/<platform>/` (tests and sanitized WDS fixtures for that platform)
- `docs/platforms/<platform>/` (lane reports)
- A lane-owned vendor allowlist, as a proposal only. It becomes effective only after approval under D08.

## 4. Shared paths that no lane may change

- `src/webdesk/specialists/contract.py`, `harness.py`, `authority.py`, `workspace.py`, `errors.py`, `catalog.py`, `mock.py`
- `src/webdesk/evidence/` (except through a core-owned change request)
- `migrations/`, `src/webdesk/auth/`, `src/webdesk/authority/`, `src/webdesk/rbac/`, any approval or policy file
- `.github/workflows/` (core-owned)
- `WebDesk_Agentic_Requirement_Platform_Specs/` (specification files)

If a lane needs a shared change, it records a change request in its report. It does not make the change.

## 5. Prohibited in every lane

- Live model or provider calls (D09).
- Retrieval outside an approved allowlist (D08).
- Execution without operator confirmation (D07).
- Acceptance on synthetic fixtures alone (D11). Fixtures are labelled as fixtures.
- Changing shared authority, database security, orchestration contracts or approval policy.

## 6. Entry criteria before a lane starts M2 Sprint 3 work

1. Sprint 2 accepted (formal QA, see the Sprint 2 report).
2. Specification approval for the reconciled package (D02), or a dated authorization that names the lane's scope.
3. Shared contract changes frozen. Any Sprint 2 change to shared interfaces has been approved.
4. The lane's allowlist and real-case set are approved, or the lane is explicitly limited to fixtures and records that limit.
