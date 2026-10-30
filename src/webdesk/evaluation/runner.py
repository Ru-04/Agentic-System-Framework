"""Runner that scores Sprint 5 scenarios with the deterministic requirement rules.

This runner calls the same ``decide`` rule the investigation provider uses, and applies the
active-source boundary from S4-PILOT-EVIDENCE-01. It does not fetch pages, so it never returns
citations. A supported outcome from this runner therefore scores as uncited support, and no
scenario is evaluated against real documentation here.

It does not reproduce the redirect check, the sibling-page refusal or the synthetic provider path.
Those outcomes are reported as mismatches where the scenario expects them.
"""

from __future__ import annotations

from typing import Final

from webdesk.evaluation.dataset import Outcome, Scenario
from webdesk.evaluation.harness import Observation
from webdesk.investigation.specialists import Decision, decide
from webdesk.specialists.catalog import SpecialistId

# Specialists with an active documentation source. Set by S4-PILOT-EVIDENCE-01 (WooCommerce docs
# and the BigCommerce product page). Every other source is inactive. Keep this in step with the
# approved pilot decision; changing it needs its own approval.
ACTIVE_SOURCE_SPECIALISTS: Final[frozenset[SpecialistId]] = frozenset(
    {SpecialistId.WORDPRESS_WOOCOMMERCE, SpecialistId.BIGCOMMERCE}
)

_DECISION_TO_OUTCOME: Final[dict[Decision, Outcome]] = {
    Decision.INVESTIGATE: Outcome.INVESTIGATE,
    Decision.INVESTIGATE_WITH_UNKNOWNS: Outcome.INVESTIGATE_WITH_UNKNOWNS,
    Decision.CLARIFY: Outcome.CLARIFY,
    Decision.REFUSE: Outcome.REFUSE,
}


def observe(scenario: Scenario) -> Observation:
    """Classify one scenario. The requested version is not stated in any scenario, so it is None.

    The operator is taken as confirmed for the evaluation. The scenarios do not test the
    confirmation refusal, which the provider path already covers.
    """
    decision, _reason = decide(
        scenario.specialist_id,
        scenario.requirement,
        requested_version=None,
        operator_confirmed=True,
    )
    outcome = _DECISION_TO_OUTCOME[decision]
    if outcome in {Outcome.INVESTIGATE, Outcome.INVESTIGATE_WITH_UNKNOWNS}:
        if scenario.specialist_id not in ACTIVE_SOURCE_SPECIALISTS:
            return Observation(outcome=Outcome.UNSUPPORTED_SOURCE)
    return Observation(outcome=outcome)
