"""Draft SOW assembly and structured rendering (S7-08, S7-09).

The assembled SOW is a reviewable draft. It is never final, is marked with a watermark and an
approval state, and carries no authority. Every item keeps the references it was built from. A
requirement keeps its provenance label, so an inference never reads as a client statement. The
estimate section states a total only when the estimate is complete (see estimates.py).

Preview and export come from one renderer (render_html), so the two cannot drift apart. All text
is HTML-escaped, including source text that came from documents, because it is untrusted.

Every input is of its exact type (see textutil). A DraftSow compares its stored derived fields with
values it recomputes from its source, field by field, so a caller cannot substitute them.
"""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Context, Decimal

from webdesk.review.estimates import (
    SUM_PRECISION,
    EstimateLine,
    EstimateSet,
    LineStatus,
    decimal_text,
    render_total,
    total_estimate,
)
from webdesk.review.evidence import Citation, CitationView, render_citation
from webdesk.review.provenance import (
    ConfirmationState,
    Requirement,
    SourceType,
    pending_inferred_ids,
)
from webdesk.review.textutil import clean_key, clean_text, exact, items_of

DRAFT_WATERMARK = "DRAFT - NOT APPROVED - NOT FOR CLIENT RELEASE"
APPROVAL_STATE = "draft_unapproved"
SOW_ID_PREFIX = "SOW-"

_VIEW_TEXT_FIELDS = (
    "citation_id",
    "source_ref",
    "source_label",
    "confidence_label",
    "edition",
    "version",
    "note",
)


@dataclass(frozen=True)
class SowItem:
    """One statement in the SOW. It must name at least one reference (source, finding or line)."""

    text: str
    refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", clean_text(self.text, "a SOW item needs text"))
        refs = items_of(self.refs, str, "every SOW item must carry text references")
        if not refs:
            raise ValueError("every SOW item must carry at least one non-empty reference")
        cleaned = tuple(
            clean_key(ref, "every SOW item must carry at least one non-empty reference")
            for ref in refs
        )
        object.__setattr__(self, "refs", cleaned)


@dataclass(frozen=True)
class DraftSowInput:
    title: str
    objective: str
    in_scope: tuple[SowItem, ...]
    out_of_scope: tuple[SowItem, ...]
    deliverables: tuple[SowItem, ...]
    acceptance_criteria: tuple[SowItem, ...]
    dependencies: tuple[SowItem, ...] = ()
    assumptions: tuple[SowItem, ...] = ()
    exclusions: tuple[SowItem, ...] = ()
    uncertainties: tuple[SowItem, ...] = ()
    risks: tuple[SowItem, ...] = ()
    requirements: tuple[Requirement, ...] = ()
    estimate: EstimateSet | None = None
    citations: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", clean_text(self.title, "a draft SOW needs a title"))
        object.__setattr__(
            self, "objective", clean_text(self.objective, "a draft SOW needs an objective")
        )
        for name in (
            "in_scope",
            "out_of_scope",
            "deliverables",
            "acceptance_criteria",
            "dependencies",
            "assumptions",
            "exclusions",
            "uncertainties",
            "risks",
        ):
            object.__setattr__(
                self, name, items_of(getattr(self, name), SowItem, "a SOW section holds SowItems")
            )
        requirements = items_of(
            self.requirements, Requirement, "the requirements must be Requirement values"
        )
        requirement_ids = [req.requirement_id for req in requirements]
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ValueError("requirement identifiers must be unique in a draft")
        object.__setattr__(self, "requirements", requirements)
        object.__setattr__(
            self,
            "citations",
            items_of(self.citations, Citation, "the citations must be Citation values"),
        )
        if self.estimate is not None:
            exact(self.estimate, EstimateSet, "a draft SOW holds an EstimateSet or no estimate")
        if not (self.in_scope and self.deliverables and self.acceptance_criteria):
            raise ValueError(
                "a draft SOW needs in-scope items, deliverables and acceptance criteria"
            )


@dataclass(frozen=True)
class DraftSow:
    sow_id: str
    source: DraftSowInput
    citation_views: tuple[CitationView, ...]
    estimate_summary: str | None
    watermark: str = DRAFT_WATERMARK
    approval_state: str = APPROVAL_STATE

    def __post_init__(self) -> None:
        exact(self.source, DraftSowInput, "a draft SOW is built from a DraftSowInput")
        _require_draft(self)
        # Derived fields are recomputed, never trusted. A caller cannot supply a total, a citation
        # status or an identifier that the source does not produce.
        if type(self.sow_id) is not str or self.sow_id != _sow_identifier(self.source):
            raise ValueError("the SOW identifier does not match its source")
        expected_summary = _estimate_summary(self.source.estimate)
        if type(self.estimate_summary) is not type(expected_summary) or (
            self.estimate_summary != expected_summary
        ):
            raise ValueError("the estimate summary does not match its source")
        expected_views = tuple(render_citation(c) for c in self.source.citations)
        if not _same_views(self.citation_views, expected_views):
            raise ValueError("the citation views do not match their source")


