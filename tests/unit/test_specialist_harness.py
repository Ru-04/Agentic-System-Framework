from __future__ import annotations

from typing import Any

import pytest

from tests.support.authority import run_specialist
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import SpecialistInput
from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode
from webdesk.specialists.mock import MockSpecialist


def _request(specialist: SpecialistId = SpecialistId.SHOPIFY, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "1.0.0",
        "request_id": "req-1",
        "workspace_id": "ws-a",
        "specialist_id": specialist.value,
        "requirement_ids": ["REQ-001", "REQ-002"],
        "evidence_refs": [],
        "task": "assess feasibility",
    }
    payload.update(overrides)
    return payload


def _evidence(workspace_id: str) -> dict[str, str]:
    return {"workspace_id": workspace_id, "source_id": "src-1", "locator": "doc#section-2"}


def _code(exc_info: pytest.ExceptionInfo[SpecialistError]) -> SpecialistErrorCode:
    return exc_info.value.code


def test_mock_run_returns_honest_incomplete_output() -> None:
    output = run_specialist(MockSpecialist(SpecialistId.SHOPIFY), _request())
    assert output.status == "incomplete"
    assert output.findings == ()
    assert output.unknowns == (
        "no evidence was retrieved for REQ-001",
        "no evidence was retrieved for REQ-002",
    )


def test_mock_run_is_deterministic() -> None:
    first = run_specialist(
        MockSpecialist(SpecialistId.BIGCOMMERCE), _request(SpecialistId.BIGCOMMERCE)
    )
    second = run_specialist(
        MockSpecialist(SpecialistId.BIGCOMMERCE), _request(SpecialistId.BIGCOMMERCE)
    )
    assert first == second


@pytest.mark.parametrize("specialist", list(SpecialistId))
def test_every_category_conforms_through_the_harness(specialist: SpecialistId) -> None:
    output = run_specialist(MockSpecialist(specialist), _request(specialist))
    assert output.specialist_id is specialist
    assert output.workspace_id == "ws-a"


def test_unsupported_contract_version_is_refused() -> None:
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY), _request(contract_version="0.9.0"))
    assert _code(exc_info) is SpecialistErrorCode.CONTRACT_VERSION_UNSUPPORTED


def test_invalid_request_is_refused_before_provider_runs() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request(approved=True))
    assert _code(exc_info) is SpecialistErrorCode.INPUT_INVALID
    assert provider.calls == 0


def test_request_for_another_specialist_is_refused() -> None:
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(
            MockSpecialist(SpecialistId.SHOPIFY), _request(SpecialistId.MAGENTO_ADOBE_COMMERCE)
        )
    assert _code(exc_info) is SpecialistErrorCode.SPECIALIST_MISMATCH


@pytest.mark.parametrize(
    "action",
    [
        "approve_artifact",
        "grant_permission",
        "modify_routing",
        "accept_inferred_requirement",
        "write_requirement",
        "resolve_blocker",
        "unlisted_action",
    ],
)
def test_forbidden_or_unlisted_actions_are_denied_before_any_run(action: str) -> None:
    provider = MockSpecialist(
        SpecialistId.STANDALONE_APPLICATIONS, declared_actions=frozenset({action})
    )
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request(SpecialistId.STANDALONE_APPLICATIONS))
    assert _code(exc_info) is SpecialistErrorCode.CAPABILITY_DENIED
    assert action in exc_info.value.message
    assert provider.calls == 0


def test_request_evidence_from_another_workspace_is_refused() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY)
    request = _request(evidence_refs=[_evidence("ws-b")])
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, request)
    assert _code(exc_info) is SpecialistErrorCode.WORKSPACE_MISMATCH
    assert "ws-b" not in exc_info.value.message
    assert provider.calls == 0


def test_output_for_another_workspace_is_refused() -> None:
    def canned(request: SpecialistInput) -> dict[str, Any]:
        return {
            "contract_version": "1.0.0",
            "request_id": request.request_id,
            "workspace_id": "ws-b",
            "specialist_id": request.specialist_id.value,
            "status": "incomplete",
            "unknowns": ["none"],
        }

    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert _code(exc_info) is SpecialistErrorCode.WORKSPACE_MISMATCH


def test_finding_citing_another_workspace_is_refused() -> None:
    def canned(request: SpecialistInput) -> dict[str, Any]:
        return {
            "contract_version": "1.0.0",
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": request.specialist_id.value,
            "status": "completed",
            "findings": [
                {
                    "statement": "supported",
                    "evidence_status": "cited",
                    "evidence_refs": [_evidence("ws-b")],
                }
            ],
        }

    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert _code(exc_info) is SpecialistErrorCode.WORKSPACE_MISMATCH


def test_provider_exception_becomes_retryable_provider_failure() -> None:
    provider = MockSpecialist(SpecialistId.SHOPIFY, failure=TimeoutError("upstream timed out"))
    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(provider, _request())
    assert _code(exc_info) is SpecialistErrorCode.PROVIDER_FAILURE
    assert exc_info.value.retryable is True
    assert "upstream timed out" not in exc_info.value.message


def test_only_provider_failure_is_retryable() -> None:
    for code in SpecialistErrorCode:
        error = SpecialistError(code, "x")
        assert error.retryable is (code is SpecialistErrorCode.PROVIDER_FAILURE)


def test_malformed_output_is_refused() -> None:
    def canned(request: SpecialistInput) -> dict[str, Any]:
        return {"request_id": request.request_id, "status": "completed"}

    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert _code(exc_info) is SpecialistErrorCode.OUTPUT_INVALID


def test_output_with_extra_authority_field_is_refused() -> None:
    def canned(request: SpecialistInput) -> dict[str, Any]:
        return {
            "contract_version": "1.0.0",
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": request.specialist_id.value,
            "status": "incomplete",
            "unknowns": ["none"],
            "approved": True,
        }

    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert _code(exc_info) is SpecialistErrorCode.OUTPUT_INVALID


def test_output_that_does_not_echo_request_identity_is_refused() -> None:
    def canned(request: SpecialistInput) -> dict[str, Any]:
        return {
            "contract_version": "1.0.0",
            "request_id": "someone-else",
            "workspace_id": request.workspace_id,
            "specialist_id": request.specialist_id.value,
            "status": "incomplete",
            "unknowns": ["none"],
        }

    with pytest.raises(SpecialistError) as exc_info:
        run_specialist(MockSpecialist(SpecialistId.SHOPIFY, canned=canned), _request())
    assert _code(exc_info) is SpecialistErrorCode.OUTPUT_INVALID
