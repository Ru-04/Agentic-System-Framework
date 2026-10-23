"""Regression tests for Sprint 2 decisions that must keep holding (S2-R1 to S2-R3, D09)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from webdesk.evidence.allowlist import SPRINT2_ALLOWLIST
from webdesk.evidence.relevance import DisabledSemanticValidator, SemanticValidationDisabled
from webdesk.evidence.retrieval import InMemoryRetriever
from webdesk.specialists.contract import SpecialistInput
from webdesk.specialists.platforms.shopify import ShopifySpecialist

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


def _specialist() -> ShopifySpecialist:
    return ShopifySpecialist(
        InMemoryRetriever([]),
        clock=lambda: NOW,
        max_age=timedelta(days=90),
        attempts=1,
        sleep=lambda _: None,
    )


def _request(task: str) -> SpecialistInput:
    payload: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": "req-keep",
        "workspace_id": "ws-a",
        "specialist_id": "shopify",
        "requirement_ids": ["REQ-1"],
        "evidence_refs": [],
        "task": task,
    }
    return SpecialistInput.model_validate(payload)


def test_short_requirement_asks_for_clarification_not_a_grade() -> None:
    output, coverage = _specialist().investigate(_request("Keep it fast."))
    assert coverage == frozenset()
    assert output["findings"] == []
    assert any("CLARIFY" in u and "restate" in u for u in output["unknowns"])


def test_www_shopify_com_plan_path_is_within_the_restricted_scope() -> None:
    assert SPRINT2_ALLOWLIST.permits("https://www.shopify.com/pricing")
    assert SPRINT2_ALLOWLIST.permits("https://shopify.com/plus")
    assert not SPRINT2_ALLOWLIST.permits("https://www.shopify.com/features")


def test_semantic_validator_stays_disabled_without_d09() -> None:
    with pytest.raises(SemanticValidationDisabled):
        DisabledSemanticValidator().judge("pickup slots", "pickup slots at checkout")
