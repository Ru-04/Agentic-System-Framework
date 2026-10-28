"""Seven-specialist conformance through adapter v0.2 (synthetic fixtures only).

Each specialist must resolve its canonical capability, honour operator and workspace restrictions,
produce a contract-valid response and an audit record with no task or page text. Foundation paths
are not evidence-backed investigations; the statuses below say so explicitly.
"""

from __future__ import annotations

import pytest

from webdesk.investigation.engine import Edition, Page
from webdesk.investigation.specialists import CATALOG, InvestigationProvider
from webdesk.specialists.adapter_v02 import (
    AdapterRequest,
    AdapterResponse,
    audit_record,
    call_adapter,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId

WS = "ws-synthetic"
TASKS: dict[SpecialistId, str] = {
    SpecialistId.SHOPIFY: "plan feature availability",
    SpecialistId.SHIFT4SHOP: "product read API",
    SpecialistId.WORDPRESS_WOOCOMMERCE: "product variation price",
    SpecialistId.BIGCOMMERCE: "product catalog read",
    SpecialistId.MAGENTO_ADOBE_COMMERCE: "release history catalog import",
    SpecialistId.STANDALONE_APPLICATIONS: "application architecture selection",
    SpecialistId.MIDDLEWARE_APPLICATIONS: "webhook delivery retry",
}
SEVEN = list(TASKS)


def _request(
    specialist: SpecialistId, *, confirmed: bool = True, workspace: str = WS
) -> AdapterRequest:
    return AdapterRequest.model_validate(
        {
            "adapter_contract_version": "0.2",
            "request_id": f"REQ-CONF-{specialist.value}",
            "workspace_id": workspace,
            "actor_id": "operator-1",
            "specialist_id": specialist,
            "capability_id": REGISTRY_CAPABILITY_IDS[specialist],
            "requirement_ids": ["REQ-SYN-1"],
            "evidence_refs": [],
            "task": TASKS[specialist],
            "allowed_actions": ["read_evidence"],
            "operator_confirmed": confirmed,
        }
    )


def _foreign_page(platform: str) -> Page:
    return Page(
        url="https://developer.woocommerce.com/docs/products/variations",
        final_url="https://developer.woocommerce.com/docs/products/variations",
        platform=platform,
        edition=Edition.NOT_APPLICABLE,
        version="1.0",
        workspace_id="ws-other",
        text="product variation price",
        synthetic=True,
    )


@pytest.mark.parametrize("specialist", SEVEN)
def test_canonical_capability_resolves_through_the_adapter(specialist: SpecialistId) -> None:
    response = call_adapter(InvestigationProvider(specialist, (), "1.0"), _request(specialist))
    assert response.error_code != "capability_mismatch"
    assert response.capability_id == REGISTRY_CAPABILITY_IDS[specialist]
    assert CATALOG[specialist]


@pytest.mark.parametrize("specialist", SEVEN)
def test_response_is_contract_valid_and_never_carries_confidence(specialist: SpecialistId) -> None:
    response = call_adapter(InvestigationProvider(specialist, (), "1.0"), _request(specialist))
    assert response.status in {"completed", "incomplete", "failed"}
    assert response.specialist_id is specialist
    assert response.confidence is None
    assert response.confidence_status == "not_assessed"


@pytest.mark.parametrize("specialist", SEVEN)
def test_operator_confirmation_is_enforced_before_any_run(specialist: SpecialistId) -> None:
    response = call_adapter(
        InvestigationProvider(specialist, (), "1.0"), _request(specialist, confirmed=False)
    )
    assert response.status == "failed"
    assert response.error_code == "operator_confirmation_required"
    assert response.findings == ()


@pytest.mark.parametrize("specialist", SEVEN)
def test_no_pages_gives_no_findings_and_declared_feasibility_unknown(
    specialist: SpecialistId,
) -> None:
    response: AdapterResponse = call_adapter(
        InvestigationProvider(specialist, (), "1.0"), _request(specialist)
    )
    assert response.findings == ()
    assert any("feasibility is not determined" in u for u in response.unknowns)


@pytest.mark.parametrize("specialist", SEVEN)
def test_foreign_workspace_evidence_is_refused_and_never_cited(specialist: SpecialistId) -> None:
    provider = InvestigationProvider(specialist, (_foreign_page("woocommerce"),), "1.0")
    response = call_adapter(provider, _request(specialist))
    assert response.findings == ()
    assert response.status == "failed"
    assert any(u.startswith("[REFUSE]") for u in response.unknowns)


@pytest.mark.parametrize("specialist", SEVEN)
def test_audit_record_holds_identifiers_and_hashes_not_task_or_page_text(
    specialist: SpecialistId,
) -> None:
    request = _request(specialist)
    response = call_adapter(InvestigationProvider(specialist, (), "1.0"), request)
    record = audit_record(request, response)
    assert TASKS[specialist] not in str(record)
    assert "task" not in record


def test_standalone_and_middleware_have_no_platform_source_and_say_so() -> None:
    for specialist in (SpecialistId.STANDALONE_APPLICATIONS, SpecialistId.MIDDLEWARE_APPLICATIONS):
        response = call_adapter(InvestigationProvider(specialist, (), "1.0"), _request(specialist))
        assert response.findings == ()
        assert any("unsupported_source" in u for u in response.unknowns)


def test_shift4shop_reports_source_unavailability_not_a_capability_claim() -> None:
    response = call_adapter(
        InvestigationProvider(SpecialistId.SHIFT4SHOP, (), "1.0"),
        _request(SpecialistId.SHIFT4SHOP),
    )
    assert response.findings == ()
    assert any("unsupported_source" in u for u in response.unknowns)
