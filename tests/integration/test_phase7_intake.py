"""Phase 7 intake hardening over HTTP (H-60, H-61, H-63, H-66; INCREMENT_3_HARDENING_PLAN §4).

Phase 7 intake hardening over HTTP (H-60, H-61, H-63, H-66; INCREMENT_3_HARDENING_PLAN §4).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.committed.test_http_intake import (  # noqa: F401 - fixture and helpers
    _auth,
    _revision,
    http,
)

pytestmark = pytest.mark.integration

FIELDS = {
    "title": "Phase 7 notes",
    "source_type": "client_brief",
    "source_trust": "untrusted_input",
    "access_classification": "internal",
}


def _client(http: dict[str, object]) -> TestClient:  # noqa: F811  # noqa: F811
    client = http["client"]
    assert isinstance(client, TestClient)
    return client


def _source_count(http: dict[str, object]) -> int:  # noqa: F811
    engine = http["engine"]
    assert isinstance(engine, Engine)
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM sources WHERE project_id = CAST(:p AS uuid)"),
                {"p": http["project"]},
            ).scalar_one()
        )


def _stored_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def test_h61_a_field_outside_the_allowlist_is_refused_before_any_work(
    http: dict[str, object],  # noqa: F811
) -> None:
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={
            **FIELDS,
            "expected_project_revision": str(_revision(engine, str(http["project"]))),
            "unexpected_field": "anything",
        },
        files={"file": ("notes.txt", b"allowlist probe\n", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "server_field_rejected"}
    assert _source_count(http) == 0


def test_h66_an_uploader_cannot_assign_approved_reference_trust(
    http: dict[str, object],  # noqa: F811
) -> None:
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={
            **FIELDS,
            "source_trust": "approved_reference",
            "expected_project_revision": str(_revision(engine, str(http["project"]))),
        },
        files={"file": ("notes.txt", b"trust probe\n", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json() == {"error": "trust_not_permitted"}
    assert _source_count(http) == 0


def test_h63_a_refused_upload_leaves_no_bytes_in_storage(
    http: dict[str, object],  # noqa: F811
    tmp_path: Path,
) -> None:
    """The refusal happens inside admission (stale source revision), after the revision precheck."""
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    root = tmp_path / "root"
    first = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={**FIELDS, "expected_project_revision": str(_revision(engine, str(http["project"])))},
        files={"file": ("kept.txt", b"first version\n", "text/plain")},
    )
    assert first.status_code == 200, first.text
    source_id = first.json()["source_id"]
    with engine.connect() as conn:
        source_revision = conn.execute(
            text("SELECT revision FROM sources WHERE source_id = CAST(:s AS uuid)"),
            {"s": source_id},
        ).scalar_one()
    stored_before = sorted(p.read_bytes() for p in _stored_files(root))
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={
            **FIELDS,
            "expected_project_revision": str(_revision(engine, str(http["project"]))),
            "supersedes_source_id": source_id,
            "expected_source_revision": str(int(source_revision) + 5),
        },
        files={"file": ("orphan.txt", b"refused bytes must not be stored\n", "text/plain")},
    )
    assert response.status_code == 409, response.text
    assert response.json() == {"error": "source_revision_conflict"}
    assert sorted(p.read_bytes() for p in _stored_files(root)) == stored_before
    assert _source_count(http) == 1


def test_h63_an_admitted_upload_stores_its_bytes_after_the_row(
    http: dict[str, object],  # noqa: F811
    tmp_path: Path,  # noqa: F811
) -> None:
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    payload = b"stored after admission\n"
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={**FIELDS, "expected_project_revision": str(_revision(engine, str(http["project"])))},
        files={"file": ("kept.txt", payload, "text/plain")},
    )
    assert response.status_code == 200, response.text
    assert _source_count(http) == 1
    stored = [p.read_bytes() for p in _stored_files(tmp_path / "root")]
    assert stored == [payload]


def test_h60_an_oversized_body_is_refused_with_413_before_parsing(
    http: dict[str, object],  # noqa: F811
) -> None:
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    oversized = b"x" * (21 * 1024 * 1024 + 16)
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={**FIELDS, "expected_project_revision": str(_revision(engine, str(http["project"])))},
        files={"file": ("big.txt", oversized, "text/plain")},
    )
    assert response.status_code == 413
    assert _source_count(http) == 0


def _audit_count(http: dict[str, object], event: str, reason: str) -> int:  # noqa: F811
    engine = http["engine"]
    assert isinstance(engine, Engine)
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(
                    "SELECT count(*) FROM audit_events"
                    " WHERE event_type = :e AND error_class = :r AND outcome = 'denied'"
                ),
                {"e": event, "r": reason},
            ).scalar_one()
        )


def test_h60_a_file_just_over_the_limit_is_413_and_audited_even_with_a_stale_revision(
    http: dict[str, object],  # noqa: F811
) -> None:
    """Over 20 MiB but under the route's body limit: the service size check runs first."""
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    stale = _revision(engine, str(http["project"])) + 7
    oversized = b"x" * (20 * 1024 * 1024 + 1)
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={**FIELDS, "expected_project_revision": str(stale)},
        files={"file": ("big.txt", oversized, "text/plain")},
    )
    assert response.status_code == 413, response.text
    assert response.json() == {"error": "too_large"}
    assert _audit_count(http, "source.upload.refused", "too_large") == 1
    assert _source_count(http) == 0


def test_h60_a_wrong_type_file_is_415_even_with_a_stale_revision(
    http: dict[str, object],  # noqa: F811
) -> None:
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    stale = _revision(engine, str(http["project"])) + 7
    response = client.post(
        f"/projects/{http['project']}/sources",
        headers=_auth(str(http["analyst_token"])),
        data={**FIELDS, "expected_project_revision": str(stale)},
        files={"file": ("tool.exe", b"MZ not a document\n", "application/octet-stream")},
    )
    assert response.status_code == 415, response.text
    assert response.json() == {"error": "unsupported_type"}
    assert _audit_count(http, "source.upload.refused", "unsupported_type") == 1
    assert _source_count(http) == 0


def test_h60_size_and_type_are_checked_before_authorization(
    http: dict[str, object],  # noqa: F811
) -> None:
    """F-1: a user refused upload (403) for a valid file still gets 415 and 413 for a bad one."""
    client = _client(http)
    engine = http["engine"]
    assert isinstance(engine, Engine)
    headers = _auth(str(http["admin_token"]))
    data = {**FIELDS, "expected_project_revision": str(_revision(engine, str(http["project"])))}
    url = f"/projects/{http['project']}/sources"

    valid = client.post(
        url, headers=headers, data=data, files={"file": ("notes.txt", b"valid\n", "text/plain")}
    )
    assert valid.status_code == 403, valid.text

    wrong_type = client.post(
        url,
        headers=headers,
        data=data,
        files={"file": ("tool.exe", b"MZ not a document\n", "application/octet-stream")},
    )
    assert wrong_type.status_code == 415, wrong_type.text
    assert wrong_type.json() == {"error": "unsupported_type"}

    too_large = client.post(
        url,
        headers=headers,
        data=data,
        files={"file": ("big.txt", b"x" * (20 * 1024 * 1024 + 1), "text/plain")},
    )
    assert too_large.status_code == 413, too_large.text
    assert too_large.json() == {"error": "too_large"}
    assert _audit_count(http, "source.upload.refused", "unsupported_type") == 1
    assert _audit_count(http, "source.upload.refused", "too_large") == 1
    assert _source_count(http) == 0
