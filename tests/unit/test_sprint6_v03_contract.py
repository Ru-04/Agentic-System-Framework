"""Sprint 6 compatibility tests for adapter v0.3 (contract 6.3, OPEN-03/07/08, section 7).

Contract test doubles are used where the Foundation verifier and the Lineage B package are not on
this branch. Those tests are marked CONTRACT DOUBLE. Genuine integration verification is pending.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tests.support.evidence_fixtures import fixture_source
from webdesk.evidence.retrieval import InMemoryRetriever, RetrievalQuery
from webdesk.evidence.sources import SourceKind, SourceRecord
from webdesk.specialists.adapter_v03 import (
    ERROR_CONFIRMATION_NOT_VERIFIED,
    ERROR_REQUEST_INVALID,
    ERROR_VERSION_UNSUPPORTED,
    AdapterRequest,
    AdapterRequestError,
    AdapterResponse,
    CheckOutcome,
    ConfirmationBinding,
    RefuseAllConfirmations,
    VerifiedConfirmation,
    binding_for,
    call_adapter,
    map_evidence_status,
    parse_request,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.platforms.shopify import ShopifySpecialist

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
RUN_ID = "6f1c2d3e-0000-4000-8000-0000000000b1"
PROJECT_ID = "6f1c2d3e-0000-4000-8000-0000000000b2"
TASK = "storefront product checkout settings in the admin"

# CONTRACT DOUBLE: the AI Engine EvidenceStatus values in ai_engine/contracts/common.py at 0389318
# (B-CMN). Copied, not imported, so this branch takes no dependency on Lineage B.
LINEAGE_B_EVIDENCE_STATUS: frozenset[str] = frozenset(
    {"verified", "partially_verified", "unverified", "conflicting", "not_applicable"}
)


class CountingVerifier:
    """CONTRACT DOUBLE for the Foundation verifier. Counts every consumption attempt."""

    def __init__(self, accept: bool = True) -> None:
        self.calls = 0
        self.accept = accept
        self.bindings: list[ConfirmationBinding] = []

    def verify(
        self, confirmation_ref: str, binding: ConfirmationBinding
    ) -> VerifiedConfirmation | None:
        self.calls += 1
        self.bindings.append(binding)
        return VerifiedConfirmation(actor_ref="proof-actor") if self.accept else None


class CountingRetriever:
    def __init__(self, sources: list[SourceRecord]) -> None:
        self._inner = InMemoryRetriever(sources)
        self.calls = 0

    def search(self, query: RetrievalQuery) -> Any:
        self.calls += 1
        return self._inner.search(query)


def _envelope(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "adapter_contract_version": "0.3",
        "request_id": "REQ-S6-1",
        "workspace_id": "ws-a",
        "run_id": RUN_ID,
        "project_id": PROJECT_ID,
        "specialist_id": SpecialistId.SHOPIFY.value,
        "capability_id": REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY],
        "requirement_refs": ["REQ-001"],
        "evidence_refs": [],
        "task": TASK,
        "allowed_actions": ["read_evidence"],
        "source_scope_digest": "a" * 64,
        "confirmation_ref": "conf-s6-1",
    }
    data.update(overrides)
    return data


def _vendor(
    origin: str, text: str = "The storefront api manages product and checkout settings."
) -> SourceRecord:
    return SourceRecord(
        source_id="shopify-plan",
        kind=SourceKind.VENDOR_DOC,
        workspace_id="ws-a",
        origin=origin,
        title="Shopify plans",
        text=text,
        retrieved_at=NOW,
    )


def _shopify(retriever: CountingRetriever) -> ShopifySpecialist:
    return ShopifySpecialist(
        retriever, clock=lambda: NOW, max_age=timedelta(days=3650), sleep=lambda _s: None
    )


# 1. Schemas


def test_request_schema_forbids_extra_fields_and_actor_authority() -> None:
    schema = AdapterRequest.model_json_schema()
    assert schema["additionalProperties"] is False
    assert {"actor_id", "operator_confirmed"}.isdisjoint(schema["properties"])
    assert {"confirmation_ref", "run_id", "project_id", "requirement_refs"} <= set(
        schema["required"]
    )


def test_response_schema_forbids_extra_fields() -> None:
    assert AdapterResponse.model_json_schema()["additionalProperties"] is False


def test_unknown_request_field_is_refused() -> None:
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(operator_confirmed=True))
    assert raised.value.code == ERROR_REQUEST_INVALID


def test_version_zero_two_is_not_accepted_as_zero_three() -> None:
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(adapter_contract_version="0.2"))
    assert raised.value.code == ERROR_VERSION_UNSUPPORTED


# 3. Requirement references (run-scoped REQ-NNN)


@pytest.mark.parametrize("ref", ["REQ-001", "REQ-0001", "REQ-123456"])
def test_valid_requirement_references_are_accepted(ref: str) -> None:
    assert parse_request(_envelope(requirement_refs=[ref])).requirement_refs == (ref,)


@pytest.mark.parametrize(
    "ref", ["REQ-1", "req-001", "REQ-001 ", "REQ-001;drop", "(run, REQ-001)", "", "REQ-"]
)
def test_malformed_requirement_references_are_refused(ref: str) -> None:
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(requirement_refs=[ref]))
    assert raised.value.code == ERROR_REQUEST_INVALID


# 4 and 5. Project binding, verified invocation, single verifier call


def test_a_verified_confirmation_binds_the_run_and_project_exactly() -> None:
    verifier = CountingVerifier()
    request = parse_request(_envelope())
    call_adapter(_shopify(CountingRetriever([])), request, verifier)
    binding = verifier.bindings[0]
    assert str(binding.run_id) == RUN_ID
    assert str(binding.project_id) == PROJECT_ID
    assert binding.specialist_id is SpecialistId.SHOPIFY
    assert binding.capability_id == REGISTRY_CAPABILITY_IDS[SpecialistId.SHOPIFY]


def test_a_refused_binding_does_not_reach_the_retriever() -> None:
    retriever = CountingRetriever([_vendor("https://www.shopify.com/pricing/plans")])
    response, verified = call_adapter(
        _shopify(retriever), parse_request(_envelope()), CountingVerifier(accept=False)
    )
    assert retriever.calls == 0
    assert verified is None
    assert response.error is not None
    assert response.error.code == ERROR_CONFIRMATION_NOT_VERIFIED


def test_the_verifier_is_consumed_exactly_once_even_when_the_harness_refuses() -> None:
    verifier = CountingVerifier()
    response, verified = call_adapter(
        _shopify(CountingRetriever([])),
        parse_request(
            _envelope(
                evidence_refs=[{"workspace_id": "ws-other", "source_id": "x", "locator": "1-2"}]
            )
        ),
        verifier,
    )
    assert verifier.calls == 1
    assert verified == VerifiedConfirmation(actor_ref="proof-actor")
    assert response.error is not None
    assert response.error.code == "workspace_mismatch"


def test_the_default_verifier_refuses_before_any_retrieval() -> None:
    retriever = CountingRetriever([_vendor("https://www.shopify.com/pricing/plans")])
    response, _ = call_adapter(
        _shopify(retriever), parse_request(_envelope()), RefuseAllConfirmations()
    )
    assert retriever.calls == 0
    assert response.findings == ()


# 8. Unsupported source refusal, enforced at the Shopify retrieval boundary


def test_an_unapproved_vendor_passage_is_excluded_even_if_the_retriever_returns_it() -> None:
    # fixture_source bypasses the SourceRecord constructor, so this models a retriever that returned
    # a vendor passage from an origin that the approved allowlist does not permit.
    rogue = fixture_source(
        source_id="rogue",
        kind=SourceKind.VENDOR_DOC,
        workspace_id="ws-a",
        origin="https://example.com/storefront-api",
        title="Rogue",
        text="The storefront api manages product and checkout settings.",
        retrieved_at=NOW,
        version=None,
    )
    retriever = CountingRetriever([rogue])
    response, _ = call_adapter(_shopify(retriever), parse_request(_envelope()), CountingVerifier())
    assert retriever.calls >= 1
    assert response.findings == ()
    assert "example.com" not in response.model_dump_json()
    assert any("outside the approved allowlist" in u for u in response.unknowns)


# 11. Shopify cited findings with an approved source


def test_shopify_cites_an_approved_vendor_passage() -> None:
    retriever = CountingRetriever([_vendor("https://www.shopify.com/pricing/plans")])
    response, _ = call_adapter(_shopify(retriever), parse_request(_envelope()), CountingVerifier())
    cited = [f for f in response.findings if f.evidence_status == "cited"]
    assert cited, "an approved vendor passage must yield a cited finding"
    assert all(ref.source_id == "shopify-plan" for f in cited for ref in f.evidence_refs)
    # 10. UNKNOWN classification without substantiation: no assessor, so no finding is SUPPORTED.
    assert {f.check_outcome for f in response.findings} == {CheckOutcome.UNKNOWN}


# 10. Invalid evidence mapping already refused elsewhere; here the AI-side table is checked.


def test_every_emitted_status_is_inside_the_lineage_b_vocabulary() -> None:
    retriever = CountingRetriever([_vendor("https://www.shopify.com/pricing/plans")])
    response, _ = call_adapter(_shopify(retriever), parse_request(_envelope()), CountingVerifier())
    for finding in response.findings:
        mapped = map_evidence_status(finding.evidence_status)
        assert mapped in LINEAGE_B_EVIDENCE_STATUS
        assert mapped != "verified"


def test_lineage_b_serialization_carries_check_outcome_separately() -> None:
    # CONTRACT DOUBLE for the AI Engine record shape. The check outcome is a separate field, as
    # OPEN-08 requires, and it never changes the evidence status.
    retriever = CountingRetriever([_vendor("https://www.shopify.com/pricing/plans")])
    response, _ = call_adapter(_shopify(retriever), parse_request(_envelope()), CountingVerifier())
    records = [
        {
            "evidence_status": map_evidence_status(f.evidence_status),
            "check_outcome": f.check_outcome.value,
            "statement": f.statement,
        }
        for f in response.findings
    ]
    assert records
    for record in records:
        assert set(record) == {"evidence_status", "check_outcome", "statement"}
        assert record["evidence_status"] in LINEAGE_B_EVIDENCE_STATUS
        assert record["check_outcome"] in {"SUPPORTED", "UNSUPPORTED", "UNKNOWN"}
        assert record["evidence_status"] != "verified"


def test_requirement_digest_is_sha256_of_the_sorted_unique_compact_array() -> None:
    # Contract v1.1: SHA-256 hex of the sorted unique JSON array, compact separators.
    refs = ["REQ-002", "REQ-001", "REQ-001"]
    expected = hashlib.sha256(b'["REQ-001","REQ-002"]').hexdigest()
    assert (
        binding_for(parse_request(_envelope(requirement_refs=refs))).requirement_refs_digest
        == expected
    )


def test_an_empty_source_scope_runs_no_retrieval_and_no_provider() -> None:
    empty = hashlib.sha256(b"[]").hexdigest()
    retriever = CountingRetriever([_vendor("https://www.shopify.com/pricing/plans")])
    response, verified = call_adapter(
        _shopify(retriever),
        parse_request(_envelope(source_scope_digest=empty)),
        CountingVerifier(),
    )
    assert retriever.calls == 0
    assert verified == VerifiedConfirmation(actor_ref="proof-actor")
    assert response.status == "incomplete"
    assert response.findings == ()
    assert response.error is None


def test_the_source_scope_digest_is_part_of_the_verified_binding() -> None:
    first = binding_for(parse_request(_envelope(source_scope_digest="a" * 64)))
    second = binding_for(parse_request(_envelope(source_scope_digest="b" * 64)))
    assert first.source_scope_digest == "a" * 64
    assert first != second


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64, "", "[]"])
def test_a_malformed_source_scope_digest_is_refused(digest: str) -> None:
    with pytest.raises(AdapterRequestError) as raised:
        parse_request(_envelope(source_scope_digest=digest))
    assert raised.value.code == ERROR_REQUEST_INVALID


def test_the_source_scope_digest_is_required() -> None:
    data = _envelope()
    del data["source_scope_digest"]
    with pytest.raises(AdapterRequestError):
        parse_request(data)
