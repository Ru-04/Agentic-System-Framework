"""Owner-signed installation ceremony (T7; P-GATE1-BOOTSTRAP-02; EVAL-F11f, F11h).

One install approves exactly two distinct, normalized contacts. Each contact enters
``pending_activation`` through a ceremony-backed approval with a single-use Administrator
appointment. ``system:bootstrap`` grants the Administrator role to the first contact only. The
second Administrator is granted later by ordinary, audited ``role.assign`` after private
activation (T11). The ceremony is closed in the same transaction, so it cannot run again. Any
failure rolls back the whole transaction.

Authorization is an Ed25519 signature by the configured owner key over canonical JSON (sorted
keys, no whitespace, UTF-8). No signing key is stored in this repository.

Two steps keep the transaction testable: ``prepare_install`` verifies everything that needs no
database, and ``apply_install`` runs the transaction on a caller-supplied connection.
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError

from webdesk.audit.service import record_event
from webdesk.config import ConfigurationError, Settings
from webdesk.identity.email import EmailPolicyError, policy_from_settings

INSTALL_KIND = "install"
ACTIVATION_WINDOW = timedelta(hours=24)


class InstallationError(RuntimeError):
    """A refused installation. ``reason`` is a stable code for the CLI and audit."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@dataclass(frozen=True)
class PreparedInstall:
    """Everything verified before any database write."""

    owner_approval_ref: str
    owner_identity_ref: str
    authorization_digest: str
    contacts: tuple[tuple[str, str], ...]  # (normalized_email, display_name)


