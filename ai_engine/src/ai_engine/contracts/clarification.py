"""Clarification questions: AI proposals and their persisted Foundation form."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from ai_engine.contracts.common import (
    ContractModel,
    ProjectId,
    ProposalKey,
    QuestionId,
    QuestionStatus,
    RequirementId,
)


class ClarificationQuestion(ContractModel):
    """A question to the client that blocks or qualifies requirements.

    Exactly one of ``question_id`` (Foundation-assigned) or ``proposal_key`` (AI proposal) is set.
    AI-proposed questions always start ``open``; only an authorized human can answer or waive them.
    """

    question_id: QuestionId | None = None
    proposal_key: ProposalKey | None = None
    project_id: ProjectId
    question_text: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)
    status: QuestionStatus = QuestionStatus.OPEN
    related_requirement_ids: list[RequirementId] = Field(default_factory=list)
    related_proposal_keys: list[ProposalKey] = Field(default_factory=list)
    impact_if_unanswered: str | None = Field(default=None, max_length=500)
    suggested_answer_options: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def _check_identity_and_links(self) -> Self:
        if (self.question_id is None) == (self.proposal_key is None):
            raise ValueError("set exactly one of question_id or proposal_key")
        if not self.related_requirement_ids and not self.related_proposal_keys:
            raise ValueError("a clarification question must relate to at least one requirement")
        if self.proposal_key is not None and self.status is not QuestionStatus.OPEN:
            raise ValueError("AI-proposed clarification questions must start open")
        return self
