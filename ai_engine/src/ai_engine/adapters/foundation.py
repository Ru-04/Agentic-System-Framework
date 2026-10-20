"""Foundation read port and the mock adapter used by the prototype.

The AI Engine never reaches Foundation storage. It reads only what a port returns, and the port
returns only what Foundation has authorized for the caller. The mock enforces the same boundaries
(project boundary, classification ceiling) so tests exercise the rules the real adapter must keep.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from ai_engine.contracts.common import ContractModel, DataClass
from ai_engine.contracts.project import ProjectContext
from ai_engine.contracts.source import SourceSegment

_CLASS_RANK: dict[DataClass, int] = {
    DataClass.INTERNAL: 0,
    DataClass.CONFIDENTIAL_CLIENT: 1,
    DataClass.RESTRICTED: 2,
}


class ProjectBoundaryError(PermissionError):
    """Raised when a read names a project outside the authorized boundary."""


class ClassificationDeniedError(PermissionError):
    """Raised when a read would return content above the authorized classification ceiling."""


class FixtureError(ValueError):
    """Raised when a fixture is not synthetic or is internally inconsistent."""


class FoundationReadPort(Protocol):
    """Read-only dependency on Foundation. Writes are deliberately absent in AI-1."""

    def get_project(self, project_id: str) -> ProjectContext: ...

    def list_source_segments(
        self, project_id: str, max_classification: DataClass
    ) -> list[SourceSegment]: ...


class SyntheticFixture(ContractModel):
    """A fixture file. ``synthetic`` must be true: real client data cannot enter here."""

    fixture_id: str = Field(min_length=1, max_length=64)
    synthetic: Literal[True]
    description: str = Field(min_length=1, max_length=500)
    project: ProjectContext
    segments: list[SourceSegment] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        floor = _CLASS_RANK[self.project.data_classification]
        for segment in self.segments:
            if segment.project_id != self.project.project_id:
                raise ValueError(f"segment {segment.segment_id} belongs to another project")
            if _CLASS_RANK[segment.access_classification] < floor:
                raise ValueError(
                    f"segment {segment.segment_id} is classified below its project classification"
                )
        return self


class MockFoundationAdapter:
    """In-memory implementation of FoundationReadPort backed by one synthetic fixture."""

    def __init__(self, fixture: SyntheticFixture) -> None:
        self._fixture = fixture

    @classmethod
    def from_file(cls, path: Path) -> Self:
        try:
            fixture = SyntheticFixture.model_validate_json(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise FixtureError(
                f"fixture {path.name} is not a valid synthetic fixture: {exc}"
            ) from exc
        return cls(fixture)

    def _check_project(self, project_id: str) -> None:
        if project_id != self._fixture.project.project_id:
            raise ProjectBoundaryError(f"project {project_id} is outside this adapter's boundary")

    def get_project(self, project_id: str) -> ProjectContext:
        self._check_project(project_id)
        return self._fixture.project

    def list_source_segments(
        self, project_id: str, max_classification: DataClass
    ) -> list[SourceSegment]:
        self._check_project(project_id)
        ceiling = _CLASS_RANK[max_classification]
        denied = [
            segment.segment_id
            for segment in self._fixture.segments
            if _CLASS_RANK[segment.access_classification] > ceiling
        ]
        if denied:
            # Refuse the whole read: a partial analysis would silently omit client content.
            raise ClassificationDeniedError(
                f"{len(denied)} segment(s) exceed the authorized classification"
            )
        return list(self._fixture.segments)
