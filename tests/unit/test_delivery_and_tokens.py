"""T9 unit tests: delivery transports fail closed; token hashing and TTL constants."""

from __future__ import annotations

import os
from datetime import timedelta

import pytest

from webdesk.config import ConfigurationError, Settings
from webdesk.delivery.transport import (
    CaptureTransport,
    TransportUnavailable,
    transport_from_settings,
)
from webdesk.tokens.service import TOKEN_TTL, token_hash


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("WEBDESK_"):
            monkeypatch.delenv(key, raising=False)


def test_default_transport_is_none_and_refuses_delivery() -> None:
    with pytest.raises(TransportUnavailable):
        transport_from_settings(Settings(_env_file=None, env="test"))


def test_capture_sink_is_available_in_test_profile() -> None:
    transport = transport_from_settings(
        Settings(_env_file=None, env="test", email_transport="capture")
    )
    assert isinstance(transport, CaptureTransport)


def test_capture_sink_is_refused_in_production() -> None:
    with pytest.raises(ConfigurationError, match="capture"):
        transport_from_settings(
            Settings(_env_file=None, env="production", email_transport="capture")
        )


def test_capture_sink_keeps_messages_in_memory_only() -> None:
    sink = CaptureTransport()
    sink.send(to="ada@wds-test.example", subject="s", body="b", idempotency_key="k-1")
    sink.send(to="ada@wds-test.example", subject="s", body="b", idempotency_key="k-1")
    assert sink.messages == [("ada@wds-test.example", "s", "b")]


def test_token_hash_is_deterministic_and_never_the_plaintext() -> None:
    token = "example-token-value"  # noqa: S105 - test value, not a credential
    assert token_hash(token) == token_hash(token)
    assert token_hash(token) != token
    assert len(token_hash(token)) == 64


def test_token_lifetime_is_thirty_minutes() -> None:
    assert TOKEN_TTL == timedelta(minutes=30)
