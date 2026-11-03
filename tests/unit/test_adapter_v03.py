"""Adapter contract v0.3: envelope, confirmation gate, evidence mapping and check outcome (OPEN-03,
OPEN-07, OPEN-08). Synthetic inputs only. No test here depends on live documentation."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from webdesk.specialists.adapter_v03 import (
    ADAPTER_CONTRACT_VERSION,
    ERROR_CONFIRMATION_NOT_VERIFIED,
    ERROR_REQUEST_INVALID,
    ERROR_VERSION_UNSUPPORTED,
    EVIDENCE_STATUS_TO_AI,
    AdapterError,
    AdapterRequest,
    AdapterRequestError,
    AdapterResponse,
    CheckOutcome,
    CitationAssessment,
    ConfirmationBinding,
    RefuseAllConfirmations,
    UnmappedValueError,
    VerifiedConfirmation,
    audit_record,
    binding_for,
    call_adapter,
    check_outcome,
    map_evidence_status,
    parse_request,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.contract import EvidenceRef
from webdesk.specialists.mock import MockSpecialist

RUN_ID = UUID("6f1c2d3e-0000-4000-8000-000000000001")
PROJECT_ID = UUID("6f1c2d3e-0000-4000-8000-000000000002")
TASK = "storefront product checkout settings in the admin"


def _actions_digest(actions: Any) -> str:
    # Contract v1.1 encoding: SHA-256 hex of the sorted unique compact JSON array.
    canonical = json.dumps(sorted(set(actions)), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def _envelope(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "adapter_contract_version": "0.3",
        "request_id": "REQ-V03-1",
        "workspace_id": "ws-a",
        "run_id": str(RUN_ID),
        "project_id": str(PROJECT_ID),
        "specialist_id": SpecialistId.SHOPIFY.value,
        "capability_id": REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY],
        "requirement_refs": ["REQ-001"],
        "evidence_refs": [],
        "task": TASK,
        "allowed_actions": ["read_evidence"],
        "source_scope_digest": "a" * 64,
        "confirmation_ref": "conf-opaque-1",
    }
    data.update(overrides)
    if "allowed_actions_digest" not in overrides:
        data["allowed_actions_digest"] = _actions_digest(data["allowed_actions"])
    return data


def _request(**overrides: Any) -> AdapterRequest:
    return parse_request(_envelope(**overrides))


class RecordingVerifier:
    def __init__(self, actor: str = "actor-from-proof", accept: bool = True) -> None:
        self.actor = actor
        self.accept = accept
        self.calls: list[tuple[str, ConfirmationBinding]] = []

    def verify(
        self, confirmation_ref: str, binding: ConfirmationBinding
    ) -> VerifiedConfirmation | None:
        self.calls.append((confirmation_ref, binding))
        return VerifiedConfirmation(actor_ref=self.actor) if self.accept else None


class RaisingVerifier:
    def verify(
        self, confirmation_ref: str, binding: ConfirmationBinding
    ) -> VerifiedConfirmation | None:
        raise RuntimeError("internal detail: database row 42")


class FixedAssessor:
    def __init__(self, assessments: list[CitationAssessment]) -> None:
        self._assessments = assessments

    def assess(
        self, statement: str, evidence_refs: tuple[EvidenceRef, ...]
    ) -> list[CitationAssessment]:
        return list(self._assessments)


SUBSTANTIATES = CitationAssessment(verified=True, applicable=True, substantiates=True, limits=False)
LIMITS = CitationAssessment(verified=True, applicable=True, substantiates=False, limits=True)
NOT_APPLICABLE = CitationAssessment(
    verified=True, applicable=False, substantiates=True, limits=False
)
UNVERIFIED = CitationAssessment(verified=False, applicable=True, substantiates=True, limits=False)
NOT_SUBSTANTIATING = CitationAssessment(
    verified=True, applicable=True, substantiates=False, limits=False
)


# Envelope


def test_parse_accepts_a_v03_envelope() -> None:
    request = _request()
    assert request.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert request.run_id == RUN_ID
    assert request.project_id == PROJECT_ID


@pytest.mark.parametrize("version", ["0.2", "0.4", "1.0", None])
def test_parse_refuses_any_other_version_without_fallback(version: object) -> None:
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(adapter_contract_version=version))
    assert raised.value.code == ERROR_VERSION_UNSUPPORTED


@pytest.mark.parametrize("field", ["actor_id", "operator_confirmed", "workspace_authority"])
def test_parse_refuses_caller_authority_fields(field: str) -> None:
    value: object = True if field == "operator_confirmed" else "caller-supplied"
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(**{field: value}))
    assert raised.value.code == ERROR_REQUEST_INVALID


def test_parse_requires_a_confirmation_reference() -> None:
    data = _envelope()
    del data["confirmation_ref"]
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(data)
    assert raised.value.code == ERROR_REQUEST_INVALID


@pytest.mark.parametrize("value", ["", "   "])
def test_parse_refuses_a_blank_confirmation_reference(value: str) -> None:
    with pytest.raises(AdapterRequestError):
        parse_request(_envelope(confirmation_ref=value))


def test_parse_refuses_a_run_id_that_is_not_a_uuid() -> None:
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(run_id="run-1"))
    assert raised.value.code == ERROR_REQUEST_INVALID


def test_parse_refuses_a_non_mapping() -> None:
    with pytest.raises(AdapterRequestError):
        parse_request("not an envelope")  # type: ignore[arg-type]


def test_request_model_itself_forbids_extra_fields() -> None:
    data = _envelope(actor_id="caller")
    with pytest.raises(ValidationError):
        AdapterRequest.model_validate(data)


# Confirmation gate


def test_default_verifier_refuses_everything_and_never_runs_the_provider() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    response, verified = call_adapter(provider, _request(), RefuseAllConfirmations())
    assert provider.calls == 0
    assert verified is None
    assert response.status == "failed"
    assert response.error == AdapterError(code=ERROR_CONFIRMATION_NOT_VERIFIED)
    assert response.findings == ()


def test_a_raising_verifier_is_a_refusal_and_its_text_is_not_echoed() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    response, verified = call_adapter(provider, _request(), RaisingVerifier())  # type: ignore[arg-type]
    assert provider.calls == 0
    assert verified is None
    assert response.error is not None
    assert response.error.code == ERROR_CONFIRMATION_NOT_VERIFIED
    assert "database row" not in response.model_dump_json()


def test_a_verified_confirmation_runs_the_provider_once() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    verifier = RecordingVerifier()
    response, verified = call_adapter(provider, _request(), verifier)
    assert provider.calls == 1
    assert len(verifier.calls) == 1
    assert verified == VerifiedConfirmation(actor_ref="actor-from-proof")
    assert response.error is None
    assert response.status == "incomplete"


def test_verifier_receives_the_reference_and_the_exact_binding() -> None:
    verifier = RecordingVerifier()
    call_adapter(MockSpecialist(SpecialistId.SHOPIFY), _request(), verifier)
    ref, binding = verifier.calls[0]
    assert ref == "conf-opaque-1"
    assert binding == binding_for(_request())
    assert binding.run_id == RUN_ID
    assert binding.project_id == PROJECT_ID
    assert binding.specialist_id is SpecialistId.SHOPIFY
    assert binding.capability_id == REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY]


def test_binding_digests_change_with_requirements_and_actions() -> None:
    base = binding_for(_request())
    assert binding_for(_request(requirement_refs=["REQ-002"])) != base
    assert binding_for(_request(allowed_actions=["propose_candidates"])) != base
    assert binding_for(_request(request_id="REQ-OTHER")) == base


def test_a_forbidden_action_is_refused_before_the_confirmation_is_consumed() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    verifier = RecordingVerifier()
    response, verified = call_adapter(
        provider, _request(allowed_actions=["approve_artifact"]), verifier
    )
    assert provider.calls == 0
    assert verifier.calls == []
    assert verified is None
    assert response.error == AdapterError(code="action_forbidden")


def test_capability_mismatch_is_refused_before_the_provider_runs() -> None:
    provider = MockSpecialist(SpecialistId.WORDPRESS_WOOCOMMERCE)
    response, _ = call_adapter(
        provider,
        _request(
            specialist_id=SpecialistId.WORDPRESS_WOOCOMMERCE.value,
            capability_id=REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY],
        ),
        RecordingVerifier(),
    )
    assert provider.calls == 0
    assert response.error == AdapterError(code="capability_mismatch")


@pytest.mark.parametrize(
    ("actions", "code"),
    [
        (["approve_artifact"], "action_forbidden"),
        (["grant_permission"], "action_forbidden"),
        (["fly_to_moon"], "action_unknown"),
    ],
)
def test_forbidden_and_unknown_actions_are_refused(actions: list[str], code: str) -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    response, _ = call_adapter(provider, _request(allowed_actions=actions), RecordingVerifier())
    assert provider.calls == 0
    assert response.error == AdapterError(code=code)


def test_an_action_the_provider_did_not_declare_is_refused() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, declared_actions=frozenset({"read_evidence"}))
    response, _ = call_adapter(
        provider, _request(allowed_actions=["propose_candidates"]), RecordingVerifier()
    )
    assert provider.calls == 0
    assert response.error == AdapterError(code="action_forbidden")


# Response model


def test_response_refuses_extra_fields_including_actor_fields() -> None:
    response, _ = call_adapter(
        MockSpecialist(SpecialistId.SHOPIFY), _request(), RecordingVerifier()
    )
    data = response.model_dump(mode="json") | {"actor_id": "caller"}
    with pytest.raises(ValidationError):
        AdapterResponse.model_validate(data)


def test_an_error_requires_a_failed_status() -> None:
    with pytest.raises(ValidationError):
        AdapterResponse(
            adapter_contract_version="0.3",
            specialist_contract_version="1.0.0",
            request_id="REQ-1",
            workspace_id="ws-a",
            specialist_id=SpecialistId.SHOPIFY,
            capability_id="CAP-ECOMMERCE",
            registry_version="v",
            status="completed",
            error=AdapterError(code="action_forbidden"),
        )


def test_confidence_is_never_invented() -> None:
    response, _ = call_adapter(
        MockSpecialist(SpecialistId.SHOPIFY), _request(), RecordingVerifier()
    )
    dumped = response.model_dump(mode="json")
    assert dumped["confidence_status"] == "not_assessed"
    assert dumped["confidence"] is None


def test_audit_record_takes_the_actor_from_the_proof_and_holds_no_task_text() -> None:
    request = _request()
    response, verified = call_adapter(
        MockSpecialist(SpecialistId.SHOPIFY), request, RecordingVerifier(actor="ai-principal-7")
    )
    record = audit_record(request, response, verified)
    assert record["actor_ref"] == "ai-principal-7"
    assert "actor_id" not in record
    assert TASK not in str(record)
    assert record["run_id"] == str(RUN_ID)


def test_audit_record_has_no_actor_for_a_refusal_before_verification() -> None:
    request = _request()
    response, verified = call_adapter(
        MockSpecialist(SpecialistId.SHOPIFY), request, RefuseAllConfirmations()
    )
    assert audit_record(request, response, verified)["actor_ref"] is None


# Evidence mapping (OPEN-07)


def test_mapping_table_covers_exactly_the_two_adapter_values() -> None:
    assert set(EVIDENCE_STATUS_TO_AI) == {"cited", "unverified"}


def test_cited_never_maps_to_verified() -> None:
    assert map_evidence_status("cited") == "unverified"
    assert map_evidence_status("unverified") == "unverified"
    assert "verified" not in set(EVIDENCE_STATUS_TO_AI.values())


@pytest.mark.parametrize(
    "value", ["verified", "partially_verified", "conflicting", "CITED", "", "approved"]
)
def test_unmapped_values_raise_and_are_never_collapsed(value: str) -> None:
    with pytest.raises(UnmappedValueError):
        map_evidence_status(value)


def test_mapping_table_cannot_be_edited_at_runtime() -> None:
    with pytest.raises(TypeError):
        EVIDENCE_STATUS_TO_AI["cited"] = "verified"  # type: ignore[index]


# Check outcome (OPEN-08)


def test_no_assessments_is_unknown() -> None:
    assert check_outcome(()) is CheckOutcome.UNKNOWN


def test_a_citation_count_alone_never_yields_supported() -> None:
    assert check_outcome([NOT_SUBSTANTIATING] * 25) is CheckOutcome.UNKNOWN


def test_unverified_or_inapplicable_substantiating_citations_are_unknown() -> None:
    assert check_outcome([UNVERIFIED] * 3) is CheckOutcome.UNKNOWN
    assert check_outcome([NOT_APPLICABLE] * 3) is CheckOutcome.UNKNOWN


def test_one_applicable_verified_substantiating_passage_is_supported() -> None:
    assert check_outcome([NOT_SUBSTANTIATING, SUBSTANTIATES]) is CheckOutcome.SUPPORTED


def test_an_applicable_verified_limitation_is_unsupported() -> None:
    assert check_outcome([LIMITS]) is CheckOutcome.UNSUPPORTED


def test_support_and_limitation_together_are_contradictory_and_unknown() -> None:
    assert check_outcome([SUBSTANTIATES, LIMITS]) is CheckOutcome.UNKNOWN


def test_an_inapplicable_limitation_does_not_count() -> None:
    limit_not_applicable = CitationAssessment(
        verified=True, applicable=False, substantiates=False, limits=True
    )
    assert check_outcome([SUBSTANTIATES, limit_not_applicable]) is CheckOutcome.SUPPORTED


def test_finding_outcome_is_unknown_without_an_assessor() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, canned=_cited_output)
    response, _ = call_adapter(provider, _request(), RecordingVerifier())
    assert [f.check_outcome for f in response.findings] == [CheckOutcome.UNKNOWN] * 2


def test_an_assessor_can_make_a_cited_finding_supported() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, canned=_cited_output)
    response, _ = call_adapter(
        provider, _request(), RecordingVerifier(), FixedAssessor([SUBSTANTIATES])
    )
    cited = [f for f in response.findings if f.evidence_status == "cited"]
    assert [f.check_outcome for f in cited] == [CheckOutcome.SUPPORTED]


def test_an_unverified_finding_is_never_supported_even_with_an_assessor() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, canned=_cited_output)
    response, _ = call_adapter(
        provider, _request(), RecordingVerifier(), FixedAssessor([SUBSTANTIATES])
    )
    unverified = [f for f in response.findings if f.evidence_status == "unverified"]
    assert [f.check_outcome for f in unverified] == [CheckOutcome.UNKNOWN]


def test_many_non_substantiating_citations_leave_a_cited_finding_unknown() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, canned=_cited_output)
    response, _ = call_adapter(
        provider, _request(), RecordingVerifier(), FixedAssessor([NOT_SUBSTANTIATING] * 10)
    )
    cited = [f for f in response.findings if f.evidence_status == "cited"]
    assert [f.check_outcome for f in cited] == [CheckOutcome.UNKNOWN]


def _cited_output(request: Any) -> dict[str, Any]:
    ref = {"workspace_id": "ws-a", "source_id": "fx-1", "locator": "1-40"}
    return {
        "contract_version": "1.0.0",
        "request_id": request.request_id,
        "workspace_id": request.workspace_id,
        "specialist_id": request.specialist_id.value,
        "status": "incomplete",
        "findings": [
            {
                "statement": "Source addresses storefront api.",
                "evidence_status": "cited",
                "evidence_refs": [ref],
            },
            {
                "statement": "Unverified remark.",
                "evidence_status": "unverified",
                "evidence_refs": [],
            },
        ],
        "unknowns": ["fixture"],
    }
