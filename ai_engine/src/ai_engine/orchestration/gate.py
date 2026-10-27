"""
Operator-confirmation gate for AI-S06.

Execution is allowed only when every check below passes. Checks run in a fixed order, and the replay
ledger is updated only after all of them pass, so a refused attempt consumes nothing.

Checks: mock refused on the production path; actor kind must be human; the confirming actor must be
the actor requesting execution (no transfer); the confirmer must not be the proposer; project,
proposal and run must match; confirmed categories must be a subset of the proposal; the confirmation
must not be expired; the confirmation ID and nonce must not have been used before (no replay, no
duplicate).

Foundation remains the authoritative owner of operator identity, session validation and approval
persistence. This gate verifies the record shape and binding inside the AI Engine. It is not an
authorization authority and is not a substitute for Foundation's operator confirmation.
"""

from __future__ import annotations

from datetime import datetime

from ai_engine.orchestration.contracts import (
    ConfirmationRefused,
    OperatorConfirmation,
    RecommendationProposal,
)


class ConfirmationLedger:
    """Records consumed confirmation IDs and nonces, so that a confirmation is accepted once."""

    def __init__(self) -> None:
        self._ids: set[str] = set()
        self._nonces: set[str] = set()

    def consume(self, confirmation: OperatorConfirmation) -> None:
        if confirmation.confirmation_id in self._ids:
            raise ConfirmationRefused("confirmation ID was already used")
        if confirmation.nonce in self._nonces:
            raise ConfirmationRefused("confirmation nonce was already used (replay)")
        self._ids.add(confirmation.confirmation_id)
        self._nonces.add(confirmation.nonce)


def verify_confirmation(
    confirmation: OperatorConfirmation,
    proposal: RecommendationProposal,
    *,
    run_id: str,
    project_id: str,
    actor: str,
    now: datetime,
    ledger: ConfirmationLedger,
    allow_mock: bool,
) -> None:
    if confirmation.mock and not allow_mock:
        raise ConfirmationRefused("mock confirmation is not permitted on the production path")
    if confirmation.actor_kind != "human":
        raise ConfirmationRefused("only a human operator can confirm a selection")
    if confirmation.confirmed_by != actor:
        raise ConfirmationRefused("confirmation was issued to a different actor")
    if confirmation.confirmed_by == proposal.proposed_by:
        raise ConfirmationRefused("the proposer cannot confirm its own proposal")
    if confirmation.project_id != project_id or proposal.project_id != project_id:
        raise ConfirmationRefused("confirmation is bound to another project")
    if confirmation.proposal_id != proposal.proposal_id:
        raise ConfirmationRefused("confirmation does not name this proposal")
    if confirmation.run_id != run_id:
        raise ConfirmationRefused("confirmation is bound to another run")
    if not confirmation.confirmed_categories:
        raise ConfirmationRefused("confirmation selects no specialist")
    not_proposed = set(confirmation.confirmed_categories) - set(proposal.categories)
    if not_proposed:
        raise ConfirmationRefused("confirmation selects categories that were not proposed")
    if confirmation.expires_at <= now:
        raise ConfirmationRefused("confirmation has expired")
    ledger.consume(confirmation)
