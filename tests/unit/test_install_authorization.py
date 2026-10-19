"""T7 unit tests: owner-signed installation authorization, fail-closed preparation, CLI refusal.

The signing key is generated per test. No private key is stored in the repository.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from webdesk.ceremony.install import (
    InstallationError,
    canonical_bytes,
    prepare_install,
)
from webdesk.cli.install import main
from webdesk.config import Settings

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("WEBDESK_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def owner_key(tmp_path: Path) -> tuple[Ed25519PrivateKey, Path]:
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    path = tmp_path / "owner.pub.pem"
    path.write_bytes(public_pem)
    return private, path


def _payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "install",
        "owner_approval_ref": "OWNER-APR-2026-001",
        "owner_identity_ref": "owner:wds-sign-off",
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "nonce": "n-001",
        "contacts": [
            {"email": "Ada@WDS-Test.example", "display_name": "Ada"},
            {"email": "grace@wds-test.example", "display_name": "Grace"},
        ],
    }
    payload.update(overrides)
    return payload


def _write(tmp_path: Path, key: Ed25519PrivateKey, payload: dict[str, Any]) -> Path:
    signature = base64.b64encode(key.sign(canonical_bytes(payload))).decode("ascii")
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps({"payload": payload, "signature": signature}), encoding="utf-8")
    return path


def _settings(public_key: Path, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "env": "test",
        "email_domain_allowlist": "wds-test.example",
        "email_alias_denylist": "admin,root",
        "email_transport": "capture",
        "rl_login_failures_per_account_ip": 5,
        "rl_login_window_minutes": 15,
        "rl_ip_requests_per_window": 100,
        "rl_contact_actions_per_window": 5,
        "rl_contact_ip_requests_per_window": 100,
        "rl_window_minutes": 15,
        "outbox_dead_letter_threshold": 5,
        "outbox_encryption_key": "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",  # test only
        "owner_public_key_path": public_key,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_valid_authorization_prepares_two_normalized_contacts(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _payload())
    prepared = prepare_install(_settings(public), path, FixedClock())
    assert prepared.contacts == (
        ("ada@wds-test.example", "Ada"),
        ("grace@wds-test.example", "Grace"),
    )
    assert len(prepared.authorization_digest) == 64


def test_tampered_payload_is_refused(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _payload())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["payload"]["contacts"][1]["email"] = "mallory@wds-test.example"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public), path, FixedClock())
    assert exc.value.reason == "signature_invalid"


def test_signature_from_another_key_is_refused(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    _, public = owner_key
    impostor = Ed25519PrivateKey.generate()
    path = _write(tmp_path, impostor, _payload())
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public), path, FixedClock())
    assert exc.value.reason == "signature_invalid"


def test_expired_authorization_is_refused(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    stale = _payload(expires_at=(NOW - timedelta(minutes=1)).isoformat())
    path = _write(tmp_path, private, stale)
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public), path, FixedClock())
    assert exc.value.reason == "authorization_expired"


def test_identical_contacts_are_refused(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    same = [
        {"email": "ada@wds-test.example", "display_name": "A"},
        {"email": "ADA@wds-test.example", "display_name": "B"},
    ]
    path = _write(tmp_path, private, _payload(contacts=same))
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public), path, FixedClock())
    assert exc.value.reason == "contacts_not_distinct"


def test_exactly_two_contacts_are_required(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _payload(contacts=[{"email": "ada@wds-test.example"}]))
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public), path, FixedClock())
    assert exc.value.reason == "exactly_two_contacts_required"


def test_contact_outside_allowlist_is_refused(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    bad = _payload(
        contacts=[
            {"email": "ada@wds-test.example"},
            {"email": "grace@gmail.example"},
        ]
    )
    path = _write(tmp_path, private, bad)
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public), path, FixedClock())
    assert exc.value.reason == "contact_refused:domain_not_allowed"


def test_missing_owner_key_fails_closed_before_reading_anything(tmp_path: Path) -> None:
    path = tmp_path / "does-not-matter.json"
    with pytest.raises(InstallationError) as exc:
        prepare_install(
            _settings(tmp_path / "absent.pem", owner_public_key_path=None), path, FixedClock()
        )
    assert exc.value.reason.startswith("configuration_incomplete")
    assert "WEBDESK_OWNER_PUBLIC_KEY_PATH" in exc.value.reason


def test_missing_allowlist_fails_closed(
    tmp_path: Path, owner_key: tuple[Ed25519PrivateKey, Path]
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _payload())
    with pytest.raises(InstallationError) as exc:
        prepare_install(_settings(public, email_domain_allowlist=None), path, FixedClock())
    assert "WEBDESK_EMAIL_DOMAIN_ALLOWLIST" in exc.value.reason


def test_cli_refuses_without_database_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "authorization.json"
    path.write_text("{}", encoding="utf-8")
    code = main(["--authorization", str(path), "--operator", "op-1", "--verifier", "v-1"])
    assert code == 2
    assert "WEBDESK_DATABASE_URL" in capsys.readouterr().err
