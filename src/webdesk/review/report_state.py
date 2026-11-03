"""Report state: staleness, incomplete evidence and regeneration (S7-11, model only).

A report is a snapshot of one run. The snapshot records the inputs it was built from, the run
outcome and any evidence that is missing. Three rules are enforced here:

- Stale detection. A snapshot is stale when the current input set does not hash to the same value as
  the recorded input set. The hash is the Foundation's input_revision_hash
  (src/webdesk/runs/hashing.py), so staleness uses the same definition as the run guard.
- No concealed incompleteness. A report is complete only when the run completed and no evidence is
  missing. A partial, canceled or failed run, or a run with missing evidence, is never reported as
  complete, and this module never claims full verification.
- Regeneration keeps history. A failed or canceled regeneration returns the prior records unchanged.
  A regeneration that completes appends its snapshot; no earlier record is removed.

NOT implemented here, and blocked: the live run lifecycle (partial specialist results and the
cancel and fail transitions in the Sprint 6 run service) needs the Sprint 6 integration (S6-INT).
Persistence of snapshots needs the audit and persistence contract (S7-10).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from webdesk.review.textutil import clean_key, enum_of, exact, items_of
from webdesk.runs.hashing import InputTuple, input_revision_hash


class RunOutcome(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    CANCELED = "canceled"
    FAILED = "failed"


@dataclass(frozen=True)
class ReportSnapshot:
    report_id: str
    outcome: RunOutcome
    inputs: tuple[InputTuple, ...]
    missing_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", clean_key(self.report_id, "a report needs an id"))
        object.__setattr__(
            self, "outcome", enum_of(self.outcome, RunOutcome, "unknown run outcome")
        )
        inputs = _checked_inputs(self.inputs, "a snapshot holds InputTuple values")
        if not inputs:
            raise ValueError("a snapshot needs at least one recorded input")
        object.__setattr__(self, "inputs", inputs)
        missing = tuple(
            clean_key(item, "missing evidence must be named")
            for item in items_of(self.missing_evidence, str, "missing evidence must be text")
        )
        object.__setattr__(self, "missing_evidence", missing)


@dataclass(frozen=True)
class Assessment:
    report_id: str
    stale: bool
    complete: bool
    outcome: RunOutcome
    missing_evidence: tuple[str, ...]


def assess(snapshot: ReportSnapshot, current_inputs: tuple[InputTuple, ...]) -> Assessment:
    """Judge a snapshot against the current inputs. Nothing is changed."""
    snapshot = exact(snapshot, ReportSnapshot, "a report is judged from a ReportSnapshot")
    current = _checked_inputs(current_inputs, "current inputs must be InputTuple values")
    stale = input_revision_hash(snapshot.inputs) != input_revision_hash(current)
    complete = (
        snapshot.outcome == RunOutcome.COMPLETED and not snapshot.missing_evidence and not stale
    )
    return Assessment(
        report_id=snapshot.report_id,
        stale=stale,
        complete=complete,
        outcome=snapshot.outcome,
        missing_evidence=snapshot.missing_evidence,
    )


def status_line(assessment: Assessment) -> str:
    """The text a report shows. It never says the report is fully verified."""
    assessment = exact(assessment, Assessment, "a status line is written from an Assessment")
    missing = ", ".join(assessment.missing_evidence) or "none recorded"
    if assessment.stale:
        return (
            f"Stale: the inputs changed after this report ({assessment.report_id}); "
            f"missing evidence: {missing}."
        )
    if assessment.complete:
        return f"Complete run; citations remain unverified ({assessment.report_id})."
    missing = ", ".join(assessment.missing_evidence) or "none recorded"
    return (
        f"Incomplete: run {assessment.outcome} ({assessment.report_id}); "
        f"missing evidence: {missing}."
    )


def _checked_inputs(values: object, message: str) -> tuple[InputTuple, ...]:
    """Exact input tuples with exact field types, each entity at most once."""
    items = items_of(values, InputTuple, message)
    seen: set[tuple[str, str]] = set()
    for item in items:
        if type(item.entity_type) is not str or type(item.entity_id) is not str:
            raise ValueError("an input's entity type and identifier must be text")
        if type(item.revision) is not int or item.revision < 0:
            raise ValueError("an input's revision is a whole number from 0")
        key = (item.entity_type, item.entity_id)
        if key in seen:
            raise ValueError("each entity may appear once in a snapshot")
        seen.add(key)
    return items


def regenerate(
    prior: tuple[ReportSnapshot, ...], attempt: ReportSnapshot
) -> tuple[ReportSnapshot, ...]:
    """Return the history after a regeneration attempt. Prior records are never removed."""
    history = items_of(prior, ReportSnapshot, "prior records must be ReportSnapshot values")
    attempt_checked = items_of((attempt,), ReportSnapshot, "an attempt is a ReportSnapshot")[0]
    if attempt_checked.outcome in (RunOutcome.CANCELED, RunOutcome.FAILED):
        return history
    return history + (attempt_checked,)
