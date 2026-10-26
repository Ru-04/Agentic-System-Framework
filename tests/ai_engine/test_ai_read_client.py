"""Mock-Foundation contract tests for the ai-read/v1 read adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from webdesk_ai import synthetic
from webdesk_ai.foundation.client import (
    CONTRACT_HEADER,
    CONTRACT_ID,
    MAX_CONTENT_BYTES,
    ContractViolationError,
    CredentialExpiredError,
    CredentialRejectedError,
    FoundationReadClient,
    FoundationReadError,
    FoundationUnavailableError,
    PrincipalCredential,
    ReadRequest,
    ReadResponse,
    ResourceUnavailableError,
    ResponseTooLargeError,
    ScopeMismatchError,
    VersionMismatchError,
)
from webdesk_ai.foundation.mock import MockFoundation, MockVersion, segment_row

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
TOKEN = "synthetic-test-token"


class RecordingTransport:
    """Wraps a transport and records every request, so header rules can be asserted."""

    def __init__(self, inner: MockFoundation) -> None:
        self.inner = inner
        self.requests: list[ReadRequest] = []

    def send(self, request: ReadRequest) -> ReadResponse:
        self.requests.append(request)
        return self.inner.send(request)


def _client(
    foundation: MockFoundation | RecordingTransport,
    *,
    token: str = TOKEN,
    expires_at: datetime = NOW + timedelta(minutes=15),
    clock: datetime = NOW,
    project_id: UUID = synthetic.PROJECT_ID,
) -> FoundationReadClient:
    return FoundationReadClient(
        transport=foundation,
        credential=PrincipalCredential(token=token, expires_at=expires_at),
        run_id=synthetic.RUN_ID,
        project_id=project_id,
        clock=lambda: clock,
        correlation_id=lambda: "11111111-1111-4111-8111-111111111111",
    )


def _foundation(**overrides: object) -> MockFoundation:
    base = synthetic.build_foundation(token=TOKEN, now=NOW, expires_at=NOW + timedelta(minutes=15))
    return replace(base, **overrides)  # type: ignore[arg-type]


class _StatusTransport:
    def __init__(self, status: int, body: bytes = b'{"contract":"ai-read/v1","error":"x"}') -> None:
        self.status = status
        self.body = body

    def send(self, request: ReadRequest) -> ReadResponse:
        return ReadResponse(status=self.status, headers={}, body=self.body)


def test_requests_carry_contract_version_credential_and_correlation_id() -> None:
    transport = RecordingTransport(_foundation())
    _client(transport).get_run()
    request = transport.requests[0]
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"AI-Principal {TOKEN}"
    assert request.headers[CONTRACT_HEADER] == CONTRACT_ID
    assert request.headers["X-Correlation-Id"] == "11111111-1111-4111-8111-111111111111"


def test_credential_repr_does_not_expose_the_token() -> None:
    assert TOKEN not in repr(PrincipalCredential(token=TOKEN, expires_at=NOW))


def test_run_and_project_scope_are_checked() -> None:
    run = _client(_foundation()).get_run()
    assert run.run_id == synthetic.RUN_ID
    project = _client(_foundation()).get_project()
    assert project.project_id == synthetic.PROJECT_ID
    with pytest.raises(ScopeMismatchError):
        _client(_foundation(project_override_id=UUID(int=9))).get_project()


def test_source_versions_drop_quarantined_and_restricted_and_never_leak_them() -> None:
    versions = list(_client(_foundation()).iter_source_versions())
    ids = {v.source_version_id for v in versions}
    assert synthetic.VERSION_QUARANTINED not in ids
    assert synthetic.VERSION_RESTRICTED not in ids
    assert {synthetic.VERSION_BRIEF, synthetic.VERSION_EMAIL, synthetic.VERSION_APPENDIX} == ids
    assert all(v.scan_status in ("not_scanned", "clean") for v in versions)
    assert all(v.access_classification != "restricted" for v in versions)


def test_pagination_yields_every_visible_version_exactly_once() -> None:
    transport = RecordingTransport(_foundation())
    versions = list(_client(transport).iter_source_versions(page_limit=1))
    assert len(versions) == 3
    assert len({v.source_version_id for v in versions}) == 3
    list_requests = [r for r in transport.requests if "source-versions?" in r.path]
    assert len(list_requests) == 3
    assert "after=" in list_requests[1].path


def test_segments_are_paged_and_truncation_is_reported_not_hidden() -> None:
    client = _client(_foundation())
    appendix = next(
        v
        for v in client.iter_source_versions()
        if v.source_version_id == synthetic.VERSION_APPENDIX
    )
    segments = list(client.iter_segments(appendix, page_limit=1))
    assert len(segments) == 1
    assert segments[0].text_truncated is True
    assert len(segments[0].text_content) == 4000
    brief = next(
        v for v in client.iter_source_versions() if v.source_version_id == synthetic.VERSION_BRIEF
    )
    brief_segments = list(client.iter_segments(brief, page_limit=2))
    assert len(brief_segments) == 4
    assert all(not s.text_truncated for s in brief_segments)


def test_quarantined_version_is_not_found_for_segments_and_content() -> None:
    client = _client(_foundation())
    hidden = synthetic.VERSION_QUARANTINED
    with pytest.raises(ResourceUnavailableError):
        client.read_content(hidden)
    stub = next(
        v for v in client.iter_source_versions() if v.source_version_id == synthetic.VERSION_BRIEF
    )
    hidden_ref = stub.model_copy(update={"source_version_id": hidden})
    with pytest.raises(ResourceUnavailableError):
        list(client.iter_segments(hidden_ref))


def test_content_within_limit_is_returned_and_oversize_is_refused() -> None:
    client = _client(_foundation())
    assert client.read_content(synthetic.VERSION_EMAIL) == synthetic.TEXT_E.encode()
    oversize = MockVersion(
        source_version_id=UUID(int=77),
        source_id=UUID(int=78),
        version=1,
        content=b"x" * (MAX_CONTENT_BYTES + 1),
    )
    big = _foundation(versions=[oversize])
    with pytest.raises(ResponseTooLargeError):
        _client(big).read_content(UUID(int=77))


def test_client_side_expiry_refuses_without_contacting_foundation() -> None:
    transport = RecordingTransport(_foundation())
    client = _client(transport, clock=NOW + timedelta(minutes=16))
    with pytest.raises(CredentialExpiredError):
        client.get_run()
    assert transport.requests == []


def test_server_side_expiry_and_revocation_are_neutral_credential_rejections() -> None:
    expired = _foundation()
    expired.expire_now()
    with pytest.raises(CredentialRejectedError):
        _client(expired).get_run()
    revoked = _foundation()
    revoked.revoke()
    with pytest.raises(CredentialRejectedError):
        _client(revoked).get_run()


def test_wrong_token_and_inactive_run_are_the_same_neutral_rejection() -> None:
    with pytest.raises(CredentialRejectedError):
        _client(_foundation(), token="wrong").get_run()
    with pytest.raises(CredentialRejectedError):
        _client(_foundation(run_status="cancelled")).get_run()


def test_unknown_contract_version_from_server_is_a_version_mismatch() -> None:
    class V2Transport:
        def send(self, request: ReadRequest) -> ReadResponse:
            return ReadResponse(
                status=200,
                headers={},
                body=b'{"contract":"ai-read/v2","run_id":"x"}',
            )

    with pytest.raises(VersionMismatchError):
        _client(V2Transport()).get_run()
    with pytest.raises(VersionMismatchError):
        _client(
            _StatusTransport(
                400, b'{"contract":"ai-read/v1","error":"contract_version_unsupported"}'
            )
        ).get_run()


def test_error_table_maps_to_typed_errors() -> None:
    with pytest.raises(ContractViolationError):
        _client(_StatusTransport(400, b'{"error":"invalid_request"}')).get_run()
    with pytest.raises(ContractViolationError):
        _client(_StatusTransport(405, b'{"error":"method_not_allowed"}')).get_run()
    with pytest.raises(ResponseTooLargeError):
        _client(_StatusTransport(413)).get_run()
    with pytest.raises(FoundationUnavailableError):
        _client(_StatusTransport(503)).get_run()


def test_transport_failure_becomes_an_unavailable_error() -> None:
    class BrokenTransport:
        def send(self, request: ReadRequest) -> ReadResponse:
            raise ConnectionError("refused")

    with pytest.raises(FoundationUnavailableError):
        _client(BrokenTransport()).get_run()


def test_forbidden_storage_fields_in_version_metadata_are_refused() -> None:
    class LeakyTransport:
        def send(self, request: ReadRequest) -> ReadResponse:
            if "source-versions" in request.path:
                body = (
                    '{"contract":"ai-read/v1","next_cursor":null,"items":[{"source_version_id":'
                    '"40000000-0000-4000-8000-000000000001","source_id":"30000000-0000-4000-8000-000000000001",'
                    '"version":1,"scan_status":"clean","parse_status":"succeeded",'
                    '"access_classification":"confidential","revision":1,"mime_type":"text/plain",'
                    '"file_size_bytes":3,"storage_key":"secret/path"}]}'
                )
                return ReadResponse(status=200, headers={}, body=body.encode())
            return _foundation().send(request)

    with pytest.raises(ContractViolationError):
        list(_client(LeakyTransport()).iter_source_versions())


def test_non_advancing_cursor_is_refused_rather_than_looping() -> None:
    class StuckTransport:
        def send(self, request: ReadRequest) -> ReadResponse:
            body = (
                '{"contract":"ai-read/v1","next_cursor":"00000000-0000-0000-0000-000000000000",'
                '"items":[]}'
            )
            return ReadResponse(status=200, headers={}, body=body.encode())

    with pytest.raises(ContractViolationError):
        list(_client(StuckTransport()).iter_source_versions(page_limit=1))


def test_invalid_limits_are_refused_before_any_request() -> None:
    transport = RecordingTransport(_foundation())
    with pytest.raises(ContractViolationError):
        list(_client(transport).iter_source_versions(page_limit=101))
    with pytest.raises(ContractViolationError):
        list(
            _client(transport).iter_segments(
                next(iter(_client(transport).iter_source_versions())), page_limit=201
            )
        )
    assert len(transport.requests) == 1


def test_mock_refuses_a_request_with_the_wrong_contract_header() -> None:
    response = _foundation().send(
        ReadRequest(
            method="GET",
            path=f"/v1/ai/runs/{synthetic.RUN_ID}",
            headers={"Authorization": f"AI-Principal {TOKEN}", CONTRACT_HEADER: "ai-read/v9"},
        )
    )
    assert response.status == 400


def test_mock_refuses_writes_with_405_and_an_unauthenticated_call_with_401() -> None:
    foundation = _foundation()
    write = foundation.send(
        ReadRequest(
            method="POST",
            path=f"/v1/ai/runs/{synthetic.RUN_ID}",
            headers={"Authorization": f"AI-Principal {TOKEN}", CONTRACT_HEADER: CONTRACT_ID},
        )
    )
    assert write.status == 405
    anonymous = foundation.send(
        ReadRequest(
            method="GET",
            path=f"/v1/ai/runs/{synthetic.RUN_ID}",
            headers={CONTRACT_HEADER: CONTRACT_ID},
        )
    )
    assert anonymous.status == 401


def test_read_errors_share_one_base_class() -> None:
    assert issubclass(CredentialExpiredError, CredentialRejectedError)
    assert issubclass(CredentialRejectedError, FoundationReadError)
    assert issubclass(ScopeMismatchError, FoundationReadError)


def test_segment_row_helper_keeps_identifiers_as_given() -> None:
    row = segment_row(synthetic.SEG_A, "txt_line_range", {"line_start": 1}, "text")
    assert row["segment_id"] == synthetic.SEG_A
