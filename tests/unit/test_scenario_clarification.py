"""Three-term clarification rule for Sprint 4 scenarios (synthetic fixtures only).

A requirement with fewer than three specific terms gets a clarification, not a finding.
"""

from __future__ import annotations

import pytest

from webdesk.investigation.engine import Edition, Page
from webdesk.investigation.specialists import (
    MIN_SPECIFIC_TERMS,
    InvestigationProvider,
    canonical_capability,
    specific_terms,
)
from webdesk.specialists.adapter_v02 import AdapterRequest, AdapterResponse, call_adapter
from webdesk.specialists.catalog import SpecialistId

WS = "ws-synthetic"
WOO_PAGE = Page(
    url="https://developer.woocommerce.com/docs/products/variations",
    final_url="https://developer.woocommerce.com/docs/products/variations",
    platform="woocommerce",
    edition=Edition.NOT_APPLICABLE,
    version="1.0",
    workspace_id=WS,
    text="Each variation has its own price.",
    synthetic=True,
)


def _request(task: str) -> AdapterRequest:
    return AdapterRequest.model_validate(
        {
            "adapter_contract_version": "0.2",
            "request_id": "REQ-CLARIFY",
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


def _run(task: str) -> AdapterResponse:
    provider = InvestigationProvider(SpecialistId.WORDPRESS_WOOCOMMERCE, (WOO_PAGE,), "1.0")
    return call_adapter(provider, _request(task))


def test_minimum_is_three_specific_terms() -> None:
    assert MIN_SPECIFIC_TERMS == 3


def test_stopwords_and_short_words_are_not_specific_terms() -> None:
    assert specific_terms("the for and of to") == frozenset()
    assert specific_terms("a is it") == frozenset()


def test_terms_are_counted_once_regardless_of_case_or_repetition() -> None:
    assert specific_terms("Product PRODUCT product") == frozenset({"product"})


@pytest.mark.parametrize("task", ["product", "security check", "the store for pricing"])
def test_fewer_than_three_specific_terms_gets_a_clarification_not_a_finding(task: str) -> None:
    response = _run(task)
    assert response.status == "incomplete"
    assert response.findings == ()
    assert any("clarification required" in u for u in response.unknowns)


def test_clarification_runs_no_investigation_even_with_an_approved_page() -> None:
    response = _run("product variation")
    assert response.findings == ()
    assert len(response.unknowns) == 2
    assert response.unknowns[1] == "feasibility is not determined by this specialist"


def test_three_specific_terms_proceed_to_investigation() -> None:
    response = _run("product variation pricing")
    assert len(response.findings) == 1
    assert response.findings[0].statement.startswith("[SYNTHETIC]")
    assert not any("clarification required" in u for u in response.unknowns)
