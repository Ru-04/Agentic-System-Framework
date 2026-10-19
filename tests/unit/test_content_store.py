"""I-2: project-isolated content store and the intake storage setting (ARCH §13; F03 storage)."""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import pytest

from webdesk.config import Settings
from webdesk.storage.content_store import MAX_BYTES, ByteStoreError, ContentStore

PROJECT_A = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
PROJECT_B = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002")


@pytest.fixture
def store(tmp_path: Path) -> ContentStore:
    return ContentStore(tmp_path / "root")


def test_round_trip_returns_the_same_bytes_under_their_sha256_key(store: ContentStore) -> None:
    data = b"Client brief: inventory sync with the warehouse."
    key = store.put(PROJECT_A, data)
    assert key == hashlib.sha256(data).hexdigest()
    assert store.get(PROJECT_A, key) == data


def test_identical_content_in_two_projects_is_stored_separately(
    store: ContentStore, tmp_path: Path
) -> None:
    key_a = store.put(PROJECT_A, b"same bytes")
    key_b = store.put(PROJECT_B, b"same bytes")
    assert key_a == key_b  # the key is the content hash
    assert store.get(PROJECT_A, key_a) == b"same bytes"
    assert store.get(PROJECT_B, key_b) == b"same bytes"
    assert (tmp_path / "root" / str(PROJECT_A) / key_a).is_file()
    assert (tmp_path / "root" / str(PROJECT_B) / key_b).is_file()


def test_another_project_cannot_read_a_file_it_did_not_store(store: ContentStore) -> None:
    key = store.put(PROJECT_A, b"only project A")
    with pytest.raises(ByteStoreError) as exc:
        store.get(PROJECT_B, key)
    assert exc.value.reason == "not_found"


def test_a_modified_file_is_refused_on_read(store: ContentStore, tmp_path: Path) -> None:
    key = store.put(PROJECT_A, b"original")
    (tmp_path / "root" / str(PROJECT_A) / key).write_bytes(b"tampered")
    with pytest.raises(ByteStoreError) as exc:
        store.get(PROJECT_A, key)
    assert exc.value.reason == "integrity_failure"


@pytest.mark.parametrize(
    "bad_key",
    ["../../etc/passwd", "A" * 64, "a" * 63, "a" * 65, "..\\secret", "g" * 64],
)
def test_keys_that_could_escape_the_project_directory_are_refused(
    store: ContentStore, bad_key: str
) -> None:
    with pytest.raises(ByteStoreError) as exc:
        store.get(PROJECT_A, bad_key)
    assert exc.value.reason == "storage_key_invalid"


def test_oversized_and_empty_content_are_refused(store: ContentStore) -> None:
    with pytest.raises(ByteStoreError) as exc:
        store.put(PROJECT_A, b"x" * (MAX_BYTES + 1))
    assert exc.value.reason == "too_large"
    with pytest.raises(ByteStoreError) as exc:
        store.put(PROJECT_A, b"")
    assert exc.value.reason == "empty_content"


def test_a_relative_root_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ByteStoreError) as exc:
        ContentStore(Path("relative-root"))
    assert exc.value.reason == "storage_root_must_be_absolute"
    assert tmp_path.is_dir()


def test_no_temporary_files_remain_after_a_write(store: ContentStore, tmp_path: Path) -> None:
    store.put(PROJECT_A, b"clean write")
    leftovers = [p for p in (tmp_path / "root").rglob("*.tmp")]
    assert leftovers == []


def test_intake_is_disabled_without_an_absolute_storage_root(tmp_path: Path) -> None:
    assert Settings(_env_file=None).intake_capability().enabled is False
    relative = Settings(_env_file=None, storage_root=Path("uploads"))
    assert relative.intake_capability().enabled is False
    absolute = Settings(_env_file=None, storage_root=tmp_path)
    assert absolute.intake_capability().enabled is True
    assert os.name in ("nt", "posix")
