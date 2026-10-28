"""SOURCE-REFUSAL-01: refusal, unsupported-source and inactive configuration stay distinct.

Synthetic fixtures only. An unauthorized access is never reported as an unsupported source, and an
inactive source is never reported as an unauthorized access.
"""

from __future__ import annotations

from tests.support.authority import call_adapter, run_in_harness
from webdesk.investigation.engine import (
    Capability,
    ClaimKind,
    Edition,
    Finding,
    Outcome,
    Page,
    investigate,
)
from webdesk.investigation.specialists import InvestigationProvider, canonical_capability
from webdesk.specialists.adapter_v02 import (
    ERROR_AUTHORIZATION_REFUSED,
    AdapterRequest,
)
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import SpecialistInput

WS = "ws-synthetic"
WOO_VARIATION = Capability(
    "product variation pricing",
    "woocommerce",
    Edition.NOT_APPLICABLE,
    ClaimKind.FEATURE,
    ("variation", "price"),
)
MAGENTO_CATALOG = Capability(
    "catalog import",
    "magento_open_source",
    Edition.MAGENTO_OPEN_SOURCE,
    ClaimKind.FEATURE,
    ("catalog",),
)
SHOPIFY_PLAN = Capability(
    "plan feature availability",
    "shopify",
    Edition.NOT_APPLICABLE,
    ClaimKind.FEATURE,
    ("plan", "feature"),
)
OFF_BOUNDARY_URL = "https://developer.woocommerce.com/blog/variations"
APPROVED_URL = "https://developer.woocommerce.com/docs/products/variations"


def _page(
    url: str,
    text: str,
    *,
    platform: str = "woocommerce",
    edition: Edition = Edition.NOT_APPLICABLE,
    final_url: str | None = None,
    workspace: str = WS,
    synthetic: bool = True,
) -> Page:
    return Page(
        url=url,
        final_url=final_url or url,
        platform=platform,
        edition=edition,
        version="1.0",
        workspace_id=workspace,
        text=text,
        synthetic=synthetic,
    )


def _adapter_request(task: str) -> AdapterRequest:
    return AdapterRequest.model_validate(
        {
            "adapter_contract_version": "0.2",
            "request_id": "REQ-PREC",
            "workspace_id": WS,
            "actor_id": "operator-1",
            "specialist_id": SpecialistId.WORDPRESS_WOOCOMMERCE,
            "capability_id": canonical_capability(SpecialistId.WORDPRESS_WOOCOMMERCE),
            "requirement_ids": ["REQ-SYN-1"],
            "evidence_refs": [],
            "task": task,
            "allowed_actions": ["read_evidence"],
            "operator_confirmed": True,
        }
    )


def _investigate(capability: Capability, pages: list[Page]) -> Finding:
    return investigate(
        capability, pages, workspace_id=WS, requested_version="1.0", operator_confirmed=True
    )


# --- authorization refusal takes precedence ---------------------------------------------------


def test_unapproved_path_is_refused_not_reported_as_unsupported() -> None:
    finding = _investigate(WOO_VARIATION, [_page(OFF_BOUNDARY_URL, "variation price")])
    assert finding.outcome is Outcome.REFUSED


def test_refusal_takes_precedence_over_a_supporting_authorized_page() -> None:
    pages = [_page(APPROVED_URL, "variation price"), _page(OFF_BOUNDARY_URL, "variation price")]
    finding = _investigate(WOO_VARIATION, pages)
    assert finding.outcome is Outcome.REFUSED
    assert finding.citations == ()


