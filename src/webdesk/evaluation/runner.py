"""Runner that scores Sprint 5 scenarios with the deterministic requirement rules.

This runner calls the same ``decide`` rule the investigation provider uses, and applies the
active-source boundary from S4-PILOT-EVIDENCE-01. It does not fetch pages, so it never returns
citations. A supported outcome from this runner therefore scores as uncited support, and no
scenario is evaluated against real documentation here.

A request to follow a redirect is refused at requirement level, because source policy forbids
following redirects. The page-level redirect check, the sibling-page refusal and the synthetic
provider path are not run here. They are covered by the investigation unit tests.
"""

from __future__ import annotations

from typing import Final

from webdesk.evaluation.dataset import Outcome, Scenario
from webdesk.evaluation.harness import Observation
from webdesk.investigation.engine import (
    ACTIVE_BOUNDARIES,
    RELEASE_ONLY,
    Capability,
    ClaimKind,
    Edition,
    term_in_text,
)
from webdesk.investigation.specialists import Decision, decide, matched_capabilities, stated_version

# Activation is per capability boundary, read from the engine, so this runner and the investigation
# path cannot disagree. A feature claim from a release-only boundary is never active (MAGENTO-01).
_OPEN_SOURCE_TERM: Final = ("open source",)

_DECISION_TO_OUTCOME: Final[dict[Decision, Outcome]] = {
    Decision.INVESTIGATE: Outcome.INVESTIGATE,
    Decision.INVESTIGATE_WITH_UNKNOWNS: Outcome.INVESTIGATE_WITH_UNKNOWNS,
    Decision.CLARIFY: Outcome.CLARIFY,
    Decision.REFUSE: Outcome.REFUSE,
    Decision.UNSUPPORTED_SOURCE: Outcome.UNSUPPORTED_SOURCE,
}


def observe(scenario: Scenario) -> Observation:
    """Classify one scenario using the version the requirement itself states, if any.

    The operator is taken as confirmed for the evaluation. The scenarios do not test the
    confirmation refusal, which the provider path already covers.
    """
    decision, _reason = decide(
        scenario.specialist_id,
        scenario.requirement,
        requested_version=stated_version(scenario.requirement),
        operator_confirmed=True,
    )
    outcome = _DECISION_TO_OUTCOME[decision]
    if outcome in {Outcome.INVESTIGATE, Outcome.INVESTIGATE_WITH_UNKNOWNS}:
        if not _any_applicable_source(scenario):
            return Observation(outcome=Outcome.UNSUPPORTED_SOURCE)
    return Observation(outcome=outcome)


def _applicable(capability: Capability, requirement: str) -> bool:
    """A capability can be investigated only from an active boundary that fits the requirement."""
    key = (capability.platform, capability.edition)
    if key not in ACTIVE_BOUNDARIES:
        return False
    if key in RELEASE_ONLY and capability.claim_kind is ClaimKind.FEATURE:
        return False
    # ADOBE-01: an Adobe Commerce feature is not attributed to Magento Open Source.
    if capability.edition is Edition.ADOBE_COMMERCE and term_in_text(
        _OPEN_SOURCE_TERM[0], requirement
    ):
        return False
    return True


def _any_applicable_source(scenario: Scenario) -> bool:
    capabilities = matched_capabilities(scenario.specialist_id, scenario.requirement)
    return any(_applicable(c, scenario.requirement) for c in capabilities)
