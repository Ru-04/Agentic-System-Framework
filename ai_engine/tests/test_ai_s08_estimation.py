"""
AI-S08 draft effort estimation tests.

Every number asserted here is a hand-computed sum or a stated input. Synthetic fixtures only; no
historical data, rates or benchmarks. The engine is offline: no network, provider or Foundation.
"""

from __future__ import annotations

import ast
import json
import pathlib
from typing import Any

import pytest
from pydantic import ValidationError

from ai_engine.estimation.contracts import (
    BasisKind,
    Discipline,
    EstimateBasis,
    EstimateRequest,
    EstimateStatus,
    EstimationInputError,
    GovernanceSummary,
    Readiness,
    RequirementSnapshot,
    ResourceAllocation,
    TaskInput,
    ThreePoint,
    WorkCategory,
)
from ai_engine.estimation.engine import build_request, estimate

PROJECT = "PRJ-SYN-0001"
OTHER = "PRJ-SYN-0002"
REQ1 = "REQ-SYN-0001"
REQ2 = "REQ-SYN-0002"
REQ3 = "REQ-SYN-0003"
FINGERPRINT = "a" * 64
PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "src/ai_engine/estimation"


def _basis(
    *,
    kind: BasisKind = BasisKind.SYNTHETIC_FIXTURE,
    ref: str = "REF-SYN-A",
    project: str = PROJECT,
    version: str = "1",
) -> EstimateBasis:
    provenance = (
        "synthetic fixture for isolated tests"
        if kind is BasisKind.SYNTHETIC_FIXTURE
        else "approved reference provenance"
    )
    return EstimateBasis(
        kind=kind, reference_id=ref, project_id=project, version=version, provenance=provenance
    )


def _alloc(discipline: Discipline, low: float, likely: float, high: float) -> ResourceAllocation:
    return ResourceAllocation(
        discipline=discipline, hours=ThreePoint(low=low, likely=likely, high=high)
    )


def _task(
    task_id: str = "TSK-001",
    *,
    key: str = "IMP-A",
    rid: str = REQ1,
    revision: int = 1,
    category: WorkCategory = WorkCategory.FRONTEND_DEVELOPMENT,
    allocations: tuple[ResourceAllocation, ...] | None = None,
    basis: EstimateBasis | None = None,
    **extra: Any,
) -> TaskInput:
    if allocations is None:
        allocations = (_alloc(Discipline.FRONTEND, 8.0, 12.0, 20.0),)
    if extra.pop("no_basis", False):
        basis = None
    elif basis is None:
        basis = _basis()
    return TaskInput(
        task_id=task_id,
        implementation_key=key,
        requirement_id=rid,
        requirement_revision=revision,
        work_category=category,
        title="Synthetic work item",
        allocations=allocations,
        basis=basis,
        **extra,
    )


def _snapshot(rid: str, revision: int = 1, project: str = PROJECT) -> RequirementSnapshot:
    return RequirementSnapshot(requirement_id=rid, project_id=project, revision=revision)


def _governance(
    statuses: dict[str, Any] | None = None,
    *,
    blocking: frozenset[str] = frozenset(),
    escalations: int = 0,
    has_blocker: bool = False,
    project: str = PROJECT,
) -> GovernanceSummary:
    if statuses is None:
        statuses = {REQ1: "evidence_backed", REQ2: "evidence_backed", REQ3: "evidence_backed"}
    return GovernanceSummary(
        run_id="RUN-AI-S08-0001",
        project_id=project,
        input_fingerprint=FINGERPRINT,
        requirement_status=statuses,
        blocking_requirement_ids=blocking,
        escalation_count=escalations,
        has_blocker=has_blocker,
    )


