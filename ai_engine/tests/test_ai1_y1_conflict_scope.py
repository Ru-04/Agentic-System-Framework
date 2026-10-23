"""Y-1 regression (WDS approved exception to the AI-S03 rule on AI-1 code).

The mock evidence lookup keyed conflict groups by evidence identifier alone. Two projects with
a record of the same identifier overwrote each other's group. Groups are now keyed by project
and identifier.
"""

from __future__ import annotations

import pytest

from ai_engine.evidence.lookup import CollectedEvidence, MockEvidenceLookup
from ai_engine.shopify.synthetic_evidence import synthetic_shopify_evidence

PROJECT_A = "PRJ-SYN-0001"
PROJECT_B = "PRJ-SYN-0002"


def _two_projects(group_a: str | None, group_b: str | None) -> tuple[list[CollectedEvidence], str]:
    base = synthetic_shopify_evidence(PROJECT_A)[0]
    record_a = base.record
    record_b = record_a.model_copy(update={"project_id": PROJECT_B})
    items = [
        CollectedEvidence(base.collection, record_a, group_a),
        CollectedEvidence(base.collection, record_b, group_b),
    ]
    return items, record_a.evidence_id


@pytest.mark.parametrize("reverse", [False, True])
def test_same_identifier_in_two_projects_keeps_each_projects_group(reverse: bool) -> None:
    items, evidence_id = _two_projects("group-of-a", "group-of-b")
    if reverse:
        items.reverse()
    lookup = MockEvidenceLookup(items)
    assert lookup.conflict_group_of(evidence_id, project_id=PROJECT_A) == "group-of-a"
    assert lookup.conflict_group_of(evidence_id, project_id=PROJECT_B) == "group-of-b"


def test_one_project_group_does_not_appear_for_another_project_with_no_group() -> None:
    items, evidence_id = _two_projects("group-of-a", None)
    lookup = MockEvidenceLookup(items)
    assert lookup.conflict_group_of(evidence_id, project_id=PROJECT_B) is None
    assert lookup.conflict_group_of(evidence_id, project_id=PROJECT_A) == "group-of-a"


def test_without_a_project_an_identifier_shared_by_two_projects_gets_no_group() -> None:
    items, evidence_id = _two_projects("group-of-a", "group-of-b")
    lookup = MockEvidenceLookup(items)
    # The identifier names two records, so no group is guessed between them.
    assert lookup.conflict_group_of(evidence_id) is None


def test_an_unknown_project_gets_no_group() -> None:
    items, evidence_id = _two_projects("group-of-a", "group-of-b")
    lookup = MockEvidenceLookup(items)
    assert lookup.conflict_group_of(evidence_id, project_id="PRJ-SYN-0009") is None


def test_single_project_behaviour_is_unchanged() -> None:
    base = synthetic_shopify_evidence(PROJECT_A)[0]
    lookup = MockEvidenceLookup([CollectedEvidence(base.collection, base.record, "only-group")])
    assert lookup.conflict_group_of(base.record.evidence_id) == "only-group"
    assert lookup.conflict_group_of(base.record.evidence_id, project_id=PROJECT_A) == "only-group"
    assert lookup.conflict_group_of(base.record.evidence_id, project_id=PROJECT_B) is None


def test_search_still_returns_only_the_requested_projects_record() -> None:
    items, evidence_id = _two_projects("group-of-a", "group-of-b")
    lookup = MockEvidenceLookup(items)
    found = lookup.search(
        project_id=PROJECT_B,
        allowed_collections=[items[0].collection],
        query="",
    )
    assert [record.project_id for record in found] == [PROJECT_B]
    assert lookup.conflict_group_of(evidence_id, project_id=PROJECT_B) == "group-of-b"
