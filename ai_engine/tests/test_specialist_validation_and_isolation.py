"""Direct negative-path tests for result validation, and isolation from Foundation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from factories import NOW
from support import PROJECT_ID, build_bundle, make_task, synthetic_evidence

from ai_engine.adapters.foundation import FoundationReadPort
from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceReference,
    PlatformContext,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.specialist import SpecialistInvestigationResult, SpecialistOutputStatus
from ai_engine.specialists.validation import validate_specialist_result

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "ai_engine"


def base_result(task, **overrides: object) -> SpecialistInvestigationResult:  # type: ignore[no-untyped-def]
    data: dict[str, object] = {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "capability_id": task.capability_id,
        "specialist_category_id": task.specialist_category_id,
        "requirement_ids": list(task.requirement_ids),
        "status": SpecialistOutputStatus.COMPLETED,
        "registry_version": task.registry_version,
        "catalog_version": task.catalog_version,
    }
    data.update(overrides)
    return SpecialistInvestigationResult(**data)  # type: ignore[arg-type]


@pytest.fixture(scope="module")
def ctx():  # type: ignore[no-untyped-def]
    bundle = build_bundle()
    task = make_task(bundle)
    served = {item.record.evidence_id: item.record for item in synthetic_evidence()[:1]}
    return bundle, task, served


def claim_citing(evidence_ids: list[str], requirement_id: str, platform: str = "shopify") -> Claim:
    return Claim(
        proposal_key="CLM-009",
        project_id=PROJECT_ID,
        claim_text="Placeholder claim.",
        claim_type=ClaimType.OTHER,
        evidence_status=EvidenceStatus.UNVERIFIED,
        subject_refs=[
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id=requirement_id,
                project_id=PROJECT_ID,
            )
        ],
        evidence_ids=evidence_ids,
        platform_context=PlatformContext(platform_id=platform, version_status="unknown"),
        verification_task="Check official docs.",
    )


def test_a_faithful_result_has_no_errors(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    assert validate_specialist_result(base_result(task), task, bundle.by_id, served) == []


def test_identity_mismatch_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    errors = validate_specialist_result(
        base_result(task, task_id="SPT-OTHER-0001", registry_version="other"),
        task,
        bundle.by_id,
        served,
    )
    assert any("task_id" in e for e in errors)
    assert any("registry or catalog" in e for e in errors)


def test_result_for_another_project_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    result = base_result(task, project_id="PRJ-OTHER-0001")
    assert any(
        "project does not match" in e
        for e in validate_specialist_result(result, task, bundle.by_id, served)
    )


def test_claim_about_another_platform_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    rid = task.requirement_ids[0]
    result = base_result(task, claims=[claim_citing([], rid, platform="bigcommerce")])
    assert any(
        "other than the task's platform" in e
        for e in validate_specialist_result(result, task, bundle.by_id, served)
    )


def test_claim_subject_outside_task_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    result = base_result(task, claims=[claim_citing([], "REQ-SYN-9999")])
    assert any(
        "outside the task" in e
        for e in validate_specialist_result(result, task, bundle.by_id, served)
    )


def test_claim_citing_unserved_evidence_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    result = base_result(task, claims=[claim_citing(["EVD-NOT-SERVED"], task.requirement_ids[0])])
    assert any(
        "unknown evidence EVD-NOT-SERVED" in e
        for e in validate_specialist_result(result, task, bundle.by_id, served)
    )


def test_result_evidence_that_differs_from_served_record_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    original = served["EVD-SYN-0001"]
    altered = original.model_copy(update={"relevance_summary": "Edited after lookup."})
    result = base_result(task, evidence=[altered])
    assert any(
        "was not served" in e
        for e in validate_specialist_result(result, task, bundle.by_id, served)
    )


def test_evidence_from_another_project_cannot_be_cited(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, _ = ctx
    foreign = EvidenceReference(
        evidence_id="EVD-FOR-0001",
        project_id="PRJ-OTHER-0001",
        evidence_kind=synthetic_evidence()[0].record.evidence_kind,
        evidence_status=EvidenceStatus.UNVERIFIED,
        checked_at=NOW,
        relevance_summary="Synthetic other project.",
    )
    served = {"EVD-FOR-0001": foreign}
    result = base_result(task, evidence=[foreign])
    errors = validate_specialist_result(result, task, bundle.by_id, served)
    assert any("another project" in e for e in errors)


def test_clarification_question_outside_task_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    from ai_engine.contracts.clarification import ClarificationQuestion

    bundle, task, served = ctx
    question = ClarificationQuestion(
        proposal_key="QPROP-009",
        project_id=PROJECT_ID,
        question_text="Which storefront plan applies?",
        reason="Plan affects feasibility.",
        related_requirement_ids=["REQ-SYN-9999"],
    )
    errors = validate_specialist_result(
        base_result(task, clarification_questions=[question]), task, bundle.by_id, served
    )
    assert any("outside the task" in e for e in errors)


def test_task_requirement_missing_from_context_is_reported(ctx) -> None:  # type: ignore[no-untyped-def]
    bundle, task, served = ctx
    errors = validate_specialist_result(base_result(task), task, {}, served)
    assert any("is missing or in another project" in e for e in errors)


# --- Isolation -------------------------------------------------------------------------------

FORBIDDEN_IMPORT_ROOTS = {
    "webdesk",
    "sqlalchemy",
    "psycopg",
    "alembic",
    "fastapi",
    "argon2",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "http",
}


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_engine_never_imports_foundation_database_auth_or_network() -> None:
    offenders = {
        str(path.relative_to(SRC_ROOT)): sorted(_imported_roots(path) & FORBIDDEN_IMPORT_ROOTS)
        for path in SRC_ROOT.rglob("*.py")
    }
    assert {k: v for k, v in offenders.items() if v} == {}


def test_foundation_port_is_read_only() -> None:
    methods = {name for name in dir(FoundationReadPort) if not name.startswith("_")}
    assert methods == {"get_project", "list_source_segments"}
    assert not any(
        word in name
        for name in methods
        for word in ("write", "create", "update", "delete", "accept")
    )
