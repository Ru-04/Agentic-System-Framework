"""Draft estimate line items and deterministic totals (S7-06).

PROPOSAL, NOT AN APPROVED SCHEMA. The repository has no approved estimate schema. The field set
below is a labelled proposal for WDS review. Approval, revision history and authorization are
S7-07 and are not implemented here, so every estimate set is a draft.

Rules enforced here:
- An unestimated or uncertain line has no hours. Its hours are never stored as zero.
- A total never counts unestimated or uncertain work as zero. A partial set states no total at all;
  it names the counts of unresolved work, and the per-line ranges stay visible in the SOW.
- An estimated line is a range (low, high). A degenerate range with low equal to high is allowed.
- Hours are exact Decimal values with a bounded number of significant digits and exponent, summed
  under an explicit precision, so every total is exact and independent of line order.
- Every input is of its exact type (see textutil). A total is publishable only when it is computed
  from its estimate here; no caller-supplied total is trusted.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from enum import StrEnum

from webdesk.review.textutil import clean_key, clean_text, enum_of, exact, items_of, text_items

# Every estimate set is a draft until S7-07 provides an authorized approval path.
DRAFT_STATE = "draft"

# Hours inputs are bounded so that the exact sum always fits the arithmetic precision below. The
# exponent bound keeps the leading digit at or above 1E-6 hours. A value of up to 30 significant
# digits can still extend below that, down to about 1E-35; sums remain exact at SUM_PRECISION.
MAX_HOURS = Decimal(1_000_000)
MIN_ADJUSTED_EXPONENT = -6
MAX_SIGNIFICANT_DIGITS = 30
SUM_PRECISION = 80

_TOTAL_FIELDS = (
    "known_low",
    "known_high",
    "estimated_count",
    "unestimated_count",
    "uncertain_count",
)


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
        object.__setattr__(self, "status", enum_of(self.status, LineStatus, "unknown line status"))
        object.__setattr__(
            self, "line_id", clean_key(self.line_id, "an estimate line needs a line identifier")
        )
        object.__setattr__(
            self, "work_item", clean_text(self.work_item, "an estimate line needs a work item")
        )
        object.__setattr__(
            self,
            "scope_boundary",
            clean_text(self.scope_boundary, "an estimate line needs a scope boundary"),
        )
        object.__setattr__(
            self,
            "provenance_ref",
            clean_key(self.provenance_ref, "an estimate line needs a provenance reference"),
        )
        for name in ("complexity_drivers", "dependencies", "assumptions"):
            items = text_items(getattr(self, name), f"the estimate line {name} must hold text only")
            cleaned = tuple(
                clean_text(item, f"the estimate line {name} must hold non-empty text")
                for item in items
            )
            object.__setattr__(self, name, cleaned)
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
        if not self.assumptions:
            raise ValueError("an estimated line needs at least one stated assumption")


@dataclass(frozen=True)
class EstimateSet:
    estimate_id: str
    version: int
    owner: str
    lines: tuple[EstimateLine, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "estimate_id", clean_key(self.estimate_id, "an estimate set needs an identifier")
        )
        object.__setattr__(self, "owner", clean_text(self.owner, "an estimate set needs an owner"))
        if type(self.version) is not int:
            raise ValueError("an estimate set version is a whole number")
        if self.version < 1:
            raise ValueError("an estimate set version starts at 1")
        lines = items_of(self.lines, EstimateLine, "an estimate set holds only EstimateLine values")
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
    """Counts and known hours computed by total_estimate. Use publishable_range for a total."""

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


def total_estimate(estimate: EstimateSet) -> EstimateTotal:
    """The counts for an estimate, and its sum only when every line is estimated.

    For a partial estimate the sums are None. A sum over the estimated lines would count the
    unresolved lines as zero, so none is given (QA 6, D-4).
    """
    estimate = exact(estimate, EstimateSet, "a total is computed from an EstimateSet")
    estimated = [line for line in estimate.lines if line.status == LineStatus.ESTIMATED]
    unestimated = _count(estimate.lines, LineStatus.UNESTIMATED)
    uncertain = _count(estimate.lines, LineStatus.UNCERTAIN)
    complete = bool(estimated) and unestimated == 0 and uncertain == 0
    return EstimateTotal(
        known_low=_sum(line.low_hours for line in estimated) if complete else None,
        known_high=_sum(line.high_hours for line in estimated) if complete else None,
        estimated_count=len(estimated),
        unestimated_count=unestimated,
        uncertain_count=uncertain,
    )


def publishable_range(estimate: EstimateSet) -> tuple[Decimal, Decimal] | None:
    """The total range for ``estimate``, or None while any line is unestimated or uncertain."""
    total = total_estimate(estimate)
    if not total.complete or total.known_low is None or total.known_high is None:
        return None
    return total.known_low, total.known_high


def render_total(estimate: EstimateSet, total: EstimateTotal) -> str:
    """A plain-text statement of the total. A partial set states no total.

    The total is recomputed from the estimate. A total supplied by a caller that does not match the
    estimate, field for field and by exact type, is refused.
    """
    expected = total_estimate(estimate)
    if type(total) is not EstimateTotal or not _same_total(total, expected):
        raise ValueError("the total does not match its estimate")
    header = f"Draft estimate {estimate.estimate_id} v{estimate.version} (state: {estimate.state})"
    if expected.complete:
        body = f"total {_range_text(expected.known_low, expected.known_high)} hours"
    elif expected.estimated_count == 0:
        body = "no line is estimated; no total is stated"
    else:
        body = (
            f"partial; total not stated: {expected.unestimated_count} unestimated and "
            f"{expected.uncertain_count} uncertain line(s) are unresolved; "
            f"{expected.estimated_count} line(s) carry their own ranges"
        )
    return f"{header}: {body}."


def _same_total(total: EstimateTotal, expected: EstimateTotal) -> bool:
    for name in _TOTAL_FIELDS:
        left = getattr(total, name)
        right = getattr(expected, name)
        if type(left) is not type(right) or left != right:
            return False
    return True


def _hours(value: object) -> Decimal:
    plain = exact(
        value, Decimal, "estimated hours must be a Decimal, not a float, text or subclass"
    )
    if not plain.is_finite():
        raise ValueError("estimated hours must be finite")
    if plain < 0:
        raise ValueError("estimated hours must not be negative")
    if plain > MAX_HOURS:
        raise ValueError("estimated hours exceed the bound for a single line")
    if plain.is_zero():
        return Decimal(0)
    if len(plain.as_tuple().digits) > MAX_SIGNIFICANT_DIGITS:
        raise ValueError("estimated hours have too many significant digits")
    if plain.adjusted() < MIN_ADJUSTED_EXPONENT:
        raise ValueError("estimated hours are below the smallest bound for a single line")
    return plain


def _sum(values: Iterable[Decimal | None]) -> Decimal | None:
    items = [value for value in values if value is not None]
    if not items:
        return None
    with localcontext() as context:
        context.prec = SUM_PRECISION
        return sum(items, Decimal(0))


def _count(lines: Sequence[EstimateLine], status: LineStatus) -> int:
    return sum(1 for line in lines if line.status == status)


def decimal_text(value: Decimal | None) -> str:
    """One text form per numeric value (1.5 and 1.50 both read 1.5; 1E+2 reads 100)."""
    if value is None:
        return "none"
    plain = exact(value, Decimal, "a number is written from an exact Decimal")
    if not plain.is_finite():
        raise ValueError("a number written as text must be finite")
    if not plain.is_zero() and not (-MIN_ADJUSTED_EXPONENT - 40 <= plain.adjusted() <= 40):
        # The bound is far wider than any hours value the model accepts, so it only stops a
        # caller from writing a value of millions of digits.
        raise ValueError("a number written as text is outside the supported range")
    return format(plain.normalize(Context(prec=SUM_PRECISION)), "f")


def _range_text(low: Decimal | None, high: Decimal | None) -> str:
    if low is None or high is None:
        return "none"
    return f"{decimal_text(low)}-{decimal_text(high)}"
