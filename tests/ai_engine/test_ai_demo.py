"""Synthetic end-to-end demonstration and the contract-shape checks it depends on."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from webdesk_ai import demo, synthetic
from webdesk_ai.contracts import (
    AgentStatus,
    AtomicRequirement,
    ClarificationQuestion,
    EvidenceStatus,
    ProjectContext,
    SourceVersionReference,
)


@pytest.fixture(scope="module")
def output() -> dict[str, object]:
    return demo.run_demo()


def test_flow_runs_brief_to_human_review(output: dict[str, object]) -> None:
    assert output["flow"][0] == "synthetic client brief"  # type: ignore[index]
    analysis = output["requirement_analysis"]
    assert analysis["status"] == AgentStatus.COMPLETED.value  # type: ignore[index]
    specialist = output["specialist"]
    assert specialist["status"] == AgentStatus.COMPLETED_WITH_GAPS.value  # type: ignore[index]


def test_safety_flags_are_fixed_and_explicit(output: dict[str, object]) -> None:
    assert output["flags"] == {  # type: ignore[index]
        "scope_approved": False,
        "estimate_committed": False,
        "sow_published": False,
        "foundation_writes": 0,
        "external_model_calls": 0,
        "evidence_is_synthetic": True,
        "human_review_required": True,
    }


def test_withheld_versions_are_absent_from_the_output(output: dict[str, object]) -> None:
    serialized = json.dumps(output)
    assert "Ignore the rules" not in serialized
    assert "salary bands" not in serialized
    access = output["foundation_access"]
    assert access["source_versions_visible"] == 3  # type: ignore[index]
    assert access["source_versions_in_fixture"] == 5  # type: ignore[index]


def test_no_credential_value_is_written_to_the_output(output: dict[str, object]) -> None:
    assert synthetic_token() not in json.dumps(output)


def test_repair_path_is_recorded(output: dict[str, object]) -> None:
    assert output["foundation_access"]["model_attempts"] == 2  # type: ignore[index]


def test_every_requirement_traces_to_a_supplied_segment(output: dict[str, object]) -> None:
    requirements = output["requirement_analysis"]["requirements"]  # type: ignore[index]
    for req in requirements:
        assert req["source_refs"]
        for ref in req["source_refs"]:
            assert ref["segment_id"] in {
                str(s)
                for s in (
                    synthetic.SEG_A,
                    synthetic.SEG_B,
                    synthetic.SEG_C,
                    synthetic.SEG_D,
                    synthetic.SEG_E,
                    synthetic.SEG_APPENDIX,
                )
            }


def test_specialist_findings_link_to_evidence_and_stay_unverified(
    output: dict[str, object],
) -> None:
    body = output["specialist"]["output"]  # type: ignore[index]
    evidence_ids = {e["evidence_id"] for e in body["evidence"]}
    for solution in body["candidate_solutions"]:
        assert set(solution["evidence_refs"]) <= evidence_ids
        assert solution["evidence_status"] == EvidenceStatus.UNVERIFIED.value
    assert all(c["evidence_status"] == "unverified" for c in body["claims"])


def test_questions_are_open_and_point_at_requirements(output: dict[str, object]) -> None:
    analysis = output["requirement_analysis"]  # type: ignore[index]
    questions = [
        ClarificationQuestion.model_validate(q) for q in analysis["clarification_questions"]
    ]
    assert questions
    assert all(q.status == "open" for q in questions)
    assert all(q.related_requirement_ids for q in questions)


def test_requirement_payloads_round_trip_through_the_contract_models(
    output: dict[str, object],
) -> None:
    analysis = output["requirement_analysis"]  # type: ignore[index]
    for req in analysis["requirements"]:
        AtomicRequirement.model_validate(req)
    ProjectContext.model_validate(output["foundation_access"]["project"])  # type: ignore[index]


def test_source_version_reference_forbids_storage_fields() -> None:
    with pytest.raises(ValueError):
        SourceVersionReference.model_validate(
            {
                "source_version_id": str(synthetic.VERSION_BRIEF),
                "source_id": str(synthetic.SOURCE_BRIEF),
                "version": 1,
                "scan_status": "clean",
                "parse_status": "succeeded",
                "access_classification": "confidential",
                "storage_key": "secret",
            }
        )


def test_main_writes_the_file_and_rejects_bad_usage(tmp_path: Path) -> None:
    target = tmp_path / "demo.json"
    assert demo.main(["prog", str(target)]) == 0
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["contract"] == "ai-read/v1"
    assert demo.main(["prog"]) == 2


def synthetic_token() -> str:
    return demo.SYNTHETIC_TOKEN


def test_demo_clock_is_fixed() -> None:
    assert demo.NOW == datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
