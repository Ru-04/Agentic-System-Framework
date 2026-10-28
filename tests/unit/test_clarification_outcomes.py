"""Four requirement outcomes for Sprint 4 investigations (synthetic fixtures only).

INVESTIGATE, INVESTIGATE_WITH_UNKNOWNS, CLARIFY and REFUSE are deterministic rules. None is a
confidence value. Each outcome is reported as a labelled unknown on the existing response
fields, so the public contract is unchanged. Clarification and refusal never carry a finding.
"""

from __future__ import annotations

import pytest

from webdesk.investigation.engine import Edition, Page
from webdesk.investigation.specialists import (
    CATALOG,
    Decision,
    InvestigationProvider,
    canonical_capability,
    decide,
    matched_capabilities,
)
from webdesk.specialists.adapter_v02 import AdapterRequest, AdapterResponse, call_adapter
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import SpecialistInput

WS = "ws-synthetic"
WOO = SpecialistId.WORDPRESS_WOOCOMMERCE
VERBOSE_AMBIGUOUS = (
    "We need something good for our online shop that is fast, cheap and easy for the team "
    "to use every single day, and it should just work well for everyone involved."
)
VERBOSE_MEANINGFUL = (
    "We need to know whether each product variation can have its own price on the store, "
    "as shown in the current documentation, for our planned catalogue."
)
WOO_VARIATION_PAGE = Page(
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
            "request_id": "REQ-OUTCOME",
            "workspace_id": WS,
            "actor_id": "operator-1",
            "specialist_id": WOO,
            "capability_id": canonical_capability(WOO),
            "requirement_ids": ["REQ-SYN-1"],
            "evidence_refs": [],
            "task": task,
            "allowed_actions": ["read_evidence"],
            "operator_confirmed": True,
        }
    )


def _through_adapter(task: str, version: str | None = "1.0") -> AdapterResponse:
    provider = InvestigationProvider(WOO, (WOO_VARIATION_PAGE,), version)
    return call_adapter(provider, _request(task))


def _labels(response: AdapterResponse) -> list[str]:
    return [u.split("]", 1)[0] + "]" for u in response.unknowns if u.startswith("[")]


# --- INVESTIGATE: sufficient information ----------------------------------------------------------


def test_concise_but_meaningful_requirement_is_investigated() -> None:
    response = _through_adapter("product variation price")
    assert len(response.findings) == 1
    assert response.findings[0].statement.startswith("[SYNTHETIC]")
    assert _labels(response) == ["[INVESTIGATE]"]


def test_verbose_but_meaningful_requirement_is_investigated() -> None:
    response = _through_adapter(VERBOSE_MEANINGFUL)
    assert len(response.findings) == 1
    assert _labels(response) == ["[INVESTIGATE]"]


# --- INVESTIGATE_WITH_UNKNOWNS: objective known, nonessential detail missing ----------------------


def test_missing_version_is_declared_as_an_unknown_not_guessed() -> None:
    response = _through_adapter("product variation price", version=None)
    assert response.findings == ()
    assert _labels(response) == ["[INVESTIGATE_WITH_UNKNOWNS]", "[INVESTIGATE_WITH_UNKNOWNS]"]
    assert any("version is not stated" in u for u in response.unknowns)


# --- CLARIFY: essential information missing or materially ambiguous -------------------------------


@pytest.mark.parametrize("task", ["product", "security check", VERBOSE_AMBIGUOUS])
def test_unrecognisable_objective_gets_a_clarification_and_no_finding(task: str) -> None:
    response = _through_adapter(task)
    assert response.status == "incomplete"
    assert response.findings == ()
    assert _labels(response) == ["[CLARIFY]", "[CLARIFY]"]


# --- REFUSE: authorization is checked before any investigation -----------------------------------


def test_missing_operator_confirmation_refuses_before_any_page_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def must_not_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("investigation ran without operator confirmation")

    monkeypatch.setattr("webdesk.investigation.specialists.investigate", must_not_run)
    provider = InvestigationProvider(WOO, (WOO_VARIATION_PAGE,), "1.0", operator_confirmed=False)
    output = provider.run(
        SpecialistInput.model_validate(
            {
                "contract_version": "1.0.0",
                "request_id": "REQ-REFUSE",
                "workspace_id": WS,
                "specialist_id": WOO,
                "requirement_ids": ["REQ-SYN-1"],
                "task": "product variation price",
            }
        )
    )
    assert output["status"] == "failed"
    assert output["findings"] == []
    assert output["unknowns"] == [
        "[REFUSE] operator confirmation is missing; no investigation was run"
    ]


def test_adapter_refuses_unconfirmed_requests_before_the_provider_runs() -> None:
    request = _request("product variation price").model_copy(update={"operator_confirmed": False})
    response = call_adapter(InvestigationProvider(WOO, (WOO_VARIATION_PAGE,), "1.0"), request)
    assert response.status == "failed"
    assert response.error_code == "operator_confirmation_required"
    assert response.findings == ()


# --- the decision rule itself ---------------------------------------------------------------------


def test_decide_returns_each_of_the_four_outcomes() -> None:
    assert (
        decide(WOO, "product variation price", requested_version="1.0", operator_confirmed=True)[0]
        is Decision.INVESTIGATE
    )
    assert (
        decide(WOO, "product variation price", requested_version=None, operator_confirmed=True)[0]
        is Decision.INVESTIGATE_WITH_UNKNOWNS
    )
    assert (
        decide(WOO, "product", requested_version="1.0", operator_confirmed=True)[0]
        is Decision.CLARIFY
    )
    assert (
        decide(WOO, "product variation price", requested_version="1.0", operator_confirmed=False)[0]
        is Decision.REFUSE
    )


def test_refusal_takes_precedence_over_a_missing_objective() -> None:
    decision, _ = decide(WOO, "product", requested_version=None, operator_confirmed=False)
    assert decision is Decision.REFUSE


def test_inflected_forms_match_the_required_terms() -> None:
    names = [c.name for c in matched_capabilities(WOO, "variations with pricing")]
    assert names == ["product variation pricing"]
    assert matched_capabilities(WOO, "unrelated forest tree") == ()


def test_objective_match_requires_every_required_term_of_a_capability() -> None:
    names = [c.name for c in matched_capabilities(WOO, "product variation pricing")]
    assert names == ["product variation pricing"]
    assert matched_capabilities(WOO, "variation") == ()


def test_every_specialist_has_a_capability_that_its_own_terms_can_match() -> None:
    for specialist, capabilities in CATALOG.items():
        for capability in capabilities:
            task = " ".join(capability.required_terms)
            assert capability in matched_capabilities(specialist, task), (specialist, capability)


def test_stem_matching_does_not_match_unrelated_words() -> None:
    # "prickly" begins with "prick", not "price"; it must not classify a cactus requirement as a
    # WooCommerce price capability, even with the word "variation" present.
    assert matched_capabilities(WOO, "variation of prickly pear cactus") == ()
    assert matched_capabilities(WOO, "price list for the office") == ()
    assert [c.name for c in matched_capabilities(WOO, "variation pricing")] == [
        "product variation pricing"
    ]
