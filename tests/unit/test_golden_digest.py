"""EVAL-F10: canonical input digest. Golden reference from EVALUATION_PLAN.md, not regenerated here.

Expected digest: 5df52f543349fa88dd4a96d4f1f1f6183384adc754b477f65960b62e9b926da9
Canonical JSON:  {"config_versions":{"extraction_version":"v1","parser_library_version":"p1"},
                  "inputs":[{"entity_id":"S1","entity_type":"Source","revision":1}]}
"""

from __future__ import annotations

import hashlib

import pytest
import rfc8785

from webdesk.runs.hashing import InputTuple, input_revision_hash

GOLDEN_CONFIG = {"extraction_version": "v1", "parser_library_version": "p1"}
GOLDEN_DIGEST = "5df52f543349fa88dd4a96d4f1f1f6183384adc754b477f65960b62e9b926da9"
S1 = InputTuple("Source", "S1", 1)


def test_the_golden_canonical_json_is_the_specified_document() -> None:
    document = {
        "config_versions": GOLDEN_CONFIG,
        "inputs": [{"entity_id": "S1", "entity_type": "Source", "revision": 1}],
    }
    expected = (
        b'{"config_versions":{"extraction_version":"v1","parser_library_version":"p1"},'
        b'"inputs":[{"entity_id":"S1","entity_type":"Source","revision":1}]}'
    )
    assert rfc8785.dumps(document) == expected
    assert hashlib.sha256(expected).hexdigest() == GOLDEN_DIGEST


def test_the_encoder_reproduces_the_golden_digest() -> None:
    assert input_revision_hash([S1], config_versions=GOLDEN_CONFIG) == GOLDEN_DIGEST


def test_input_order_does_not_change_the_digest_because_inputs_are_sorted() -> None:
    a = InputTuple("Source", "S1", 1)
    b = InputTuple("Source", "S2", 1)
    assert input_revision_hash([a, b], config_versions=GOLDEN_CONFIG) == input_revision_hash(
        [b, a], config_versions=GOLDEN_CONFIG
    )


def test_a_changed_config_version_changes_the_digest() -> None:
    changed = {**GOLDEN_CONFIG, "parser_library_version": "p2"}
    assert input_revision_hash([S1], config_versions=changed) != GOLDEN_DIGEST


def test_a_changed_revision_changes_the_digest() -> None:
    bumped = InputTuple("Source", "S1", 2)
    assert input_revision_hash([bumped], config_versions=GOLDEN_CONFIG) != GOLDEN_DIGEST


def test_duplicate_entities_are_refused() -> None:
    with pytest.raises(ValueError):
        input_revision_hash([S1, S1], config_versions=GOLDEN_CONFIG)
