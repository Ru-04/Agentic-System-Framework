"""Explicit operator decisions on which requirement proposals are investigated (AI-4.1).

This is an AI-side record of a named operator's choice. It is not a Foundation approval, it does not
accept any requirement, and it does not select any solution. It is never inferred from keyword
classification: a proposal is investigated only when an operator names it.

A selection is bound to the exact analysis it was made against. If the analysis changes, the
selection is stale and is refused until an operator decides again.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from ai_engine.contracts.analysis import RequirementAnalysisResult
from ai_engine.contracts.common import ContractModel, ProjectId, ProposalKey, Sha256Hex


class SelectionError(ValueError):
    """An operator decision cannot be recorded or does not match the analysis."""


class StaleSelectionError(SelectionError):
    """The analysis changed after the operator decided. A new decision is required."""


class OperatorDecisionKind(StrEnum):
    CONFIRM = "confirm_for_investigation"
    REJECT = "reject_for_investigation"


class OperatorDecision(ContractModel):
    proposal_key: ProposalKey
    decision: OperatorDecisionKind
    rationale: str = Field(min_length=1, max_length=300)


class OperatorSelection(ContractModel):
    """Who decided what, against which analysis. Omitted proposals have no decision at all."""

    selection_authority: Literal["operator_confirmation_ai_side_record"] = (
        "operator_confirmation_ai_side_record"
    )
    operator_label: str = Field(min_length=1, max_length=100)
    project_id: ProjectId
    analysis_fingerprint: Sha256Hex
    decisions: list[OperatorDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique(self) -> OperatorSelection:
        keys = [d.proposal_key for d in self.decisions]
        if len(set(keys)) != len(keys):
            raise ValueError("a proposal can carry only one operator decision")
        return self

    def confirmed_keys(self) -> list[str]:
        return [
            d.proposal_key for d in self.decisions if d.decision is OperatorDecisionKind.CONFIRM
        ]

    def rejected_keys(self) -> list[str]:
        return [d.proposal_key for d in self.decisions if d.decision is OperatorDecisionKind.REJECT]

    def decision_for(self, proposal_key: str) -> OperatorDecisionKind | None:
        for decision in self.decisions:
            if decision.proposal_key == proposal_key:
                return decision.decision
        return None


def analysis_fingerprint(analysis: RequirementAnalysisResult) -> str:
    """Hash of the proposal content an operator decided on. Any change makes a selection stale."""
    payload = {
        "project_id": analysis.project_id,
        "project_revision": analysis.project_revision,
        "requirements": sorted(
            [
                r.proposal_key,
                r.origin.value,
                r.requirement_type.value,
                r.status.value,
                r.original_wording,
                r.normalized_statement,
            ]
            for r in analysis.requirements
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_operator_selection(
    *,
    operator_label: str,
    analysis: RequirementAnalysisResult,
    confirm: Sequence[str] = (),
    reject: Sequence[str] = (),
    rationale: str,
) -> OperatorSelection:
    """Record explicit decisions. Every named proposal must exist in the analysis."""
    if (confirm or reject) and not operator_label.strip():
        raise SelectionError("an operator label is required for any decision")
    known = {r.proposal_key for r in analysis.requirements}
    decisions: list[OperatorDecision] = []
    for kind, keys in (
        (OperatorDecisionKind.CONFIRM, confirm),
        (OperatorDecisionKind.REJECT, reject),
    ):
        for key in keys:
            if key not in known:
                raise SelectionError(f"unknown proposal {key} in this analysis")
            decisions.append(OperatorDecision(proposal_key=key, decision=kind, rationale=rationale))
    try:
        return OperatorSelection(
            operator_label=operator_label.strip() or "none",
            project_id=analysis.project_id,
            analysis_fingerprint=analysis_fingerprint(analysis),
            decisions=decisions,
        )
    except ValueError as exc:
        raise SelectionError(str(exc)) from exc


def verify_selection(selection: OperatorSelection, analysis: RequirementAnalysisResult) -> None:
    """Refuse a selection that belongs to another project or to a different analysis."""
    if selection.project_id != analysis.project_id:
        raise SelectionError("the operator selection belongs to another project")
    if selection.analysis_fingerprint != analysis_fingerprint(analysis):
        raise StaleSelectionError("the analysis changed after the operator decided; decide again")
    known = {r.proposal_key for r in analysis.requirements}
    for decision in selection.decisions:
        if decision.proposal_key not in known:
            raise SelectionError(f"decision names unknown proposal {decision.proposal_key}")