@dataclass(frozen=True)
class InstallResult:
    ceremony_id: uuid.UUID
    user_ids: tuple[uuid.UUID, uuid.UUID]
    approval_ids: tuple[uuid.UUID, uuid.UUID]
    bootstrap_assignment_id: uuid.UUID
    authorization_digest: str


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def load_signed_authorization(
    path: Path, owner_public_key_path: Path, clock: Clock
) -> tuple[dict[str, Any], str]:
    """Verify the owner signature and expiry; return the payload and its SHA-256 digest."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        payload = document["payload"]
        signature = base64.b64decode(document["signature"], validate=True)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise InstallationError("authorization_malformed") from exc
    if not isinstance(payload, dict):
        raise InstallationError("authorization_malformed")

    key = load_pem_public_key(owner_public_key_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ConfigurationError("owner public key must be Ed25519")
    body = canonical_bytes(payload)
    try:
        key.verify(signature, body)
    except InvalidSignature as exc:
        raise InstallationError("signature_invalid") from exc

    try:
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    except (KeyError, ValueError) as exc:
        raise InstallationError("authorization_malformed") from exc
    if expires_at.tzinfo is None or expires_at <= clock.now():
        raise InstallationError("authorization_expired")
    return payload, hashlib.sha256(body).hexdigest()


def prepare_install(settings: Settings, authorization_path: Path, clock: Clock) -> PreparedInstall:
    """Fail closed on configuration, then verify the authorization and the two contacts."""
    missing = list(settings.onboarding_capability().missing) + list(
        settings.ceremony_capability().missing
    )
    if missing:
        raise InstallationError("configuration_incomplete: " + ", ".join(missing))
    if settings.owner_public_key_path is None:  # narrowed by the capability check above
        raise InstallationError("configuration_incomplete: WEBDESK_OWNER_PUBLIC_KEY_PATH")
    policy = policy_from_settings(settings)

    payload, digest = load_signed_authorization(
        authorization_path, settings.owner_public_key_path, clock
    )
    if payload.get("kind") != INSTALL_KIND:
        raise InstallationError("authorization_kind_mismatch")
    contacts = payload.get("contacts")
    if not isinstance(contacts, list) or len(contacts) != 2:
        raise InstallationError("exactly_two_contacts_required")
    owner_ref = str(payload.get("owner_approval_ref", "")).strip()
    owner_identity = str(payload.get("owner_identity_ref", "")).strip()
    if not owner_ref or not owner_identity:
        raise InstallationError("authorization_malformed")

    normalized: list[tuple[str, str]] = []
    for contact in contacts:
        if not isinstance(contact, dict) or "email" not in contact:
            raise InstallationError("authorization_malformed")
        try:
            email = policy.normalize(str(contact["email"]))
        except EmailPolicyError as exc:
            raise InstallationError(f"contact_refused:{exc.reason}") from exc
        name = str(contact.get("display_name", "")).strip() or "WDS user"
        normalized.append((email, name))
    if normalized[0][0] == normalized[1][0]:
        raise InstallationError("contacts_not_distinct")

    return PreparedInstall(
        owner_approval_ref=owner_ref,
        owner_identity_ref=owner_identity,
        authorization_digest=digest,
        contacts=(normalized[0], normalized[1]),
    )


def apply_install(
    conn: Connection,
    prepared: PreparedInstall,
    *,
    operator_id: str,
    verifier_id: str,
    clock: Clock,
) -> InstallResult:
    """Run the installation transaction on ``conn``. The caller commits or rolls back."""
    now = clock.now()
    deadline = now + ACTIVATION_WINDOW
    try:
        conn.execute(text("SET LOCAL ROLE webdesk_ceremony"))
        conn.execute(text("SELECT pg_advisory_xact_lock(727272)"))
        if conn.execute(
            text("SELECT 1 FROM setup_trust_ceremonies WHERE kind = 'install'")
        ).first():
            raise InstallationError("install_already_closed")

        ceremony_id = uuid.UUID(
            str(
                conn.execute(
                    text(
                        """INSERT INTO setup_trust_ceremonies (kind, owner_approval_ref,
                               signed_authorization_digest, owner_identity_ref,
                               independent_verifier_id, deployment_operator_id,
                               effective_admin_count_at_start, authorized_user_ids,
                               activation_deadline, status)
                           VALUES ('install', :ref, :digest, :owner, :verifier, :operator,
                               0, '{}', :deadline, 'initiated')
                           RETURNING ceremony_id"""
                    ),
                    {
                        "ref": prepared.owner_approval_ref,
                        "digest": prepared.authorization_digest,
                        "owner": prepared.owner_identity_ref,
                        "verifier": verifier_id,
                        "operator": operator_id,
                        "deadline": deadline,
                    },
                ).scalar_one()
            )
        )

        user_ids: list[uuid.UUID] = []
        approval_ids: list[uuid.UUID] = []
        for email, name in prepared.contacts:
            user_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO users (display_name, email, normalized_email, status)
                               VALUES (:name, :email, :email, 'pending_contact_approval')
                               RETURNING user_id"""
                        ),
                        {"name": name, "email": email},
                    ).scalar_one()
                )
            )
            conn.execute(
                text(
                    """INSERT INTO contact_reservations (normalized_email, user_id)
                       VALUES (:email, :user)"""
                ),
                {"email": email, "user": user_id},
            )
            approval_id = uuid.UUID(
                str(
                    conn.execute(
                        text(
                            """INSERT INTO user_contact_approvals (user_id, request_type,
                                   requested_email_normalized, ceremony_id, status,
                                   expires_at, approved_at, administrator_appointment)
                               VALUES (:user, 'create', :email, :ceremony, 'approved',
                                   :deadline, :now, true)
                               RETURNING approval_id"""
                        ),
                        {
                            "user": user_id,
                            "email": email,
                            "ceremony": ceremony_id,
                            "deadline": deadline,
                            "now": now,
                        },
                    ).scalar_one()
                )
            )
            # The contact transition is accepted only with the matching approval (trigger).
            conn.execute(
                text("UPDATE users SET status = 'pending_activation' WHERE user_id = :u"),
                {"u": user_id},
            )
            user_ids.append(user_id)
            approval_ids.append(approval_id)

        assignment_id = uuid.UUID(
            str(
                conn.execute(
                    text(
                        """INSERT INTO role_assignments (user_id, role, assigned_by_system,
                               appointment_approval_id)
                           VALUES (:user, 'Administrator', 'system:bootstrap', :approval)
                           RETURNING assignment_id"""
                    ),
                    {"user": user_ids[0], "approval": approval_ids[0]},
                ).scalar_one()
            )
        )

        conn.execute(
            text(
                """UPDATE setup_trust_ceremonies
                   SET authorized_user_ids = CAST(:users AS uuid[]),
                       effective_admin_count_at_start = 0,
                       status = 'closed', completed_at = :now, closed_at = :now
                   WHERE ceremony_id = :ceremony"""
            ),
            {"users": [str(u) for u in user_ids], "now": now, "ceremony": ceremony_id},
        )
        record_event(
            conn,
            actor_type="ceremony",
            actor_id=operator_id,
            event_type="ceremony.install.completed",
            outcome="success",
            record_refs=[str(ceremony_id), *map(str, user_ids), str(assignment_id)],
            configuration_versions={"ceremony": "install-v1"},
            details={"verifier": verifier_id, "authorization": prepared.authorization_digest},
        )
    except InstallationError:
        raise
    except SQLAlchemyError as exc:
        # Reserved contacts, a second install, existing Administrators and any other trigger
        # refusal surface here. The caller's transaction rolls back, so nothing is partial.
        raise InstallationError("database_refused") from exc

    return InstallResult(
        ceremony_id=ceremony_id,
        user_ids=(user_ids[0], user_ids[1]),
        approval_ids=(approval_ids[0], approval_ids[1]),
        bootstrap_assignment_id=assignment_id,
        authorization_digest=prepared.authorization_digest,
    )


def run_install(
    engine: Engine,
    settings: Settings,
    authorization_path: Path,
    *,
    operator_id: str,
    verifier_id: str,
    clock: Clock,
) -> InstallResult:
    """Verify, then run the one-time installation as a single all-or-nothing transaction."""
    prepared = prepare_install(settings, authorization_path, clock)
    with engine.begin() as conn:
        return apply_install(
            conn, prepared, operator_id=operator_id, verifier_id=verifier_id, clock=clock
        )
