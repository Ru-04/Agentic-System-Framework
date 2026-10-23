"""AI-S02 traceability: quotes verbatim, citations resolve, every segment cited or unclassified."""

from __future__ import annotations

from ai_engine.contracts.common import DataClass, LocatorType, SourceTrust, SourceType
from ai_engine.contracts.source import SourceSegment
from ai_engine.llm_agents.traceability import check_coverage

PROJECT = "PRJ-TEST-0001"


def _segment(segment_id: str, text: str, project: str = PROJECT) -> SourceSegment:
    return SourceSegment(
        segment_id=segment_id,
        project_id=project,
        source_id="SRC-TEST-0001",
        source_version="1",
        source_type=SourceType.CLIENT_BRIEF,
        source_trust=SourceTrust.UNTRUSTED_INPUT,
        access_classification=DataClass.INTERNAL,
        locator_type=LocatorType.TXT_LINE_RANGE,
        line_start=1,
        line_end=1,
        extraction_version="test-1",
        text=text,
    )


A = _segment("SEG-TEST-0001", "The store must sync orders. Inventory must be accurate.")
B = _segment("SEG-TEST-0002", "Shoppers want gift cards.")


def test_fully_covered_input_passes() -> None:
    errors = check_coverage(
        [("SEG-TEST-0001", "The store must sync orders.")],
        ["SEG-TEST-0002"],
        [A, B],
        PROJECT,
    )
    assert errors == []


def test_quote_matches_after_whitespace_normalisation() -> None:
    errors = check_coverage(
        [("SEG-TEST-0001", "The store\n  must   sync orders.")],
        ["SEG-TEST-0002"],
        [A, B],
        PROJECT,
    )
    assert errors == []


def test_hallucinated_quote_is_refused() -> None:
    errors = check_coverage(
        [("SEG-TEST-0001", "The store must explode.")], ["SEG-TEST-0002"], [A, B], PROJECT
    )
    assert "quote is not verbatim in segment SEG-TEST-0001" in errors


def test_empty_quote_is_refused() -> None:
    errors = check_coverage([("SEG-TEST-0001", "   ")], ["SEG-TEST-0002"], [A, B], PROJECT)
    assert "quote is too short to trace in segment SEG-TEST-0001" in errors


def test_unknown_cited_segment_is_refused() -> None:
    errors = check_coverage(
        [("SEG-TEST-0009", "anything")], ["SEG-TEST-0001", "SEG-TEST-0002"], [A, B], PROJECT
    )
    assert errors == ["unknown segment SEG-TEST-0009"]


def test_cited_segment_of_another_project_is_refused() -> None:
    other = _segment("SEG-TEST-0003", "Other project text.", project="PRJ-OTHER-0001")
    errors = check_coverage(
        [("SEG-TEST-0003", "Other project text.")],
        ["SEG-TEST-0001", "SEG-TEST-0002"],
        [A, B, other],
        PROJECT,
    )
    assert errors == [
        "segment SEG-TEST-0003 belongs to another project",
        "segment SEG-TEST-0003 was omitted: cite it or list it as unclassified",
    ]


def test_silently_omitted_segment_is_refused() -> None:
    errors = check_coverage([("SEG-TEST-0001", "Inventory must be accurate.")], [], [A, B], PROJECT)
    assert errors == [
        "segment SEG-TEST-0002 was omitted: cite it or list it as unclassified",
    ]


def test_unclassified_segment_satisfies_coverage() -> None:
    errors = check_coverage([], ["SEG-TEST-0001", "SEG-TEST-0002"], [A, B], PROJECT)
    assert errors == []


def test_segment_both_cited_and_unclassified_is_refused() -> None:
    errors = check_coverage(
        [("SEG-TEST-0001", "The store must sync orders.")],
        ["SEG-TEST-0001", "SEG-TEST-0002"],
        [A, B],
        PROJECT,
    )
    assert errors == ["segment SEG-TEST-0001 is both cited and unclassified"]


def test_unknown_unclassified_segment_is_refused() -> None:
    errors = check_coverage(
        [], ["SEG-TEST-0001", "SEG-TEST-0002", "SEG-TEST-0404"], [A, B], PROJECT
    )
    assert errors == ["unknown unclassified segment SEG-TEST-0404"]


def test_duplicate_input_segment_is_refused() -> None:
    errors = check_coverage([], ["SEG-TEST-0001", "SEG-TEST-0002"], [A, B, A], PROJECT)
    assert errors == ["duplicate segment SEG-TEST-0001 in the input"]