def _require_draft(sow: DraftSow) -> None:
    """The watermark and the draft state are fixed. Nothing in this module can change them."""
    if type(sow.watermark) is not str or sow.watermark != DRAFT_WATERMARK:
        raise ValueError("a draft SOW must carry the draft watermark")
    if type(sow.approval_state) is not str or sow.approval_state != APPROVAL_STATE:
        raise ValueError("a draft SOW must carry the draft state")


def _same_views(views: tuple[CitationView, ...], expected: tuple[CitationView, ...]) -> bool:
    if type(views) is not tuple or len(views) != len(expected):
        return False
    for view, want in zip(views, expected, strict=True):
        if type(view) is not CitationView:
            return False
        for name in _VIEW_TEXT_FIELDS:
            got = getattr(view, name)
            if type(got) is not str or got != getattr(want, name):
                return False
        if type(view.verified) is not bool or view.verified != want.verified:
            return False
    return True


def assemble_draft_sow(source: DraftSowInput) -> DraftSow:
    """Build the draft. The identifier is derived from the input, so equal inputs give equal ids."""
    source = exact(source, DraftSowInput, "a draft SOW is built from a DraftSowInput")
    return DraftSow(
        sow_id=_sow_identifier(source),
        source=source,
        citation_views=tuple(render_citation(citation) for citation in source.citations),
        estimate_summary=_estimate_summary(source.estimate),
    )


def render_html(sow: DraftSow) -> str:
    """Render the draft as an HTML document. Preview and export both use this output."""
    sow = exact(sow, DraftSow, "only a DraftSow can be rendered")
    _require_draft(sow)
    source = sow.source
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="robots" content="noindex">',
        f"<title>{_e(source.title)}</title>",
        "</head>",
        "<body>",
        f'<div class="draft-watermark" role="status">{_e(sow.watermark)}</div>',
        f"<h1>{_e(source.title)}</h1>",
        f'<p class="sow-identity">Identifier {_e(sow.sow_id)}. '
        f"Approval state: {_e(sow.approval_state)}. Not final, not signed off.</p>",
        f"<h2>Objective</h2><p>{_e(source.objective)}</p>",
    ]
    pending = pending_inferred_ids(source.requirements)
    for heading, items in (
        ("In scope", source.in_scope),
        ("Out of scope", source.out_of_scope),
        ("Deliverables", source.deliverables),
        ("Dependencies", source.dependencies),
        ("Assumptions", source.assumptions),
        ("Exclusions", source.exclusions),
        ("Uncertainties", source.uncertainties),
        ("Risks", source.risks),
        ("Acceptance criteria", source.acceptance_criteria),
    ):
        parts.append(_items_section(heading, items, pending))
    parts.append(_requirements_section(source.requirements))
    parts.append(_estimate_section(sow))
    parts.append(_citations_section(sow.citation_views))
    parts.extend(["</body>", "</html>", ""])
    return "\n".join(parts)


def export_bytes(sow: DraftSow) -> bytes:
    return render_html(sow).encode("utf-8")