def _request(
    tasks: tuple[TaskInput, ...],
    *,
    requirements: tuple[RequirementSnapshot, ...] | None = None,
    governance: GovernanceSummary | None = None,
    **extra: Any,
) -> EstimateRequest:
    if requirements is None:
        requirements = (_snapshot(REQ1), _snapshot(REQ2))
    if governance is None and "no_governance" not in extra:
        governance = _governance()
    extra.pop("no_governance", None)
    options: dict[str, Any] = {
        "current_reference_versions": {"REF-SYN-A": "1"},
        "allow_synthetic_fixtures": True,
    }
    options.update(extra)
    return EstimateRequest(
        project_id=PROJECT,
        estimate_version="EST-v1",
        requirements=requirements,
        tasks=tasks,
        governance=governance,
        **options,
    )


# 1. Single requirement estimation


def test_a_single_task_reports_its_stated_hours_and_totals() -> None:
    draft = estimate(_request((_task(),), requirements=(_snapshot(REQ1),)))
    assert len(draft.lines) == 1
    line = draft.lines[0]
    assert (line.low, line.likely, line.high) == (8.0, 12.0, 20.0)
    assert line.status is EstimateStatus.INDICATIVE
    assert (draft.project.low, draft.project.likely, draft.project.high) == (8.0, 12.0, 20.0)
    assert draft.project.complete is True
    assert draft.draft_status == "draft_not_approved"


# 2. Multiple requirements


def test_totals_sum_across_requirements_and_by_requirement_subtotals_are_separate() -> None:
    tasks = (
        _task(
            "TSK-001",
            key="IMP-A",
            rid=REQ1,
            allocations=(_alloc(Discipline.FRONTEND, 8.0, 12.0, 20.0),),
        ),
        _task(
            "TSK-002",
            key="IMP-B",
            rid=REQ2,
            allocations=(_alloc(Discipline.BACKEND, 5.0, 6.0, 9.0),),
            category=WorkCategory.BACKEND_DEVELOPMENT,
        ),
    )
    draft = estimate(_request(tasks))
    assert (draft.project.low, draft.project.likely, draft.project.high) == (13.0, 18.0, 29.0)
    assert draft.by_requirement[REQ1].likely == 12.0
    assert draft.by_requirement[REQ2].likely == 6.0


# 3. Multiple resource roles


def test_a_task_with_two_roles_yields_one_line_per_role_and_discipline_totals() -> None:
    task = _task(
        allocations=(
            _alloc(Discipline.FRONTEND, 8.0, 12.0, 20.0),
            _alloc(Discipline.QA, 4.0, 6.0, 9.0),
        )
    )
    draft = estimate(_request((task,), requirements=(_snapshot(REQ1),)))
    assert {line.discipline for line in draft.lines} == {Discipline.FRONTEND, Discipline.QA}
    assert draft.by_discipline[Discipline.QA].likely == 6.0
    assert draft.project.likely == 18.0
    assert draft.project.high == 29.0


# 4. Low / Likely / High validation


@pytest.mark.parametrize(
    ("low", "likely", "high"),
    [
        (9.0, 8.0, 10.0),
        (1.0, 12.0, 11.0),
        (-1.0, 0.0, 1.0),
        (float("nan"), 1.0, 2.0),
        (0.0, float("inf"), 2.0),
        (True, 1.0, 2.0),
    ],
)
def test_invalid_three_point_hours_are_refused(low: Any, likely: Any, high: Any) -> None:
    with pytest.raises(ValidationError):
        ThreePoint(low=low, likely=likely, high=high)


def test_equal_and_zero_three_point_values_are_accepted() -> None:
    assert ThreePoint(low=0.0, likely=0.0, high=0.0).likely == 0.0
    assert ThreePoint(low=3.0, likely=3.0, high=3.0).high == 3.0


def test_an_integer_hour_value_is_stored_as_a_float_and_text_is_refused() -> None:
    value = ThreePoint(low=8, likely=12.0, high=20.0)
    assert value.low == 8.0 and isinstance(value.low, float)
    with pytest.raises(ValidationError):
        ThreePoint(low="8", likely=12.0, high=20.0)  # type: ignore[arg-type]


# 5. Totals and subtotals


