"""Test support for AI-2: a deterministic stub specialist, synthetic evidence and a fixture bundle.

The stub is test-only. It is not a platform specialist and produces only placeholder, unverified
content. Its ``mode`` switches on the failure paths the execution wrapper must handle.
"""

from __future__ import annotations

from dataclasses import dataclass

from conftest import FIXTURE_PATH, SPEC_REGISTRY_PATH
from factories import CATALOG_VERSION, NOW, REGISTRY_VERSION

from ai_engine.adapters.foundation import MockFoundationAdapter
from ai_engine.contracts.common import (
    DataClass,
    EvidenceStatus,
    FeasibilityStatus,
    RoutingOutcome,
)
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceKind,
    EvidenceReference,
    PlatformContext,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    ApproachType,
    CandidateSolution,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.evidence.lookup import CollectedEvidence, MockEvidenceLookup
from ai_engine.requirement_analysis.agent import RequirementAnalysisAgent
from ai_engine.routing.explicit import ExplicitSelection
from ai_engine.specialists.base import (
    PermissionDeniedError,
    SpecialistContext,
    TransientSpecialistError,
    UnsupportedRequestError,
)
from ai_engine.specialists.registry import AgentRegistry
from ai_engine.specialists.task_builder import build_specialist_task

PROJECT_ID = "PRJ-SYN-0001"
EVIDENCE_COLLECTION = "synthetic_patterns"
OTHER_COLLECTION = "synthetic_other"
SELECTION = ExplicitSelection(
    capability_id="CAP-ECOMMERCE",
    specialist_category_id="shopify_specialist",
    rationale="Operator selected the Shopify specialist for this test.",
)
PLATFORM = PlatformContext(platform_id="shopify", version_status="unknown")
QUERY = "native capability options"


def synthetic_evidence(project_id: str = PROJECT_ID) -> list[CollectedEvidence]:
    def record(evidence_id: str, project: str, summary: str) -> EvidenceReference:
        return EvidenceReference(
            evidence_id=evidence_id,
            project_id=project,
            evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
            evidence_status=EvidenceStatus.UNVERIFIED,
            checked_at=NOW,
            relevance_summary=summary,
        )

    return [
        CollectedEvidence(
            EVIDENCE_COLLECTION,
            record(
                "EVD-SYN-0001", project_id, "Synthetic placeholder for a native capability option."
            ),
        ),
        CollectedEvidence(
            OTHER_COLLECTION,
            record(
                "EVD-SYN-0002", project_id, "Synthetic note about a native capability, other set."
            ),
        ),
        CollectedEvidence(
            EVIDENCE_COLLECTION,
            record(
                "EVD-SYN-0003", "PRJ-OTHER-0001", "Synthetic native capability of another project."
            ),
        ),
    ]


@dataclass(frozen=True)
class Bundle:
    project: ProjectContext
    requirements: list[AtomicRequirement]
    registry: AgentRegistry
    lookup: MockEvidenceLookup
    context: SpecialistContext

    @property
    def by_id(self) -> dict[str, AtomicRequirement]:
        return {r.requirement_id: r for r in self.requirements if r.requirement_id is not None}


def build_bundle() -> Bundle:
    """Run the real analysis on the synthetic fixture, then assign test Foundation IDs."""
    adapter = MockFoundationAdapter.from_file(FIXTURE_PATH)
    project = adapter.get_project(PROJECT_ID)
    analysed = RequirementAnalysisAgent(
        registry_version=REGISTRY_VERSION, catalog_version=CATALOG_VERSION
    ).analyze(project, adapter.list_source_segments(PROJECT_ID, DataClass.INTERNAL))
    shopify = [
        r for r in analysed.requirements if "shopify_specialist" in r.specialist_category_ids
    ]
    assigned = [
        requirement.model_copy(update={"requirement_id": f"REQ-SYN-{number:04d}"})
        for number, requirement in enumerate(shopify, start=1)
    ]
    registry = AgentRegistry.from_yaml(SPEC_REGISTRY_PATH)
    lookup = MockEvidenceLookup(synthetic_evidence())
    context = SpecialistContext(
        project=project,
        requirements={r.requirement_id: r for r in assigned if r.requirement_id is not None},
        evidence=lookup,
    )
    return Bundle(
        project=project, requirements=assigned, registry=registry, lookup=lookup, context=context
    )


def make_task(
    bundle: Bundle, *, task_id: str = "SPT-SYN-0001", **overrides: object
) -> SpecialistTask:
    data: dict[str, object] = {
        "task_id": task_id,
        "project": bundle.project,
        "requirements": bundle.requirements,
        "selection": SELECTION,
        "registry": bundle.registry,
        "platform_context": PLATFORM,
        "allowed_evidence_collections": [EVIDENCE_COLLECTION],
        "catalog_version": CATALOG_VERSION,
        "created_at": NOW,
    }
    data.update(overrides)
    return build_specialist_task(**data)  # type: ignore[arg-type]


