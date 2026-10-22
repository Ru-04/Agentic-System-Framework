"""Requirement Analysis result contract: the full, reviewable output of one analysis pass."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import (
    ContractModel,
    ProjectId,
    ProposalKey,
    RelationType,
    RunId,
    SourceId,
    SourceVersionStr,
    VersionStr,
    proposal_key_is_namespaced,
)
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.source import SourceReference


class SourceVersionRef(ContractModel):
    """A Source version the analysis read. Every reference must fall inside this set."""

    source_id: SourceId
    source_version: SourceVersionStr


class StatementKind(StrEnum):
    GOAL = "goal"
    CONSTRAINT = "constraint"
    AMBIGUITY = "ambiguity"
    UNTRUSTED_INSTRUCTION = "untrusted_instruction"
    # Added in AI-5.1: sentences the rules did not classify are recorded, never silently dropped.
    UNCLASSIFIED = "unclassified"


class ProposedStatement(ContractModel):
    """A goal, constraint, ambiguity or flagged instruction-like passage, always source-linked."""

    proposal_key: ProposalKey
    kind: StatementKind
    statement: str = Field(min_length=1, max_length=1000)
    source_refs: list[SourceReference] = Field(min_length=1)


class AssumptionProposal(ContractModel):
    """Something the analysis relies on that the client has not yet confirmed."""

    proposal_key: ProposalKey
    statement: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=500)
    impact_if_false: str = Field(min_length=1, max_length=500)
    owner_to_confirm: str | None = Field(default=None, max_length=120)
    related_proposal_keys: list[ProposalKey] = Field(min_length=1)
    status: Literal["proposed"] = "proposed"


class ConflictProposal(ContractModel):
    """Two or more requirement proposals that contradict each other. Both are preserved."""

    proposal_key: ProposalKey
    description: str = Field(min_length=1, max_length=500)
    requirement_proposal_keys: list[ProposalKey] = Field(min_length=2)
    source_refs: list[SourceReference] = Field(min_length=2)
    status: Literal["open"] = "open"


class RelationProposal(ContractModel):
    from_proposal_key: ProposalKey
    to_proposal_key: ProposalKey
    relation_type: RelationType
    rationale: str = Field(min_length=1, max_length=300)


class AnalysisStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED_VALIDATION = "failed_validation"


_REQUIREMENT_RELATIONS = frozenset(
    {
        RelationType.DEPENDS_ON,
        RelationType.CONFLICTS_WITH,
        RelationType.RELATED_TO,
        RelationType.REFINES,
        RelationType.DUPLICATES_CANDIDATE,
    }
)


class RequirementAnalysisResult(ContractModel):
    """Output of the Requirement Analysis Agent. It proposes; humans decide.

    ``human_review_required`` and ``scope_committed`` are fixed. An analysis result can never
    commit scope or record a human decision.
    """

    run_id: RunId | None = None
    project_id: ProjectId
    project_revision: int = Field(ge=1)
    source_versions: list[SourceVersionRef] = Field(min_length=1)
    requirements: list[AtomicRequirement] = Field(default_factory=list)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    statements: list[ProposedStatement] = Field(default_factory=list)
    assumptions: list[AssumptionProposal] = Field(default_factory=list)
    conflicts: list[ConflictProposal] = Field(default_factory=list)
    relations: list[RelationProposal] = Field(default_factory=list)
    status: AnalysisStatus
    validation_errors: list[str] = Field(default_factory=list)
    registry_version: VersionStr
    catalog_version: VersionStr
    human_review_required: Literal[True] = True
    scope_committed: Literal[False] = False

    @model_validator(mode="after")
    def _check_internal_consistency(self) -> Self:
        if self.status is AnalysisStatus.COMPLETED and self.validation_errors:
            raise ValueError("a completed analysis must not carry validation errors")
        if any(r.requirement_id is not None for r in self.requirements):
            raise ValueError("analysis output must not carry Foundation requirement IDs")
        if any(q.question_id is not None for q in self.clarification_questions):
            raise ValueError("analysis output must not carry Foundation question IDs")

        requirement_keys = {r.proposal_key for r in self.requirements}
        question_keys = {q.proposal_key for q in self.clarification_questions if q.proposal_key}
        all_keys = [
            *(r.proposal_key for r in self.requirements),
            *question_keys,
            *(s.proposal_key for s in self.statements),
            *(a.proposal_key for a in self.assumptions),
            *(c.proposal_key for c in self.conflicts),
        ]
        if len(set(all_keys)) != len(all_keys):
            raise ValueError("proposal keys must be unique across the analysis result")
        if not all(proposal_key_is_namespaced(key) for key in all_keys):
            raise ValueError("a proposal key reuses a Foundation identifier prefix")

        for question in self.clarification_questions:
            if question.project_id != self.project_id:
                raise ValueError("questions must stay within the analysis project")
            if not set(question.related_proposal_keys) <= requirement_keys:
                raise ValueError(
                    "questions may only reference requirement proposals in this result"
                )
        for requirement in self.requirements:
            if requirement.project_id != self.project_id:
                raise ValueError("requirements must stay within the analysis project")
            if not set(requirement.clarification_proposal_keys) <= question_keys:
                raise ValueError("requirements may only reference questions in this result")
        for assumption in self.assumptions:
            if not set(assumption.related_proposal_keys) <= requirement_keys:
                raise ValueError(
                    "assumptions may only reference requirement proposals in this result"
                )
        for conflict in self.conflicts:
            if not set(conflict.requirement_proposal_keys) <= requirement_keys:
                raise ValueError(
                    "conflicts may only reference requirement proposals in this result"
                )
            if len({ref.segment_id for ref in conflict.source_refs}) < 2:
                raise ValueError("a conflict must cite at least two distinct segments")
        for relation in self.relations:
            if relation.relation_type not in _REQUIREMENT_RELATIONS:
                raise ValueError(
                    f"relation type {relation.relation_type} is not an analysis relation"
                )
            if relation.from_proposal_key == relation.to_proposal_key:
                raise ValueError("a relation must connect two different proposals")
            if not {relation.from_proposal_key, relation.to_proposal_key} <= requirement_keys:
                raise ValueError("relations may only connect requirement proposals in this result")

        allowed_versions = {(v.source_id, v.source_version) for v in self.source_versions}
        for statement in self.statements:
            _require_versions(statement.source_refs, allowed_versions)
        for conflict in self.conflicts:
            _require_versions(conflict.source_refs, allowed_versions)
        for requirement in self.requirements:
            _require_versions(requirement.source_refs, allowed_versions)
        return self


def _require_versions(refs: list[SourceReference], allowed: set[tuple[str, str]]) -> None:
    for ref in refs:
        if (ref.source_id, ref.source_version) not in allowed:
            raise ValueError(
                "source reference falls outside the source versions this analysis read"
            )