def test_fractional_totals_are_exact_sums_of_the_stated_hours() -> None:
    tasks = (
        _task(
            "TSK-001",
            key="IMP-A",
            rid=REQ1,
            allocations=(_alloc(Discipline.FRONTEND, 0.1, 0.2, 0.3),),
        ),
        _task(
            "TSK-002",
            key="IMP-B",
            rid=REQ1,
            allocations=(_alloc(Discipline.FRONTEND, 0.2, 0.3, 0.4),),
        ),
    )
    draft = estimate(_request(tasks, requirements=(_snapshot(REQ1),)))
    assert draft.project.low == pytest.approx(0.3, abs=1e-12)
    assert draft.project.likely == pytest.approx(0.5, abs=1e-12)
    assert draft.project.high == pytest.approx(0.7, abs=1e-12)
    assert draft.by_work_category[WorkCategory.FRONTEND_DEVELOPMENT].estimated_line_count == 2


# 6. Duplicate work-item handling


def test_shared_implementation_counts_once_in_project_totals() -> None:
    tasks = (
        _task("TSK-001", key="IMP-CART", rid=REQ1),
        _task("TSK-002", key="IMP-CART", rid=REQ2),
    )
    draft = estimate(_request(tasks))
    assert len(draft.lines) == 1
    assert draft.lines[0].task_ids == ("TSK-001", "TSK-002")
    assert draft.lines[0].requirement_ids == (REQ1, REQ2)
    assert draft.project.likely == 12.0
    assert draft.project.estimated_line_count == 1


def test_shared_implementation_with_conflicting_hours_is_not_estimated() -> None:
    tasks = (
        _task("TSK-001", key="IMP-CART", rid=REQ1),
        _task(
            "TSK-002",
            key="IMP-CART",
            rid=REQ2,
            allocations=(_alloc(Discipline.FRONTEND, 4.0, 6.0, 9.0),),
        ),
    )
    draft = estimate(_request(tasks))
    line = draft.lines[0]
    assert line.status is EstimateStatus.NEEDS_INPUTS
    assert line.likely is None
    assert any("conflicting hours" in issue for issue in line.issues)
    assert draft.project.estimated_line_count == 0


def test_shared_implementation_with_conflicting_work_category_is_not_estimated() -> None:
    tasks = (
        _task("TSK-001", key="IMP-CART", rid=REQ1),
        _task("TSK-002", key="IMP-CART", rid=REQ2, category=WorkCategory.QA_REGRESSION_TESTING),
    )
    draft = estimate(_request(tasks))
    assert any("conflicting work category" in issue for issue in draft.lines[0].issues)
    assert draft.project.complete is False


# 7. Missing technical detail


def test_a_task_without_a_numeric_basis_gives_no_numbers() -> None:
    draft = estimate(_request((_task(no_basis=True),), requirements=(_snapshot(REQ1),)))
    line = draft.lines[0]
    assert line.status is EstimateStatus.NEEDS_INPUTS
    assert line.likely is None
    assert "TSK-001: no authorised numeric basis" in line.issues
    assert draft.project.complete is False


def test_a_task_without_hours_is_reported_not_silently_dropped() -> None:
    tasks = (
        _task("TSK-001", key="IMP-A", rid=REQ1),
        _task("TSK-002", key="IMP-B", rid=REQ2, allocations=()),
    )
    draft = estimate(_request(tasks))
    assert len(draft.lines) == 2
    empty = next(line for line in draft.lines if "TSK-002" in line.task_ids)
    assert empty.status is EstimateStatus.NEEDS_INPUTS
    assert empty.discipline is None and empty.likely is None
    assert "TSK-002: no hours supplied" in empty.issues
    assert draft.project.complete is False
    assert empty.line_id in draft.project.excluded_line_ids


# 8. Missing evidence and 10. Unverified hypotheses


