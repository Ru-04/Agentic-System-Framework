"""Read-only bridges from AI-S07 governance and AI-S06 orchestration into estimation inputs.

The estimator consumes these summaries; it never edits the review or the orchestration result.
"""

from __future__ import annotations

from ai_engine.estimation.contracts import GovernanceSummary
from ai_engine.governance.contracts import ReviewReport, Severity
from ai_engine.orchestration.workflow import OrchestrationResult


def governance_summary(report: ReviewReport) -> GovernanceSummary:
    """Summarise a review for estimation. Findings and statuses are copied, never changed."""
    blocking = frozenset(
        rid for f in report.findings if f.severity is Severity.BLOCKER for rid in f.requirement_ids
    )
    return GovernanceSummary(
        run_id=report.run_id,
        project_id=report.project_id,
        input_fingerprint=report.input_fingerprint,
        requirement_status={rid: status.value for rid, status in report.requirement_status.items()},
        blocking_requirement_ids=blocking,
        escalation_count=len(report.escalations),
        has_blocker=report.has_blocker,
    )


def specialist_result_refs(result: OrchestrationResult) -> dict[str, str]:
    """A reference per specialist outcome, so tasks can cite the specialist work they came from."""
    return {
        outcome.category_id: (
            f"{result.run_id}/{outcome.category_id}/"
            f"{outcome.specialist_status.value if outcome.specialist_status else 'none'}"
        )
        for outcome in result.outcomes
    }
