"""T14 unit tests: AES-GCM sealing of prior contact addresses; fail-closed key handling."""

from __future__ import annotations

import base64
import uuid

import pytest

from webdesk.config import ConfigurationError
from webdesk.crypto.contact_box import ContactBox, ContactBoxError, outbox_aad

KEY = base64.b64encode(b"\x01" * 32).decode("ascii")  # test-only key
USER = uuid.UUID("11111111-2222-3333-4444-555555555555")


def test_round_trip_recovers_the_address_for_the_same_row() -> None:
    box = ContactBox(KEY)
    blob = box.seal("former@wds-test.example", aad=outbox_aad("prior_contact_change", USER))
    assert box.open(blob, aad=outbox_aad("prior_contact_change", USER)) == (
        "former@wds-test.example"
    )


def test_ciphertext_does_not_contain_the_address() -> None:
    box = ContactBox(KEY)
    blob = box.seal("former@wds-test.example", aad=outbox_aad("prior_contact_change", USER))
    assert b"former@wds-test.example" not in blob


def test_blob_moved_to_another_user_or_purpose_fails_to_open() -> None:
    box = ContactBox(KEY)
    blob = box.seal("former@wds-test.example", aad=outbox_aad("prior_contact_change", USER))
    other = uuid.UUID("99999999-2222-3333-4444-555555555555")
    with pytest.raises(ContactBoxError):
        box.open(blob, aad=outbox_aad("prior_contact_change", other))
    with pytest.raises(ContactBoxError):
        box.open(blob, aad=outbox_aad("delivery_failure_alert", USER))


def test_a_different_key_cannot_open_the_blob() -> None:
    blob = ContactBox(KEY).seal("x@wds-test.example", aad=b"a")
    other_key = base64.b64encode(b"\x02" * 32).decode("ascii")
    with pytest.raises(ContactBoxError):
        ContactBox(other_key).open(blob, aad=b"a")


def test_each_seal_uses_a_fresh_nonce() -> None:
    box = ContactBox(KEY)
    first = box.seal("same@wds-test.example", aad=b"a")
    second = box.seal("same@wds-test.example", aad=b"a")
    assert first != second


@pytest.mark.parametrize("bad", ["not base64!", base64.b64encode(b"short").decode("ascii")])
def test_malformed_or_short_key_is_a_configuration_error(bad: str) -> None:
    with pytest.raises(ConfigurationError):
        ContactBox(bad)


def test_truncated_blob_is_refused_without_leaking_detail() -> None:
    with pytest.raises(ContactBoxError) as exc:
        ContactBox(KEY).open(b"tiny", aad=b"a")
    assert str(exc.value) == "unreadable"
