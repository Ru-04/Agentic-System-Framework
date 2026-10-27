"""Seven-specialist investigation paths through adapter v0.2 (synthetic pages only).

These tests show the supported engineering path. They do not show a real platform investigation:
every page is a synthetic fixture, and every supported claim is labelled [SYNTHETIC].
"""

from __future__ import annotations

import pytest

from webdesk.investigation.engine import Edition, Page
from webdesk.investigation.specialists import CATALOG, InvestigationProvider, canonical_capability
from webdesk.specialists.adapter_v02 import (
    AdapterRequest,
    AdapterResponse,
    audit_record,
    call_adapter,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId

WS = "ws-synthetic"
SEVEN = list(SpecialistId)


def _request(
    specialist: SpecialistId,
    *,
    confirmed: bool = True,
    capability: str | None = None,
    actions: tuple[str, ...] = ("read_evidence",),
    workspace: str = WS,
    task: str = "product variation pricing for the store",
) -> AdapterRequest:
    return AdapterRequest.model_validate(
        {
            "adapter_contract_version": "0.2",
            "request_id": f"REQ-{specialist.value}",
            "workspace_id": workspace,
            "actor_id": "operator-1",
            "specialist_id": specialist,
            "capability_id": capability or canonical_capability(specialist),
            "requirement_ids": ["REQ-SYN-1"],
            "evidence_refs": [],
            "task": task,
            "allowed_actions": list(actions),
            "operator_confirmed": confirmed,
        }
    )


def _page(
    url: str,
    text: str,
    *,
    platform: str,
    edition: Edition = Edition.NOT_APPLICABLE,
    version: str | None = "1.0",
    workspace: str = WS,
) -> Page:
    return Page(
        url=url,
        final_url=url,
        platform=platform,
        edition=edition,
        version=version,
        workspace_id=workspace,
        text=text,
        synthetic=True,
    )


def _run(specialist: SpecialistId, pages: tuple[Page, ...]) -> AdapterResponse:
    provider = InvestigationProvider(specialist, pages, "1.0")
    return call_adapter(provider, _request(specialist))


WOO_VARIATION = _page(
    "https://developer.woocommerce.com/docs/products/variations",
    "Each variation has its own price.",
    platform="woocommerce",
)


# --- canonical identity -----------------------------------------------------------------------


def test_all_seven_categories_have_a_canonical_capability_id() -> None:
    assert set(REGISTRY_CAPABILITY_IDS) == set(SEVEN)
    assert len(SEVEN) == 7


def test_shift4shop_keeps_the_legacy_compatibility_identifier() -> None:
    assert REGISTRY_CAPABILITY_IDS[SpecialistId.SHIFT4SHOP] == "CAP-3D-CART-SHIFT-SHOPIFY"


def test_every_specialist_has_a_capability_catalog_entry() -> None:
    assert set(CATALOG) == set(SEVEN)
    assert all(CATALOG[s] for s in SEVEN)


# --- every specialist runs through the adapter with the shared contract ----------------------


@pytest.mark.parametrize("specialist", SEVEN)
def test_every_specialist_returns_a_contract_valid_incomplete_result_with_no_pages(
    specialist: SpecialistId,
) -> None:
    response = call_adapter(InvestigationProvider(specialist, (), "1.0"), _request(specialist))
    assert response.status == "incomplete"
    assert response.findings == ()
    assert any("feasibility is not determined" in u for u in response.unknowns)


# --- supported path: WooCommerce synthetic ---------------------------------------------------


def test_woocommerce_synthetic_capability_is_labelled_synthetic() -> None:
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (WOO_VARIATION,))
    assert response.status == "incomplete"  # type: ignore[attr-defined]
    assert len(response.findings) == 1  # type: ignore[attr-defined]
    statement = response.findings[0].statement  # type: ignore[attr-defined]
    assert statement.startswith("[SYNTHETIC]")
    assert "verified" not in statement.lower().replace("not verified", "")


def test_woocommerce_unsupported_capability_is_reported_as_unknown() -> None:
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (WOO_VARIATION,))
    assert any("REST API product read" in u for u in response.unknowns)  # type: ignore[attr-defined]


# --- source boundaries and edition separation -------------------------------------------------


def test_page_outside_the_approved_boundary_is_not_cited() -> None:
    page = _page(
        "https://developer.woocommerce.com/blog/variations",
        "Each variation has its own price.",
        platform="woocommerce",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,))
    assert response.findings == ()  # type: ignore[attr-defined]


def test_bigcommerce_sibling_page_is_not_cited() -> None:
    page = _page(
        "https://docs.bigcommerce.com/developer/api-reference/rest/admin/catalog/products/get-products",
        "product catalog",
        platform="bigcommerce",
    )
    response = _run(SpecialistId.BIGCOMMERCE, (page,))
    assert response.findings == ()  # type: ignore[attr-defined]


