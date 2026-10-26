"""Synthetic end-to-end demonstration: flow coverage, source references and boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from webdesk_ai import demo, synthetic
from webdesk_ai.contracts import ClarificationQuestion, SourceVersionReference


@pytest.fixture(scope="module")
def output() -> dict[str, Any]:
    return demo.run_demo()


def test_main_run_is_human_review_with_all_scenarios(output: dict[str, Any]) -> None:
    run = output["main_run"]
    assert run["status"] == "human_review_required"
    analysis = run["analysis"]
    assert analysis["status"] == "completed"
    assert len(analysis["requirements"]) == 8


def test_retry_and_repair_are_both_visible(output: dict[str, Any]) -> None:
    model = output["model"]
    assert model["transport_attempts"] == 3  # one transient failure, then two content calls
    assert model["content_attempts"] == 2
    assert model["schema_failures"] == 1
    assert model["rejected_attempts"] == 1


def test_conflict_unsupported_platform_and_missing_evidence_are_all_surfaced(
    output: dict[str, Any],
) -> None:
    analysis = output["main_run"]["analysis"]
    by_id = {r["requirement_id"]: r for r in analysis["requirements"]}
    assert by_id["REQ-007"]["conflict_ids"] == ["REQ-008"]
    assert by_id["REQ-008"]["conflict_ids"] == ["REQ-007"]
    routing = {(r["category_id"], r["outcome"]) for r in analysis["routing_recommendations"]}
    assert ("platform:zendesk", "unsupported") in routing
    assert ("shopify_specialist", "selected") in routing
    assert ("3dcart_shift4shop_specialist", "unavailable") in routing
    specialist = output["main_specialists"][0]
    body = output["main_run"]["specialist_results"][0]["output"]
    assert specialist["status"] == "completed_with_gaps"
    reasons = [item["reason"] for item in body["human_review_items"]]
    assert any("No evidence returned" in reason for reason in reasons)


def test_clarifications_cover_every_flagged_requirement(output: dict[str, Any]) -> None:
    analysis = output["main_run"]["analysis"]
    questions = [
        ClarificationQuestion.model_validate(q) for q in analysis["clarification_questions"]
    ]
    assert questions
    assert all(q.status == "open" for q in questions)
    assert output["main_run"]["clarification_gaps"] == []


def test_every_requirement_keeps_its_source_reference(output: dict[str, Any]) -> None:
    for req in output["main_run"]["analysis"]["requirements"]:
        assert req["source_refs"]
        for ref in req["source_refs"]:
            assert ref["segment_id"]
            assert ref["source_version_id"]


def test_invalid_specialist_probe_is_rejected_and_nothing_unsupported_accepted(
    output: dict[str, Any],
) -> None:
    probe = output["invalid_specialist_probe"]
    assert probe["specialists"][0]["status"] == "invalid_output"
    assert probe["unsupported_claims_accepted"] == 0


def test_flags_are_fixed_and_no_approval_is_claimed(output: dict[str, Any]) -> None:
    assert output["flags"] == {
        "human_review_required": True,
        "requirements_approved": False,
        "scope_approved": False,
        "estimate_committed": False,
        "sow_published": False,
        "foundation_writes": 0,
        "machine_routing_enabled": False,
    }
    for req in output["main_run"]["analysis"]["requirements"]:
        assert req["status"] not in ("verified", "accepted_for_scope")


def test_withheld_content_and_credentials_never_reach_the_output(output: dict[str, Any]) -> None:
    serialized = json.dumps(output)
    assert "Ignore the rules" not in serialized
    assert "salary bands" not in serialized
    assert demo.SYNTHETIC_TOKEN not in serialized


def test_no_synthetic_evidence_is_presented_as_verified(output: dict[str, Any]) -> None:
    body = output["main_run"]["specialist_results"][0]["output"]
    assert all(e["origin"] == "synthetic_fixture" for e in body["evidence"])
    assert all(c["evidence_status"] == "unverified" for c in body["claims"])


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
