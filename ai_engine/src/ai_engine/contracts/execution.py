"""Agent execution envelope: one run of one registered agent or specialist."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from ai_engine.contracts.analysis import RequirementAnalysisResult
from ai_engine.contracts.common import (
    AgentId,
    ContractModel,
    ExecutionId,
    ProjectId,
    RunId,
    SpecialistTaskId,
    VersionStr,
)
from ai_engine.contracts.specialist import SpecialistInvestigationResult


class AgentExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED_VALIDATION = "failed_validation"
    UNSUPPORTED_REQUEST = "unsupported_request"
    FAILED_TRANSIENT = "failed_transient"
    PERMISSION_DENIED = "permission_denied"


class AgentExecutionResult(ContractModel):
    """Envelope around an agent output. Only a succeeded execution carries an output."""

    execution_id: ExecutionId
    agent_id: AgentId
    project_id: ProjectId
    run_id: RunId | None = None
    task_id: SpecialistTaskId | None = None
    status: AgentExecutionStatus
    output: RequirementAnalysisResult | SpecialistInvestigationResult | None = None
    validation_errors: list[str] = Field(default_factory=list)
    tool_invocations: list[str] = Field(default_factory=list)
    registry_version: VersionStr
    catalog_version: VersionStr
    model_config_ref: str | None = Field(default=None, max_length=64)
    started_at: AwareDatetime
    finished_at: AwareDatetime

    @model_validator(mode="after")
    def _check_execution(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not precede started_at")
        if self.status is AgentExecutionStatus.SUCCEEDED:
            if self.output is None:
                raise ValueError("a succeeded execution must carry its output")
            if self.validation_errors:
                raise ValueError("a succeeded execution must not carry validation errors")
            if self.output.project_id != self.project_id:
                raise ValueError("the output must belong to the execution's project")
        elif self.output is not None:
            raise ValueError("only a succeeded execution may carry an output")
        return self
