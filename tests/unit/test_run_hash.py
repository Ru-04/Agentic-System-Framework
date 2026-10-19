"""I-10 unit tests: the run input hash is canonical, order-independent and revision-sensitive."""

from __future__ import annotations

import pytest

from webdesk.runs.hashing import InputTuple, input_revision_hash

A = InputTuple("SourceVersion", "11111111-0000-0000-0000-000000000001", 1)
B = InputTuple("SourceVersion", "22222222-0000-0000-0000-000000000002", 3)


def test_the_hash_is_independent_of_input_order() -> None:
    assert input_revision_hash([A, B]) == input_revision_hash([B, A])


def test_a_changed_revision_changes_the_hash() -> None:
    changed = InputTuple(B.entity_type, B.entity_id, B.revision + 1)
    assert input_revision_hash([A, B]) != input_revision_hash([A, changed])


def test_an_entity_may_appear_only_once() -> None:
    with pytest.raises(ValueError):
        input_revision_hash([A, A])


def test_the_hash_is_a_sha256_hex_digest() -> None:
    digest = input_revision_hash([A])
    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")