def test_an_unverified_hypothesis_keeps_numbers_but_is_provisional() -> None:
    governance = _governance({REQ1: "not_evidence_verified", REQ2: "evidence_backed"})
    tasks = (_task(), _task("TSK-002", key="IMP-B", rid=REQ2))
    draft = estimate(
        _request(tasks, requirements=(_snapshot(REQ1), _snapshot(REQ2)), governance=governance)
    )
    assert draft.lines[0].likely == 12.0
    assert draft.lines[0].readiness is Readiness.PROVISIONAL
    assert draft.requirement_readiness[REQ1] is Readiness.PROVISIONAL
    assert draft.readiness is Readiness.PROVISIONAL


def test_an_unsupported_requirement_is_unresolved_not_established() -> None:
    governance = _governance({REQ1: "unsupported", REQ2: "evidence_backed"})
    draft = estimate(
        _request((_task(),), requirements=(_snapshot(REQ1), _snapshot(REQ2)), governance=governance)
    )
    assert draft.lines[0].readiness is Readiness.UNRESOLVED
    assert draft.readiness is Readiness.UNRESOLVED


# 9. Conflicting specialist findings and 19. Governance findings influencing readiness


def test_a_conflicted_requirement_blocks_readiness_of_its_lines() -> None:
    governance = _governance({REQ1: "conflicted", REQ2: "evidence_backed"})
    draft = estimate(
        _request((_task(),), requirements=(_snapshot(REQ1), _snapshot(REQ2)), governance=governance)
    )
    assert draft.lines[0].readiness is Readiness.BLOCKED
    assert draft.readiness is Readiness.BLOCKED


def test_a_blocking_finding_blocks_even_when_status_reads_backed() -> None:
    governance = _governance(
        {REQ1: "evidence_backed", REQ2: "evidence_backed"},
        blocking=frozenset({REQ1}),
        has_blocker=True,
    )
    draft = estimate(
        _request((_task(),), requirements=(_snapshot(REQ1), _snapshot(REQ2)), governance=governance)
    )
    assert draft.requirement_readiness[REQ1] is Readiness.BLOCKED
    assert draft.lines[0].readiness is Readiness.BLOCKED
    assert "governance reports blocking findings" in draft.outstanding_issues


def test_escalations_are_listed_for_human_review() -> None:
    draft = estimate(_request((_task(),), governance=_governance(escalations=2)))
    assert "2 governance escalation(s) need human review" in draft.outstanding_issues


# 11. Stale source references


def test_a_stale_reference_version_gives_no_numbers() -> None:
    draft = estimate(
        _request(
            (_task(basis=_basis(kind=BasisKind.APPROVED_REFERENCE_RANGE, version="1")),),
            requirements=(_snapshot(REQ1),),
            current_reference_versions={"REF-SYN-A": "2"},
        )
    )
    line = draft.lines[0]
    assert line.status is EstimateStatus.NEEDS_INPUTS and line.likely is None
    assert any("stale reference version" in issue for issue in line.issues)


def test_an_unconfirmed_reference_version_gives_no_numbers() -> None:
    draft = estimate(
        _request(
            (_task(basis=_basis(kind=BasisKind.APPROVED_REFERENCE_RANGE)),),
            requirements=(_snapshot(REQ1),),
            current_reference_versions={},
        )
    )
    assert any("reference version not confirmed" in issue for issue in draft.lines[0].issues)


# 12. Unsupported resource categories and 13. Invalid, negative and nonfinite hours (raw input)


def test_an_unsupported_discipline_is_refused_with_a_sanitised_message() -> None:
    raw = _raw_request()
    raw["tasks"][0]["allocations"][0]["discipline"] = "wizardry"
    with pytest.raises(EstimationInputError) as info:
        build_request(raw)
    assert "wizardry" not in str(info.value)


@pytest.mark.parametrize("hours", [float("nan"), float("inf"), -1.0, "SECRETVALUE8", None])
def test_malformed_hour_values_are_refused_and_not_echoed(hours: Any) -> None:
    raw = _raw_request()
    raw["tasks"][0]["allocations"][0]["hours"]["likely"] = hours
    with pytest.raises(EstimationInputError) as info:
        build_request(raw)
    assert "SECRETVALUE8" not in str(info.value)


