"""Draft SOW assembly and structured rendering (S7-08, S7-09).

The assembled SOW is a reviewable draft. It is never final, is marked with a watermark and an
approval state, and carries no authority. Every item keeps the references it was built from. A
requirement keeps its provenance label, so an inference never reads as a client statement. The
estimate section states a total only when the estimate is complete (see estimates.py).

Preview and export come from one renderer (render_html), so the two cannot drift apart. All text
is HTML-escaped, including source text that came from documents, because it is untrusted.
"""

from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, dataclass

from webdesk.review.estimates import (
    EstimateLine,
    EstimateSet,
    LineStatus,
    render_total,
    total_estimate,
)
from webdesk.review.evidence import Citation, CitationView, render_citation
from webdesk.review.provenance import ConfirmationState, Requirement, SourceType

DRAFT_WATERMARK = "DRAFT - NOT APPROVED - NOT FOR CLIENT RELEASE"
APPROVAL_STATE = "draft_unapproved"
SOW_ID_PREFIX = "SOW-"


@dataclass(frozen=True)
class SowItem:
    """One statement in the SOW. It must name at least one reference (source, finding or line)."""

    text: str
    refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a SOW item needs text")
        if not self.refs or not all(ref.strip() for ref in self.refs):
            raise ValueError("every SOW item must carry at least one non-empty reference")


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
        if not self.title.strip() or not self.objective.strip():
            raise ValueError("a draft SOW needs a title and an objective")
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


def assemble_draft_sow(source: DraftSowInput) -> DraftSow:
    """Build the draft. The identifier is derived from the input, so equal inputs give equal ids."""
    return DraftSow(
        sow_id=_sow_identifier(source),
        source=source,
        citation_views=tuple(render_citation(citation) for citation in source.citations),
        estimate_summary=_estimate_summary(source.estimate),
    )


def render_html(sow: DraftSow) -> str:
    """Render the draft as an HTML document. Preview and export both use this output."""
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
        parts.append(_items_section(heading, items))
    parts.append(_requirements_section(source.requirements))
    parts.append(_estimate_section(sow))
    parts.append(_citations_section(sow.citation_views))
    parts.extend(["</body>", "</html>", ""])
    return "\n".join(parts)


def export_bytes(sow: DraftSow) -> bytes:
    return render_html(sow).encode("utf-8")


def _sow_identifier(source: DraftSowInput) -> str:
    canonical = json.dumps(asdict(source), sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{SOW_ID_PREFIX}{digest[:16].upper()}"


def _estimate_summary(estimate: EstimateSet | None) -> str | None:
    if estimate is None:
        return None
    return render_total(estimate, total_estimate(estimate))


def _e(value: str) -> str:
    return html.escape(value, quote=True)


def _items_section(heading: str, items: tuple[SowItem, ...]) -> str:
    if not items:
        return f"<h2>{_e(heading)}</h2><p>None stated.</p>"
    rows = "".join(
        f"<li>{_e(item.text)} <span class=\"refs\">References: "
        f"{_e(', '.join(item.refs))}</span></li>"
        for item in items
    )
    return f"<h2>{_e(heading)}</h2><ul>{rows}</ul>"


def _requirements_section(requirements: tuple[Requirement, ...]) -> str:
    if not requirements:
        return "<h2>Requirements</h2><p>No requirements recorded.</p>"
    sections = []
    for source_type, heading in (
        (SourceType.CLIENT_STATED, "Client-stated requirements"),
        (SourceType.INFERRED, "Inferred requirements (not client-stated)"),
    ):
        selected = [req for req in requirements if req.source_type is source_type]
        rows = "".join(_requirement_row(req) for req in selected) or "<li>None.</li>"
        sections.append(f"<h3>{_e(heading)}</h3><ul>{rows}</ul>")
    return "<h2>Requirements</h2>" + "".join(sections)


def _requirement_row(req: Requirement) -> str:
    state = "confirmed" if req.confirmation is ConfirmationState.CONFIRMED else "pending review"
    if req.acknowledgement is not None:
        state += f", acknowledged by {req.acknowledgement.reviewer_id}"
    return (
        f"<li>{_e(req.requirement_id)}: {_e(req.text)} "
        f'<span class="provenance">{_e(req.source_label)}; {_e(state)}; '
        f"source {_e(req.source_ref)}</span></li>"
    )


def _estimate_section(sow: DraftSow) -> str:
    estimate = sow.source.estimate
    if estimate is None or sow.estimate_summary is None:
        return "<h2>Estimated effort</h2><p>No estimate recorded; no total is stated.</p>"
    rows = "".join(_estimate_row(line) for line in estimate.lines)
    return f"<h2>Estimated effort</h2><p>{_e(sow.estimate_summary)}</p><ul>{rows}</ul>"


def _estimate_row(line: EstimateLine) -> str:
    if line.status is LineStatus.ESTIMATED:
        hours = f"{line.low_hours}-{line.high_hours} hours"
    elif line.status is LineStatus.UNCERTAIN:
        hours = "uncertain, hours not stated"
    else:
        hours = "not estimated, hours not stated"
    assumptions = "; ".join(line.assumptions) or "none stated"
    return (
        f"<li>{_e(line.line_id)}: {_e(line.work_item)} ({_e(line.scope_boundary)}). "
        f"{_e(hours)}. Assumptions: {_e(assumptions)}. "
        f"Reference: {_e(line.provenance_ref)}</li>"
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
