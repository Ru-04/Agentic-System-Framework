"""Conformance for all seven specialists through adapter 0.3 (contract section 5.3, OPEN-21).

Every test here runs on synthetic fixtures with an in-memory retriever. Sockets are blocked for the
whole module, so no live documentation can be fetched by accident.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from tests.support.evidence_fixtures import fixture_source
from webdesk.evidence.retrieval import InMemoryRetriever, RetrievalQuery
from webdesk.evidence.sources import SourceKind, SourceRecord
from webdesk.specialists import platforms
from webdesk.specialists.adapter_v03 import (
    AdapterResponse,
    CheckOutcome,
    RefuseAllConfirmations,
    VerifiedConfirmation,
    call_adapter,
    parse_request,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.mock import MockSpecialist
from webdesk.specialists.platforms.bigcommerce import BigcommerceSpecialist
from webdesk.specialists.platforms.magento_adobe_commerce import MagentoAdobeCommerceSpecialist
from webdesk.specialists.platforms.middleware_applications import MiddlewareApplicationsSpecialist
from webdesk.specialists.platforms.shift4shop import Shift4ShopSpecialist
from webdesk.specialists.platforms.shopify import ShopifySpecialist
from webdesk.specialists.platforms.standalone_applications import StandaloneApplicationsSpecialist
from webdesk.specialists.platforms.wordpress_woocommerce import WordpressWoocommerceSpecialist

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
RUN_ID = UUID("6f1c2d3e-0000-4000-8000-0000000000a1")
PROJECT_ID = UUID("6f1c2d3e-0000-4000-8000-0000000000a2")
WORKSPACE = "ws-a"
TASK = "storefront product checkout settings in the admin"

# Contract v1.1 section 5.3, the canonical capability per specialist. Written out here so a change
# to the catalog fails this test instead of silently moving the contract.
CONTRACT_CAPABILITY: Mapping[SpecialistId, str] = {
    SpecialistId.SHOPIFY: "CAP-ECOMMERCE",
    SpecialistId.SHIFT4SHOP: "CAP-3D-CART-SHIFT-SHOPIFY",
    SpecialistId.WORDPRESS_WOOCOMMERCE: "CAP-WORDPRESS-WOOCOMMERCE",
    SpecialistId.BIGCOMMERCE: "CAP-BIGCOMMERCE",
    SpecialistId.MAGENTO_ADOBE_COMMERCE: "CAP-MAGENTO-ADOBE-COMMERCE",
    SpecialistId.STANDALONE_APPLICATIONS: "CAP-STANDALONE-APPLICATIONS",
    SpecialistId.MIDDLEWARE_APPLICATIONS: "CAP-MIDDLEWARE-APPLICATIONS",
}

# Only the Shopify module carries a live retrieval path. The other six are profiles over the shared
# base, and their approved source is None, so they never retrieve.
PLATFORM_CLASSES: Mapping[SpecialistId, type] = {
    SpecialistId.SHIFT4SHOP: Shift4ShopSpecialist,
    SpecialistId.WORDPRESS_WOOCOMMERCE: WordpressWoocommerceSpecialist,
    SpecialistId.BIGCOMMERCE: BigcommerceSpecialist,
    SpecialistId.MAGENTO_ADOBE_COMMERCE: MagentoAdobeCommerceSpecialist,
    SpecialistId.STANDALONE_APPLICATIONS: StandaloneApplicationsSpecialist,
    SpecialistId.MIDDLEWARE_APPLICATIONS: MiddlewareApplicationsSpecialist,
}

SEVEN = tuple(SpecialistId)
NO_RETRIEVAL = tuple(s for s in SEVEN if s is not SpecialistId.SHOPIFY)

RESPONSE_KEYS = {
    "adapter_contract_version",
    "specialist_contract_version",
    "request_id",
    "workspace_id",
    "specialist_id",
    "capability_id",
    "registry_version",
    "status",
    "findings",
    "unknowns",
    "error",
    "confidence",
    "confidence_status",
}


class CountingRetriever:
    def __init__(self, sources: list[SourceRecord]) -> None:
        self._inner = InMemoryRetriever(sources)
        self.calls = 0

    def search(self, query: RetrievalQuery) -> Any:
        self.calls += 1
        return self._inner.search(query)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("conformance tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    yield


def _provider(specialist: SpecialistId, retriever: CountingRetriever) -> Any:
    kwargs: dict[str, Any] = {
        "clock": lambda: NOW,
        "max_age": timedelta(days=3650),
        "sleep": lambda _seconds: None,
    }
    if specialist is SpecialistId.SHOPIFY:
        return ShopifySpecialist(retriever, **kwargs)
    return PLATFORM_CLASSES[specialist](retriever, **kwargs)


def _envelope(specialist: SpecialistId, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "adapter_contract_version": "0.3",
        "request_id": f"REQ-{specialist.value}",
        "workspace_id": WORKSPACE,
        "run_id": str(RUN_ID),
        "project_id": str(PROJECT_ID),
        "specialist_id": specialist.value,
        "capability_id": CONTRACT_CAPABILITY[specialist],
        "requirement_refs": ["REQ-001"],
        "evidence_refs": [],
        "task": TASK,
        "allowed_actions": ["read_evidence"],
        "confirmation_ref": f"conf-{specialist.value}",
    }
    data.update(overrides)
    return data


class AcceptingVerifier:
    def verify(self, confirmation_ref: str, binding: Any) -> VerifiedConfirmation | None:
        return VerifiedConfirmation(actor_ref="actor-from-proof")


def _vendor_source(origin: str) -> SourceRecord:
    # The real constructor, not the fixture helper: the origin rule must be the one that runs.
    return SourceRecord(
        source_id="vendor-fx",
        kind=SourceKind.VENDOR_DOC,
        workspace_id=WORKSPACE,
        origin=origin,
        title="Fixture",
        text="storefront api product checkout settings in the admin",
        retrieved_at=NOW,
    )


# Identity and capability mapping


def test_there_are_exactly_seven_specialists() -> None:
    assert len(SEVEN) == 7
    assert {s.value for s in SEVEN} == {
        "shopify",
        "shift4shop",
        "wordpress_woocommerce",
        "bigcommerce",
        "magento_adobe_commerce",
        "standalone_applications",
        "middleware_applications",
    }


def test_every_specialist_has_a_conformance_provider() -> None:
    assert set(CONTRACT_CAPABILITY) == set(SEVEN)
    assert set(PLATFORM_CLASSES) | {SpecialistId.SHOPIFY} == set(SEVEN)


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_canonical_id_round_trips(specialist: SpecialistId) -> None:
    assert SpecialistId(specialist.value) is specialist


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_capability_mapping_matches_contract_5_3(specialist: SpecialistId) -> None:
    assert REGISTRY_CAPABILITY_IDS[specialist] == CONTRACT_CAPABILITY[specialist]


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_provider_identity_matches_its_specialist(specialist: SpecialistId) -> None:
    provider = _provider(specialist, CountingRetriever([]))
    assert provider.specialist_id is specialist


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_a_capability_of_another_specialist_is_refused(specialist: SpecialistId) -> None:
    other = next(s for s in SEVEN if s is not specialist)
    retriever = CountingRetriever([])
    response, _ = call_adapter(
        _provider(specialist, retriever),
        parse_request(_envelope(specialist, capability_id=CONTRACT_CAPABILITY[other])),
        AcceptingVerifier(),
    )
    assert retriever.calls == 0
    assert response.error is not None
    assert response.error.code == "capability_mismatch"


# Confirmation, source access and workspace


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_no_specialist_runs_without_a_verified_confirmation(specialist: SpecialistId) -> None:
    retriever = CountingRetriever([_vendor_source("https://shopify.com/pricing")])
    response, verified = call_adapter(
        _provider(specialist, retriever),
        parse_request(_envelope(specialist)),
        RefuseAllConfirmations(),
    )
    assert retriever.calls == 0
    assert verified is None
    assert response.status == "failed"
    assert response.findings == ()
    assert response.error is not None
    assert response.error.code == "confirmation_not_verified"


@pytest.mark.parametrize("specialist", NO_RETRIEVAL, ids=lambda s: s.value)
def test_unapproved_source_access_is_not_attempted(specialist: SpecialistId) -> None:
    # No approved source is configured for these platforms, so retrieval must never be called.
    retriever = CountingRetriever([_vendor_source("https://shopify.com/pricing")])
    response, _ = call_adapter(
        _provider(specialist, retriever), parse_request(_envelope(specialist)), AcceptingVerifier()
    )
    assert retriever.calls == 0
    assert response.status == "incomplete"
    assert response.findings == ()
    assert any("no approved evidence source" in u for u in response.unknowns)


@pytest.mark.parametrize(
    "origin",
    [
        "https://example.com/docs/storefront",
        "http://shopify.com/pricing",
        "https://shopify.com.evil.example/pricing",
        "https://shopify.com/admin/private",
    ],
)
def test_an_unapproved_vendor_origin_cannot_become_an_evidence_record(origin: str) -> None:
    with pytest.raises(ValueError):
        _vendor_source(origin)


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_evidence_from_another_workspace_is_refused(specialist: SpecialistId) -> None:
    evidence = {"workspace_id": "ws-other", "source_id": "fx", "locator": "1-10"}
    response, _ = call_adapter(
        _provider(specialist, CountingRetriever([])),
        parse_request(_envelope(specialist, evidence_refs=[evidence])),
        AcceptingVerifier(),
    )
    assert response.error is not None
    assert response.error.code == "workspace_mismatch"
    assert "ws-other" not in response.model_dump_json()


# Finding serialization


def _cited_canned(request: Any) -> dict[str, Any]:
    ref = {"workspace_id": WORKSPACE, "source_id": "fx-1", "locator": "1-40"}
    return {
        "contract_version": "1.0.0",
        "request_id": request.request_id,
        "workspace_id": request.workspace_id,
        "specialist_id": request.specialist_id.value,
        "status": "incomplete",
        "findings": [
            {
                "statement": "Source addresses checkout.",
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


def _assert_serialized_contract(response: AdapterResponse, specialist: SpecialistId) -> None:
    dumped = response.model_dump(mode="json")
    assert set(dumped) == RESPONSE_KEYS
    assert "actor_id" not in dumped
    assert "operator_confirmed" not in dumped
    assert dumped["adapter_contract_version"] == "0.3"
    assert dumped["specialist_contract_version"] == "1.0.0"
    assert dumped["specialist_id"] == specialist.value
    assert dumped["capability_id"] == CONTRACT_CAPABILITY[specialist]
    assert dumped["confidence_status"] == "not_assessed"
    assert dumped["confidence"] is None
    assert AdapterResponse.model_validate(dumped) == response
    for finding in dumped["findings"]:
        assert finding["evidence_status"] in {"cited", "unverified"}
        assert finding["check_outcome"] in {"SUPPORTED", "UNSUPPORTED", "UNKNOWN"}
        if finding["evidence_status"] == "cited":
            assert finding["evidence_refs"]


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_findings_serialize_with_their_check_outcome(specialist: SpecialistId) -> None:
    provider = MockSpecialist(specialist, canned=_cited_canned)
    response, _ = call_adapter(provider, parse_request(_envelope(specialist)), AcceptingVerifier())
    assert [f.evidence_status for f in response.findings] == ["cited", "unverified"]
    # No assessor is supplied, so no check was made and no finding can be SUPPORTED.
    assert [f.check_outcome for f in response.findings] == [CheckOutcome.UNKNOWN] * 2
    _assert_serialized_contract(response, specialist)


@pytest.mark.parametrize("specialist", SEVEN, ids=lambda s: s.value)
def test_an_incomplete_platform_answer_serializes(specialist: SpecialistId) -> None:
    retriever = CountingRetriever([])
    response, _ = call_adapter(
        _provider(specialist, retriever), parse_request(_envelope(specialist)), AcceptingVerifier()
    )
    assert response.status == "incomplete"
    assert response.findings == ()
    assert response.error is None
    _assert_serialized_contract(response, specialist)


def test_shopify_retrieval_path_serializes_real_findings() -> None:
    # The only specialist with a live retrieval path, exercised on an internal synthetic source.
    source = fixture_source(
        source_id="internal-fx",
        kind=SourceKind.INTERNAL_RAG,
        workspace_id=WORKSPACE,
        origin="internal:fixture-storefront",
        title="Fixture",
        text="The storefront api exposes product and checkout settings in the admin.",
        retrieved_at=NOW,
        version=None,
    )
    retriever = CountingRetriever([source])
    response, _ = call_adapter(
        _provider(SpecialistId.SHOPIFY, retriever),
        parse_request(_envelope(SpecialistId.SHOPIFY)),
        AcceptingVerifier(),
    )
    assert retriever.calls >= 1
    assert response.error is None
    assert response.findings
    assert {f.evidence_status for f in response.findings} == {"cited"}
    _assert_serialized_contract(response, SpecialistId.SHOPIFY)


# Canonical Shopify module (OPEN-21)


def test_one_canonical_shopify_module_and_no_second_implementation() -> None:
    package = Path(platforms.__file__).parent
    defining = [
        path.name
        for path in package.glob("*.py")
        if "class ShopifySpecialist" in path.read_text(encoding="utf-8")
    ]
    assert defining == ["shopify.py"]


def test_no_specialist_module_imports_the_ai_engine_shopify_path() -> None:
    package = Path(platforms.__file__).parents[1]
    offenders = [
        path.as_posix()
        for path in package.rglob("*.py")
        if "ai_engine" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_the_shopify_provider_is_the_canonical_module() -> None:
    assert ShopifySpecialist.__module__ == "webdesk.specialists.platforms.shopify"
    assert ShopifySpecialist.specialist_id is SpecialistId.SHOPIFY
