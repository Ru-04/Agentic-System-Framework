"""Explicit operator decisions on which requirement proposals are investigated (AI-4.1, AI-5.1).

This is an AI-side record of a named operator's choice. It is not a Foundation approval, it does not
accept any requirement, and it does not select any solution. It is never inferred from keyword
classification: a proposal is investigated only when an operator names it.

AI-5.1 changes:
- Every selection records who decided and when. Both are required and non-empty.
- Decisions are an immutable tuple. Duplicate proposals are refused on every verification.
- The analysis fingerprint hashes the whole serialised analysis, so any change to reviewed content
  makes the selection stale.
- Verification re-validates the selection from its serialised form, so model_copy and
  model_construct cannot bypass the contract.

Authority: the record states who decided, but it cannot prove that the actor was authorised. That
proof belongs to Foundation identity and governance (GOVERNANCE 11). Until then the record is an
attributed claim, not an authorisation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, ValidationError, model_validator

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
    """Who decided what, when, against which analysis. Omitted proposals have no decision at all."""

    selection_authority: Literal["operator_confirmation_ai_side_record"] = (
        "operator_confirmation_ai_side_record"
    )
    operator_label: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=120)
    decided_at: AwareDatetime
    project_id: ProjectId
    analysis_fingerprint: Sha256Hex
    decisions: tuple[OperatorDecision, ...] = ()

    @model_validator(mode="after")
    def _check_unique(self) -> OperatorSelection:
        keys = [d.proposal_key for d in self.decisions]
        if len(set(keys)) != len(keys):
            raise ValueError("a proposal can carry only one operator decision")
        for text in (self.operator_label, self.actor_id):
            # str.strip keeps invisible characters such as U+200B, so printability is checked too.
            if not text.strip() or not text.isprintable():
                raise ValueError(
                    "operator label and actor identifier must not be blank or contain "
                    "control or invisible characters"
                )
        return self

    def confirmed_keys(self) -> list[str]:
        return [
            d.proposal_key for d in self.decisions if d.decision == OperatorDecisionKind.CONFIRM
        ]

    def rejected_keys(self) -> list[str]:
        return [d.proposal_key for d in self.decisions if d.decision == OperatorDecisionKind.REJECT]

    def decision_for(self, proposal_key: str) -> OperatorDecisionKind | None:
        for decision in self.decisions:
            if decision.proposal_key == proposal_key:
                return OperatorDecisionKind(decision.decision)
        return None


def analysis_fingerprint(analysis: RequirementAnalysisResult) -> str:
    """Hash of the entire serialised analysis. Any change to reviewed content is detected."""
    encoded = json.dumps(
        analysis.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_operator_selection(
    *,
    operator_label: str,
    actor_id: str,
    decided_at: datetime,
    analysis: RequirementAnalysisResult,
    confirm: Sequence[str] = (),
    reject: Sequence[str] = (),
    rationale: str,
) -> OperatorSelection:
    """Record explicit decisions. Every named proposal must exist in the analysis."""
    if not operator_label.strip() or not actor_id.strip():
        raise SelectionError("an operator label and actor identifier are required")
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
            actor_id=actor_id.strip() or "none",
            decided_at=decided_at,
            project_id=analysis.project_id,
            analysis_fingerprint=analysis_fingerprint(analysis),
            decisions=tuple(decisions),
        )
    except ValueError as exc:
        raise SelectionError(str(exc)) from exc


def verify_selection(
    selection: OperatorSelection, analysis: RequirementAnalysisResult
) -> OperatorSelection:
    """Re-validate the selection and return the checked instance. Use the return value."""
    try:
        # Re-validate from serialised form: model_copy and model_construct are not trusted (N-4).
        checked = OperatorSelection.model_validate(selection.model_dump())
    except ValidationError as exc:
        raise SelectionError(
            f"operator selection failed validation: {exc.errors()[0]['msg']}"
        ) from exc
    if checked.project_id != analysis.project_id:
        raise SelectionError("the operator selection belongs to another project")
    if checked.analysis_fingerprint != analysis_fingerprint(analysis):
        raise StaleSelectionError("the analysis changed after the operator decided; decide again")
    known = {r.proposal_key for r in analysis.requirements}
    for decision in checked.decisions:
        if decision.proposal_key not in known:
            raise SelectionError(f"decision names unknown proposal {decision.proposal_key}")
    return checked
