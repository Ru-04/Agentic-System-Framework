"""T4 unit tests: server-side redaction used by the audit service (EVAL-F12)."""

from __future__ import annotations

from webdesk.audit.service import REDACTED, redact


def test_secret_and_contact_values_are_replaced() -> None:
    result = redact(
        {
            "password": "hunter2",
            "reset_token": "abc",
            "token_hash": "deadbeef",
            "proof_ref": "wds-proof-1",
            "normalized_email": "ada@wds-test.example",
            "contact_ref": "ref-1",
        }
    )
    assert result == {
        "password": REDACTED,
        "reset_token": REDACTED,
        "token_hash": REDACTED,
        "proof_ref": REDACTED,
        "normalized_email": REDACTED,
        "contact_ref": REDACTED,
    }


def test_nested_structures_are_redacted_and_ordinary_fields_kept() -> None:
    result = redact(
        {
            "outcome_detail": {"status": "denied", "reason": "role_missing"},
            "items": [{"email": "x@y.example", "id": "A1"}, {"id": "B2"}],
        }
    )
    assert result == {
        "outcome_detail": {"status": "denied", "reason": "role_missing"},
        "items": [{"email": REDACTED, "id": "A1"}, {"id": "B2"}],
    }


def test_scalar_values_pass_through_unchanged() -> None:
    assert redact(7) == 7
    assert redact("plain") == "plain"