def test_magento_feature_is_not_supported_by_release_notes() -> None:
    notes = _page(
        "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
        "magento-open-source/overview",
        "catalog import release notes",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    response = _run(SpecialistId.MAGENTO_ADOBE_COMMERCE, (notes,))
    assert all("catalog import" not in f.statement for f in response.findings)  # type: ignore[attr-defined]


def test_magento_release_history_is_supported_from_release_notes() -> None:
    notes = _page(
        "https://experienceleague.adobe.com/en/docs/commerce-operations/release/notes/"
        "magento-open-source/overview",
        "release notes for this version",
        platform="magento_open_source",
        edition=Edition.MAGENTO_OPEN_SOURCE,
    )
    response = _run(SpecialistId.MAGENTO_ADOBE_COMMERCE, (notes,))
    assert any("release history" in f.statement for f in response.findings)  # type: ignore[attr-defined]


def test_adobe_only_page_is_not_applied_to_magento_open_source_claims() -> None:
    rest = _page(
        "https://developer.adobe.com/commerce/webapi/rest/",
        "REST product endpoints",
        platform="adobe_commerce",
        edition=Edition.ADOBE_COMMERCE,
    )
    response = _run(SpecialistId.MAGENTO_ADOBE_COMMERCE, (rest,))
    # The Adobe Commerce REST claim is supported. No Magento Open Source claim is produced from it.
    assert any("REST product read" in f.statement for f in response.findings)  # type: ignore[attr-defined]
    assert all("catalog import" not in f.statement for f in response.findings)  # type: ignore[attr-defined]


def test_shift4shop_has_no_approved_source_so_no_claim_is_made() -> None:
    page = _page(
        "https://developer.3dcart.com/api/products",
        "product read API",
        platform="shift4shop",
    )
    response = _run(SpecialistId.SHIFT4SHOP, (page,))
    assert response.findings == ()  # type: ignore[attr-defined]
    assert any("unsupported_source" in u for u in response.unknowns)  # type: ignore[attr-defined]


def test_standalone_and_middleware_return_explicit_unsupported_outcomes() -> None:
    for specialist in (SpecialistId.STANDALONE_APPLICATIONS, SpecialistId.MIDDLEWARE_APPLICATIONS):
        response = call_adapter(InvestigationProvider(specialist, (), "1.0"), _request(specialist))
        assert response.status == "incomplete"
        assert response.findings == ()
        assert any("unsupported_source" in u for u in response.unknowns)


# --- adapter-level security ------------------------------------------------------------------


def test_missing_operator_confirmation_is_refused_by_the_adapter() -> None:
    response = call_adapter(
        InvestigationProvider(SpecialistId.WORDPRESS_WOOCOMMERCE, (WOO_VARIATION,), "1.0"),
        _request(SpecialistId.WORDPRESS_WOOCOMMERCE, confirmed=False),
    )
    assert response.status == "failed"
    assert response.error_code == "operator_confirmation_required"


def test_wrong_capability_id_is_refused_by_the_adapter() -> None:
    response = call_adapter(
        InvestigationProvider(SpecialistId.BIGCOMMERCE, (), "1.0"),
        _request(SpecialistId.BIGCOMMERCE, capability="CAP-NOT-REAL"),
    )
    assert response.error_code == "capability_mismatch"


def test_forbidden_action_is_refused_by_the_adapter() -> None:
    response = call_adapter(
        InvestigationProvider(SpecialistId.BIGCOMMERCE, (), "1.0"),
        _request(SpecialistId.BIGCOMMERCE, actions=("approve_artifact",)),
    )
    assert response.error_code == "action_forbidden"


def test_other_workspace_page_is_excluded() -> None:
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        "variation price",
        platform="woocommerce",
        workspace="ws-other",
    )
    response = _run(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,))
    assert response.findings == ()  # type: ignore[attr-defined]


def test_audit_record_does_not_contain_page_text() -> None:
    secret = "PRIVATE PRODUCT SENTENCE"
    page = _page(
        "https://developer.woocommerce.com/docs/products/variations",
        secret + " variation price",
        platform="woocommerce",
    )
    request = _request(SpecialistId.WORDPRESS_WOOCOMMERCE)
    response = call_adapter(
        InvestigationProvider(SpecialistId.WORDPRESS_WOOCOMMERCE, (page,), "1.0"), request
    )
    record = audit_record(request, response)
    assert secret not in str(record)


# --- Shopify: connected to the engine through its inactive approved boundary -----------------


def test_shopify_synthetic_page_on_an_approved_host_is_labelled_synthetic() -> None:
    page = _page(
        "https://shopify.dev/docs/apps/plans",
        "Plan feature availability for apps.",
        platform="shopify",
    )
    response = call_adapter(
        InvestigationProvider(SpecialistId.SHOPIFY, (page,), "1.0"),
        _request(SpecialistId.SHOPIFY, task="plan feature availability"),
    )
    assert response.status == "incomplete"
    assert len(response.findings) == 1
    assert response.findings[0].statement.startswith("[SYNTHETIC]")


def test_shopify_page_outside_the_plan_scopes_is_refused() -> None:
    page = _page(
        "https://www.shopify.com/features",
        "Plan feature availability for apps.",
        platform="shopify",
    )
    response = call_adapter(
        InvestigationProvider(SpecialistId.SHOPIFY, (page,), "1.0"),
        _request(SpecialistId.SHOPIFY, task="plan feature availability"),
    )
    assert response.findings == ()


def test_shopify_pricing_page_on_the_approved_scope_is_accepted() -> None:
    page = _page(
        "https://www.shopify.com/pricing",
        "Plan feature availability for apps.",
        platform="shopify",
    )
    response = call_adapter(
        InvestigationProvider(SpecialistId.SHOPIFY, (page,), "1.0"),
        _request(SpecialistId.SHOPIFY, task="plan feature availability"),
    )
    assert len(response.findings) == 1
