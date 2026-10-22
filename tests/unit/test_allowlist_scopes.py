"""Regression tests for scoped allowlist traversal (QA4-01, QA4-02, QA4-03)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from webdesk.evidence.allowlist import SPRINT2_ALLOWLIST
from webdesk.evidence.sources import SourceKind, SourceRecord

CRA_EXACT = (
    "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/"
    "gst-hst-businesses/charge-collect-specific-situations/e-commerce.html"
)
CRA_BULLETIN = (
    "https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/b-090.html"
)


@pytest.mark.parametrize(
    "url",
    [
        "https://shopify.com/pricing/../features",
        "https://shopify.com/pricing/./x",
        "https://shopify.com/pricing/%2e%2e/features",
        "https://shopify.com/pricing/..%2ffeatures",
        "https://shopify.com/pricing.%2F..%2Ffeatures",
        "https://shopify.com/pricing\\..\\features",
        "https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/b-090.html/child",
        CRA_EXACT + "/child",
        CRA_EXACT + "/../../../../t4-eng.html",
    ],
)
def test_traversal_and_children_are_refused(url: str) -> None:
    assert not SPRINT2_ALLOWLIST.permits(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://shopify.com/pricing",
        "https://shopify.com/pricing/x",
        "https://www.shopify.com/plus",
        CRA_EXACT,
        CRA_BULLETIN,
    ],
)
def test_legitimate_scoped_paths_are_permitted(url: str) -> None:
    assert SPRINT2_ALLOWLIST.permits(url)


def test_origin_rule_refuses_traversal_for_vendor_records() -> None:
    with pytest.raises(ValueError):
        SourceRecord(
            source_id="s",
            kind=SourceKind.VENDOR_DOC,
            workspace_id="ws-a",
            origin="https://shopify.com/pricing/../features",
            title="t",
            text="x",
            retrieved_at=datetime(2026, 10, 22, tzinfo=UTC),
        )
