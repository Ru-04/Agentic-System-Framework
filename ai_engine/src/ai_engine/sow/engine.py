"""
Detailed WDS draft Statement of Work engine (AI-S09).

Reads one ``SowRequest`` and returns one ``DraftSow``. It reads no Foundation data, network,
provider, clock or file. It never mutates its input. Output is a draft for human review: no
approved state, no approver identity, no price, rate, signature or commitment is produced.

Source text (requirements, findings, notes, client items and every other free-text field) is data.
It is copied verbatim, screened for instruction-like content, and never executed.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import TypeVar

from pydantic import ValidationError

from ai_engine.estimation.contracts import (
    EstimateDraft,
    EstimateLine,
    EstimateStatus,
    GovernanceSummary,
    Readiness,
    Totals,
    worst,
)
from ai_engine.sow.contracts import (
    Approval,
    DeliverableView,
    DocumentControl,
    DraftSow,
    MilestoneView,
    ResourceLine,
    ResourceView,
    ScopeDisposition,
    SectionState,
    SourceManifestEntry,
    SowChange,
    SowInputError,
    SowItem,
    SowRequest,
    SowRequirement,
    SowSection,
    TechTopic,
    TraceRow,
    WorkstreamView,
    sanitized,
)

_T = TypeVar("_T")

GENERATOR = "ai_engine.sow.engine (AI-S09)"
SEPARATION_RULE = (
    "The approver must be a different individual from the preparer and submitter (REVIEW_POLICY "
    "Gate F; D-05). This draft never assigns or records an approver."
)
APPROVAL_NOTE = (
    "Draft prepared by the system for human review. It is not an offer, a commitment or an "
    "approved SOW. Approval belongs to an authorised operator under the Foundation workflow."
)
ELAPSED_NOTE = (
    "Milestone sequence only. Elapsed duration is not derived from effort hours, and no calendar "
    "date is assigned."
)
RESOURCE_CAVEAT = (
    "Resource values are the AI-S08 draft estimate. Lines with no hours are not estimated. Totals "
    "marked incomplete exclude unresolved lines and are not the complete project estimate."
)
PENDING_DECISIONS = (
    "Pending WDS decision: house SOW template and section contract (D-10); approver separation "
    "application (REVIEW_POLICY Gate F, D-05); client and WDS responsibility wording (approved "
    "text not supplied)."
)
CALC_PROVENANCE = (
    "Structural sections are built only from supplied inputs. Effort values are copied from the "
    "AI-S08 draft estimate without rates, prices, weighting, contingency or expected value. "
    "Milestone sequence is not a calendar schedule. Acceptance criteria are listed in sorted order."
)
_INSTRUCTION = re.compile(
    r"\b(ignore|disregard|override|system prompt|approve|approved|sign(?:ed)?[- ]?off|"
    r"set (?:the )?status|execute|you are now)\b",
    re.IGNORECASE,
)
_STOP = frozenset({"the", "and", "for", "with", "that", "this", "from", "are", "must"})
_GOV_READINESS = {
    "evidence_backed": Readiness.READY_FOR_REVIEW,
    "not_evidence_verified": Readiness.PROVISIONAL,
    "unsupported": Readiness.UNRESOLVED,
    "conflicted": Readiness.BLOCKED,
}


def build_request(raw: Mapping[str, object]) -> SowRequest:
    """Parse untrusted input into a request. Errors name fields and error types, never values."""
    try:
        return SowRequest.model_validate(raw)
    except ValidationError as error:
        raise sanitized(error) from None


def _index_unique(
    items: Iterable[_T], identifier_of: Callable[[_T], str], label: str
) -> dict[str, _T]:
    result: dict[str, _T] = {}
    for item in items:
        identifier = identifier_of(item)
        if identifier in result:
            raise SowInputError(f"duplicate {label} identifier")
        result[identifier] = item
    return result


def _require_known(values: Iterable[str], known: Mapping[str, object], label: str) -> None:
    if any(value not in known for value in values):
        raise SowInputError(f"a {label} reference is not in the request")


def _check_cycles(edges: Mapping[str, tuple[str, ...]], label: str) -> None:
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        if state.get(node) == 1:
            raise SowInputError(f"{label} dependencies form a cycle")
        if state.get(node) == 2:
            return
        state[node] = 1
        for nxt in edges.get(node, ()):
            visit(nxt)
        state[node] = 2

    for node in edges:
        visit(node)


def _gov_readiness(governance: GovernanceSummary, rid: str) -> Readiness:
    if rid in governance.blocking_requirement_ids:
        return Readiness.BLOCKED
    return _GOV_READINESS[governance.requirement_status[rid]]


def _combined_readiness(
    rid: str, estimate: EstimateDraft | None, governance: GovernanceSummary
) -> Readiness:
    """The stricter of the governance readiness and the estimate's readiness for one requirement.

    A blocker in this SOW's governance review stays visible even when the estimate was built
    without it.
    """
    values = [_gov_readiness(governance, rid)]
    if estimate is not None and rid in estimate.requirement_readiness:
        values.append(estimate.requirement_readiness[rid])
    return worst(values)


def _normalise(text: str) -> str:
    return " ".join(text.casefold().split())


def _title_key(text: str) -> str:
    return " ".join(w for w in _normalise(text).split() if w not in _STOP)


def _totals_for(
    lines: Iterable[EstimateLine],
) -> tuple[float | None, float | None, float | None, bool]:
    """Sums of estimated lines. No number is presented when no line is estimated."""
    selected = list(lines)
    if not selected:
        return (None, None, None, False)
    estimated = [line for line in selected if line.status is EstimateStatus.INDICATIVE]
    if not estimated:
        return (None, None, None, False)
    return (
        sum(line.low or 0.0 for line in estimated),
        sum(line.likely or 0.0 for line in estimated),
        sum(line.high or 0.0 for line in estimated),
        len(estimated) == len(selected),
    )


def _screen(texts: Iterable[tuple[str, str]], issues: list[str]) -> None:
    for source, text in texts:
        if _INSTRUCTION.search(text):
            issues.append(
                f"instruction-like text in {source} is treated as data and was not executed"
            )


def _require_governance(
    request: SowRequest, reqs: Mapping[str, SowRequirement]
) -> GovernanceSummary:
    governance = request.governance
    if governance is None:
        raise SowInputError("a governance review is required before drafting a SOW")
    if governance.project_id != request.project_id:
        raise SowInputError("governance review belongs to another project")
    missing = [rid for rid in reqs if rid not in governance.requirement_status]
    if missing:
        raise SowInputError(f"governance has no assessment for {len(missing)} requirement(s)")
    return governance


def _deliverable_estimate(
    d_tasks: tuple[str, ...],
    task_to_lines: Mapping[str, list[str]],
    line_by_id: Mapping[str, EstimateLine],
    known_tasks: set[str],
    has_estimate: bool,
) -> tuple[float | None, float | None, float | None, bool]:
    if not has_estimate or not d_tasks:
        return (None, None, None, False)
    lines = list(
        {lid: line_by_id[lid] for t in d_tasks for lid in task_to_lines.get(t, [])}.values()
    )
    low, likely, high, complete = _totals_for(lines)
    if any(t not in known_tasks for t in d_tasks):
        complete = False
    return (low, likely, high, complete)


def generate(request: SowRequest) -> DraftSow:
    """Build a structured draft SOW. Raises SowInputError for input it cannot trust."""
    project = request.project_id
    reqs = _index_unique(request.requirements, lambda r: r.requirement_id, "requirement")
    for req in reqs.values():
        if req.project_id != project:
            raise SowInputError("a requirement belongs to another project")
    governance = _require_governance(request, reqs)
    estimate = request.estimate
    if estimate is not None and estimate.project_id != project:
        raise SowInputError("estimate belongs to another project")
    specialist_refs = dict(request.specialist_result_refs)

    workstreams = _index_unique(request.workstreams, lambda x: x.workstream_id, "workstream")
    deliverables = _index_unique(request.deliverables, lambda x: x.deliverable_id, "deliverable")
    findings = _index_unique(request.findings, lambda x: x.finding_id, "finding")
    assumptions = _index_unique(request.assumptions, lambda x: x.assumption_id, "assumption")
    risks = _index_unique(request.risks, lambda x: x.risk_id, "risk")
    questions = _index_unique(request.questions, lambda x: x.question_id, "question")
    client_items = _index_unique(request.client_items, lambda x: x.item_id, "client item")
    milestones = _index_unique(request.milestones, lambda x: x.milestone_id, "milestone")
    notes = _index_unique(request.tech_notes, lambda x: x.note_id, "technical note")

    for ws in workstreams.values():
        _require_known(ws.requirement_ids, reqs, "requirement")
    for d in deliverables.values():
        _require_known(d.requirement_ids, reqs, "requirement")
        if d.workstream_id not in workstreams:
            raise SowInputError("a deliverable names a workstream not in the request")
        _require_known(d.deliverable_dependencies, deliverables, "deliverable")
        _require_known(d.finding_refs, findings, "finding")
    _check_cycles(
        {d.deliverable_id: d.deliverable_dependencies for d in deliverables.values()}, "deliverable"
    )
    for f in findings.values():
        _require_known(f.requirement_ids, reqs, "requirement")
        if f.category_id not in specialist_refs:
            raise SowInputError("a specialist finding cites an unknown specialist result")
        if estimate is not None and f.category_id not in estimate.specialist_result_refs:
            raise SowInputError("a specialist finding cites an unknown specialist result")
    for n in notes.values():
        _require_known(n.requirement_ids, reqs, "requirement")
        _require_known(n.finding_refs, findings, "finding")
    for a in assumptions.values():
        _require_known(a.related_requirement_ids, reqs, "requirement")
    for r in risks.values():
        _require_known(r.related_requirement_ids, reqs, "requirement")
    for q in questions.values():
        _require_known(q.related_requirement_ids, reqs, "requirement")
    for c in client_items.values():
        _require_known(c.related_requirement_ids, reqs, "requirement")
    for m in milestones.values():
        _require_known(m.deliverable_ids, deliverables, "deliverable")
        _require_known(m.depends_on, milestones, "milestone")
    _check_cycles({m.milestone_id: m.depends_on for m in milestones.values()}, "milestone")

    lines = estimate.lines if estimate is not None else ()
    task_to_lines: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        for task_id in line.task_ids:
            task_to_lines[task_id].append(line.line_id)
    line_by_id = {line.line_id: line for line in lines}
    known_tasks = set(task_to_lines)
    has_estimate = estimate is not None

    issues: list[str] = []
    foreign_line_ids = {
        line.line_id for line in lines if any(rid not in reqs for rid in line.requirement_ids)
    }
    if estimate is None:
        issues.append(
            "no estimate reference supplied: resource effort is not supported by approved input"
        )
    else:
        for rid, req in reqs.items():
            est_rev = estimate.requirement_revisions.get(rid)
            if est_rev is None:
                issues.append(f"requirement {rid} has no revision in the estimate")
            elif est_rev != req.revision:
                issues.append(
                    f"stale requirement revision for {rid}: SOW revision {req.revision}, "
                    f"estimate revision {est_rev}"
                )
        if foreign_line_ids:
            issues.append(
                "estimate lines cover requirements not in this SOW and are included in the "
                f"estimate totals: {', '.join(sorted(foreign_line_ids))}"
            )

    covered_by: dict[str, list[str]] = defaultdict(list)
    for d in deliverables.values():
        for rid in d.requirement_ids:
            covered_by[rid].append(d.deliverable_id)
    for rid, req in sorted(reqs.items()):
        if req.disposition is ScopeDisposition.IN_SCOPE and not covered_by.get(rid):
            issues.append(f"unrepresented in-scope requirement {rid}: no deliverable covers it")
        if req.disposition is ScopeDisposition.PROPOSED_EXCLUSION and covered_by.get(rid):
            issues.append(f"contradictory scope: {rid} is proposed for exclusion but is covered")
        if req.disposition is ScopeDisposition.IN_SCOPE and not any(
            rid in f.requirement_ids for f in findings.values()
        ):
            issues.append(f"evidence gap: no specialist finding for in-scope requirement {rid}")
    for d in sorted(deliverables.values(), key=lambda x: x.deliverable_id):
        if all(
            reqs[rid].disposition is ScopeDisposition.PROPOSED_EXCLUSION
            for rid in d.requirement_ids
        ):
            issues.append(f"deliverable {d.deliverable_id} has no in-scope requirement")
        if not d.acceptance_criteria:
            issues.append(f"deliverable {d.deliverable_id} has no supplied acceptance criteria")
        for task_id in d.estimate_task_ids:
            if task_id not in known_tasks:
                issues.append(
                    f"deliverable {d.deliverable_id} cites an estimate task not in the estimate"
                )
    for ws in sorted(workstreams.values(), key=lambda x: x.workstream_id):
        ws_reqs = {
            rid
            for d in deliverables.values()
            if d.workstream_id == ws.workstream_id
            for rid in d.requirement_ids
        } | set(ws.requirement_ids)
        if not ws_reqs:
            issues.append(f"workstream {ws.workstream_id} covers no requirement")
        elif all(reqs[rid].disposition is ScopeDisposition.PROPOSED_EXCLUSION for rid in ws_reqs):
            issues.append(
                f"contradictory workstream scope: {ws.workstream_id} holds only proposed exclusions"
            )
    groups: dict[tuple[str, frozenset[str]], list[str]] = defaultdict(list)
    for d in deliverables.values():
        groups[(_title_key(d.title), frozenset(d.requirement_ids))].append(d.deliverable_id)
    for ids in groups.values():
        if len(ids) > 1:
            issues.append("duplicate deliverables: " + ", ".join(sorted(ids)))
    by_key: dict[str, set[str]] = defaultdict(set)
    ids_by_key: dict[str, list[str]] = defaultdict(list)
    for a in assumptions.values():
        by_key[a.key].add(_normalise(a.value))
        ids_by_key[a.key].append(a.assumption_id)
    for key, values in sorted(by_key.items()):
        if len(values) > 1:
            issues.append(
                f"contradictory assumptions for {key}: " + ", ".join(sorted(ids_by_key[key]))
            )
    for m in sorted(milestones.values(), key=lambda x: x.milestone_id):
        if not m.deliverable_ids:
            issues.append(f"milestone {m.milestone_id} groups no deliverable")

    text_sources: list[tuple[str, str]] = []
    text_sources += [(f"requirement {r.requirement_id}", r.statement) for r in reqs.values()]
    if request.overview is not None:
        ov = request.overview
        text_sources += [
            ("overview business objective", ov.business_objective),
            ("overview solution summary", ov.solution_summary),
        ]
        text_sources += [("overview platform", p) for p in ov.platforms]
    text_sources += [(f"workstream {w.workstream_id}", w.title) for w in workstreams.values()]
    text_sources += [
        (f"workstream {w.workstream_id} platform", p)
        for w in workstreams.values()
        for p in w.platforms
    ]
    for d in deliverables.values():
        text_sources.append((f"deliverable {d.deliverable_id} title", d.title))
        text_sources.append((f"deliverable {d.deliverable_id} description", d.description))
        text_sources += [
            (f"deliverable {d.deliverable_id} criterion", c) for c in d.acceptance_criteria
        ]
        text_sources += [(f"deliverable {d.deliverable_id} dependency", c) for c in d.dependencies]
        text_sources += [
            (f"deliverable {d.deliverable_id} constraint", c) for c in d.technical_constraints
        ]
    text_sources += [(f"finding {f.finding_id}", f.summary) for f in findings.values()]
    text_sources += [(f"technical note {n.note_id}", n.text) for n in notes.values()]
    text_sources += [(f"assumption {a.assumption_id}", a.statement) for a in assumptions.values()]
    text_sources += [(f"assumption {a.assumption_id} value", a.value) for a in assumptions.values()]
    text_sources += [(f"risk {r.risk_id}", r.description) for r in risks.values()]
    text_sources += [(f"question {q.question_id}", q.text) for q in questions.values()]
    text_sources += [(f"client item {c.item_id}", c.text) for c in client_items.values()]
    text_sources += [(f"milestone {m.milestone_id}", m.title) for m in milestones.values()]
    _screen(text_sources, issues)

    unrepresented = tuple(
        sorted(
            rid
            for rid, req in reqs.items()
            if req.disposition is ScopeDisposition.IN_SCOPE and not covered_by.get(rid)
        )
    )
    issues = sorted(set(issues))

    readiness_of = {rid: _combined_readiness(rid, estimate, governance) for rid in reqs}
    status_of = governance.requirement_status

    overview_items: list[SowItem] = []
    if request.overview is None:
        overview_state = SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT
        overview_items.append(
            SowItem(
                text="Business objective: not supported by approved input.",
                refs=(),
                label="not_supported",
            )
        )
    else:
        overview_state = SectionState.SUPPORTED
        ov = request.overview
        overview_items.append(
            SowItem(
                text=f"Business objective (client-supplied): {ov.business_objective}",
                refs=(ov.source_ref,),
                label="client_supplied",
            )
        )
        overview_items.append(
            SowItem(
                text=f"Proposed solution summary: {ov.solution_summary}",
                refs=(ov.source_ref,),
                label="proposal",
            )
        )
        for platform in ov.platforms:
            overview_items.append(
                SowItem(text=f"Intended platform: {platform}", refs=(), label="proposal")
            )

    def _unresolved(rids: Iterable[str]) -> str | None:
        note: str | None = None
        for rid in rids:
            status = status_of.get(rid)
            if status is not None and status != "evidence_backed":
                note = f"governance status {status} for {rid}"
        return note

    requirement_items: list[SowItem] = []
    for req in sorted(reqs.values(), key=lambda x: x.requirement_id):
        if req.disposition is ScopeDisposition.IN_SCOPE:
            requirement_items.append(
                SowItem(
                    text=(
                        f"{req.requirement_id} (revision {req.revision}, {req.origin.value}): "
                        f"{req.statement}"
                    ),
                    refs=(req.requirement_id,),
                    label="requirement_statement",
                )
            )

    workstream_items: list[SowItem] = list(requirement_items)
    ws_views: list[WorkstreamView] = []
    deliverable_estimates = {
        d.deliverable_id: _deliverable_estimate(
            d.estimate_task_ids, task_to_lines, line_by_id, known_tasks, has_estimate
        )
        for d in deliverables.values()
    }
    for ws in sorted(workstreams.values(), key=lambda x: x.workstream_id):
        ws_dels = sorted(
            d.deliverable_id for d in deliverables.values() if d.workstream_id == ws.workstream_id
        )
        ws_req_ids = sorted(
            {
                rid
                for d in deliverables.values()
                if d.workstream_id == ws.workstream_id
                for rid in d.requirement_ids
            }
            | set(ws.requirement_ids)
        )
        ws_task_ids = {
            t
            for d in deliverables.values()
            if d.workstream_id == ws.workstream_id
            for t in d.estimate_task_ids
        }
        ws_lines = list(
            {
                lid: line_by_id[lid]
                for t in sorted(ws_task_ids)
                for lid in task_to_lines.get(t, [])
            }.values()
        )
        complete: bool | None
        if not has_estimate:
            low = likely = high = None
            complete = None
        else:
            low, likely, high, _ = _totals_for(ws_lines)
            all_dels_complete = bool(ws_dels) and all(
                deliverable_estimates[did][3] for did in ws_dels
            )
            complete = all_dels_complete and not any(
                line.line_id in foreign_line_ids for line in ws_lines
            )
        ws_views.append(
            WorkstreamView(
                workstream_id=ws.workstream_id,
                title=ws.title,
                platforms=ws.platforms,
                requirement_ids=tuple(ws_req_ids),
                deliverable_ids=tuple(ws_dels),
                estimate_low=low,
                estimate_likely=likely,
                estimate_high=high,
                estimate_complete=complete,
            )
        )
        workstream_items.append(
            SowItem(
                text=f"{ws.workstream_id}: {ws.title}"
                + (f" (platforms: {', '.join(ws.platforms)})" if ws.platforms else ""),
                refs=tuple(ws_req_ids),
                label="in_scope",
            )
        )
    if not workstreams:
        workstream_items.append(
            SowItem(text="No workstream is supplied.", refs=(), label="not_supported")
        )

    finding_items: list[SowItem] = []
    for f in sorted(findings.values(), key=lambda x: x.finding_id):
        finding_items.append(
            SowItem(
                text=(
                    f"{f.finding_id} ({f.category_id}, {f.kind.value}) on "
                    f"{', '.join(sorted(f.requirement_ids))}: {f.summary}"
                ),
                refs=(f.source_ref,) + tuple(sorted(f.requirement_ids)),
                label=f.kind.value,
            )
        )
    if not findings:
        finding_items.append(
            SowItem(
                text="Specialist findings: not supported by approved input.",
                refs=(),
                label="not_supported",
            )
        )

    deliverable_views: list[DeliverableView] = []
    deliverable_items: list[SowItem] = []
    acceptance_items: list[SowItem] = []
    for d in sorted(deliverables.values(), key=lambda x: x.deliverable_id):
        low, likely, high, d_complete = deliverable_estimates[d.deliverable_id]
        readiness_map = {rid: readiness_of[rid].value for rid in d.requirement_ids}
        criteria = tuple(sorted(d.acceptance_criteria))
        deliverable_views.append(
            DeliverableView(
                deliverable_id=d.deliverable_id,
                workstream_id=d.workstream_id,
                title=d.title,
                description=d.description,
                requirement_ids=tuple(sorted(d.requirement_ids)),
                acceptance_criteria=criteria,
                acceptance_state=SectionState.SUPPORTED
                if criteria
                else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
                dependencies=d.dependencies,
                deliverable_dependencies=d.deliverable_dependencies,
                technical_constraints=d.technical_constraints,
                evidence_refs=d.evidence_refs,
                finding_refs=d.finding_refs,
                governance_readiness=dict(sorted(readiness_map.items())),
                estimate_task_ids=d.estimate_task_ids,
                estimate_low=low,
                estimate_likely=likely,
                estimate_high=high,
                estimate_complete=d_complete,
            )
        )
        note = _unresolved(d.requirement_ids)
        deliverable_items.append(
            SowItem(
                text=f"{d.deliverable_id}: {d.title} - {d.description}"
                + (f" [{note}]" if note else ""),
                refs=tuple(sorted(d.requirement_ids)),
                label="not_established" if note else "proposal",
            )
        )
        for index, criterion in enumerate(criteria, start=1):
            acceptance_items.append(
                SowItem(
                    text=f"{d.deliverable_id} criterion {index}: {criterion}",
                    refs=(d.deliverable_id,),
                    label="proposed_criterion",
                )
            )
        if not criteria:
            acceptance_items.append(
                SowItem(
                    text=(
                        f"{d.deliverable_id}: acceptance criteria not supported by approved "
                        "input."
                    ),
                    refs=(d.deliverable_id,),
                    label="not_supported",
                )
            )
    if not deliverables:
        deliverable_items.append(
            SowItem(text="No deliverable is supplied.", refs=(), label="not_supported")
        )

    out_items: list[SowItem] = []
    for req in sorted(reqs.values(), key=lambda x: x.requirement_id):
        if req.disposition is ScopeDisposition.PROPOSED_EXCLUSION:
            out_items.append(
                SowItem(
                    text=(
                        f"{req.requirement_id}: {req.statement} - proposed exclusion: "
                        f"{req.exclusion_rationale}"
                    ),
                    refs=(req.requirement_id,),
                    label="proposal_requires_human_confirmation",
                )
            )
    if not out_items:
        out_items.append(SowItem(text="No exclusion is proposed.", refs=(), label="none"))

    tech_items: list[SowItem] = []
    topics_with_notes = {n.topic for n in notes.values()}
    for note_obj in sorted(notes.values(), key=lambda x: (x.topic.value, x.note_id)):
        blocking = _unresolved(note_obj.requirement_ids)
        tech_items.append(
            SowItem(
                text=f"{note_obj.topic.value}: {note_obj.text}"
                + (f" [{blocking}]" if blocking else ""),
                refs=(note_obj.source_ref,)
                + tuple(note_obj.requirement_ids)
                + tuple(note_obj.finding_refs),
                label="not_established" if blocking else "supplied",
            )
        )
    for topic in TechTopic:
        if topic not in topics_with_notes:
            tech_items.append(
                SowItem(
                    text=f"{topic.value}: not supported by approved input.",
                    refs=(),
                    label="not_supported",
                )
            )

    milestone_items: list[SowItem] = []
    milestone_views: list[MilestoneView] = []
    for m in sorted(milestones.values(), key=lambda x: x.milestone_id):
        milestone_views.append(
            MilestoneView(
                milestone_id=m.milestone_id,
                title=m.title,
                deliverable_ids=tuple(sorted(m.deliverable_ids)),
                depends_on=tuple(sorted(m.depends_on)),
                elapsed_duration_note=ELAPSED_NOTE,
            )
        )
        milestone_items.append(
            SowItem(
                text=f"{m.milestone_id}: {m.title}; deliverables "
                f"{', '.join(sorted(m.deliverable_ids)) or 'none'}; "
                f"after {', '.join(sorted(m.depends_on)) or 'start'}",
                refs=tuple(sorted(m.deliverable_ids)),
                label="proposal",
            )
        )
    if not milestones:
        milestone_items.append(
            SowItem(
                text="Milestones: not supported by approved input.", refs=(), label="not_supported"
            )
        )
    milestone_items.append(SowItem(text=ELAPSED_NOTE, refs=(), label="caveat"))

    assumption_items: list[SowItem] = []
    for a in sorted(assumptions.values(), key=lambda x: x.assumption_id):
        assumption_items.append(
            SowItem(
                text=f"{a.assumption_id} ({a.key}): {a.statement} - {a.value}",
                refs=tuple(sorted(a.related_requirement_ids)) + (a.source_ref,),
                label=a.status.value,
            )
        )
    if not assumptions:
        assumption_items.append(
            SowItem(
                text="Assumptions: not supported by approved input.", refs=(), label="not_supported"
            )
        )

    client_items_out: list[SowItem] = []
    for c in sorted(client_items.values(), key=lambda x: x.item_id):
        client_items_out.append(
            SowItem(
                text=f"{c.item_id} ({c.kind.value}): {c.text}",
                refs=tuple(sorted(c.related_requirement_ids)),
                label=c.kind.value,
            )
        )
    if not client_items:
        client_items_out.append(
            SowItem(
                text="Client responsibilities: not supported by approved input.",
                refs=(),
                label="not_supported",
            )
        )

    risk_items: list[SowItem] = []
    for rid in sorted(reqs):
        readiness = readiness_of[rid]
        if readiness is Readiness.BLOCKED:
            risk_items.append(
                SowItem(
                    text=(
                        f"Governance blocker: {rid} is blocked and must not be treated as "
                        "supported."
                    ),
                    refs=(rid,),
                    label="blocked",
                )
            )
        elif readiness is Readiness.UNRESOLVED:
            risk_items.append(
                SowItem(
                    text=f"Unsupported claim: {rid} is unresolved.", refs=(rid,), label="unresolved"
                )
            )
        elif readiness is Readiness.PROVISIONAL:
            risk_items.append(
                SowItem(
                    text=f"Unverified hypothesis: {rid} is provisional.",
                    refs=(rid,),
                    label="provisional",
                )
            )
        if status_of.get(rid) == "conflicted":
            risk_items.append(
                SowItem(text=f"Specialist conflict on {rid}.", refs=(rid,), label="conflicted")
            )
    if governance.has_blocker:
        risk_items.append(
            SowItem(
                text="The governance review reports blocking findings.",
                refs=(governance.run_id,),
                label="blocked",
            )
        )
    if governance.escalation_count:
        risk_items.append(
            SowItem(
                text=(
                    f"{governance.escalation_count} governance escalation(s) require human "
                    "review."
                ),
                refs=(governance.run_id,),
                label="human_review",
            )
        )
    for r in sorted(risks.values(), key=lambda x: x.risk_id):
        risk_items.append(
            SowItem(
                text=f"{r.risk_id}: {r.description}",
                refs=tuple(sorted(r.related_requirement_ids)) + (r.status.value,),
                label=r.status.value,
            )
        )
    for q in sorted(questions.values(), key=lambda x: x.question_id):
        risk_items.append(
            SowItem(
                text=f"Open question {q.question_id}: {q.text}",
                refs=tuple(sorted(q.related_requirement_ids)),
                label="open_question",
            )
        )
    if estimate is not None:
        for line in lines:
            if line.status is EstimateStatus.NEEDS_INPUTS:
                risk_items.append(
                    SowItem(
                        text=f"Missing estimate inputs: {line.line_id} has no hours "
                        f"({'; '.join(line.issues)}).",
                        refs=(line.line_id,),
                        label="needs_inputs",
                    )
                )
    risk_items.append(SowItem(text=PENDING_DECISIONS, refs=(), label="pending_decision"))
    for issue in issues:
        risk_items.append(SowItem(text=f"Integrity: {issue}", refs=(), label="integrity"))

    resources, resource_items = _resources(estimate, foreign_line_ids)

    change_items = [
        SowItem(
            text=f"Version {request.sow_version}"
            + (
                f", previous {request.previous_version}"
                if request.previous_version
                else ", first version"
            ),
            refs=(),
            label="draft",
        ),
        SowItem(
            text="Approval state: pending human approval. Not approved.",
            refs=(),
            label="pending_human_approval",
        ),
    ]

    traceability: list[TraceRow] = []
    for rid, req in sorted(reqs.items()):
        d_ids = sorted(d.deliverable_id for d in deliverables.values() if rid in d.requirement_ids)
        w_ids = sorted({d.workstream_id for d in deliverables.values() if rid in d.requirement_ids})
        f_ids = sorted(f.finding_id for f in findings.values() if rid in f.requirement_ids)
        l_ids = sorted(line.line_id for line in lines if rid in line.requirement_ids)
        traceability.append(
            TraceRow(
                requirement_id=rid,
                requirement_revision=req.revision,
                origin=req.origin.value,
                disposition=req.disposition.value,
                finding_ids=tuple(f_ids),
                governance_status=status_of.get(rid),
                governance_readiness=readiness_of[rid].value,
                estimate_line_ids=tuple(l_ids),
                deliverable_ids=tuple(d_ids),
                workstream_ids=tuple(w_ids),
            )
        )

    manifest = [
        SourceManifestEntry(source_kind="requirement", source_id=rid, revision=str(req.revision))
        for rid, req in sorted(reqs.items())
    ]
    manifest += [
        SourceManifestEntry(source_kind="specialist_result", source_id=cat, revision=ref)
        for cat, ref in sorted(specialist_refs.items())
    ]
    manifest.append(
        SourceManifestEntry(
            source_kind="governance_review",
            source_id=governance.run_id,
            revision=governance.input_fingerprint,
        )
    )
    if estimate is not None:
        manifest.append(
            SourceManifestEntry(
                source_kind="estimate",
                source_id=estimate.project_id,
                revision=estimate.estimate_version,
            )
        )

    control = DocumentControl(
        sow_id=request.sow_id,
        sow_version=request.sow_version,
        previous_version=request.previous_version,
        project_id=project,
        requirement_revisions={rid: req.revision for rid, req in sorted(reqs.items())},
        specialist_result_refs=dict(sorted(specialist_refs.items())),
        governance_run_id=governance.run_id,
        governance_fingerprint=governance.input_fingerprint,
        estimate_version=estimate.estimate_version if estimate else None,
        estimate_draft_status=estimate.draft_status if estimate else None,
        generator=GENERATOR,
        manifest=tuple(manifest),
    )

    sections = (
        SowSection(
            section_id="scope_in",
            title="In-scope work",
            state=SectionState.SUPPORTED
            if workstreams
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(workstream_items),
        ),
        SowSection(
            section_id="scope_out",
            title="Out-of-scope work (proposed)",
            state=SectionState.SUPPORTED,
            items=tuple(out_items),
        ),
        SowSection(
            section_id="specialist_findings",
            title="Specialist findings",
            state=SectionState.SUPPORTED
            if findings
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(finding_items),
        ),
        SowSection(
            section_id="deliverables",
            title="Deliverables",
            state=SectionState.SUPPORTED
            if deliverables
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(deliverable_items),
        ),
        SowSection(
            section_id="acceptance",
            title="Acceptance criteria (proposed)",
            state=SectionState.SUPPORTED
            if any(d.acceptance_criteria for d in deliverables.values())
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(acceptance_items)
            or (
                SowItem(
                    text="Acceptance criteria: not supported by approved input.",
                    refs=(),
                    label="not_supported",
                ),
            ),
        ),
        SowSection(
            section_id="technical",
            title="Technical approach and integrations",
            state=SectionState.SUPPORTED if notes else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(tech_items),
        ),
        SowSection(
            section_id="resources",
            title="Resource effort (AI-S08 draft)",
            state=resources.state,
            items=tuple(resource_items),
        ),
        SowSection(
            section_id="milestones",
            title="Milestones and dependencies",
            state=SectionState.SUPPORTED
            if milestones
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(milestone_items),
        ),
        SowSection(
            section_id="assumptions",
            title="Assumptions",
            state=SectionState.SUPPORTED
            if assumptions
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(assumption_items),
        ),
        SowSection(
            section_id="client_responsibilities",
            title="Client and WDS responsibilities",
            state=SectionState.SUPPORTED
            if client_items
            else SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            items=tuple(client_items_out),
        ),
        SowSection(
            section_id="risks",
            title="Risks, open questions and decisions",
            state=SectionState.SUPPORTED,
            items=tuple(risk_items),
        ),
        SowSection(
            section_id="change_control",
            title="Change control and approval",
            state=SectionState.SUPPORTED,
            items=tuple(change_items),
        ),
    )

    return DraftSow(
        document_control=control,
        approval=Approval(separation_rule=SEPARATION_RULE, note=APPROVAL_NOTE),
        overview=tuple(overview_items),
        overview_state=overview_state,
        sections=sections,
        workstreams=tuple(ws_views),
        deliverables=tuple(deliverable_views),
        milestones=tuple(milestone_views),
        resources=resources,
        traceability=tuple(traceability),
        unrepresented_requirement_ids=unrepresented,
        integrity_issues=tuple(issues),
        calculation_provenance=CALC_PROVENANCE,
    )


def _resources(
    estimate: EstimateDraft | None, foreign_line_ids: set[str]
) -> tuple[ResourceView, list[SowItem]]:
    if estimate is None:
        view = ResourceView(
            state=SectionState.NOT_SUPPORTED_BY_APPROVED_INPUT,
            estimate_version=None,
            project_complete=None,
            project_low=None,
            project_likely=None,
            project_high=None,
            excluded_line_ids=(),
            banner="No estimate reference supplied. No resource effort is presented.",
            by_discipline={},
            lines=(),
        )
        return view, [SowItem(text=view.banner, refs=(), label="not_supported")]
    project: Totals = estimate.project
    has_numbers = project.estimated_line_count > 0
    complete = project.complete and not foreign_line_ids
    if not has_numbers:
        banner = "No line has numeric hours. No project total is presented."
    elif complete:
        banner = "Project total: complete for all counted lines (draft estimate; not approved)."
    else:
        reasons: list[str] = []
        if project.excluded_line_ids:
            reasons.append(f"{len(project.excluded_line_ids)} unresolved line(s)")
        if foreign_line_ids:
            reasons.append("effort for requirements not in this SOW is included")
        banner = f"PARTIAL: {'; '.join(reasons)}. This is not the complete project estimate."
    view = ResourceView(
        state=SectionState.SUPPORTED,
        estimate_version=estimate.estimate_version,
        project_complete=complete,
        project_low=project.low if has_numbers else None,
        project_likely=project.likely if has_numbers else None,
        project_high=project.high if has_numbers else None,
        excluded_line_ids=tuple(project.excluded_line_ids),
        banner=banner,
        by_discipline={
            key: (
                (totals.low, totals.likely, totals.high, totals.complete)
                if totals.estimated_line_count > 0
                else (None, None, None, False)
            )
            for key, totals in sorted(estimate.by_discipline.items())
        },
        lines=tuple(
            ResourceLine(
                line_id=line.line_id,
                discipline=line.discipline.value if line.discipline is not None else None,
                task_ids=line.task_ids,
                requirement_ids=line.requirement_ids,
                status=line.status.value,
                readiness=line.readiness,
                low=line.low,
                likely=line.likely,
                high=line.high,
            )
            for line in estimate.lines
        ),
    )
    items = [
        SowItem(
            text=view.banner,
            refs=(estimate.estimate_version,),
            label="complete" if complete else "partial",
        ),
        SowItem(text=RESOURCE_CAVEAT, refs=(), label="caveat"),
    ]
    for key, row in view.by_discipline.items():
        low, likely, high, row_complete = row
        if low is None or likely is None or high is None:
            text = f"{key}: not estimated (no line has numeric hours)"
        else:
            text = f"{key}: low {low:g}, likely {likely:g}, high {high:g} hours" + (
                "" if row_complete else " (incomplete)"
            )
        items.append(
            SowItem(
                text=text,
                refs=(estimate.estimate_version,),
                label="complete" if row_complete else "partial",
            )
        )
    return view, items


def compare_versions(previous: DraftSow, current: DraftSow) -> SowChange:
    """A structural comparison of two drafts of the same SOW, for version review."""
    old_d = {d.deliverable_id for d in previous.deliverables}
    new_d = {d.deliverable_id for d in current.deliverables}
    old_r = previous.document_control.requirement_revisions
    new_r = current.document_control.requirement_revisions
    return SowChange(
        added_deliverables=tuple(sorted(new_d - old_d)),
        removed_deliverables=tuple(sorted(old_d - new_d)),
        added_requirements=tuple(sorted(set(new_r) - set(old_r))),
        removed_requirements=tuple(sorted(set(old_r) - set(new_r))),
        revised_requirements=tuple(
            sorted(rid for rid in set(old_r) & set(new_r) if old_r[rid] != new_r[rid])
        ),
    )
