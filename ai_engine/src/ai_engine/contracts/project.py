"""Foundation-owned project read model handed to the AI Engine."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ai_engine.contracts.common import ContractModel, DataClass, ProjectId, Slug


class ProjectContext(ContractModel):
    """Read-only snapshot of a Project, owned by Foundation.

    The AI Engine never writes this record. ``project_revision`` lets every derived output state
    which Project revision it was produced from.
    """

    project_id: ProjectId
    project_revision: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=200)
    data_classification: DataClass
    access_boundary_id: str = Field(min_length=1, max_length=120)
    status: Literal["active", "archived", "deleted_pending_retention"] = "active"
    platforms: list[Slug] = Field(default_factory=list)
    application_types: list[Slug] = Field(default_factory=list)
