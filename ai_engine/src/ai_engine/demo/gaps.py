"""Specification and governance gaps tracked by the demonstration.

Each entry is reported in every demonstration output. None is resolved here. Closing one needs a
WDS decision or an approved specification change.
"""

from __future__ import annotations

from ai_engine.demo.model import TrackedGap

TRACKED_GAPS: tuple[TrackedGap, ...] = (
    TrackedGap(
        gap_id="S1",
        title="Specialist output has no assumptions field (REQUIREMENT_SCHEMA 4.3.1)",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S2",
        title="Claim has no conflict references required by section 6.8",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S3",
        title="Conflicting evidence cannot be expressed on a synthetic EvidenceReference",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S4",
        title="SERVICE_CATALOG loader not built; service_pattern_ids are empty",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S5",
        title="Platform version unknown; no platform claim can be verified",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="S6",
        title="[stance] tags are a test-fixture convention, not a spec construct",
        source="AI-3 9.1",
    ),
    TrackedGap(
        gap_id="C-05",
        title="Structured routing predicates not approved; machine routing disabled",
        source="AGENT_REGISTRY",
    ),
    TrackedGap(
        gap_id="D-12",
        title="LLM provider, model and data-processing policy undecided; no LLM called",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-02/C-06",
        title="Vendor evidence allowlist undecided; only synthetic evidence used",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-06",
        title="Criticality predicates undecided; materiality stays unassessed",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-08/H-16",
        title="Requirement acceptance eligibility predicates undecided; nothing accepted",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="G9",
        title="Proposed ID prefixes (SPT, EXEC, CAND, QPROP, APROP, STMT, CONF) need approval",
        source="AI-1 plan 4",
    ),
    TrackedGap(
        gap_id="G11",
        title="No ai_proposed lifecycle state; AI output limited to captured and blocked states",
        source="AI-1 plan 4",
    ),
    TrackedGap(
        gap_id="G12",
        title="Registry entries are proposed and the registry is an unapproved draft",
        source="AGENT_REGISTRY",
    ),
    TrackedGap(
        gap_id="D-PERS",
        title="No Foundation persistence or WorkflowRun integration; IDs are mock-assigned",
        source="AI-4 boundary",
    ),
    TrackedGap(
        gap_id="D-OP",
        title="Operator confirmation of the requirement list is not modelled",
        source="AI-4 selection",
    ),
    TrackedGap(
        gap_id="D-10",
        title="No approved SOW template; no SOW is generated",
        source="DECISION_REGISTER",
    ),
    TrackedGap(
        gap_id="D-04",
        title="No reference estimate dataset; no estimates are produced",
        source="DECISION_REGISTER",
    ),
)
