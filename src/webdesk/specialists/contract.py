"""Versioned common input and output contract for every specialist (M1 S1).

The orchestrator and the specialists exchange only these models. Each model forbids unknown
fields, so a specialist cannot carry approval, permission or routing data in an extra key.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from webdesk.specialists.catalog import SpecialistId

CONTRACT_VERSION: Literal["1.0.0"] = "1.0.0"


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank or whitespace only")
    return value


# Non-empty after stripping whitespace. Min length alone accepted "   " as an identifier.
NonBlank = Annotated[str, Field(min_length=1), AfterValidator(_not_blank)]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(_Contract):
    workspace_id: NonBlank
    source_id: NonBlank
    locator: NonBlank


class SpecialistInput(_Contract):
    contract_version: Literal["1.0.0"]
    request_id: NonBlank
    workspace_id: NonBlank
    specialist_id: SpecialistId
    requirement_ids: tuple[NonBlank, ...] = Field(min_length=1)
    evidence_refs: tuple[EvidenceRef, ...] = ()
    task: NonBlank


class EvidenceStatus(StrEnum):
    CITED = "cited"
    UNVERIFIED = "unverified"


class Finding(_Contract):
    statement: NonBlank
    evidence_status: EvidenceStatus
    evidence_refs: tuple[EvidenceRef, ...] = ()

    @model_validator(mode="after")
    def _cited_requires_evidence(self) -> Finding:
        if self.evidence_status is EvidenceStatus.CITED and not self.evidence_refs:
            raise ValueError("a cited finding must reference at least one evidence ref")
        return self


class OutputStatus(StrEnum):
    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class SpecialistOutput(_Contract):
    contract_version: Literal["1.0.0"]
    request_id: NonBlank
    workspace_id: NonBlank
    specialist_id: SpecialistId
    status: OutputStatus
    findings: tuple[Finding, ...] = ()
    unknowns: tuple[NonBlank, ...] = ()

    @model_validator(mode="after")
    def _incomplete_must_declare_unknowns(self) -> SpecialistOutput:
        if self.status is OutputStatus.INCOMPLETE and not self.unknowns:
            raise ValueError("an incomplete output must declare at least one unknown")
        return self
