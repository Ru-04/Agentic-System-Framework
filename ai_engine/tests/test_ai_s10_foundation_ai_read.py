"""Offline tests for the Foundation AI read client (``ai-read/v1``).

A fake transport returns responses shaped as the contract documents (section 6.1). Each refusal
test checks the intended rule and the reason; each positive test shows the same path accepts a
conforming response, so a refusal cannot pass merely because the fixture is malformed.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ai_engine.adapters.foundation_ai_read import (
    AiReadClient,
    AiReadNotFound,
    AiReadRefused,
    AiReadResponse,
)

RUN = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
SYNTHETIC_CREDENTIAL = "SYNTHETIC-AI-PRINCIPAL-SYNTHETIC_CREDENTIAL-0001"
BASE = f"/v1/ai/runs/{RUN}"
CONTRACT_HEADERS = {"X-AI-Contract-Version": "ai-read/v1"}


class FakeTransport:
    def __init__(self, routes: dict[str, AiReadResponse]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, path: str, headers: Any) -> AiReadResponse:
        self.calls.append((path, dict(headers)))
        key = path.split("?", 1)[0]
        if key not in self.routes:
            return AiReadResponse(404, {}, b"{}")
        return self.routes[key]


def ok(payload: dict[str, Any]) -> AiReadResponse:
    return AiReadResponse(200, CONTRACT_HEADERS, json.dumps(payload).encode("utf-8"))


def run_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract": "ai-read/v1",
        "run_id": RUN,
        "project_id": PROJECT,
        "state": "awaiting_review",
        "status": "waiting_human",
        "revision": 3,
        "is_stale": False,
        "failure_class": None,
        "created_at": "2026-10-20T12:00:00Z",
        "updated_at": "2026-10-20T12:05:00Z",
    }
    payload.update(overrides)
    return payload


def project_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract": "ai-read/v1",
        "project_id": PROJECT,
        "name": "Synthetic brief",
        "data_classification": "internal",
        "status": "active",
        "revision": 2,
    }
    payload.update(overrides)
    return payload


def version(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "source_version_id": VERSION,
        "source_id": "44444444-4444-4444-8444-444444444444",
        "version": 1,
        "scan_status": "clean",
        "parse_status": "parsed",
        "access_classification": "internal",
        "revision": 1,
        "mime_type": "text/plain",
        "file_size_bytes": 128,
    }
    item.update(overrides)
    return item


def client_for(routes: dict[str, AiReadResponse]) -> tuple[AiReadClient, FakeTransport]:
    transport = FakeTransport(routes)
    return AiReadClient(
        transport=transport, run_id=RUN, principal_token=SYNTHETIC_CREDENTIAL
    ), transport


# --- positive controls ----------------------------------------------------------------------------


def test_run_metadata_is_read_with_the_documented_headers_and_get_only() -> None:
    client, transport = client_for({BASE: ok(run_payload())})
    run = client.run()
    assert run.project_id == PROJECT
    ((path, headers),) = transport.calls
    assert path == BASE
    assert headers == {
        "Authorization": f"AI-Principal {SYNTHETIC_CREDENTIAL}",
        "X-AI-Contract-Version": "ai-read/v1",
    }


def test_project_metadata_matching_the_run_is_accepted() -> None:
    client, _ = client_for({BASE: ok(run_payload()), f"{BASE}/project": ok(project_payload())})
    assert client.project().project_id == PROJECT


def test_clean_and_not_scanned_readable_versions_are_accepted() -> None:
    page = {
        "contract": "ai-read/v1",
        "items": [version(), version(scan_status="not_scanned")],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions": ok(page)})
    assert len(client.source_versions().items) == 2


def test_truncated_segment_of_exact_contract_length_is_accepted() -> None:
    segment = {
        "segment_id": "s-1",
        "locator_type": "paragraph",
        "locator": "p1",
        "text_content": "x" * 4000,
        "text_truncated": True,
    }
    page = {
        "contract": "ai-read/v1",
        "source_version_id": VERSION,
        "items": [segment],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions/{VERSION}/segments": ok(page)})
    assert client.segments(VERSION).items[0].text_truncated is True


# --- refusals: the run and project scope ----------------------------------------------------------


def test_run_response_naming_another_run_is_refused() -> None:
    other = "55555555-5555-4555-8555-555555555555"
    client, _ = client_for({BASE: ok(run_payload(run_id=other))})
    with pytest.raises(AiReadRefused, match="different run"):
        client.run()


def test_project_response_for_another_project_is_refused() -> None:
    other = "66666666-6666-4666-8666-666666666666"
    client, _ = client_for(
        {BASE: ok(run_payload()), f"{BASE}/project": ok(project_payload(project_id=other))}
    )
    with pytest.raises(AiReadRefused, match="does not match the run's project"):
        client.project()


def test_an_invalid_run_identifier_is_refused_before_any_request() -> None:
    transport = FakeTransport({})
    with pytest.raises(AiReadRefused, match="not a UUID"):
        AiReadClient(transport=transport, run_id="not-a-uuid", principal_token=SYNTHETIC_CREDENTIAL)
    assert transport.calls == []


def test_a_missing_credential_is_refused_before_any_request() -> None:
    transport = FakeTransport({})
    with pytest.raises(AiReadRefused, match="credential is missing"):
        AiReadClient(transport=transport, run_id=RUN, principal_token="")
    assert transport.calls == []


# --- refusals: read rules (contract section 5) ---------------------------------------------------


def test_a_quarantined_version_in_the_list_is_refused() -> None:
    page = {
        "contract": "ai-read/v1",
        "items": [version(scan_status="quarantined")],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions": ok(page)})
    with pytest.raises(AiReadRefused, match="unreadable scan status"):
        client.source_versions()


def test_a_restricted_version_in_the_list_is_refused() -> None:
    page = {
        "contract": "ai-read/v1",
        "items": [version(access_classification="restricted")],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions": ok(page)})
    with pytest.raises(AiReadRefused, match="outside the read rules"):
        client.source_versions()


def test_an_unknown_scan_status_is_refused() -> None:
    page = {
        "contract": "ai-read/v1",
        "items": [version(scan_status="pending")],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions": ok(page)})
    with pytest.raises(AiReadRefused, match="unreadable scan status"):
        client.source_versions()


def test_quarantined_content_is_not_disclosed_as_existing() -> None:
    client, _ = client_for({})  # the Foundation answers 404 for every out-of-scope version
    with pytest.raises(AiReadNotFound):
        client.content(VERSION)


# --- refusals: paging and limits -----------------------------------------------------------------


@pytest.mark.parametrize("limit", [0, 101])
def test_a_source_limit_outside_the_contract_is_refused_before_any_request(limit: int) -> None:
    client, transport = client_for({})
    with pytest.raises(AiReadRefused, match="limit must be between 1 and 100"):
        client.source_versions(limit=limit)
    assert transport.calls == []


def test_a_next_cursor_that_is_not_the_last_identifier_is_refused() -> None:
    page = {
        "contract": "ai-read/v1",
        "items": [version()],
        "next_cursor": "99999999-9999-4999-8999-999999999999",
    }
    client, _ = client_for({f"{BASE}/source-versions": ok(page)})
    with pytest.raises(AiReadRefused, match="next cursor"):
        client.source_versions()


def test_segment_text_over_the_contract_limit_is_refused() -> None:
    segment = {
        "segment_id": "s-1",
        "locator_type": "p",
        "locator": "1",
        "text_content": "x" * 4001,
        "text_truncated": False,
    }
    page = {
        "contract": "ai-read/v1",
        "source_version_id": VERSION,
        "items": [segment],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions/{VERSION}/segments": ok(page)})
    with pytest.raises(AiReadRefused, match="exceeds the contract limit"):
        client.segments(VERSION)


def test_a_segment_page_naming_another_source_version_is_refused() -> None:
    other_version = "55555555-5555-4555-8555-555555555555"
    page = {
        "contract": "ai-read/v1",
        "source_version_id": other_version,
        "items": [],
        "next_cursor": None,
    }
    client, _ = client_for({f"{BASE}/source-versions/{VERSION}/segments": ok(page)})
    with pytest.raises(AiReadRefused, match="different source version"):
        client.segments(VERSION)


def test_an_expired_or_revoked_credential_is_refused_even_with_a_contract_body() -> None:
    # A 401 must never be read as data, whatever body accompanies it (contract section 9).
    body = json.dumps(run_payload()).encode("utf-8")
    client, _ = client_for({f"{BASE}": AiReadResponse(401, CONTRACT_HEADERS, body)})
    with pytest.raises(AiReadRefused, match="credential is not valid"):
        client.run()


def test_a_malformed_cursor_is_refused_before_any_request() -> None:
    client, transport = client_for({})
    with pytest.raises(AiReadRefused, match="cursor is malformed"):
        client.source_versions(after="x&limit=100")
    assert transport.calls == []


# --- refusals: content and transport ------------------------------------------------------------


def test_content_reported_over_the_size_limit_is_refused() -> None:
    client, _ = client_for(
        {f"{BASE}/source-versions/{VERSION}/content": AiReadResponse(413, {}, b"")}
    )
    with pytest.raises(AiReadRefused, match="size limit"):
        client.content(VERSION)


def test_content_larger_than_the_limit_is_refused_even_with_status_200() -> None:
    too_big = b"x" * (10 * 1024 * 1024 + 1)
    headers = {"X-AI-Contract": "ai-read/v1", "Content-Type": "text/plain"}
    client, _ = client_for(
        {f"{BASE}/source-versions/{VERSION}/content": AiReadResponse(200, headers, too_big)}
    )
    with pytest.raises(AiReadRefused, match="size limit"):
        client.content(VERSION)


def test_content_without_the_contract_tag_is_refused() -> None:
    headers = {**CONTRACT_HEADERS, "Content-Type": "text/plain"}
    client, _ = client_for(
        {f"{BASE}/source-versions/{VERSION}/content": AiReadResponse(200, headers, b"ok")}
    )
    with pytest.raises(AiReadRefused, match="contract tag"):
        client.content(VERSION)


def test_a_response_declaring_another_contract_version_is_refused() -> None:
    response = AiReadResponse(
        200, {"X-AI-Contract-Version": "ai-read/v2"}, json.dumps(run_payload()).encode()
    )
    client, _ = client_for({BASE: response})
    with pytest.raises(AiReadRefused, match="another contract version"):
        client.run()


def test_a_method_not_allowed_response_is_refused() -> None:
    client, _ = client_for({BASE: AiReadResponse(405, {}, b"{}")})
    with pytest.raises(AiReadRefused, match="method not allowed"):
        client.run()


def test_additive_optional_fields_are_accepted_as_contract_section_13_allows() -> None:
    client, _ = client_for({BASE: ok(run_payload(new_optional_hint="additive"))})
    assert client.run().run_id == RUN


@pytest.mark.parametrize(
    "field", ["storage_key", "content_hash", "ingested_by_user_id", "session_id"]
)
def test_a_forbidden_field_is_refused_at_any_level(field: str) -> None:
    item = version()
    item[field] = "must-not-appear"
    page = {"contract": "ai-read/v1", "items": [item], "next_cursor": None}
    client, _ = client_for({f"{BASE}/source-versions": ok(page)})
    with pytest.raises(AiReadRefused, match="forbids"):
        client.source_versions()


def test_a_forbidden_field_at_the_top_level_is_refused() -> None:
    client, _ = client_for({BASE: ok(run_payload(content_hash="abc"))})
    with pytest.raises(AiReadRefused, match="forbids"):
        client.run()


def test_a_success_without_the_contract_version_header_is_refused() -> None:
    client, _ = client_for({BASE: AiReadResponse(200, {}, json.dumps(run_payload()).encode())})
    with pytest.raises(AiReadRefused, match="does not declare the contract version"):
        client.run()


def test_a_body_without_its_contract_field_is_refused() -> None:
    payload = run_payload()
    del payload["contract"]
    client, _ = client_for({BASE: ok(payload)})
    with pytest.raises(AiReadRefused, match="schema|does not declare the contract"):
        client.run()


def test_a_non_json_body_is_refused() -> None:
    client, _ = client_for({BASE: AiReadResponse(200, CONTRACT_HEADERS, b"<html>")})
    with pytest.raises(AiReadRefused, match="not valid JSON"):
        client.run()


# --- credential and surface ---------------------------------------------------------------------


def test_the_credential_never_appears_in_any_refusal_or_representation() -> None:
    client, _ = client_for({BASE: AiReadResponse(200, CONTRACT_HEADERS, b"<html>")})
    with pytest.raises(AiReadRefused) as caught:
        client.run()
    assert SYNTHETIC_CREDENTIAL not in str(caught.value)
    assert SYNTHETIC_CREDENTIAL not in caught.value.reason
    assert SYNTHETIC_CREDENTIAL not in repr(client)


def test_the_client_exposes_no_write_operation() -> None:
    client, _ = client_for({})
    for name in ("post", "put", "patch", "delete", "create", "save", "persist", "approve", "grant"):
        assert not hasattr(client, name), name
