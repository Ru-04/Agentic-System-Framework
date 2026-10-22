from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.contract import SpecialistInput, SpecialistOutput

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "WebDesk_Agentic_Requirement_Platform_Specs"
    / "AGENT_REGISTRY.yaml"
)


def _request(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": "req-1",
        "workspace_id": "ws-a",
        "specialist_id": "shopify",
        "requirement_ids": ["REQ-001"],
        "evidence_refs": [],
        "task": "assess storefront feasibility",
    }
    payload.update(overrides)
    return payload


def _output(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": "req-1",
        "workspace_id": "ws-a",
        "specialist_id": "shopify",
        "status": "incomplete",
        "findings": [],
        "unknowns": ["no evidence retrieved"],
    }
    payload.update(overrides)
    return payload


def test_catalog_has_exactly_the_seven_categories_in_governance() -> None:
    assert {specialist.value for specialist in SpecialistId} == {
        "shopify",
        "shift4shop",
        "wordpress_woocommerce",
        "bigcommerce",
        "magento_adobe_commerce",
        "standalone_applications",
        "middleware_applications",
    }
    assert set(REGISTRY_CAPABILITY_IDS) == set(SpecialistId)


def test_registry_capability_ids_exist_in_agent_registry() -> None:
    registry_text = REGISTRY.read_text(encoding="utf-8")
    for specialist, capability_id in REGISTRY_CAPABILITY_IDS.items():
        assert f"  - id: {capability_id}\n" in registry_text, specialist


def test_valid_request_parses() -> None:
    request = SpecialistInput.model_validate(_request())
    assert request.specialist_id is SpecialistId.SHOPIFY
    assert request.requirement_ids == ("REQ-001",)


@pytest.mark.parametrize(
    "overrides",
    [
        {"approved": True},
        {"permissions": ["grant_permission"]},
        {"routing": "bypass"},
    ],
)
def test_request_rejects_authority_fields(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SpecialistInput.model_validate(_request(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"specialist_id": "unknown_platform"},
        {"requirement_ids": []},
        {"workspace_id": ""},
        {"contract_version": "2.0.0"},
    ],
)
def test_request_rejects_invalid_fields(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SpecialistInput.model_validate(_request(**overrides))


def test_output_rejects_approval_fields() -> None:
    with pytest.raises(ValidationError):
        SpecialistOutput.model_validate(_output(approved_by="reviewer"))


def test_cited_finding_requires_evidence_ref() -> None:
    finding = {"statement": "Storefront supports X", "evidence_status": "cited"}
    with pytest.raises(ValidationError):
        SpecialistOutput.model_validate(_output(status="completed", findings=[finding]))


def test_unverified_finding_needs_no_evidence_ref() -> None:
    finding = {"statement": "Storefront may support X", "evidence_status": "unverified"}
    output = SpecialistOutput.model_validate(
        _output(status="completed", findings=[finding], unknowns=[])
    )
    assert output.findings[0].evidence_refs == ()


def test_incomplete_output_must_declare_unknowns() -> None:
    with pytest.raises(ValidationError):
        SpecialistOutput.model_validate(_output(unknowns=[]))


def test_failed_output_is_valid_without_findings() -> None:
    output = SpecialistOutput.model_validate(_output(status="failed", unknowns=[]))
    assert output.status == "failed"
