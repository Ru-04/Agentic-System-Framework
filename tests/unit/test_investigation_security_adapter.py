"""Security and evidence checks on the investigation path, exercised through adapter v0.2.

Synthetic fixtures only. No retrieval, no live source, no verified evidence is produced here.
"""

from __future__ import annotations

from webdesk.investigation.engine import Edition, Page
from webdesk.investigation.specialists import CATALOG, InvestigationProvider, canonical_capability
from webdesk.specialists.adapter_v02 import AdapterRequest, AdapterResponse, call_adapter
from webdesk.specialists.catalog import SpecialistId

WS = "ws-synthetic"
MAGENTO_NOTES = (
    "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
    "magento-open-source/overview"
)


def _request(specialist: SpecialistId, *, workspace: str = WS) -> AdapterRequest:
    return AdapterRequest.model_validate(
        {
            "adapter_contract_version": "0.2",
            "request_id": f"REQ-SEC-{specialist.value}",
            "workspace_id": workspace,
            "actor_id": "operator-1",
            "specialist_id": specialist,
            "capability_id": canonical_capability(specialist),
            "requirement_ids": ["REQ-SYN-1"],
            "evidence_refs": [],
            "task": "product variation pricing for the store",
            "allowed_actions": ["read_evidence"],
            "operator_confirmed": True,
        }
    )


def _page(
    url: str,
    text: str,
    *,
    platform: str,
    edition: Edition = Edition.NOT_APPLICABLE,
    final_url: str | None = None,
    version: str | None = "1.0",
    workspace: str = WS,
) -> Page:
    return Page(
        url=url,
        final_url=final_url or url,
        platform=platform,
        edition=edition,
        version=version,
        workspace_id=workspace,
        text=text,
        synthetic=True,
    )


def _run(specialist: SpecialistId, pages: tuple[Page, ...], workspace: str = WS) -> AdapterResponse:
    return call_adapter(
        InvestigationProvider(specialist, pages, "1.0"), _request(specialist, workspace=workspace)
    )


# --- redirects ------------------------------------------------------------------------------------


def test_redirect_from_an_approved_page_to_an_unapproved_host_is_not_cited() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "Each variation has its own price.",
        platform="woocommerce",
        final_url="https://evil.example.com/docs/products/variations",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,))
    assert response.findings == ()


def test_redirect_from_a_magento_devdocs_page_is_not_cited() -> None:
    page = _page(
        MAGENTO_NOTES,
        "release notes for this version",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
        final_url="https://developer.adobe.com/commerce/",
    )
    response = _run(SpecialistId.MAGENTO_ADOBE_COMMERCE, (page,))
    assert all("release history" not in f.statement for f in response.findings)


# --- release-only restriction through the adapter -------------------------------------------------


def test_magento_release_notes_never_support_a_feature_claim_through_the_adapter() -> None:
    page = _page(
        MAGENTO_NOTES,
        "catalog import is available in this release",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    response = _run(SpecialistId.MAGENTO_ADOBE_COMMERCE, (page,))
    assert all("catalog import" not in f.statement for f in response.findings)
    assert any(
        "catalog import" in unknown and "unsupported_source" in unknown
        for unknown in response.unknowns
    )


# --- citations and evidence references ------------------------------------------------------------


def test_every_finding_is_labelled_synthetic_and_never_claims_verified_evidence() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "Each variation has its own price.",
        platform="woocommerce",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,))
    assert response.findings
    for finding in response.findings:
        assert finding.statement.startswith("[SYNTHETIC]")
        assert finding.evidence_status == "cited"


def test_evidence_refs_are_bound_to_the_request_workspace_only() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "Each variation has its own price.",
        platform="woocommerce",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,))
    for finding in response.findings:
        for ref in finding.evidence_refs:
            assert ref.workspace_id == WS


def test_other_workspace_evidence_never_reaches_the_response() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "Each variation has its own price.",
        platform="woocommerce",
        workspace="ws-other",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,), workspace=WS)
    assert response.findings == ()
    assert response.workspace_id == WS


def test_version_mismatch_is_reported_as_unknown_not_as_support() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "Each variation has its own price.",
        platform="woocommerce",
        version="2.0",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,))
    assert response.findings == ()
    assert any("insufficient evidence" in u for u in response.unknowns)


# --- source-unavailable handling for specialists without an approved source ----------------------


def test_shift4shop_source_unavailable_is_an_explicit_unknown_with_reason() -> None:
    response = call_adapter(
        InvestigationProvider(SpecialistId.SHIFT4SHOP, (), "1.0"),
        _request(SpecialistId.SHIFT4SHOP),
    )
    assert response.status == "incomplete"
    assert response.findings == ()
    assert any("unsupported_source" in u for u in response.unknowns)


def test_technology_neutral_specialists_have_no_platform_source_and_no_claims() -> None:
    for specialist in (SpecialistId.STANDALONE_APPLICATIONS, SpecialistId.MIDDLEWARE_APPLICATIONS):
        page = _page(
            "https://developer.woocommerce.com/docs/products/variations",
            "webhook delivery retry architecture catalog",
            platform="woocommerce",
        )
        response = _run(specialist, (page,))
        assert response.findings == ()
        assert any("feasibility is not determined" in u for u in response.unknowns)


def test_every_catalog_capability_is_complete_enough_to_investigate() -> None:
    for specialist, capabilities in CATALOG.items():
        assert capabilities, specialist
        for capability in capabilities:
            assert capability.name
            assert capability.platform
            assert capability.required_terms
