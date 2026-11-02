"""Phase 6 unit tests (H-50, H-51): artifact validation and CLI refusals. No database is used.

The fail-closed CLI paths are checked with the environment cleared, so no database is touched.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_install_authorization import (  # noqa: F401 - fixtures and helpers
    OPERATOR,
    _payload,
    _settings,
    _write,
    owner_key,
)
from webdesk.ceremony.install import InstallationError
from webdesk.ceremony.recovery import prepare_recovery
from webdesk.cli import outbox as outbox_cli
from webdesk.cli import recover as recover_cli
from webdesk.cli import sweep as sweep_cli


def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("WEBDESK_"):
            monkeypatch.delenv(key, raising=False)


def _recovery(**overrides: Any) -> dict[str, Any]:
    payload = _payload(
        kind="recover",
        request_type="appointment",
        contact={"email": "ada@wds-test.example", "display_name": "Ada"},
        contacts=[],
        **overrides,
    )
    # A recovery artifact names its own verifier (H-50): none unless the test supplies one.
    if "independent_verifier_id" not in overrides:
        del payload["independent_verifier_id"]
    return payload


def test_recovery_artifact_without_a_verifier_is_refused(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _recovery())
    with pytest.raises(InstallationError) as exc:
        prepare_recovery(_settings(public), path, operator_id=OPERATOR)
    assert exc.value.reason == "authorization_malformed"


def test_recovery_artifact_supplies_the_verifier_it_names(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _recovery(independent_verifier_id="verifier-signed-07"))
    request = prepare_recovery(_settings(public), path, operator_id=OPERATOR)
    assert request.verifier_id == "verifier-signed-07"
    assert request.email == "ada@wds-test.example"


def test_recovery_cli_refuses_without_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clean_env(monkeypatch)
    path = tmp_path / "unused.json"
    assert recover_cli.main(["--authorization", str(path), "--operator", "op"]) == 2


def test_sweep_cli_refuses_without_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    assert sweep_cli.main([]) == 2


def test_outbox_cli_refuses_without_a_transport_or_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clean_env(monkeypatch)
    assert outbox_cli.main([]) == 2


def test_outbox_cli_rejects_a_non_positive_limit() -> None:
    assert outbox_cli.main(["--limit", "0"]) == 2


def test_a_malformed_owner_key_is_a_refusal_not_a_traceback(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _recovery(independent_verifier_id="verifier-signed-q1"))
    public.write_bytes(b"this is not a PEM public key")
    with pytest.raises(InstallationError) as exc:
        prepare_recovery(_settings(public), path, operator_id=OPERATOR)
    assert exc.value.reason == "owner_key_invalid"


def test_a_permission_denial_is_a_refusal_and_an_outage_is_status_three() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    from webdesk.cli.diagnostics import database_refusal

    class _Orig:
        sqlstate = "42501"

    denied = SQLAlchemyError("permission denied")
    denied.orig = _Orig()  # type: ignore[attr-defined]
    assert database_refusal(denied) == ("refused: insufficient_privilege", 2)

    outage = SQLAlchemyError("connection refused")
    assert database_refusal(outage) == ("refused: database_unavailable", 3)


def test_the_outbox_cli_refuses_production_with_a_capture_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBDESK_ENV", "production")
    monkeypatch.setenv("WEBDESK_DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/none")
    monkeypatch.setenv("WEBDESK_EMAIL_TRANSPORT", "capture")
    monkeypatch.setenv("WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD", "5")
    monkeypatch.setenv(
        "WEBDESK_OUTBOX_ENCRYPTION_KEY", "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE="
    )
    assert outbox_cli.main([]) == 2


def test_h74_a_recovery_artifact_without_a_signed_operator_is_refused(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    payload = _recovery(independent_verifier_id="verifier-signed-h74")
    del payload["deployment_operator_id"]
    path = _write(tmp_path, private, payload)
    with pytest.raises(InstallationError) as exc:
        prepare_recovery(_settings(public), path, operator_id=OPERATOR)
    assert exc.value.reason == "authorization_malformed"


def test_h74_the_recovery_cli_operator_must_match_the_signed_operator(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _recovery(independent_verifier_id="verifier-signed-h74"))
    with pytest.raises(InstallationError) as exc:
        prepare_recovery(_settings(public), path, operator_id="op-other")
    assert exc.value.reason == "operator_mismatch"