def _sow_identifier(source: DraftSowInput) -> str:
    canonical = json.dumps(
        asdict(source), sort_keys=True, separators=(",", ":"), default=_canonical_value
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{SOW_ID_PREFIX}{digest[:16].upper()}"


def _canonical_value(value: object) -> str:
    """One text form per value, so that equal values give equal identifiers.

    Decimal values are normalised (1.5 and 1.50 are the same hours). Datetimes are written in UTC
    (the same instant with a different offset is the same time). Anything else is refused.
    """
    if type(value) is Decimal:
        return format(value.normalize(Context(prec=SUM_PRECISION)), "f")
    if type(value) is datetime:
        return value.astimezone(UTC).isoformat()
    raise TypeError(f"no canonical form for {type(value).__name__}")


def _estimate_summary(estimate: EstimateSet | None) -> str | None:
    if estimate is None:
        return None
    return render_total(estimate, total_estimate(estimate))


def _e(value: str) -> str:
    return html.escape(value, quote=True)


def _items_section(heading: str, items: tuple[SowItem, ...], pending: frozenset[str]) -> str:
    if not items:
        return f"<h2>{_e(heading)}</h2><p>None stated.</p>"
    rows = "".join(_item_row(item, pending) for item in items)
    return f"<h2>{_e(heading)}</h2><ul>{rows}</ul>"


def _item_row(item: SowItem, pending: frozenset[str]) -> str:
    # An item that rests on an unacknowledged inference says so, wherever it appears.
    unresolved = [ref for ref in item.refs if ref in pending]
    flag = (
        f' <span class="provenance">Rests on unacknowledged inference: '
        f"{_e(', '.join(unresolved))}</span>"
        if unresolved
        else ""
    )
    return (
        f"<li>{_e(item.text)} <span class=\"refs\">References: "
        f"{_e(', '.join(item.refs))}</span>{flag}</li>"
    )


def _requirements_section(requirements: tuple[Requirement, ...]) -> str:
    if not requirements:
        return "<h2>Requirements</h2><p>No requirements recorded.</p>"
    sections = []
    for source_type, heading in (
        (SourceType.CLIENT_STATED, "Client-stated requirements"),
        (SourceType.INFERRED, "Inferred requirements (not client-stated)"),
    ):
        selected = [req for req in requirements if req.source_type == source_type]
        rows = "".join(_requirement_row(req) for req in selected) or "<li>None.</li>"
        sections.append(f"<h3>{_e(heading)}</h3><ul>{rows}</ul>")
    return "<h2>Requirements</h2>" + "".join(sections)


def _requirement_row(req: Requirement) -> str:
    state = "confirmed" if req.confirmation == ConfirmationState.CONFIRMED else "pending review"
    ack = req.acknowledgement
    if ack is not None:
        state += (
            f", acknowledged by {ack.reviewer_id} at "
            f"{ack.acknowledged_at.astimezone(UTC).isoformat()} (reason: {ack.reason})"
        )
    return (
        f"<li>{_e(req.requirement_id)}: {_e(req.text)} "
        f'<span class="provenance">{_e(req.source_label)}; {_e(state)}; '
        f"source {_e(req.source_ref)}</span></li>"
    )


def _estimate_section(sow: DraftSow) -> str:
    estimate = sow.source.estimate
    if estimate is None or sow.estimate_summary is None:
        return "<h2>Estimated effort</h2><p>No estimate recorded; no total is stated.</p>"
    pending = pending_inferred_ids(sow.source.requirements)
    rows = "".join(_estimate_row(line, pending) for line in estimate.lines)
    return (
        f"<h2>Estimated effort</h2><p>{_e(sow.estimate_summary)}</p>"
        f"<p>Owner: {_e(estimate.owner)}. Version {_e(str(estimate.version))}.</p><ul>{rows}</ul>"
    )


def _estimate_row(line: EstimateLine, pending: frozenset[str]) -> str:
    # A line that rests on an unacknowledged inference says so, as an SOW item does (QA 6, D-5).
    flag = (
        f' <span class="provenance">Rests on unacknowledged inference: '
        f"{_e(line.provenance_ref)}</span>"
        if line.provenance_ref in pending
        else ""
    )
    if line.status == LineStatus.ESTIMATED:
        hours = f"{decimal_text(line.low_hours)}-{decimal_text(line.high_hours)} hours"
    elif line.status == LineStatus.UNCERTAIN:
        hours = "uncertain, hours not stated"
    else:
        hours = "not estimated, hours not stated"
    assumptions = "; ".join(line.assumptions) or "none stated"
    drivers = "; ".join(line.complexity_drivers) or "none stated"
    dependencies = "; ".join(line.dependencies) or "none stated"
    return (
        f"<li>{_e(line.line_id)}: {_e(line.work_item)} ({_e(line.scope_boundary)}). "
        f"{_e(hours)}. Complexity drivers: {_e(drivers)}. Dependencies: {_e(dependencies)}. "
        f"Assumptions: {_e(assumptions)}. Reference: {_e(line.provenance_ref)}{flag}</li>"
    )


def _citations_section(views: tuple[CitationView, ...]) -> str:
    if not views:
        return "<h2>Evidence</h2><p>No citations recorded.</p>"
    rows = "".join(
        f"<li>{_e(view.citation_id)}: {_e(view.source_ref)}. "
        f"Source status: {_e(view.source_label)}. Confidence: {_e(view.confidence_label)}. "
        f"Edition: {_e(view.edition)}. Version: {_e(view.version)}. "
        f"Verified: {'yes' if view.verified else 'no'}."
        + (f" {_e(view.note)}" if view.note else "")
        + "</li>"
        for view in views
    )
    return f"<h2>Evidence</h2><ul>{rows}</ul>"
