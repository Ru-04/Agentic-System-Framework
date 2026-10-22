"""Regression tests for approved proposals P1 (origin rule) and P2 (no environment proxies)."""

from __future__ import annotations

import urllib.request
from datetime import UTC, datetime
from typing import Any

import pytest

from webdesk.evidence.http_vendor import build_vendor_opener
from webdesk.evidence.sources import SourceKind, SourceRecord

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def _record(kind: SourceKind, origin: str, **overrides: Any) -> SourceRecord:
    payload: dict[str, Any] = {
        "source_id": "s",
        "kind": kind,
        "workspace_id": "ws-a",
        "origin": origin,
        "title": "t",
        "text": "x",
        "retrieved_at": NOW,
    }
    payload.update(overrides)
    return SourceRecord(**payload)


# P1: a vendor record must come from an allowlisted https origin.
@pytest.mark.parametrize(
    "origin",
    [
        "https://shopify.dev/docs/api",
        "https://help.shopify.com/en/manual",
    ],
)
def test_vendor_record_with_allowlisted_origin_is_accepted(origin: str) -> None:
    assert _record(SourceKind.VENDOR_DOC, origin).origin == origin


@pytest.mark.parametrize(
    "origin",
    [
        "fixture://shopify/x",
        "http://shopify.dev/docs",
        "https://evil.example/docs",
        "https://shopify.dev.attacker.example/docs",
        "internal:rag/doc-1",
    ],
)
def test_vendor_record_with_unapproved_origin_is_refused(origin: str) -> None:
    with pytest.raises(ValueError):
        _record(SourceKind.VENDOR_DOC, origin)


@pytest.mark.parametrize("origin", ["internal:rag/doc-1", "internal:wiki/42"])
def test_internal_record_with_internal_origin_is_accepted(origin: str) -> None:
    assert _record(SourceKind.INTERNAL_RAG, origin).origin == origin


@pytest.mark.parametrize("origin", ["https://shopify.dev/docs", "fixture://x", "rag/doc-1"])
def test_internal_record_with_other_origin_is_refused(origin: str) -> None:
    with pytest.raises(ValueError):
        _record(SourceKind.INTERNAL_RAG, origin)


# P2: vendor fetches ignore environment proxies. With an explicit empty ProxyHandler, urllib adds
# no proxy handler at all, and its default environment-reading handler is suppressed.
def test_vendor_opener_has_no_proxy_handler() -> None:
    opener = build_vendor_opener()
    assert not any(isinstance(h, urllib.request.ProxyHandler) for h in opener.handlers)


def test_environment_proxy_setting_does_not_add_a_proxy_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    opener = build_vendor_opener()
    assert not any(isinstance(h, urllib.request.ProxyHandler) for h in opener.handlers)