# 14. Estimate version consistency


def test_the_draft_carries_the_version_revisions_and_governance_fingerprint() -> None:
    draft = estimate(
        _request((_task(),), requirements=(_snapshot(REQ1, revision=3), _snapshot(REQ2)))
    )
    assert draft.estimate_version == "EST-v1"
    assert dict(draft.requirement_revisions) == {REQ1: 3, REQ2: 1}
    assert draft.governance_fingerprint == FINGERPRINT


# 15. Requirement revision changes


def test_a_task_built_on_an_older_revision_is_stale_until_it_is_rebuilt() -> None:
    stale = estimate(_request((_task(revision=1),), requirements=(_snapshot(REQ1, revision=2),)))
    assert stale.lines[0].status is EstimateStatus.NEEDS_INPUTS
    assert any("stale requirement revision" in issue for issue in stale.lines[0].issues)
    fresh = estimate(_request((_task(revision=2),), requirements=(_snapshot(REQ1, revision=2),)))
    assert fresh.lines[0].status is EstimateStatus.INDICATIVE
    assert fresh.lines[0].likely == 12.0


# 16. Cross-project isolation


def test_a_requirement_snapshot_from_another_project_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="another project"):
        estimate(_request((_task(),), requirements=(_snapshot(REQ1, project=OTHER),)))


def test_governance_for_another_project_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="another project"):
        estimate(_request((_task(),), governance=_governance(project=OTHER)))


def test_a_cross_project_basis_gives_no_numbers_unless_authorised() -> None:
    cross = _basis(
        kind=BasisKind.AUTHORISED_HISTORICAL, ref="REF-HIST-1", project=OTHER, version="3"
    )
    refused = estimate(
        _request(
            (_task(basis=cross),),
            requirements=(_snapshot(REQ1),),
            current_reference_versions={"REF-HIST-1": "3"},
        )
    )
    assert refused.lines[0].likely is None
    assert any("unauthorised cross-project" in issue for issue in refused.lines[0].issues)
    allowed = estimate(
        _request(
            (_task(basis=cross),),
            requirements=(_snapshot(REQ1),),
            current_reference_versions={"REF-HIST-1": "3"},
            authorised_reference_projects=frozenset({OTHER}),
        )
    )
    assert allowed.lines[0].likely == 12.0


# 17. Historical reference authorisation


def test_a_historical_reference_needs_a_confirmed_current_version() -> None:
    hist = _basis(kind=BasisKind.AUTHORISED_HISTORICAL, ref="REF-HIST-1", version="3")
    draft = estimate(
        _request(
            (_task(basis=hist),),
            requirements=(_snapshot(REQ1),),
            current_reference_versions={"REF-HIST-1": "4"},
        )
    )
    assert any("stale reference version" in issue for issue in draft.lines[0].issues)
    assert draft.lines[0].likely is None


def test_a_synthetic_fixture_is_refused_unless_the_request_allows_it() -> None:
    draft = estimate(
        _request((_task(),), requirements=(_snapshot(REQ1),), allow_synthetic_fixtures=False)
    )
    assert draft.lines[0].likely is None
    assert any("synthetic fixture not permitted" in issue for issue in draft.lines[0].issues)


def test_a_synthetic_basis_must_say_it_is_synthetic() -> None:
    with pytest.raises(ValidationError):
        EstimateBasis(
            kind=BasisKind.SYNTHETIC_FIXTURE,
            reference_id="REF-SYN-A",
            project_id=PROJECT,
            version="1",
            provenance="client figures",
        )


# 18. Partial estimation outputs


