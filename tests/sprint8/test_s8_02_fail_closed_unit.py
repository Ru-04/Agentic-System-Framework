"""S8-02 fail-closed checks that need no database (Sprint 8 hardening, GREEN scope).

Each test pins one refusal path of an existing Foundation contract:

- the authorization engine (``webdesk.rbac.engine``) with an in-memory store, so cross-project and
  wrong-resource-binding denials are proven without PostgreSQL;
- the operation-proof refusal vocabulary (``webdesk.authority.proofs``), where an unknown database
  refusal must not be mistaken for a named one;
- the application-side authority client (``webdesk.authority.client``), which must fail closed when
  the authority is unreachable or when it is asked to talk to a non-loopback address.

No production code is changed. The tests assert the current behaviour and do not loosen any check.
"""

from __future__ import annotations

import socket
import uuid
from dataclasses import dataclass, field

import pytest
from sqlalchemy.exc import DBAPIError

from webdesk.authority.client import AuthorityClient, AuthorityUnavailable
from webdesk.authority.proofs import REFUSAL_REASONS, refusal_reason, wrapper_refusal
from webdesk.rbac.engine import ResourceRef, authorize
from webdesk.rbac.matrix import Permission, Role

PROJECT_A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
PROJECT_B = uuid.UUID("00000000-0000-4000-8000-00000000000b")


@dataclass
class FakeStore:
    """An in-memory ``AuthorizationStore``. Anything not listed is absent (deny by default)."""

    active: bool = True
    roles: frozenset[Role] = frozenset()
    memberships: frozenset[uuid.UUID] = frozenset()
    grants: frozenset[tuple[uuid.UUID, str]] = frozenset()
    restricted: frozenset[uuid.UUID] = field(default_factory=frozenset)

    def user_is_active(self, user_id: uuid.UUID) -> bool:
        return self.active

    def active_roles(self, user_id: uuid.UUID) -> frozenset[Role]:
        return self.roles

    def has_active_membership(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return project_id in self.memberships

    def has_project_grant(self, user_id: uuid.UUID, project_id: uuid.UUID, action: str) -> bool:
        return (project_id, action) in self.grants

    def has_restricted_grant(self, user_id: uuid.UUID, resource: ResourceRef) -> bool:
        return resource.project_id in self.restricted


USER = uuid.UUID("00000000-0000-4000-8000-000000000001")


def test_an_unknown_permission_name_is_denied() -> None:
    decision = authorize(FakeStore(roles=frozenset({Role.ADMINISTRATOR})), USER, "project.delete")
    assert (decision.allowed, decision.reason) == (False, "unknown_permission")


def test_an_inactive_account_is_denied_even_with_every_role_and_membership() -> None:
    store = FakeStore(
        active=False,
        roles=frozenset({Role.ANALYST}),
        memberships=frozenset({PROJECT_A}),
    )
    decision = authorize(
        store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_A)
    )
    assert (decision.allowed, decision.reason) == (False, "user_inactive")


def test_an_account_with_no_role_is_denied() -> None:
    store = FakeStore(memberships=frozenset({PROJECT_A}))
    decision = authorize(
        store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_A)
    )
    assert (decision.allowed, decision.reason) == (False, "role_missing")


def test_a_project_resource_needs_a_resource_reference() -> None:
    store = FakeStore(roles=frozenset({Role.ANALYST}), memberships=frozenset({PROJECT_A}))
    decision = authorize(store, USER, Permission.PROJECT_VIEW.value, None)
    assert (decision.allowed, decision.reason) == (False, "resource_required")


def test_membership_in_one_project_does_not_open_another_project() -> None:
    """Cross-project read: the analyst is assigned to A and asks about B."""
    store = FakeStore(roles=frozenset({Role.ANALYST}), memberships=frozenset({PROJECT_A}))
    own = authorize(store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_A))
    other = authorize(store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_B))
    assert own.allowed is True
    assert (other.allowed, other.reason) == (False, "membership_missing")


