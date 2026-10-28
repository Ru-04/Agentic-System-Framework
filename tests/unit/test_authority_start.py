"""Start-up parsing and redaction for the authority test harness (authority_start.py)."""

from __future__ import annotations

from tests.support.authority_start import listen_port, redact


def test_the_start_up_line_names_the_bound_port() -> None:
    assert listen_port("authority listening on ('127.0.0.1', 54321)\n") == 54321


def test_an_empty_or_unrelated_line_names_no_port() -> None:
    assert listen_port("") is None
    assert listen_port("Traceback (most recent call last):\n") is None
    assert listen_port("authority listening on ('10.0.0.1', 80)\n") is None


def test_a_failure_report_removes_secrets_and_url_user_information() -> None:
    text = "could not connect to postgresql://role:s3cret-value@127.0.0.1/db with s3cret-value"
    cleaned = redact(text, ["s3cret-value"])
    assert "s3cret-value" not in cleaned
    assert "role:" not in cleaned
    assert "postgresql://<redacted>@127.0.0.1/db" in cleaned