def test_a_partial_estimate_reports_exact_excluded_lines_and_incomplete_totals() -> None:
    tasks = (
        _task("TSK-001", key="IMP-A", rid=REQ1),
        _task("TSK-002", key="IMP-B", rid=REQ2, allocations=()),
    )
    draft = estimate(_request(tasks))
    excluded = [line.line_id for line in draft.lines if line.status is EstimateStatus.NEEDS_INPUTS]
    assert list(draft.project.excluded_line_ids) == excluded
    assert draft.project.complete is False
    assert draft.project.estimated_line_count == 1
    assert draft.project.likely == 12.0


# 20. No automatic estimate approval


def test_no_output_can_carry_an_approved_status() -> None:
    assert "approved" not in {status.value for status in EstimateStatus}
    draft = estimate(_request((_task(),)))
    assert all(
        line.status in (EstimateStatus.INDICATIVE, EstimateStatus.NEEDS_INPUTS)
        for line in draft.lines
    )
    assert draft.draft_status == "draft_not_approved"
    assert any("human" in issue and "approve" in issue for issue in draft.outstanding_issues)


# 21. Compatibility with AI-S01 to AI-S07: offline pipeline


def test_the_offline_pipeline_runs_orchestration_review_then_estimation() -> None:
    from test_ai_s06_orchestration import (
        OPERATOR,
        _confirmation,
        _orchestrator,
        _proposed,
        _seven_requirements,
    )

    from ai_engine.estimation.bridge import governance_summary, specialist_result_refs
    from ai_engine.governance.adapter import review_orchestration
    from ai_engine.orchestration.registry_map import IDENTITIES

    orchestrator = _orchestrator()
    proposal = _proposed(orchestrator, _seven_requirements())
    orchestrator.confirm(_confirmation(proposal), actor=OPERATOR)
    result = orchestrator.execute(
        actor=OPERATOR, authorised_collections=[i.collection for i in IDENTITIES]
    )
    evidence = [item.record for identity in IDENTITIES for item in identity.make_evidence(PROJECT)]
    requirements = _seven_requirements()
    report = review_orchestration(
        result,
        project_id=PROJECT,
        requirements={r.requirement_id or "": r for r in requirements},
        admitted_evidence=evidence,
    )
    summary = governance_summary(report)
    assert summary.input_fingerprint == report.input_fingerprint
    assert summary.requirement_status == {
        rid: s.value for rid, s in report.requirement_status.items()
    }

    rids = [r.requirement_id or "" for r in requirements]
    tasks = tuple(
        _task(
            f"TSK-{i:03d}",
            key=f"IMP-R{i}",
            rid=rid,
            category=WorkCategory.BACKEND_DEVELOPMENT,
            allocations=(_alloc(Discipline.BACKEND, 4.0, 6.0, 9.0),),
        )
        for i, rid in enumerate(rids, start=1)
    )
    request = EstimateRequest(
        project_id=PROJECT,
        estimate_version="EST-v1",
        requirements=tuple(_snapshot(rid) for rid in rids),
        tasks=tasks,
        governance=summary,
        specialist_result_refs=specialist_result_refs(result),
        current_reference_versions={"REF-SYN-A": "1"},
        allow_synthetic_fixtures=True,
    )
    draft = estimate(request)
    assert len(draft.lines) == len(rids)
    assert draft.project.estimated_line_count == len(rids)
    assert draft.project.likely == pytest.approx(6.0 * len(rids))
    assert draft.governance_fingerprint == report.input_fingerprint
    assert set(draft.specialist_result_refs) == set(specialist_result_refs(result))
    assert all(line.status is EstimateStatus.INDICATIVE for line in draft.lines)


# 22. Offline handoff suitability


def test_the_draft_serialises_to_json_and_is_deterministic() -> None:
    request = _request(
        (_task("TSK-002", key="IMP-B", rid=REQ2), _task("TSK-001", key="IMP-A", rid=REQ1))
    )
    first = estimate(request).model_dump_json()
    second = estimate(request).model_dump_json()
    assert first == second
    payload = json.loads(first)
    assert payload["draft_status"] == "draft_not_approved"
    assert [line["line_id"] for line in payload["lines"]] == ["LINE-001", "LINE-002"]


# Security and integrity


