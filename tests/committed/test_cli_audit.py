"""F12: installation refusals are audited when a database is available (committed rows).

Each refusal test runs the real CLI entry point with an environment that points at the session
database. The refusals commit their audit rows, so they are checked on a separate connection. No
test here completes an installation, so the session installation is not disturbed.
"""

from __future__ import annotations

import base64
import json
import uuid
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from sqlalchemy.engine import Engine

from webdesk.ceremony.install import canonical_bytes
from webdesk.cli.install import main

pytestmark = pytest.mark.integration

LOCK_ENV = {
    "WEBDESK_ENV": "test",
    "WEBDESK_EMAIL_DOMAIN_ALLOWLIST": "wds-test.example",
    "WEBDESK_EMAIL_ALIAS_DENYLIST": "admin,root",
    "WEBDESK_EMAIL_TRANSPORT": "capture",
    "WEBDESK_RL_LOGIN_FAILURES_PER_ACCOUNT_IP": "5",
    "WEBDESK_RL_LOGIN_WINDOW_MINUTES": "15",
    "WEBDESK_RL_IP_REQUESTS_PER_WINDOW": "100",
    "WEBDESK_RL_CONTACT_ACTIONS_PER_WINDOW": "5",
    "WEBDESK_RL_CONTACT_IP_REQUESTS_PER_WINDOW": "100",
    "WEBDESK_RL_WINDOW_MINUTES": "15",
    "WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD": "5",
    "WEBDESK_OUTBOX_ENCRYPTION_KEY": base64.b64encode(b"\x0b" * 32).decode("ascii"),
}


@pytest.fixture
def owner(tmp_path: Path) -> tuple[Ed25519PrivateKey, Path]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    path = tmp_path / "owner.pub.pem"
    path.write_bytes(public)
    return private, path


def _authorization(tmp_path: Path, key: Ed25519PrivateKey, name: str = "auth.json") -> Path:
    payload = {
        "kind": "install",
        "owner_approval_ref": "OWNER-CLI",
        "owner_identity_ref": "owner:cli",
        "expires_at": "2099-01-01T00:00:00+00:00",
        "nonce": uuid.uuid4().hex,
        "contacts": [
            {"email": f"{uuid.uuid4().hex}@wds-test.example", "display_name": "A"},
            {"email": f"{uuid.uuid4().hex}@wds-test.example", "display_name": "B"},
        ],
    }
    import base64 as b64

    signature = b64.b64encode(key.sign(canonical_bytes(payload))).decode("ascii")
    path = tmp_path / name
    path.write_text(json.dumps({"payload": payload, "signature": signature}), encoding="utf-8")
    return path


def _env(monkeypatch: pytest.MonkeyPatch, committed_engine: Engine, owner_key: Path | None) -> None:
    for key, value in LOCK_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv(
        "WEBDESK_DATABASE_URL", committed_engine.url.render_as_string(hide_password=False)
    )
    if owner_key is not None:
        monkeypatch.setenv("WEBDESK_OWNER_PUBLIC_KEY_PATH", str(owner_key))
    else:
        monkeypatch.delenv("WEBDESK_OWNER_PUBLIC_KEY_PATH", raising=False)


def _denials(engine: Engine, reason: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """SELECT count(*) FROM audit_events
                       WHERE event_type = 'ceremony.install.denied'
                         AND error_class LIKE :r"""
                ),
                {"r": f"{reason}%"},
            ).scalar_one()
        )


def test_a_forged_authorization_is_refused_and_the_refusal_is_audited(
    monkeypatch: pytest.MonkeyPatch,
    committed_engine: Engine,
    owner: tuple[Ed25519PrivateKey, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, public = owner
    impostor = Ed25519PrivateKey.generate()
    _env(monkeypatch, committed_engine, public)
    before = _denials(committed_engine, "signature_invalid")
    code = main(
        [
            "--authorization",
            str(_authorization(tmp_path, impostor)),
            "--operator",
            "op-cli",
            "--verifier",
            "v-cli",
        ]
    )
    assert code == 2
    assert "signature_invalid" in capsys.readouterr().err
    assert _denials(committed_engine, "signature_invalid") == before + 1


def test_a_missing_configuration_is_refused_and_the_refusal_is_audited(
    monkeypatch: pytest.MonkeyPatch,
    committed_engine: Engine,
    owner: tuple[Ed25519PrivateKey, Path],
    tmp_path: Path,
) -> None:
    private, public = owner
    _env(monkeypatch, committed_engine, public)
    monkeypatch.delenv("WEBDESK_EMAIL_DOMAIN_ALLOWLIST", raising=False)
    before = _denials(committed_engine, "configuration")
    code = main(
        [
            "--authorization",
            str(_authorization(tmp_path, private)),
            "--operator",
            "op-cli",
            "--verifier",
            "v-cli",
        ]
    )
    assert code == 2
    assert _denials(committed_engine, "configuration") == before + 1


def test_a_missing_database_url_is_refused_to_stderr_only(
    monkeypatch: pytest.MonkeyPatch,
    owner: tuple[Ed25519PrivateKey, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    private, public = owner
    for key, value in LOCK_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("WEBDESK_OWNER_PUBLIC_KEY_PATH", str(public))
    monkeypatch.delenv("WEBDESK_DATABASE_URL", raising=False)
    code = main(
        [
            "--authorization",
            str(_authorization(tmp_path, private)),
            "--operator",
            "op-cli",
            "--verifier",
            "v-cli",
        ]
    )
    assert code == 2
    assert "WEBDESK_DATABASE_URL" in capsys.readouterr().err
