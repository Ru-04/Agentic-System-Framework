"""Frozen relevance thresholds (S2-D15, 23 October 2026).

These values are frozen for the Sprint 2 evaluation. Changing one fails this test on purpose.
A change is allowed only after separate development labels and an untouched held-out evaluation set
exist (S2-D15), and only with a new, recorded decision that updates this test.
"""

from __future__ import annotations

from webdesk.evidence import relevance
from webdesk.specialists.platforms import shopify


def test_relevance_thresholds_are_frozen() -> None:
    assert relevance.DIRECT_MIN_TERMS == 3
    assert relevance.DIRECT_MIN_RATIO == 0.5
    assert relevance.PARTIAL_MIN_TERMS == 3


def test_retrieval_candidate_and_match_floors_are_frozen() -> None:
    assert shopify.MIN_TERM_HITS == 2
    assert shopify.CANDIDATE_LIMIT == 20
    assert shopify.MAX_FINDINGS == 20


def test_platform_generic_terms_are_frozen() -> None:
    assert relevance.PLATFORM_GENERIC_TERMS == frozenset(
        {
            "shopify",
            "store",
            "online",
            "merchant",
            "customer",
            "order",
            "product",
            "platform",
            "business",
            "client",
            "site",
            "website",
            "system",
            "feature",
            "solution",
            "support",
            "using",
            "based",
            "app",
        }
    )
