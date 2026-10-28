"""B-1 regression (WDS-authorised AI-S09 compatibility correction).

A draft SOW must detect an estimate tied to a different governance review, report the integrity
mismatch, and must not present the mismatched estimate as current or authoritative. A matching
fingerprint is a positive control: the same request with matching fingerprints gives numbers and no
mismatch finding, so these tests fail if the comparison is removed.
"""

from __future__ import annotations

from typing import Any

from test_ai_s09_sow import REQ1, _estimate, _request

from ai_engine.sow.contracts import SectionState
from ai_engine.sow.engine import generate

MISMATCH = "e" * 64
TIED = "different governance review"


def _with_estimate_fingerprint(
    fingerprint: str | None,
    *,
    with_hours_for_req2: bool = False,
    revisions: dict[str, int] | None = None,
) -> Any:
    estimate = _estimate(with_hours_for_req2=with_hours_for_req2, revisions=revisions).model_copy(
        update={"governance_fingerprint": fingerprint}
    )
    return _request(estimate_draft=estimate)


def _mismatch_findings(sow: Any) -> list[str]:
    return [i for i in sow.integrity_issues if TIED in i]


def _numeric_deliverables(sow: Any) -> list[str]:
    return [d.deliverable_id for d in sow.deliverables if d.estimate_likely is not None]


def test_matching_fingerprint_is_a_positive_control() -> None:
    sow = generate(_with_estimate_fingerprint("a" * 64, with_hours_for_req2=True))
    assert _mismatch_findings(sow) == []
    assert _numeric_deliverables(sow), "a matching estimate must still supply deliverable values"


def test_mismatched_fingerprint_is_reported_as_an_integrity_finding() -> None:
    sow = generate(_with_estimate_fingerprint(MISMATCH, with_hours_for_req2=True))
    findings = _mismatch_findings(sow)
    assert len(findings) == 1
    assert "estimate values are excluded from authoritative use" in findings[0]


def test_mismatched_estimate_values_are_excluded_from_authoritative_use() -> None:
    sow = generate(_with_estimate_fingerprint(MISMATCH, with_hours_for_req2=True))
    assert _numeric_deliverables(sow) == []
    # The resource section falls back to 'not supported by approved input'; it never reports a
    # complete total.
    assert sow.resources.state is SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT
    assert sow.resources.project_complete is not True


def test_mismatched_estimate_does_not_make_the_sow_complete_or_approved() -> None:
    sow = generate(_with_estimate_fingerprint(MISMATCH, with_hours_for_req2=True))
    assert sow.approval.state == "pending_human_approval"
    assert sow.document_control.draft_state == "draft_not_approved"


def test_mismatched_estimate_keeps_its_traceability_fields() -> None:
    sow = generate(_with_estimate_fingerprint(MISMATCH, with_hours_for_req2=True))
    assert sow.document_control.estimate_version is not None


def test_revision_checks_still_run_on_a_mismatched_estimate() -> None:
    estimate = _estimate(revisions={REQ1: 2}).model_copy(
        update={"governance_fingerprint": MISMATCH}
    )
    sow = generate(_request(estimate_draft=estimate))
    assert any(f"stale requirement revision for {REQ1}" in i for i in sow.integrity_issues)
    assert _mismatch_findings(sow)


def test_an_estimate_with_no_fingerprint_is_not_treated_as_tied_elsewhere() -> None:
    sow = generate(_with_estimate_fingerprint(None, with_hours_for_req2=True))
    assert _mismatch_findings(sow) == []
