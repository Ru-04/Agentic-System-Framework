"""Citation verification and unsupported-claim detection (M1 S2).

A citation is verified only if its quote is the exact text at its span in the cited source, the
source belongs to the same workspace, and the source hash still matches. A claim with no citation,
or with any failed citation, is not supported.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from webdesk.evidence.retrieval import Passage
from webdesk.evidence.sources import SourceRecord


class CitationCheck(StrEnum):
    VERIFIED = "verified"
    UNKNOWN_SOURCE = "unknown_source"
    WORKSPACE_MISMATCH = "workspace_mismatch"
    HASH_MISMATCH = "hash_mismatch"
    SPAN_MISMATCH = "span_mismatch"


class ClaimIssue(StrEnum):
    UNSUPPORTED = "unsupported"
    CITATION_FAILED = "citation_failed"


@dataclass(frozen=True)
class Citation:
    source_id: str
    workspace_id: str
    content_sha256: str
    start: int
    end: int
    quote: str

    @classmethod
    def from_passage(cls, passage: Passage) -> Citation:
        return cls(
            source_id=passage.source.source_id,
            workspace_id=passage.source.workspace_id,
            content_sha256=passage.source.content_sha256,
            start=passage.start,
            end=passage.end,
            quote=passage.text,
        )


@dataclass(frozen=True)
class Claim:
    statement: str
    citations: tuple[Citation, ...] = ()


def verify_citation(
    citation: Citation, sources: Mapping[str, SourceRecord], workspace_id: str
) -> CitationCheck:
    source = sources.get(citation.source_id)
    if source is None:
        return CitationCheck.UNKNOWN_SOURCE
    if citation.workspace_id != workspace_id or source.workspace_id != workspace_id:
        return CitationCheck.WORKSPACE_MISMATCH
    if citation.content_sha256 != source.content_sha256:
        return CitationCheck.HASH_MISMATCH
    if not 0 <= citation.start < citation.end <= len(source.text):
        return CitationCheck.SPAN_MISMATCH
    if source.text[citation.start : citation.end] != citation.quote:
        return CitationCheck.SPAN_MISMATCH
    return CitationCheck.VERIFIED


def check_claim(
    claim: Claim, sources: Mapping[str, SourceRecord], workspace_id: str
) -> ClaimIssue | None:
    if not claim.citations:
        return ClaimIssue.UNSUPPORTED
    for citation in claim.citations:
        if verify_citation(citation, sources, workspace_id) is not CitationCheck.VERIFIED:
            return ClaimIssue.CITATION_FAILED
    return None