def test_the_request_is_not_mutated_by_estimation() -> None:
    request = _request((_task(),))
    before = request.model_dump_json()
    estimate(request)
    assert request.model_dump_json() == before


def test_a_missing_governance_review_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="governance review is required"):
        estimate(_request((_task(),), no_governance=True))


def test_a_requirement_without_a_governance_assessment_is_refused() -> None:
    governance = _governance({REQ1: "evidence_backed"})
    with pytest.raises(EstimationInputError, match="has no assessment"):
        estimate(
            _request(
                (_task(),), requirements=(_snapshot(REQ1), _snapshot(REQ2)), governance=governance
            )
        )


@pytest.mark.parametrize("bad_id", ["req-1", "REQ-", "REQ 1", "TSK-001", "../REQ-1"])
def test_malformed_requirement_ids_are_refused(bad_id: str) -> None:
    raw = _raw_request()
    raw["tasks"][0]["requirement_id"] = bad_id
    with pytest.raises(EstimationInputError):
        build_request(raw)


def test_a_duplicate_task_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="duplicate task"):
        estimate(_request((_task("TSK-001", key="IMP-A"), _task("TSK-001", key="IMP-B", rid=REQ2))))


def test_a_task_for_an_unknown_requirement_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="not in the request"):
        estimate(_request((_task(rid=REQ3),), requirements=(_snapshot(REQ1),)))


def test_a_task_citing_an_unknown_specialist_result_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="unknown specialist result"):
        estimate(_request((_task(specialist_category_ids=("shopify_specialist",)),)))


def test_an_unknown_task_dependency_is_refused() -> None:
    with pytest.raises(EstimationInputError, match="depends on a task"):
        estimate(_request((_task(dependencies=("TSK-999",)),)))


def test_a_task_may_name_each_discipline_once() -> None:
    with pytest.raises(ValidationError):
        _task(
            allocations=(_alloc(Discipline.QA, 1.0, 2.0, 3.0), _alloc(Discipline.QA, 1.0, 2.0, 3.0))
        )


def test_the_estimator_package_imports_no_network_or_foundation_modules() -> None:
    forbidden = (
        "socket",
        "http",
        "urllib",
        "requests",
        "httpx",
        "sqlalchemy",
        "psycopg",
        "ai_engine.foundation",
    )
    found: set[str] = set()
    for path in PACKAGE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.startswith(forbidden) or name.split(".")[0] in forbidden:
                    found.add(f"{path.name}:{name}")
    assert found == set()


def test_the_estimator_package_never_writes_an_approval() -> None:
    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "EstimateStatus.APPROVED" not in source
        assert '"approved"' not in source


# Helpers for raw-input tests


def _raw_request() -> dict[str, Any]:
    return {
        "project_id": PROJECT,
        "estimate_version": "EST-v1",
        "requirements": [{"requirement_id": REQ1, "project_id": PROJECT, "revision": 1}],
        "tasks": [
            {
                "task_id": "TSK-001",
                "implementation_key": "IMP-A",
                "requirement_id": REQ1,
                "requirement_revision": 1,
                "work_category": "frontend_development",
                "title": "Synthetic",
                "allocations": [
                    {"discipline": "frontend", "hours": {"low": 8.0, "likely": 12.0, "high": 20.0}}
                ],
                "basis": {
                    "kind": "synthetic_fixture",
                    "reference_id": "REF-SYN-A",
                    "project_id": PROJECT,
                    "version": "1",
                    "provenance": "synthetic fixture for isolated tests",
                },
            }
        ],
        "governance": {
            "run_id": "RUN-AI-S08-0001",
            "project_id": PROJECT,
            "input_fingerprint": FINGERPRINT,
            "requirement_status": {REQ1: "evidence_backed"},
        },
        "current_reference_versions": {"REF-SYN-A": "1"},
        "allow_synthetic_fixtures": True,
    }


