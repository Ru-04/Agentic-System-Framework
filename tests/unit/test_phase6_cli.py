"""Phase 6 unit tests (H-50, H-51): artifact validation and CLI refusals. No database is used.

The fail-closed CLI paths are checked with the environment cleared, so no database is touched.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_install_authorization import (  # noqa: F401 - fixtures and helpers
    FixedClock,
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
    return payload


def test_recovery_artifact_without_a_verifier_is_refused(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _recovery())
    with pytest.raises(InstallationError) as exc:
        prepare_recovery(_settings(public), path, FixedClock())
    assert exc.value.reason == "authorization_malformed"


def test_recovery_artifact_supplies_the_verifier_it_names(
    tmp_path: Path,
    owner_key: tuple[Any, Path],  # noqa: F811
) -> None:
    private, public = owner_key
    path = _write(tmp_path, private, _recovery(independent_verifier_id="verifier-signed-07"))
    request = prepare_recovery(_settings(public), path, FixedClock())
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
