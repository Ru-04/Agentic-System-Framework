"""Adapter contract v0.2 and the synthetic vertical slice (INT-01, INT-02). Synthetic only."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from webdesk.specialists.adapter_v02 import (
    ADAPTER_CONTRACT_VERSION,
    CONFIDENCE_STATUS,
    REGISTRY_VERSION,
    AdapterRequest,
    call_adapter,
    check_allowed_actions,
    resolve_capability,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.synthetic_slice import (
    SyntheticSliceProvider,
    build_request,
    load_fixture,
    run_slice,
)

SEVEN = list(SpecialistId)


def _envelope(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "adapter_contract_version": "0.2",
        "request_id": "REQ-T-1",
        "workspace_id": "ws-synthetic",
        "actor_id": "synthetic-operator",
        "specialist_id": SpecialistId.SHOPIFY,
        "capability_id": REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY],
        "requirement_ids": ["REQ-SYN-1"],
        "evidence_refs": [],
        "task": "storefront product checkout settings in the admin",
        "allowed_actions": ["read_evidence"],
        "operator_confirmed": True,
    }
    data.update(overrides)
    return data


def test_envelope_refuses_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AdapterRequest.model_validate(_envelope(approved=True))


def test_envelope_refuses_other_adapter_versions() -> None:
    with pytest.raises(ValidationError):
        AdapterRequest.model_validate(_envelope(adapter_contract_version="0.1"))


@pytest.mark.parametrize("specialist_id", SEVEN)
def test_all_seven_categories_resolve_their_canonical_capability(
    specialist_id: SpecialistId,
) -> None:
    assert (
        resolve_capability(specialist_id, REGISTRY_CAPABILITY_IDS[specialist_id])
        == (REGISTRY_CAPABILITY_IDS[specialist_id])
    )


def test_shift4shop_legacy_identifier_is_the_canonical_capability() -> None:
    assert REGISTRY_CAPABILITY_IDS[SpecialistId.SHIFT4SHOP] == "CAP-3D-CART-SHIFT-SHOPIFY"
    with pytest.raises(ValueError, match="capability_mismatch"):
        resolve_capability(SpecialistId.SHIFT4SHOP, "CAP-SHIFT4SHOP-NEW")


def test_wrong_capability_is_refused_by_the_adapter() -> None:
    request = AdapterRequest.model_validate(_envelope(capability_id="CAP-NOT-A-REAL-ONE"))
    response = call_adapter(SyntheticSliceProvider(SpecialistId.SHOPIFY), request)
    assert response.status == "failed"
    assert response.error_code == "capability_mismatch"


def test_operator_confirmation_is_required() -> None:
    request = AdapterRequest.model_validate(_envelope(operator_confirmed=False))
    response = call_adapter(SyntheticSliceProvider(SpecialistId.SHOPIFY), request)
    assert response.status == "failed"
    assert response.error_code == "operator_confirmation_required"


@pytest.mark.parametrize(
    "action",
    [
        "approve_artifact",
        "grant_permission",
        "modify_routing",
        "accept_inferred_requirement",
        "write_requirement",
        "resolve_blocker",
    ],
)
def test_forbidden_actions_are_refused(action: str) -> None:
    request = AdapterRequest.model_validate(_envelope(allowed_actions=[action]))
    response = call_adapter(SyntheticSliceProvider(SpecialistId.SHOPIFY), request)
    assert response.status == "failed"
    assert response.error_code == "action_forbidden"


def test_unknown_action_is_refused() -> None:
    request = AdapterRequest.model_validate(_envelope(allowed_actions=["do_anything"]))
    response = call_adapter(SyntheticSliceProvider(SpecialistId.SHOPIFY), request)
    assert response.error_code == "action_unknown"


def test_action_outside_provider_declaration_is_refused() -> None:
    with pytest.raises(ValueError, match="action_forbidden"):
        check_allowed_actions(("read_evidence",), frozenset({"propose_candidates"}))


def test_evidence_from_another_workspace_is_refused_by_the_shared_harness() -> None:
    envelope = _envelope(
        evidence_refs=[{"workspace_id": "ws-other", "source_id": "S", "locator": "1-2"}]
    )
    response = call_adapter(
        SyntheticSliceProvider(SpecialistId.SHOPIFY), AdapterRequest.model_validate(envelope)
    )
    assert response.status == "failed"
    assert response.error_code == "workspace_mismatch"


class _RaisingProvider:
    declared_actions: frozenset[str] = frozenset({"read_evidence"})
    specialist_id = SpecialistId.SHOPIFY

    def run(self, request: Any) -> Any:
        raise RuntimeError("provider failure")


def test_provider_failure_is_mapped_without_echoing_the_provider_text() -> None:
    response = call_adapter(_RaisingProvider(), AdapterRequest.model_validate(_envelope()))
    assert response.status == "failed"
    assert response.error_code == "provider_failure"
    assert "provider failure" not in response.model_dump_json()


def test_confidence_is_never_invented() -> None:
    response, _ = run_slice(load_fixture(), operator_confirmed=True)
    assert response.confidence is None
    assert response.confidence_status == CONFIDENCE_STATUS


def test_registry_version_and_adapter_version_are_recorded() -> None:
    response, audit = run_slice(load_fixture(), operator_confirmed=True)
    assert response.registry_version == REGISTRY_VERSION
    assert response.adapter_contract_version == ADAPTER_CONTRACT_VERSION
    assert audit["registry_version"] == REGISTRY_VERSION


def test_synthetic_slice_matches_the_fixture_expectations() -> None:
    fixture = load_fixture()
    response, _ = run_slice(fixture, operator_confirmed=True)
    expected: dict[str, Any] = fixture["expected_response_shape"]  # type: ignore[assignment]
    assert response.status == expected["status"]
    assert response.request_id == expected["request_id"]
    assert list(response.findings) == []
    for item in expected["unknowns"]:
        assert item in response.unknowns


def test_synthetic_slice_produces_no_citations_or_capability_claims() -> None:
    response, _ = run_slice(load_fixture(), operator_confirmed=True)
    assert response.findings == ()
    assert "feasib" in " ".join(response.unknowns)


def test_slice_refuses_without_operator_confirmation() -> None:
    response, _ = run_slice(load_fixture(), operator_confirmed=False)
    assert response.status == "failed"
    assert response.error_code == "operator_confirmation_required"


def test_audit_record_holds_hashes_not_task_text() -> None:
    fixture = load_fixture()
    _, audit = run_slice(fixture, operator_confirmed=True)
    task = str(fixture["request"]["task"])  # type: ignore[index]
    assert task not in str(audit)
    assert len(audit["request_sha256"]) == 64
    assert len(audit["response_sha256"]) == 64


def test_build_request_uses_the_canonical_capability() -> None:
    request = build_request(load_fixture(), operator_confirmed=True)
    assert request.capability_id == REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY]


@pytest.mark.parametrize("specialist_id", SEVEN)
def test_every_category_runs_its_foundation_path_through_the_adapter(
    specialist_id: SpecialistId,
) -> None:
    envelope = _envelope(
        specialist_id=specialist_id,
        capability_id=REGISTRY_CAPABILITY_IDS[specialist_id],
    )
    response = call_adapter(
        SyntheticSliceProvider(specialist_id), AdapterRequest.model_validate(envelope)
    )
    assert response.status == "incomplete"
    assert response.specialist_id is specialist_id
