"""Draft estimate line items and deterministic totals (S7-06).

PROPOSAL, NOT AN APPROVED SCHEMA. The repository has no approved estimate schema. The field set
below is a labelled proposal for WDS review. Approval, revision history and authorization are
S7-07 and are not implemented here, so every estimate set is a draft.

Rules enforced here:
- An unestimated or uncertain line has no hours. Its hours are never stored as zero.
- A total never counts unestimated or uncertain work as zero. A partial set states no total at all;
  it names the counts of unresolved work, and the per-line ranges stay visible in the SOW.
- No line carries a single exact figure. An estimated line is a range (low, high).
- Hours are Decimal values with a bounded number of significant digits, summed under an explicit
  precision, so every total is exact and independent of line order.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from enum import StrEnum

# Every estimate set is a draft until S7-07 provides an authorized approval path.
DRAFT_STATE = "draft"

# Hours inputs are bounded so that the exact sum always fits the arithmetic precision below. The
# exponent bound keeps the smallest value at 1E-6 hours, so 30 digits span every input exactly.
MAX_HOURS = Decimal(1_000_000)
MIN_ADJUSTED_EXPONENT = -6
MAX_SIGNIFICANT_DIGITS = 30
SUM_PRECISION = 80


class LineStatus(StrEnum):
    ESTIMATED = "estimated"
    UNESTIMATED = "unestimated"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class EstimateLine:
    line_id: str
    work_item: str
    scope_boundary: str
    status: LineStatus
    provenance_ref: str
    low_hours: Decimal | None = None
    high_hours: Decimal | None = None
    complexity_drivers: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", LineStatus(self.status))
        for name, value in (
            ("line identifier", self.line_id),
            ("work item", self.work_item),
            ("scope boundary", self.scope_boundary),
            ("provenance reference", self.provenance_ref),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"an estimate line needs a {name}")
        if self.status == LineStatus.ESTIMATED:
            self._check_range()
        elif self.low_hours is not None or self.high_hours is not None:
            raise ValueError("an unestimated or uncertain line must not carry hours")

    def _check_range(self) -> None:
        if self.low_hours is None or self.high_hours is None:
            raise ValueError("an estimated line needs both a low and a high figure")
        low = _hours(self.low_hours)
        high = _hours(self.high_hours)
        if high < low:
            raise ValueError("estimated hours need low <= high")
        object.__setattr__(self, "low_hours", low)
        object.__setattr__(self, "high_hours", high)
        if not any(isinstance(item, str) and item.strip() for item in self.assumptions):
            raise ValueError("an estimated line needs at least one stated assumption")


@dataclass(frozen=True)
class EstimateSet:
    estimate_id: str
    version: int
    owner: str
    lines: tuple[EstimateLine, ...]

    def __post_init__(self) -> None:
        if not self.estimate_id.strip() or not self.owner.strip():
            raise ValueError("an estimate set needs an identifier and an owner")
        if self.version < 1:
            raise ValueError("an estimate set version starts at 1")
        # Copy into a tuple first: a generator is consumed once, and a caller's list cannot change
        # the set after the checks below have run.
        lines = tuple(self.lines)
        if not all(isinstance(line, EstimateLine) for line in lines):
            raise ValueError("an estimate set holds only EstimateLine values")
        object.__setattr__(self, "lines", lines)
        if not lines:
            raise ValueError("an estimate set needs at least one line")
        ids = [line.line_id for line in lines]
        if len(set(ids)) != len(ids):
            raise ValueError("estimate line identifiers must be unique")

    @property
    def state(self) -> str:
        return DRAFT_STATE


@dataclass(frozen=True)
class EstimateTotal:
    """Counts and known hours. The known sums are internal; a partial total is never published."""

    known_low: Decimal | None
    known_high: Decimal | None
    estimated_count: int
    unestimated_count: int
    uncertain_count: int

    @property
    def complete(self) -> bool:
        return (
            self.estimated_count > 0 and self.unestimated_count == 0 and self.uncertain_count == 0
        )

    def publishable_range(self) -> tuple[Decimal, Decimal] | None:
        """The total range, or None while any line is unestimated or uncertain."""
        if not self.complete or self.known_low is None or self.known_high is None:
            return None
        return self.known_low, self.known_high


def total_estimate(estimate: EstimateSet) -> EstimateTotal:
    estimated = [line for line in estimate.lines if line.status == LineStatus.ESTIMATED]
    return EstimateTotal(
        known_low=_sum(line.low_hours for line in estimated),
        known_high=_sum(line.high_hours for line in estimated),
        estimated_count=len(estimated),
        unestimated_count=_count(estimate.lines, LineStatus.UNESTIMATED),
        uncertain_count=_count(estimate.lines, LineStatus.UNCERTAIN),
    )


def render_total(estimate: EstimateSet, total: EstimateTotal) -> str:
    """A plain-text statement of the total. A partial set states no total."""
    header = f"Draft estimate {estimate.estimate_id} v{estimate.version} (state: {estimate.state})"
    if total.complete:
        body = f"total {_range_text(total.known_low, total.known_high)} hours"
    elif total.estimated_count == 0:
        body = "no line is estimated; no total is stated"
    else:
        body = (
            f"partial; total not stated: {total.unestimated_count} unestimated and "
            f"{total.uncertain_count} uncertain line(s) are unresolved; "
            f"{total.estimated_count} line(s) carry their own ranges"
        )
    return f"{header}: {body}."


def _hours(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise ValueError("estimated hours must be a Decimal, not a float or text")
    if not value.is_finite():
        raise ValueError("estimated hours must be finite")
    if value < 0:
        raise ValueError("estimated hours must not be negative")
    if value > MAX_HOURS:
        raise ValueError("estimated hours exceed the bound for a single line")
    if value.is_zero():
        return Decimal(0)
    if len(value.as_tuple().digits) > MAX_SIGNIFICANT_DIGITS:
        raise ValueError("estimated hours have too many significant digits")
    if value.adjusted() < MIN_ADJUSTED_EXPONENT:
        raise ValueError("estimated hours are below the smallest bound for a single line")
    return value


def _sum(values: Iterable[Decimal | None]) -> Decimal | None:
    items = [value for value in values if value is not None]
    if not items:
        return None
    with localcontext() as context:
        context.prec = SUM_PRECISION
        return sum(items, Decimal(0))


def _count(lines: Sequence[EstimateLine], status: LineStatus) -> int:
    return sum(1 for line in lines if line.status == status)


def _range_text(low: Decimal | None, high: Decimal | None) -> str:
    if low is None or high is None:
        return "none"
    return f"{low}-{high}"