def test_a_requirement_with_no_task_makes_the_project_needs_inputs() -> None:
    draft = estimate(_request((_task(rid=REQ1),), requirements=(_snapshot(REQ1), _snapshot(REQ2))))
    assert draft.requirement_readiness[REQ2] is Readiness.READY_FOR_REVIEW
    assert draft.readiness is Readiness.NEEDS_INPUTS
    assert "REQ-SYN-0002: no task estimates this requirement" in draft.outstanding_issues
    assert draft.project.likely == 12.0


def test_an_empty_estimate_is_never_complete() -> None:
    draft = estimate(_request((), requirements=(_snapshot(REQ1), _snapshot(REQ2))))
    assert draft.lines == ()
    assert draft.project.complete is False
    assert draft.project.estimated_line_count == 0
    assert all(totals.complete is False for totals in draft.by_requirement.values())
    assert draft.readiness is Readiness.NEEDS_INPUTS


def test_a_blocker_without_requirement_ids_blocks_readiness() -> None:
    governance = _governance({REQ1: "evidence_backed"}, has_blocker=True)
    draft = estimate(_request((_task(),), requirements=(_snapshot(REQ1),), governance=governance))
    assert draft.requirement_readiness[REQ1] is Readiness.READY_FOR_REVIEW
    assert draft.readiness is Readiness.BLOCKED


def test_tasks_without_hours_appear_in_the_unassigned_bucket() -> None:
    tasks = (
        _task("TSK-001", key="IMP-A", rid=REQ1),
        _task("TSK-002", key="IMP-B", rid=REQ2, allocations=()),
    )
    draft = estimate(_request(tasks))
    assert draft.by_discipline["frontend"].complete is True
    assert draft.by_discipline["unassigned"].complete is False
    assert draft.by_discipline["unassigned"].excluded_line_ids == draft.project.excluded_line_ids


def test_error_messages_do_not_echo_mapping_keys_extra_fields_or_identifiers() -> None:
    raw = _raw_request()
    raw["specialist_result_refs"] = {"backendSENTINEL9Q": "x"}
    with pytest.raises(EstimationInputError) as mapping_key:
        build_request(raw)
    assert "SENTINEL9Q" not in str(mapping_key.value)

    raw = _raw_request()
    raw["tasks"][0]["allocations"][0]["hours"]["SENTINEL9Q"] = 1.0
    with pytest.raises(EstimationInputError) as extra_field:
        build_request(raw)
    assert "SENTINEL9Q" not in str(extra_field.value)
    assert "hours" in str(extra_field.value)

    raw = _raw_request()
    raw["tasks"].append(dict(raw["tasks"][0], task_id="TSK-SENTINEL9Q"))
    raw["tasks"].append(dict(raw["tasks"][0], task_id="TSK-SENTINEL9Q"))
    with pytest.raises(EstimationInputError) as duplicate:
        estimate(build_request(raw))
    assert "SENTINEL9Q" not in str(duplicate.value)


def test_a_missing_governance_assessment_names_a_count_not_identifiers() -> None:
    governance = _governance({REQ1: "evidence_backed"})
    with pytest.raises(EstimationInputError) as info:
        estimate(
            _request(
                (_task(),), requirements=(_snapshot(REQ1), _snapshot(REQ2)), governance=governance
            )
        )
    assert REQ2 not in str(info.value)
    assert "1 requirement" in str(info.value)


def test_an_estimate_with_no_requirements_is_incomplete_and_needs_inputs() -> None:
    governance = _governance({})
    draft = estimate(_request((), requirements=(), governance=governance))
    assert draft.lines == ()
    assert draft.project.complete is False
    assert draft.readiness is Readiness.NEEDS_INPUTS
    assert "the estimate contains no requirements" in draft.outstanding_issues


def test_an_integer_mapping_key_does_not_leak_its_value() -> None:
    raw = _raw_request()
    raw["specialist_result_refs"] = {987654321: "x"}
    with pytest.raises(EstimationInputError) as info:
        build_request(raw)
    assert "987654321" not in str(info.value)
