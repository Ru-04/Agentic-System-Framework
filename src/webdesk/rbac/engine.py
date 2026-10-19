"""Server-side, deny-by-default authorization (GOVERNANCE §11, C-3; EVAL-F01).

The engine decides; it does not write audit events. Callers record every denial (T4).
Store lookups are behind a protocol so the rules are tested without a database, and the SQL
implementation in ``sql_store`` is tested against PostgreSQL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from webdesk.rbac.matrix import MATRIX, Permission, Role, Rule

DATA_CLASSES = ("internal", "confidential_client", "restricted")


@dataclass(frozen=True)
class ResourceRef:
    """The project-scoped resource an action targets. ``data_class`` is the resource class."""

    project_id: uuid.UUID
    data_class: str = "internal"
    source_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if self.data_class not in DATA_CLASSES:
            raise ValueError(f"unknown data class: {self.data_class!r}")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


class AuthorizationStore(Protocol):
    def user_is_active(self, user_id: uuid.UUID) -> bool: ...

    def active_roles(self, user_id: uuid.UUID) -> frozenset[Role]: ...

    def has_active_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool: ...

    def has_project_grant(self, user_id: uuid.UUID, project_id: uuid.UUID, action: str) -> bool: ...

    def has_restricted_grant(self, user_id: uuid.UUID, resource: ResourceRef) -> bool: ...


def _content_allowed(store: AuthorizationStore, user: uuid.UUID, resource: ResourceRef) -> bool:
    """Restricted bytes need a RestrictedContentGrant. Other bytes accept one, or a scoped
    ProjectAccessGrant carrying source.read (C-3)."""
    if store.has_restricted_grant(user, resource):
        return True
    if resource.data_class == "restricted":
        return False
    return store.has_project_grant(user, resource.project_id, Permission.SOURCE_READ.value)


def _evaluate_rule(
    store: AuthorizationStore,
    user: uuid.UUID,
    permission: Permission,
    rule: Rule,
    resource: ResourceRef | None,
) -> Decision:
    if rule is Rule.DENY:
        return Decision(False, "denied_by_policy")
    if rule is Rule.ROLE or rule is Rule.ADMIN_METADATA:
        return Decision(True, "allowed")

    if resource is None:
        return Decision(False, "resource_required")

    if rule in (Rule.ASSIGNED, Rule.ASSIGNED_CLASSIFIED):
        if not store.has_active_membership(user, resource.project_id):
            return Decision(False, "membership_missing")
    if rule in (Rule.GRANTED, Rule.GRANTED_CLASSIFIED):
        if not store.has_project_grant(user, resource.project_id, permission.value):
            return Decision(False, "grant_missing")
    if rule in (Rule.ASSIGNED_CLASSIFIED, Rule.GRANTED_CLASSIFIED):
        if resource.data_class == "restricted" and not store.has_restricted_grant(user, resource):
            return Decision(False, "restricted_content_grant_missing")
        return Decision(True, "allowed")
    if rule is Rule.ADMIN_CONTENT:
        if not _content_allowed(store, user, resource):
            return Decision(False, "content_grant_missing")
        return Decision(True, "allowed")
    return Decision(True, "allowed")


def authorize(
    store: AuthorizationStore,
    user_id: uuid.UUID,
    permission: str,
    resource: ResourceRef | None = None,
) -> Decision:
    """Return whether ``user_id`` may perform ``permission``. Deny by default."""
    try:
        key = Permission(permission)
    except ValueError:
        return Decision(False, "unknown_permission")

    if not store.user_is_active(user_id):
        return Decision(False, "user_inactive")

    cells = MATRIX.get(key, {})
    if not cells:
        # Disabled in Gate 1 or later-phase: no role is permitted, whatever is granted.
        return Decision(False, "denied_by_policy")
    held = store.active_roles(user_id)
    last_reason = "role_missing"
    for role in sorted(held, key=lambda r: r.value):
        rule = cells.get(role)
        if rule is None:
            continue
        decision = _evaluate_rule(store, user_id, key, rule, resource)
        if decision.allowed:
            return decision
        last_reason = decision.reason
    if not held or not any(role in cells for role in held):
        return Decision(False, "role_missing")
    return Decision(False, last_reason)
