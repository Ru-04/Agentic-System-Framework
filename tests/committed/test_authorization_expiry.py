"""Signed-authorization expiry is decided by the database clock (Phase 3, D-3).

The owner-signed installation and recovery authorizations carry an ``expires_at``. The application
may read it, but
the decision is taken inside the database transaction, against ``clock_timestamp()``. These tests
build real signed
files, so the signature path is exercised, and they compare the outcome with the database's own
time.

Boundary cases use a margin of 30 seconds (well above the time one transaction takes) so they do not
depend on
scheduling. The application clock is never used to grant or refuse.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from tests.support.ceremony_time import FAR_FUTURE
from webdesk.api.transactions import run_in_transaction
from webdesk.ceremony.dbclock import database_now
from webdesk.ceremony.install import (
    InstallationError,
    apply_install,
    canonical_bytes,
    prepare_install,
)
from webdesk.ceremony.recovery import RecoveryError, RecoveryRequest, apply_recovery
from webdesk.cli.install import run_install_audited
from webdesk.config import Settings

pytestmark = pytest.mark.integration

OPERATOR = "op-1"
VERIFIER = "v-1"


@pytest.fixture
def owner(tmp_path: Path) -> tuple[Ed25519PrivateKey, Path]:
    private = Ed25519PrivateKey.generate()
    public = tmp_path / "owner.pub.pem"
    public.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return private, public


def _settings(public: Path) -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        email_domain_allowlist="wds-test.example",
        email_alias_denylist="admin,root",
        email_transport="capture",
        rl_login_failures_per_account_ip=5,
        rl_login_window_minutes=15,
        rl_ip_requests_per_window=100,
        rl_contact_actions_per_window=5,
        rl_contact_ip_requests_per_window=100,
        rl_window_minutes=15,
        outbox_dead_letter_threshold=5,
        outbox_encryption_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",  # test only
        owner_public_key_path=public,
    )


def _signed(tmp_path: Path, key: Ed25519PrivateKey, expires_at: datetime) -> Path:
    payload: dict[str, Any] = {
        "kind": "install",
        "owner_approval_ref": f"OWNER-{uuid.uuid4().hex[:8]}",
        "owner_identity_ref": "owner:wds-sign-off",
        "expires_at": expires_at.isoformat(),
        "nonce": uuid.uuid4().hex,
        # Phase 7 H-74: the owner signs the operator and the verifier; the CLI values must match.
        "deployment_operator_id": OPERATOR,
        "independent_verifier_id": VERIFIER,
        "contacts": [
            {"email": f"{uuid.uuid4().hex}@wds-test.example", "display_name": "Ada"},
            {"email": f"{uuid.uuid4().hex}@wds-test.example", "display_name": "Grace"},
        ],
    }
    signature = base64.b64encode(key.sign(canonical_bytes(payload))).decode("ascii")
    path = tmp_path / f"authorization-{uuid.uuid4().hex[:6]}.json"
    path.write_text(json.dumps({"payload": payload, "signature": signature}), encoding="utf-8")
    return path


def _db_now(engine: Engine) -> datetime:
    with engine.connect() as conn:
        return database_now(conn)


def _ceremonies(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT count(*) FROM setup_trust_ceremonies")).scalar_one())


def _denials(engine: Engine, event: str, reason: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    """SELECT count(*) FROM audit_events
                       WHERE event_type = :e AND outcome = 'denied' AND error_class = :r"""
                ),
                {"e": event, "r": reason},
            ).scalar_one()
        )


# --- Boundary behaviour, decided by the database clock -------------------------------------------


def test_an_authorization_the_database_clock_has_not_reached_installs(
    committed_engine: Engine, owner: tuple[Ed25519PrivateKey, Path], tmp_path: Path
) -> None:
    key, public = owner
    expires = _db_now(committed_engine) + timedelta(seconds=30)
    prepared = prepare_install(
        _settings(public),
        _signed(tmp_path, key, expires),
        operator_id=OPERATOR,
        verifier_id=VERIFIER,
    )
    assert prepared.authorization_expires_at == expires
    with committed_engine.begin() as conn:
        apply_install(conn, prepared, operator_id="op-1", verifier_id="v-1")
    assert _ceremonies(committed_engine) == 1


def test_an_authorization_the_database_clock_has_passed_is_refused_and_audited(
    committed_engine: Engine, owner: tuple[Ed25519PrivateKey, Path], tmp_path: Path
) -> None:
    key, public = owner
    expired = _db_now(committed_engine) - timedelta(seconds=30)
    path = _signed(tmp_path, key, expired)
    with pytest.raises(InstallationError) as exc:
        run_install_audited(
            committed_engine, _settings(public), path, operator_id="op-1", verifier_id="v-1"
        )
    assert exc.value.reason == "authorization_expired"
    assert _ceremonies(committed_engine) == 0
    assert _denials(committed_engine, "ceremony.install.denied", "authorization_expired") == 1


# --- Clock skew: an application clock grants nothing and refuses nothing -------------------------


def test_an_application_clock_that_says_valid_cannot_grant_a_database_expired_authorization(
    committed_engine: Engine, owner: tuple[Ed25519PrivateKey, Path], tmp_path: Path
) -> None:
    """Preparation reads the signed expiry only. A signed expiry far in the past is accepted at
    preparation (no application decision), and the database refuses it at the transaction."""
    key, public = owner
    long_ago = datetime(2000, 1, 1, tzinfo=UTC)
    prepared = prepare_install(
        _settings(public),
        _signed(tmp_path, key, long_ago),
        operator_id=OPERATOR,
        verifier_id=VERIFIER,
    )
    assert prepared.authorization_expires_at == long_ago
    with pytest.raises(InstallationError) as exc:
        with committed_engine.begin() as conn:
            apply_install(conn, prepared, operator_id="op-1", verifier_id="v-1")
    assert exc.value.reason == "authorization_expired"
    assert _ceremonies(committed_engine) == 0


def test_a_far_future_authorization_is_decided_by_the_database_and_installs(
    committed_engine: Engine, owner: tuple[Ed25519PrivateKey, Path], tmp_path: Path
) -> None:
    key, public = owner
    prepared = prepare_install(
        _settings(public),
        _signed(tmp_path, key, FAR_FUTURE),
        operator_id=OPERATOR,
        verifier_id=VERIFIER,
    )
    with committed_engine.begin() as conn:
        apply_install(conn, prepared, operator_id="op-1", verifier_id="v-1")
    assert _ceremonies(committed_engine) == 1


# --- Database availability: fail closed, no partial state ----------------------------------------


def test_database_unavailable_fails_closed_without_a_ceremony(
    committed_engine: Engine, owner: tuple[Ed25519PrivateKey, Path], tmp_path: Path
) -> None:
    key, public = owner
    path = _signed(tmp_path, key, FAR_FUTURE)
    unreachable = create_engine(
        committed_engine.url.set(port=1).render_as_string(hide_password=False),
        connect_args={"connect_timeout": 2},
    )
    with pytest.raises(SQLAlchemyError):
        run_install_audited(
            unreachable, _settings(public), path, operator_id="op-1", verifier_id="v-1"
        )
    unreachable.dispose()
    assert _ceremonies(committed_engine) == 0


# --- Recovery: the same database decision, with the refusal audited ------------------------------


def test_an_expired_recovery_authorization_is_refused_with_a_denial_record(
    committed_admins: tuple[uuid.UUID, uuid.UUID], committed_engine: Engine
) -> None:
    expired = _db_now(committed_engine) - timedelta(seconds=30)
    request = RecoveryRequest(
        authorization_expires_at=expired,
        request_type="replacement",
        email=f"{uuid.uuid4().hex}@wds-test.example",
        display_name="Replacement",
        owner_approval_ref="OWNER-RECOVERY-1",
        owner_identity_ref="owner:wds-sign-off",
        verifier_id="v-recovery",
        authorization_digest="r" * 64,
    )
    with pytest.raises(RecoveryError) as exc:
        run_in_transaction(
            committed_engine,
            lambda conn: apply_recovery(conn, request, operator_id="op-recovery"),
        )
    assert (exc.value.status, exc.value.reason) == (409, "authorization_expired")
    assert _denials(committed_engine, "ceremony.recover.denied", "authorization_expired") == 1
