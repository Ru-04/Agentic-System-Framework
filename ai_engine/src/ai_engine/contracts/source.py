"""Foundation-owned source segments and the references that point at them."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from ai_engine.contracts.common import (
    ContractModel,
    DataClass,
    LocatorType,
    ProjectId,
    ReferenceRelation,
    SegmentId,
    SourceId,
    SourceTrust,
    SourceType,
    SourceVersionStr,
)


class SourceSegment(ContractModel):
    """Immutable, parsed segment of one Source version (Foundation-owned).

    ``text`` is untrusted client content. It is data for analysis and is never interpreted as
    instructions, configuration or approval.
    """

    segment_id: SegmentId
    project_id: ProjectId
    source_id: SourceId
    source_version: SourceVersionStr
    source_type: SourceType
    source_trust: SourceTrust
    access_classification: DataClass
    locator_type: LocatorType
    extraction_version: str = Field(min_length=1, max_length=32)
    text: str = Field(max_length=50_000)
    page_number: int | None = Field(default=None, ge=1)
    paragraph_index: int | None = Field(default=None, ge=0)
    heading_path: list[str] | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    eml_part: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _check_locator(self) -> Self:
        """Each locator type must carry the fields that make its segment addressable."""
        required: dict[LocatorType, bool] = {
            LocatorType.PDF_PAGE: self.page_number is not None,
            LocatorType.DOCX_PARAGRAPH: self.paragraph_index is not None,
            LocatorType.MD_HEADING_PARAGRAPH: bool(self.heading_path),
            LocatorType.TXT_LINE_RANGE: self.line_start is not None and self.line_end is not None,
            LocatorType.EML_PART: self.eml_part is not None,
        }
        if not required[self.locator_type]:
            raise ValueError(f"locator_type {self.locator_type} is missing its locator fields")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("line_end must not precede line_start")
        return self


class SourceReference(ContractModel):
    """Traceable pointer from an AI output to a persisted SourceSegment.

    ``segment_id`` is the canonical locator. Auxiliary fields are navigation only and never replace
    it (REQUIREMENT_SCHEMA.md section 4.3).
    """

    source_id: SourceId
    source_version: SourceVersionStr
    segment_id: SegmentId
    relation: ReferenceRelation = ReferenceRelation.SUPPORTS
    page: int | None = Field(default=None, ge=1)
    heading_path: list[str] | None = None
    supporting_quote: str | None = Field(default=None, max_length=500)
