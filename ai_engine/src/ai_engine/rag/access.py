"""Collection and project authorisation for retrieval (default deny).

Authorisation happens before any search (SVC-EVIDENCE-RETRIEVAL: enforce_access_before_search). A
collection is readable only when all three hold:
1. WDS has supplied a CollectionApproval for that collection and that project.
2. The access port grants the actor read access to that collection in that project.
3. The collection's approval is for the request's project, not another project.

The access port is a seam. Foundation owns user permissions and will supply the real port. The
engine ships
only a static port, used by tests, that is empty by default. Nothing here grants access by default.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from ai_engine.rag.contracts import CollectionApproval, CollectionScope


class AccessPort(Protocol):
    """Foundation-owned permission check. The engine asks; it never decides who a user is."""

    def actor_may_read(self, *, actor_id: str, project_id: str, collection_id: str) -> bool: ...


@dataclass(frozen=True)
class StaticAccessPort:
    """Explicit grants for tests. An empty port denies everything."""

    grants: frozenset[tuple[str, str, str]] = field(default_factory=frozenset)

    @classmethod
    def granting(cls, grants: Iterable[tuple[str, str, str]]) -> StaticAccessPort:
        return cls(frozenset(grants))

    def actor_may_read(self, *, actor_id: str, project_id: str, collection_id: str) -> bool:
        return (actor_id, project_id, collection_id) in self.grants


class CollectionRegistry:
    """WDS approvals keyed by collection. Holds no default and fails closed."""

    def __init__(self, approvals: Iterable[CollectionApproval] = ()) -> None:
        self._by_collection: dict[str, CollectionApproval] = {}
        for approval in approvals:
            if approval.collection_id in self._by_collection:
                raise ValueError(f"duplicate approval for {approval.collection_id}")
            self._by_collection[approval.collection_id] = approval

    def approval_for(self, collection_id: str, project_id: str) -> CollectionApproval | None:
        approval = self._by_collection.get(collection_id)
        if approval is None or approval.project_id != project_id:
            return None
        return approval

    def approval_for_other_project(self, collection_id: str, project_id: str) -> bool:
        approval = self._by_collection.get(collection_id)
        return approval is not None and approval.project_id != project_id

    def scope_of(self, collection_id: str) -> CollectionScope | None:
        approval = self._by_collection.get(collection_id)
        return None if approval is None else approval.scope


@dataclass(frozen=True)
class CollectionDecision:
    allowed: tuple[str, ...]
    denied: tuple[str, ...]
    cross_project: tuple[str, ...]


def decide_collections(
    *,
    registry: CollectionRegistry,
    access: AccessPort,
    actor_id: str,
    project_id: str,
    collections: Iterable[str],
) -> CollectionDecision:
    """Split requested collections into allowed, denied and cross-project. Default deny."""
    allowed: list[str] = []
    denied: list[str] = []
    cross_project: list[str] = []
    for collection_id in collections:
        if registry.approval_for(collection_id, project_id) is None:
            if registry.approval_for_other_project(collection_id, project_id):
                cross_project.append(collection_id)
            else:
                denied.append(collection_id)
            continue
        # Strict check: only a real True grants access. Any other response, including a truthy
        # value, is denied, so a faulty port cannot open a collection.
        if (
            access.actor_may_read(
                actor_id=actor_id, project_id=project_id, collection_id=collection_id
            )
            is True
        ):
            allowed.append(collection_id)
        else:
            denied.append(collection_id)
    return CollectionDecision(tuple(allowed), tuple(denied), tuple(cross_project))


class ExternalDomainAllowlist:
    """Approved external domains. Empty by default, so every external domain is refused.

    AI-S03 has no live vendor research. This class exists so the refusal is tested and explicit.
    Adding a
    domain is a WDS decision and is not part of AI-S03.
    """

    def __init__(self, domains: Mapping[str, str] | None = None) -> None:
        self._domains: dict[str, str] = dict(domains or {})

    def permits(self, host: str) -> bool:
        return host.lower() in self._domains
