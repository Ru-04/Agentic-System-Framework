"""T6 unit tests: deny-by-default RBAC rules from GOVERNANCE §11 (EVAL-F01, C-1, C-3).

An in-memory store stands in for the database so each rule is tested exactly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import MATRIX, Permission, Role


@dataclass
class FakeStore:
    active: bool = True
    roles: set[Role] = field(default_factory=set)
    memberships: set[uuid.UUID] = field(default_factory=set)
    project_grants: set[tuple[uuid.UUID, str]] = field(default_factory=set)
    restricted: set[uuid.UUID] = field(default_factory=set)

    def user_is_active(self, user_id: uuid.UUID) -> bool:
        return self.active

    def active_roles(self, user_id: uuid.UUID) -> frozenset[Role]:
        return frozenset(self.roles)

    def has_active_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return project_id in self.memberships

    def has_project_grant(self, user_id: uuid.UUID, project_id: uuid.UUID, action: str) -> bool:
        return (project_id, action) in self.project_grants

    def has_restricted_grant(self, user_id: uuid.UUID, resource: ResourceRef) -> bool:
        return resource.project_id in self.restricted


USER = uuid.uuid4()
PROJECT = uuid.uuid4()
PROJECT_RES = ResourceRef(project_id=PROJECT, data_class="confidential_client")
RESTRICTED_RES = ResourceRef(project_id=PROJECT, data_class="restricted")


def test_every_matrix_key_is_a_known_permission() -> None:
    assert set(MATRIX) == set(Permission)


def test_unknown_permission_is_denied() -> None:
    decision = authorize(FakeStore(roles={Role.ADMINISTRATOR}), USER, "run.delete_all")
    assert not decision.allowed
    assert decision.reason == "unknown_permission"


def test_inactive_user_is_denied_everything() -> None:
    store = FakeStore(active=False, roles={Role.ADMINISTRATOR})
    decision = authorize(store, USER, Permission.PROJECT_ARCHIVE.value)
    assert not decision.allowed
    assert decision.reason == "user_inactive"


@pytest.mark.parametrize("permission", list(Permission))
def test_no_roles_means_denied(permission: Permission) -> None:
    decision = authorize(FakeStore(), USER, permission.value, PROJECT_RES)
    assert not decision.allowed


def test_administrator_alone_cannot_start_a_run() -> None:
    store = FakeStore(roles={Role.ADMINISTRATOR}, memberships={PROJECT})
    decision = authorize(store, USER, Permission.RUN_START.value, PROJECT_RES)
    assert not decision.allowed
    assert decision.reason == "role_missing"


def test_analyst_with_membership_can_start_a_run_but_not_without() -> None:
    assigned = FakeStore(roles={Role.ANALYST}, memberships={PROJECT})
    assert authorize(assigned, USER, Permission.RUN_START.value, PROJECT_RES).allowed
    unassigned = FakeStore(roles={Role.ANALYST})
    decision = authorize(unassigned, USER, Permission.RUN_START.value, PROJECT_RES)
    assert decision.reason == "membership_missing"


def test_administrator_with_separate_analyst_role_and_membership_can_start_a_run() -> None:
    store = FakeStore(roles={Role.ADMINISTRATOR, Role.ANALYST}, memberships={PROJECT})
    assert authorize(store, USER, Permission.RUN_START.value, PROJECT_RES).allowed


@pytest.mark.parametrize(
    "permission",
    [
        Permission.RUN_CANCEL,
        Permission.RUN_RETRY,
        Permission.RUN_RESUME,
        Permission.USER_MANAGE,
        Permission.USER_APPROVE,
        Permission.USER_WITHDRAW,
        Permission.ROLE_ASSIGN,
        Permission.MEMBERSHIP_MANAGE,
        Permission.PROJECT_GRANT_MANAGE,
        Permission.RESTRICTED_GRANT_MANAGE,
        Permission.PROJECT_ARCHIVE,
        Permission.CLASSIFICATION_REASSESS,
    ],
)
def test_administrator_only_actions_are_denied_to_other_roles(permission: Permission) -> None:
    store = FakeStore(
        roles={Role.ANALYST, Role.TECHNICAL_REVIEWER, Role.APPROVER}, memberships={PROJECT}
    )
    assert not authorize(store, USER, permission.value, PROJECT_RES).allowed
    admin = FakeStore(roles={Role.ADMINISTRATOR})
    assert authorize(admin, USER, permission.value, PROJECT_RES).allowed


@pytest.mark.parametrize(
    "permission",
    [Permission.DELETION_REQUEST, Permission.DELETION_AUTHORIZE, Permission.SOW_APPROVE],
)
def test_disabled_and_later_phase_actions_are_denied_to_everyone(permission: Permission) -> None:
    everyone = FakeStore(
        roles=set(Role), memberships={PROJECT}, project_grants={(PROJECT, permission.value)}
    )
    decision = authorize(everyone, USER, permission.value, PROJECT_RES)
    assert decision.reason == "denied_by_policy"


def test_administrator_cannot_read_source_bytes_without_a_content_grant() -> None:
    store = FakeStore(roles={Role.ADMINISTRATOR})
    decision = authorize(store, USER, Permission.SOURCE_READ.value, PROJECT_RES)
    assert decision.reason == "content_grant_missing"


def test_administrator_reads_source_bytes_with_scoped_project_grant_for_non_restricted() -> None:
    store = FakeStore(roles={Role.ADMINISTRATOR}, project_grants={(PROJECT, "source.read")})
    assert authorize(store, USER, Permission.SOURCE_READ.value, PROJECT_RES).allowed


def test_administrator_project_metadata_does_not_grant_restricted_bytes() -> None:
    store = FakeStore(roles={Role.ADMINISTRATOR}, project_grants={(PROJECT, "source.read")})
    decision = authorize(store, USER, Permission.SOURCE_READ.value, RESTRICTED_RES)
    assert decision.reason == "content_grant_missing"


def test_administrator_reads_restricted_bytes_with_restricted_grant() -> None:
    store = FakeStore(roles={Role.ADMINISTRATOR}, restricted={PROJECT})
    assert authorize(store, USER, Permission.SOURCE_READ.value, RESTRICTED_RES).allowed


def test_analyst_needs_membership_and_restricted_grant_for_restricted_bytes() -> None:
    no_grant = FakeStore(roles={Role.ANALYST}, memberships={PROJECT})
    assert (
        authorize(no_grant, USER, Permission.SOURCE_READ.value, RESTRICTED_RES).reason
        == "restricted_content_grant_missing"
    )
    granted = FakeStore(roles={Role.ANALYST}, memberships={PROJECT}, restricted={PROJECT})
    assert authorize(granted, USER, Permission.SOURCE_READ.value, RESTRICTED_RES).allowed


def test_reviewer_needs_role_and_project_grant_not_membership() -> None:
    no_grant = FakeStore(roles={Role.TECHNICAL_REVIEWER})
    assert (
        authorize(no_grant, USER, Permission.REQUIREMENT_VIEW.value, PROJECT_RES).reason
        == "grant_missing"
    )
    granted = FakeStore(
        roles={Role.TECHNICAL_REVIEWER},
        project_grants={(PROJECT, Permission.REQUIREMENT_VIEW.value)},
    )
    assert authorize(granted, USER, Permission.REQUIREMENT_VIEW.value, PROJECT_RES).allowed


def test_project_scoped_action_without_resource_is_refused() -> None:
    store = FakeStore(roles={Role.ANALYST}, memberships={PROJECT})
    assert authorize(store, USER, Permission.PROJECT_EDIT.value, None).reason == "resource_required"


def test_invalid_data_class_is_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="data class"):
        ResourceRef(project_id=PROJECT, data_class="public")
