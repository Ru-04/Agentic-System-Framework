"""Coverage and quote traceability for LLM output (AI-S02).

A reply is accepted only if every citation points at a real segment of the project, every quote is
present verbatim in that segment (whitespace-normalised) and is long enough to trace, and every
segment is either cited or listed as unclassified. Each function returns a list of error strings;
an empty list means pass.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from ai_engine.contracts.semantic import (
    bounded_pattern,
    normalise_whitespace,
    quote_is_substantive,
)
from ai_engine.contracts.source import SourceSegment

__all__ = ["check_coverage", "is_verbatim", "normalise_whitespace"]


def is_verbatim(quote: str, text: str) -> bool:
    """True if the quote appears in the text as a bounded, exact span (whitespace collapsed).

    A substring of a longer word does not count: "ers must" is not verbatim in "Users must". The
    boundary rule is the one the contract uses for statements (``bounded_pattern``).
    """
    needle = normalise_whitespace(quote)
    if not needle:
        return False
    return re.search(bounded_pattern(needle), normalise_whitespace(text)) is not None


def check_coverage(
    citations: Sequence[tuple[str, str]],
    unclassified_segment_ids: Sequence[str],
    segments: Sequence[SourceSegment],
    project_id: str,
) -> list[str]:
    """Check citations as ``(segment_id, quote)`` pairs against the segments the agent was given."""
    errors: list[str] = []
    index: dict[str, SourceSegment] = {}
    for segment in segments:
        if segment.segment_id in index:
            errors.append(f"duplicate segment {segment.segment_id} in the input")
        index[segment.segment_id] = segment

    cited: set[str] = set()
    for segment_id, quote in citations:
        cited_segment = index.get(segment_id)
        if cited_segment is None:
            errors.append(f"unknown segment {segment_id}")
            continue
        if cited_segment.project_id != project_id:
            errors.append(f"segment {segment_id} belongs to another project")
            continue
        cited.add(segment_id)
        if not quote_is_substantive(quote):
            errors.append(f"quote is too short to trace in segment {segment_id}")
            continue
        if not is_verbatim(quote, cited_segment.text):
            errors.append(f"quote is not verbatim in segment {segment_id}")

    for segment_id in unclassified_segment_ids:
        if segment_id not in index:
            errors.append(f"unknown unclassified segment {segment_id}")
        elif segment_id in cited:
            errors.append(f"segment {segment_id} is both cited and unclassified")

    listed = set(unclassified_segment_ids)
    for segment_id in index:
        if segment_id not in cited and segment_id not in listed:
            errors.append(f"segment {segment_id} was omitted: cite it or list it as unclassified")
    return errors