def test_a_project_grant_for_one_project_does_not_open_another() -> None:
    """Wrong resource binding: a granted reviewer holds a grant on A, the resource is B."""
    store = FakeStore(
        roles=frozenset({Role.TECHNICAL_REVIEWER}),
        grants=frozenset({(PROJECT_A, Permission.PROJECT_VIEW.value)}),
    )
    own = authorize(store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_A))
    other = authorize(store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_B))
    assert own.allowed is True
    assert (other.allowed, other.reason) == (False, "grant_missing")


def test_a_grant_for_another_permission_does_not_satisfy_the_check() -> None:
    store = FakeStore(
        roles=frozenset({Role.TECHNICAL_REVIEWER}),
        grants=frozenset({(PROJECT_A, Permission.PROJECT_EDIT.value)}),
    )
    decision = authorize(
        store, USER, Permission.PROJECT_VIEW.value, ResourceRef(project_id=PROJECT_A)
    )
    assert (decision.allowed, decision.reason) == (False, "grant_missing")


def test_restricted_source_needs_a_restricted_grant_even_with_membership() -> None:
    store = FakeStore(roles=frozenset({Role.ANALYST}), memberships=frozenset({PROJECT_A}))
    resource = ResourceRef(project_id=PROJECT_A, data_class="restricted")
    decision = authorize(store, USER, Permission.SOURCE_READ.value, resource)
    assert (decision.allowed, decision.reason) == (
        False,
        "restricted_content_grant_missing",
    )


def test_a_restricted_grant_on_another_project_does_not_open_this_one() -> None:
    store = FakeStore(
        roles=frozenset({Role.ANALYST}),
        memberships=frozenset({PROJECT_A}),
        restricted=frozenset({PROJECT_B}),
    )
    resource = ResourceRef(project_id=PROJECT_A, data_class="restricted")
    decision = authorize(store, USER, Permission.SOURCE_READ.value, resource)
    assert decision.allowed is False


def test_an_unknown_data_class_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="unknown data class"):
        ResourceRef(project_id=PROJECT_A, data_class="public")


def test_the_refusal_vocabulary_is_the_named_set_and_has_no_duplicates() -> None:
    assert len(REFUSAL_REASONS) == len(set(REFUSAL_REASONS))
    assert {"proof_missing", "proof_spent", "proof_expired", "proof_resource_mismatch"} <= set(
        REFUSAL_REASONS
    )


def test_an_unrecognised_database_refusal_maps_to_the_neutral_reason() -> None:
    """A refusal message that names no known reason must not be guessed into one."""
    exc = DBAPIError("SELECT 1", {}, Exception("some unexpected database message"))
    assert refusal_reason(exc) == "proof_refused"


def test_a_named_database_refusal_maps_to_its_reason() -> None:
    exc = DBAPIError("SELECT 1", {}, Exception("proof_resource_mismatch: resource differs"))
    assert refusal_reason(exc) == "proof_resource_mismatch"


def test_a_business_refusal_is_read_only_from_a_p0001_error() -> None:
    class _Orig(Exception):
        sqlstate = "42501"

    exc = DBAPIError("SELECT 1", {}, _Orig("not allowed"))
    assert wrapper_refusal(exc) is None


def _closed_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_an_unreachable_authority_fails_closed_and_trusts_no_session() -> None:
    client = AuthorityClient(f"http://127.0.0.1:{_closed_loopback_port()}", "x" * 32, timeout=2.0)
    with pytest.raises(AuthorityUnavailable):
        client.issue_operation_proof("any-token", "project.create", None)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://203.0.113.10:8080",
        "https://127.0.0.1:8080",
        "http://example.com",
    ],
)
def test_the_authority_client_refuses_non_loopback_or_non_http_addresses(base_url: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        AuthorityClient(base_url, "x" * 32)