class StubSpecialist:
    """Deterministic placeholder specialist for execution-path tests. Test-only."""

    capability_id = "CAP-ECOMMERCE"
    specialist_category_id = "shopify_specialist"

    def __init__(self, mode: str = "completed") -> None:
        self.mode = mode

    def run(
        self, task: SpecialistTask, context: SpecialistContext
    ) -> SpecialistInvestigationResult:
        if self.mode == "unsupported":
            raise UnsupportedRequestError("stub: outside this prototype's scope")
        if self.mode == "transient":
            raise TransientSpecialistError("stub: simulated timeout")
        if self.mode == "denied":
            raise PermissionDeniedError("stub: source not allowed for this specialist")
        if self.mode == "unsupported_status":
            return _result(task, status=SpecialistOutputStatus.UNSUPPORTED_REQUEST)

        served = context.evidence.search(
            project_id=task.project_id,
            allowed_collections=task.allowed_evidence_collections,
            query=QUERY,
        )
        evidence_ids = [item.evidence_id for item in served]
        requirement_ids = list(task.requirement_ids)
        if self.mode == "foreign_requirement":
            requirement_ids = [*requirement_ids, "REQ-SYN-9999"]
        solutions = [
            CandidateSolution(
                proposal_key=f"SOLP-{number:03d}",
                project_id=task.project_id,
                summary="Placeholder native option; not verified.",
                approach_type=ApproachType.NATIVE_PLATFORM,
                related_requirement_ids=[requirement_id],
                verification_tasks=["Confirm in current official documentation."],
            )
            for number, requirement_id in enumerate(requirement_ids, start=1)
        ]
        claim_status = (
            EvidenceStatus.VERIFIED if self.mode == "verified_claim" else EvidenceStatus.UNVERIFIED
        )
        claim = Claim(
            proposal_key="CLM-001",
            project_id=task.project_id,
            claim_text="A native option may exist; this placeholder is unverified.",
            claim_type=ClaimType.OTHER
            if claim_status is EvidenceStatus.VERIFIED
            else ClaimType.PLATFORM_CAPABILITY,
            evidence_status=claim_status,
            feasibility_status=FeasibilityStatus.UNKNOWN,
            subject_refs=[
                SubjectRef(
                    subject_type=SubjectType.REQUIREMENT, subject_id=rid, project_id=task.project_id
                )
                for rid in requirement_ids[:1]
            ],
            evidence_ids=evidence_ids,
            platform_context=task.platform_context,
            verification_task=(
                None
                if claim_status is EvidenceStatus.VERIFIED
                else "Confirm in official documentation."
            ),
        )
        evidence_out = list(served)
        if self.mode == "unserved_evidence":
            evidence_out.append(
                EvidenceReference(
                    evidence_id="EVD-SYN-0404",
                    project_id=task.project_id,
                    evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                    evidence_status=EvidenceStatus.UNVERIFIED,
                    checked_at=NOW,
                    relevance_summary="Invented record never served by the lookup.",
                )
            )
        return _result(
            task,
            status=SpecialistOutputStatus.COMPLETED,
            requirement_ids=requirement_ids,
            solutions=solutions,
            claims=[claim],
            evidence=evidence_out,
        )


def _result(
    task: SpecialistTask,
    *,
    status: SpecialistOutputStatus,
    requirement_ids: list[str] | None = None,
    solutions: list[CandidateSolution] | None = None,
    claims: list[Claim] | None = None,
    evidence: list[EvidenceReference] | None = None,
) -> SpecialistInvestigationResult:
    return SpecialistInvestigationResult(
        task_id=task.task_id,
        project_id=task.project_id,
        capability_id=task.capability_id,
        specialist_category_id=task.specialist_category_id,
        requirement_ids=requirement_ids or list(task.requirement_ids),
        candidate_solutions=solutions or [],
        claims=claims or [],
        evidence=evidence or [],
        status=status,
        registry_version=task.registry_version,
        catalog_version=task.catalog_version,
    )


__all__ = [
    "CATALOG_VERSION",
    "EVIDENCE_COLLECTION",
    "NOW",
    "OTHER_COLLECTION",
    "PLATFORM",
    "PROJECT_ID",
    "QUERY",
    "RoutingOutcome",
    "SELECTION",
    "Bundle",
    "StubSpecialist",
    "build_bundle",
    "make_task",
    "synthetic_evidence",
]
