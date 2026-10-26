"""Orchestration: stage order, authorization gate, short-circuits, fixed flags, and log hygiene."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from webdesk_ai import synthetic
from webdesk_ai.catalog import default_registry
from webdesk_ai.contracts import (
    AgentStatus,
    Claim,
    ClaimType,
    EvidenceOrigin,
    EvidenceReference,
    EvidenceStatus,
    FeasibilityStatus,
    RequirementAnalysisResult,
    SpecialistInvestigationResult,
)
from webdesk_ai.foundation.client import FoundationReadClient, PrincipalCredential
from webdesk_ai.models import ErrorClass, ScriptedModel
from webdesk_ai.orchestration import (
    ReviewFlags,
    Stage,
    WorkflowConfig,
    _traceability_violations,
    count_unsupported_claims,
    run_workflow,
)
from webdesk_ai.specialists.shopify import SyntheticShopifyEvidence

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
TOKEN = "orchestration-test-token"  # noqa: S105 - synthetic fixture


def _client(run_status: str = "running") -> FoundationReadClient:
    foundation = synthetic.build_expanded_foundation(
        token=TOKEN, now=NOW, expires_at=NOW + timedelta(minutes=15)
    )
    foundation.run_status = run_status
    return FoundationReadClient(
        transport=foundation,
        credential=PrincipalCredential(token=TOKEN, expires_at=NOW + timedelta(minutes=15)),
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        clock=lambda: NOW,
    )


def _config(
    model: ScriptedModel, authorized: frozenset[str] = frozenset({"shopify_specialist"})
) -> WorkflowConfig:
    return WorkflowConfig(
        model=model,
        registry=default_registry(),
        evidence=SyntheticShopifyEvidence(),
        authorized_categories=authorized,
        specialist_timeout_seconds=30.0,
    )


@pytest.fixture(scope="module")
def happy_package():  # type: ignore[no-untyped-def]
    model = ScriptedModel(outcomes=[synthetic.EXPANDED_ANALYSIS])
    return run_workflow(client=_client(), config=_config(model))


def test_stages_run_in_the_specified_order(happy_package) -> None:  # type: ignore[no-untyped-def]
    stages = [record.stage for record in happy_package.stage_log]
    assert stages == [
        Stage.LOAD_CONTEXT,
        Stage.ANALYZE,
        Stage.VALIDATE_ANALYSIS,
        Stage.CLARIFICATIONS,
        Stage.PLAN_ROUTING,
        Stage.RUN_SPECIALISTS,
        Stage.VALIDATE_OUTPUTS,
        Stage.HUMAN_REVIEW,
    ]
    assert happy_package.status == "human_review_required"


def test_authorized_specialist_runs_and_unavailable_platform_is_skipped(happy_package) -> None:  # type: ignore[no-untyped-def]
    assert [r.agent_id for r in happy_package.specialist_results] == [
        "specialist:shopify_specialist"
    ]
    skipped = {(s.category_id, s.reason) for s in happy_package.skipped_categories}
    assert ("3dcart_shift4shop_specialist", "unavailable") in skipped
    assert happy_package.unsupported_claim_count == 0


def test_routing_stays_recommendation_only(happy_package) -> None:  # type: ignore[no-untyped-def]
    assert happy_package.flags.machine_routing_enabled is False
    assert any(
        s.stage is Stage.PLAN_ROUTING and "machine routing disabled" in s.detail
        for s in happy_package.stage_log
    )


def test_unauthorized_category_is_skipped_and_never_instantiated() -> None:
    model = ScriptedModel(outcomes=[synthetic.EXPANDED_ANALYSIS])
    package = run_workflow(client=_client(), config=_config(model, authorized=frozenset()))
    assert package.specialist_results == ()
    assert ("shopify_specialist", "not_authorized") in {
        (s.category_id, s.reason) for s in package.skipped_categories
    }


def test_failed_analysis_short_circuits_to_review_without_specialists() -> None:
    model = ScriptedModel(outcomes=[ErrorClass.PERMANENT])
    package = run_workflow(client=_client(), config=_config(model))
    assert package.status == "analysis_failed"
    assert package.analysis.status is AgentStatus.FAILED
    stages = [record.stage for record in package.stage_log]
    assert Stage.RUN_SPECIALISTS not in stages
    assert stages[-1] is Stage.HUMAN_REVIEW


def test_invalid_analysis_is_not_passed_to_specialists() -> None:
    hidden = str(synthetic.SEG_HIDDEN)
    bad = (
        '{"requirements": [{"draft_id": "R1", "source_segment_ids": ["' + hidden + '"],'
        ' "original_wording": "x", "normalized_statement": "x",'
        ' "requirement_type": "functional", "origin": "client_explicit",'
        ' "status": "normalized"}]}'
    )
    model = ScriptedModel(outcomes=[bad, bad])
    package = run_workflow(client=_client(), config=_config(model))
    assert package.status == "analysis_failed"
    assert package.specialist_results == ()


def test_inactive_run_is_refused_before_any_model_call() -> None:
    model = ScriptedModel(outcomes=[synthetic.EXPANDED_ANALYSIS])
    package = run_workflow(client=_client(run_status="cancelled"), config=_config(model))
    assert package.status == "analysis_failed"
    assert model.calls == 0


def test_review_flags_cannot_claim_approval() -> None:
    with pytest.raises(ValidationError):
        ReviewFlags(scope_approved=True)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ReviewFlags(foundation_writes=1)  # type: ignore[arg-type]
    assert ReviewFlags().human_review_required is True


def test_unsupported_claims_are_counted_unless_backed_by_approved_evidence() -> None:
    synthetic_ref = EvidenceReference(
        evidence_id="SYN-1",
        origin=EvidenceOrigin.SYNTHETIC_FIXTURE,
        publisher="fixture",
        applies_to_platform="shopify",
        evidence_status=EvidenceStatus.UNVERIFIED,
        relevance_summary="placeholder",
    )
    claim = Claim(
        claim_id="C-1",
        claim_text="Supported by evidence.",
        claim_type=ClaimType.PLATFORM_CAPABILITY,
        evidence_status=EvidenceStatus.VERIFIED,
        feasibility_status=FeasibilityStatus.FEASIBLE,
        evidence_refs=("SYN-1",),
        platform_context="shopify",
    )
    output = SpecialistInvestigationResult(
        task_id="T",
        category_id="shopify_specialist",
        status=AgentStatus.COMPLETED,
        claims=(claim,),
        evidence=(synthetic_ref,),
        registry_version="test",
    )
    assert count_unsupported_claims(output) == 1
    approved = EvidenceReference(
        evidence_id="EV-OK",
        origin=EvidenceOrigin.APPROVED_EXTERNAL,
        publisher="Shopify",
        document_url="https://shopify.dev/docs",
        checked_at=NOW,
        applies_to_platform="shopify",
        evidence_status=EvidenceStatus.VERIFIED,
        relevance_summary="official",
    )
    backed = output.model_copy(
        update={
            "claims": (claim.model_copy(update={"evidence_refs": ("EV-OK",)}),),
            "evidence": (approved,),
        }
    )
    assert count_unsupported_claims(backed) == 0


def test_traceability_check_flags_references_outside_the_visible_set() -> None:
    from webdesk_ai.contracts import (
        AtomicRequirement,
        RequirementOrigin,
        RequirementStatus,
        RequirementType,
        SourceReference,
        SourceSegment,
    )

    visible = {
        synthetic.SEG_A: SourceSegment(
            segment_id=synthetic.SEG_A,
            source_id=synthetic.SOURCE_BRIEF,
            source_version_id=synthetic.VERSION_BRIEF,
            version=1,
            locator_type="txt_line_range",
            locator={"line_start": 1},
            text_content=synthetic.TEXT_A,
            text_truncated=False,
        )
    }
    good_ref = SourceReference(
        source_id=synthetic.SOURCE_BRIEF,
        source_version_id=synthetic.VERSION_BRIEF,
        version=1,
        segment_id=synthetic.SEG_A,
    )
    hidden_ref = good_ref.model_copy(update={"segment_id": synthetic.SEG_HIDDEN})
    requirement = AtomicRequirement(
        requirement_id="REQ-001",
        project_id=synthetic.PROJECT_ID,
        origin=RequirementOrigin.CLIENT_EXPLICIT,
        original_wording=synthetic.TEXT_A,
        normalized_statement="x",
        requirement_type=RequirementType.FUNCTIONAL,
        status=RequirementStatus.NORMALIZED,
        source_refs=(good_ref, hidden_ref),
    )
    analysis = RequirementAnalysisResult(
        run_id=synthetic.RUN_ID,
        project_id=synthetic.PROJECT_ID,
        status=AgentStatus.COMPLETED,
        requirements=(requirement,),
        registry_version="test",
    )
    assert _traceability_violations(analysis, visible) == 1


def test_logs_never_carry_client_text_or_credentials(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="webdesk_ai")
    model = ScriptedModel(outcomes=[ErrorClass.TRANSIENT, synthetic.EXPANDED_ANALYSIS])
    run_workflow(client=_client(), config=_config(model))
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert logged
    assert TOKEN not in logged
    assert synthetic.TEXT_A not in logged
    assert synthetic.TEXT_H not in logged
