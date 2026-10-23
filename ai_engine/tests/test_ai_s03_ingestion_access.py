"""AI-S03 access and ingestion tests: default deny, per-project approval, refused ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from ai_s03_support import (
    COLLECTION_A,
    COLLECTION_C,
    CORPUS_PATH,
    PROJECT_A,
    PROJECT_B,
    UNAPPROVED,
    approvals,
    corpus_payload,
    load_corpus,
)

from ai_engine.rag.access import (
    CollectionRegistry,
    ExternalDomainAllowlist,
    StaticAccessPort,
    decide_collections,
)
from ai_engine.rag.contracts import CollectionApproval, CollectionScope
from ai_engine.rag.ingestion import (
    DocumentStore,
    SyntheticFixtureSource,
    ingest,
)

ACTOR = "ACT-SYN-1"


def test_empty_registry_denies_every_collection() -> None:
    decision = decide_collections(
        registry=CollectionRegistry(),
        access=StaticAccessPort.granting([(ACTOR, PROJECT_A, COLLECTION_A)]),
        actor_id=ACTOR,
        project_id=PROJECT_A,
        collections=[COLLECTION_A],
    )
    assert decision.allowed == ()
    assert decision.denied == (COLLECTION_A,)


def test_empty_access_port_denies_an_approved_collection() -> None:
    decision = decide_collections(
        registry=CollectionRegistry(approvals()),
        access=StaticAccessPort(),
        actor_id=ACTOR,
        project_id=PROJECT_A,
        collections=[COLLECTION_A],
    )
    assert decision.allowed == ()
    assert decision.denied == (COLLECTION_A,)


def test_grant_is_per_actor_project_and_collection() -> None:
    registry = CollectionRegistry(approvals())
    access = StaticAccessPort.granting([(ACTOR, PROJECT_A, COLLECTION_A)])
    granted = decide_collections(
        registry=registry,
        access=access,
        actor_id=ACTOR,
        project_id=PROJECT_A,
        collections=[COLLECTION_A],
    )
    other_actor = decide_collections(
        registry=registry,
        access=access,
        actor_id="ACT-SYN-2",
        project_id=PROJECT_A,
        collections=[COLLECTION_A],
    )
    assert granted.allowed == (COLLECTION_A,)
    assert other_actor.allowed == ()


def test_collection_approved_for_another_project_is_a_cross_project_refusal() -> None:
    decision = decide_collections(
        registry=CollectionRegistry(approvals()),
        access=StaticAccessPort.granting([(ACTOR, PROJECT_B, COLLECTION_A)]),
        actor_id=ACTOR,
        project_id=PROJECT_B,
        collections=[COLLECTION_A],
    )
    assert decision.allowed == ()
    assert decision.cross_project == (COLLECTION_A,)


def test_unapproved_collection_is_denied_not_guessed() -> None:
    decision = decide_collections(
        registry=CollectionRegistry(approvals()),
        access=StaticAccessPort.granting([(ACTOR, PROJECT_A, UNAPPROVED)]),
        actor_id=ACTOR,
        project_id=PROJECT_A,
        collections=[UNAPPROVED],
    )
    assert decision.allowed == ()
    assert decision.denied == (UNAPPROVED,)


def test_duplicate_approval_is_refused() -> None:
    first = approvals()[0]
    with pytest.raises(ValueError, match="duplicate approval"):
        CollectionRegistry([first, first])


def test_approval_requires_a_reference_and_a_known_scope() -> None:
    with pytest.raises(ValueError):
        CollectionApproval(
            collection_id=COLLECTION_A,
            project_id=PROJECT_A,
            scope=CollectionScope.SYNTHETIC_TEST,
            approval_reference="",
        )
    with pytest.raises(ValueError):
        CollectionApproval(
            collection_id=COLLECTION_A,
            project_id=PROJECT_A,
            # The next argument is deliberately invalid: the scope must be refused.
            scope="live_vendor",  # type: ignore[arg-type]
            approval_reference="x",
        )


def test_external_domain_allowlist_is_empty_and_refuses_everything() -> None:
    allowlist = ExternalDomainAllowlist()
    for host in ("vendor.example.com", "shopify.dev", "localhost"):
        assert allowlist.permits(host) is False


def test_external_domain_allowlist_permits_only_listed_hosts() -> None:
    allowlist = ExternalDomainAllowlist({"approved.example.com": "WDS-DECISION-1"})
    assert allowlist.permits("APPROVED.example.com") is True
    assert allowlist.permits("other.example.com") is False


# --- Ingestion -------------------------------------------------------------------------------


def test_synthetic_corpus_ingests_all_valid_documents_and_refuses_the_rest() -> None:
    corpus = load_corpus()
    refused = {r.index: r.reason for r in corpus.report.refused}
    assert len(corpus.report.accepted) == 8
    assert set(refused) == {8, 9}
    assert refused[8].startswith("invalid metadata")
    assert refused[9] == "collection is not approved for this project"


def test_fixture_without_synthetic_flag_is_refused(tmp_path: Path) -> None:
    payload = corpus_payload()
    payload["synthetic"] = False
    path = tmp_path / "real.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="synthetic"):
        SyntheticFixtureSource(path)


def test_fixture_without_documents_list_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"synthetic": True, "documents": "nope"}), encoding="utf-8")
    with pytest.raises(ValueError, match="list of objects"):
        SyntheticFixtureSource(path)


def test_fixture_source_reads_the_committed_corpus() -> None:
    source = SyntheticFixtureSource(CORPUS_PATH)
    assert len(source.documents()) == 10


def _raw(**overrides: Any) -> dict[str, Any]:
    text = "Synthetic ingestion check: a valid note for the collection."
    import hashlib

    base: dict[str, Any] = {
        "document_id": "DOC-SYN-ING-01",
        "collection_id": COLLECTION_A,
        "project_id": PROJECT_A,
        "source_id": "SRC-SYN-ING-01",
        "kind": "synthetic_test",
        "title": "Ingestion check",
        "version": "1",
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "text": text,
    }
    base.update(overrides)
    return base


class _ListSource:
    source_id = "list:test"

    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def documents(self) -> list[dict[str, Any]]:
        return self._documents


def _registry() -> CollectionRegistry:
    return CollectionRegistry(approvals())


def test_ingestion_refuses_a_document_for_an_unapproved_project() -> None:
    report = ingest(
        _ListSource([_raw(project_id=PROJECT_B)]), registry=_registry(), store=DocumentStore()
    )
    assert report.accepted == ()
    assert report.refused[0].reason == "collection is not approved for this project"


def test_ingestion_refuses_an_unapproved_collection() -> None:
    report = ingest(
        _ListSource([_raw(collection_id=UNAPPROVED)]), registry=_registry(), store=DocumentStore()
    )
    assert report.refused[0].reason == "collection is not approved for this project"


def test_ingestion_refuses_a_kind_that_does_not_match_the_scope() -> None:
    registry = CollectionRegistry(
        [
            CollectionApproval(
                collection_id=COLLECTION_C,
                project_id=PROJECT_A,
                scope=CollectionScope.APPROVED_INTERNAL,
                approval_reference="WDS-DECISION-INTERNAL-TEST",
            )
        ]
    )
    report = ingest(
        _ListSource([_raw(collection_id=COLLECTION_C)]), registry=registry, store=DocumentStore()
    )
    assert report.refused[0].reason == "document kind does not match the collection scope"


def test_ingestion_refuses_a_duplicate_version() -> None:
    store = DocumentStore()
    first = ingest(_ListSource([_raw()]), registry=_registry(), store=store)
    second = ingest(_ListSource([_raw()]), registry=_registry(), store=store)
    assert len(first.accepted) == 1
    assert second.refused[0].reason == "duplicate document version"


def test_ingestion_never_stores_a_verified_status() -> None:
    report = ingest(
        _ListSource([_raw(verification_status="verified")]),
        registry=_registry(),
        store=DocumentStore(),
    )
    assert report.accepted == ()
    assert report.refused[0].reason.startswith("invalid metadata")


def test_refusal_reason_does_not_echo_document_text() -> None:
    marker = "LEAK-MARKER-CLIENT-SENTENCE-DO-NOT-ECHO"
    report = ingest(
        _ListSource([_raw(text=marker, content_hash="0" * 64)]),
        registry=_registry(),
        store=DocumentStore(),
    )
    assert marker not in report.refused[0].reason
