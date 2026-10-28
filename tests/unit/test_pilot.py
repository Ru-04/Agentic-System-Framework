"""Controlled retrieval pilot: scope and behaviour, with a local fake opener (no network)."""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import timedelta

import pytest

from tests.support.authority import TEST_NOW, pilot_authority
from webdesk.investigation import engine
from webdesk.investigation.pilot import PILOT_CASES, PILOT_USER_AGENT, run_pilot
from webdesk.specialists.authorization import AuthorityContext, AuthorizationDenied, AuthzCode

NOW = TEST_NOW
WOO_PAGE = (
    b"<html><body><p>Store API products: type=variation returns each variation with its price."
    b"</p></body></html>"
)
BIG_PAGE = (
    b"<html><body><p>Get Product. Use the v3 catalog path: /v3/catalog/products/1 to read it."
    b"</p></body></html>"
)


class FakeOpener:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> io.BytesIO:
        self.calls.append(url)
        return io.BytesIO(WOO_PAGE if "woocommerce" in url else BIG_PAGE)


def test_pilot_is_limited_to_the_two_approved_pages() -> None:
    assert [case.source_id for case in PILOT_CASES] == [
        "woocommerce_docs",
        "bigcommerce_docs_product_page",
    ]


def test_pilot_activates_exactly_the_two_sources() -> None:
    assert engine.ACTIVE_BOUNDARIES == frozenset(
        {
            ("woocommerce", engine.Edition.NOT_APPLICABLE),
            ("bigcommerce", engine.Edition.NOT_APPLICABLE),
        }
    )


def test_pilot_requests_only_the_two_pilot_urls() -> None:
    opener = FakeOpener()
    run_pilot(opener, pilot_authority())
    assert sorted(opener.calls) == sorted(case.url for case in PILOT_CASES)


def test_woocommerce_page_without_a_stated_version_is_unknown_not_cited() -> None:
    results = {r.case: r for r in run_pilot(FakeOpener(), pilot_authority())}
    woo = results["woocommerce_store_api_products"]
    assert woo.outcome == "unknown_support"
    assert woo.citations == ()


def test_bigcommerce_page_with_a_stated_version_is_cited_as_verified() -> None:
    results = {r.case: r for r in run_pilot(FakeOpener(), pilot_authority())}
    big = results["bigcommerce_get_product"]
    assert big.outcome == "verified_support"
    assert big.citations == (PILOT_CASES[1].url,)


def test_pilot_records_hash_and_timestamp_without_page_text() -> None:
    results = run_pilot(FakeOpener(), pilot_authority())
    for result in results:
        for record in result.fetch:
            assert record["retrieved_at"] == NOW.isoformat()
            assert "Store API" not in repr(record)
            assert "Get Product" not in repr(record)


def test_user_agent_identifies_the_pilot() -> None:
    assert PILOT_USER_AGENT.startswith("WebDesk-pilot/")


# --- pilot self-authorization is refused before any request --------------------------


@pytest.mark.parametrize(
    ("label", "mutate", "code"),
    [
        ("expired", lambda a: replace(a, now=NOW + timedelta(days=2)), AuthzCode.EXPIRED),
        ("wrong actor", lambda a: replace(a, actor_id="someone-else"), AuthzCode.MISMATCH),
        ("no verifier", lambda a: replace(a, permission_check=None), AuthzCode.VERIFIER_MISSING),
        (
            "missing run.start grant",
            lambda a: replace(a, permission_check=lambda _actor, _perm, _ws: False),
            AuthzCode.NOT_PERMITTED,
        ),
        ("unknown decision", lambda a: replace(a, decision_id="DEC-NOT-ISSUED"), AuthzCode.MISSING),
    ],
)
def test_pilot_makes_no_request_without_a_verified_decision(
    label: str, mutate: object, code: AuthzCode
) -> None:
    opener = FakeOpener()
    authority: AuthorityContext = mutate(pilot_authority())  # type: ignore[operator]
    with pytest.raises(AuthorizationDenied) as caught:
        run_pilot(opener, authority)
    assert caught.value.code is code, label
    assert opener.calls == [], label


def test_pilot_cannot_run_under_a_decision_for_another_request() -> None:
    opener = FakeOpener()
    authority = pilot_authority()
    store = authority.store
    other = replace(authority, decision_id="DEC-other")
    store.issue(  # type: ignore[attr-defined]
        replace(
            store.get(authority.decision_id),  # type: ignore[attr-defined]
            decision_id="DEC-other",
            request_id="some-other-request",
        )
    )
    with pytest.raises(AuthorizationDenied) as caught:
        run_pilot(opener, other)
    assert caught.value.code is AuthzCode.MISMATCH
    assert opener.calls == []


def test_pilot_with_a_verified_decision_retrieves_both_pages_and_audits_the_allowance() -> None:
    opener = FakeOpener()
    audit: list[dict[str, str]] = []
    authority = replace(pilot_authority(), audit=audit)
    run_pilot(opener, authority)
    assert sorted(opener.calls) == sorted(case.url for case in PILOT_CASES)
    # One audit entry per pilot case: each retrieval is its own verified operation.
    assert [entry["outcome"] for entry in audit] == ["allowed"] * len(PILOT_CASES)