def test_release_only_capability_still_refuses_an_unapproved_domain() -> None:
    devdocs = _page(
        "https://devdocs.magento.com/guides/v2.4/catalog",
        "catalog",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    finding = _investigate(MAGENTO_CATALOG, [devdocs])
    assert finding.outcome is Outcome.REFUSED


def test_redirect_to_an_unauthorized_destination_is_refused_with_no_citation() -> None:
    page = _page(APPROVED_URL, "variation price", final_url="https://example.com/variations")
    finding = _investigate(WOO_VARIATION, [page])
    assert finding.outcome is Outcome.REFUSED
    assert finding.citations == ()


def test_cross_workspace_access_is_refused() -> None:
    page = _page(APPROVED_URL, "variation price", workspace="ws-other")
    finding = _investigate(WOO_VARIATION, [page])
    assert finding.outcome is Outcome.REFUSED


# --- evidence unavailability is unsupported, not refused ------------------------------------------


def test_platform_with_no_approved_source_is_unsupported_not_refused() -> None:
    cap = Capability("x", "shift4shop", Edition.NOT_APPLICABLE, ClaimKind.FEATURE, ("x",))
    page = _page("https://developer.3dcart.com/api/products", "x", platform="shift4shop")
    finding = _investigate(cap, [page])
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE


def test_inactive_source_with_real_page_is_unsupported_not_an_authorization_refusal() -> None:
    real = _page(
        "https://shopify.dev/docs/apps/plans",
        "plan feature availability",
        platform="shopify",
        synthetic=False,
    )
    finding = _investigate(SHOPIFY_PLAN, [real])
    assert finding.outcome is Outcome.UNSUPPORTED_SOURCE
    assert any("not active" in r for r in finding.refusals)


# --- sanitized output ----------------------------------------------------------------


def test_refused_finding_does_not_echo_the_url_or_page_text() -> None:
    page = _page(OFF_BOUNDARY_URL, "PRIVATE SENTENCE variation price")
    finding = _investigate(WOO_VARIATION, [page])
    rendered = repr(finding)
    assert "blog" not in rendered
    assert "PRIVATE SENTENCE" not in rendered


# --- provider and adapter mapping -----------------------------------------------------------------


def test_all_capabilities_refused_maps_to_failed_with_authorization_error_code() -> None:
    provider = InvestigationProvider(
        SpecialistId.WORDPRESS_WOOCOMMERCE,
        (_page(OFF_BOUNDARY_URL, "variation price"),),
        "1.0",
    )
    response = call_adapter(provider, _adapter_request("product variation price"))
    assert response.status == "failed"
    assert response.error_code == ERROR_AUTHORIZATION_REFUSED
    assert response.findings == ()
    refusals = [u for u in response.unknowns if u.startswith("[REFUSE]")]
    assert len(refusals) == 3


def test_partly_authorized_result_is_incomplete_not_failed() -> None:
    provider = InvestigationProvider(
        SpecialistId.WORDPRESS_WOOCOMMERCE, (_page(APPROVED_URL, "variation price"),), "1.0"
    )
    response = call_adapter(provider, _adapter_request("product variation price"))
    assert response.status == "incomplete"
    assert response.error_code is None
    assert len(response.findings) == 1


def test_provider_output_for_refusal_is_contract_valid_and_echoes_identity() -> None:
    provider = InvestigationProvider(
        SpecialistId.WORDPRESS_WOOCOMMERCE, (_page(OFF_BOUNDARY_URL, "variation price"),), "1.0"
    )
    output = run_in_harness(
        provider,
        SpecialistInput.model_validate(
            {
                "contract_version": "1.0.0",
                "request_id": "REQ-PREC",
                "workspace_id": WS,
                "specialist_id": SpecialistId.WORDPRESS_WOOCOMMERCE,
                "requirement_ids": ["REQ-SYN-1"],
                "task": "product variation price",
            }
        ),
    )
    assert output["request_id"] == "REQ-PREC"
    assert output["workspace_id"] == WS
    assert output["findings"] == []


def test_the_refused_url_never_appears_in_the_adapter_response() -> None:
    provider = InvestigationProvider(
        SpecialistId.WORDPRESS_WOOCOMMERCE, (_page(OFF_BOUNDARY_URL, "variation price"),), "1.0"
    )
    response = call_adapter(provider, _adapter_request("product variation price"))
    assert OFF_BOUNDARY_URL not in repr(response)
