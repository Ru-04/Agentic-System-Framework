"""Specification and governance gaps tracked by the demonstration (updated in AI-4.1).

Statuses:
- ``open``: unresolved; needs a WDS decision, client input, or engineering work.
- ``addressed_pending_amendment``: implemented as an additive contract change, which needs formal
  approval before it is relied on at integration.
- ``closed``: resolved within the prototype scope.

The full issue register, with the reasoning for each status, is in
docs/AI_ENGINE_ISSUE_RESOLUTION.md.
"""

from __future__ import annotations

from ai_engine.demo.model import TrackedGap

TRACKED_GAPS: tuple[TrackedGap, ...] = (
    TrackedGap(
        gap_id="A-1",
        title="ProjectContext.status added (additive, default active); archived projects refused",
        status="addressed_pending_amendment",
        source="REQUIREMENT_SCHEMA 4.1; AI-4.1 item 12",
    ),
    TrackedGap(
        gap_id="A-2",
        title="Claim.conflict_refs added (additive); conflicting claims cite a conflict record",
        status="addressed_pending_amendment",
        source="REQUIREMENT_SCHEMA 6.8; AI-3 S2",
    ),
    TrackedGap(
        gap_id="A-3",
        title="SpecialistInvestigationResult.assumptions and .conflicts added (additive)",
        status="addressed_pending_amendment",
        source="REQUIREMENT_SCHEMA 4.3.1; AI-3 S1",
    ),
    TrackedGap(
        gap_id="A-4",
        title="Unresolved conflict (blocked) and clarification need as independent indicators",
        status="open",
        source="GOVERNANCE 6; REQUIREMENT_SCHEMA 5 and Example E",
    ),
    TrackedGap(
        gap_id="S3",
        title="Conflicting evidence cannot be expressed on a synthetic EvidenceReference",
        status="open",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S4",
        title="Service catalog references empty until an authorized catalog is available",
        status="open",
        source="AI-3 9.1; AI-4.1 item 10",
    ),
    TrackedGap(
        gap_id="S5",
        title="Platform version unknown; no platform claim can be verified",
        status="open",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S6",
        title="Stance tags removed from evidence text; contradiction groups held beside records",
        status="closed",
        source="AI-3 9.1; AI-4.1 item 8",
    ),
    TrackedGap(
        gap_id="EK-1",
        title="EvidenceKind is an AI-local extension; approval needed if the schema must carry it",
        status="open",
        source="REQUIREMENT_SCHEMA 4.4",
    ),
    TrackedGap(
        gap_id="C-05",
        title="Structured routing predicates not approved; machine routing disabled",
        status="open",
        source="AGENT_REGISTRY",
    ),
    TrackedGap(
        gap_id="D-12",
        title="LLM provider, model and data-processing policy undecided; no LLM called",
        status="open",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-02/C-06",
        title="Vendor evidence allowlist undecided; only synthetic evidence used",
        status="open",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-06",
        title="Criticality predicates undecided; materiality stays unassessed",
        status="open",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-08/H-16",
        title="Requirement acceptance eligibility predicates undecided; nothing accepted",
        status="open",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="G9",
        title="Proposed ID prefixes (SPT, EXEC, CAND, CLM, SOLP, QPROP, APROP, SASM, STMT, CONF,"
        " RSKP) open",
        status="open",
        source="AI-1 plan 4",
    ),
    TrackedGap(
        gap_id="G11",
        title="No ai_proposed state; AI output limited to captured, blocked, needs_clarification",
        status="open",
        source="AI-1 plan 4",
    ),
    TrackedGap(
        gap_id="G12",
        title="Registry entries are proposed and the registry is an unapproved draft",
        status="open",
        source="AGENT_REGISTRY",
    ),
    TrackedGap(
        gap_id="D-PERS",
        title="No Foundation persistence or WorkflowRun integration; IDs are mock-assigned",
        status="open",
        source="AI-4 boundary",
    ),
    TrackedGap(
        gap_id="D-OP",
        title="Operator confirmation is attributed; WDS policy approval still required",
        status="open",
        source="AI-4 selection; AI-4.1 item 2",
    ),
    TrackedGap(
        gap_id="D-10",
        title="No approved SOW template; no SOW is generated",
        status="open",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-04",
        title="No reference estimate dataset; no estimates are produced",
        status="open",
        source="DECISION_REGISTER",
    ),
)
