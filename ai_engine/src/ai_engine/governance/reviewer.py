"""
Independent runtime governance reviewer (AI-S07).

The reviewer reads a run's results and the evidence the caller admitted, and reports what it finds.
It is separate from the specialists: it imports only contract types, never specialist code, and it
never modifies its input. It applies no governance policy of its own. The staleness window,
collection authorisation and supersession are caller-supplied inputs.

Rules the reviewer does not invent: lifecycle states (A-4, C-15), who may accept a finding (D-05),
materiality (D-06), acceptance of inferred requirements (D-07), evidence verification authority
(D-06 and D-09, still open), and the authenticity of confirmations (R-2).

``EVIDENCE_BACKED`` is a reviewer assessment, not a verification and not an approval. A requirement
is backed only when a claim bound to it cites an admitted record that is verified and
project-scoped. The review must also supply a freshness window and an authorised collection set,
or nothing is backed. The record must be unsuperseded, identical to its served copy (apart from
the served status, which must be unverified or equal to the admitted status), and relevant to the
requirement by a deterministic term screen. Upstream claim status is never proof of support.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from ai_engine.contracts.common import EvidenceStatus, FeasibilityStatus
from ai_engine.contracts.evidence import Claim, ClaimType, EvidenceKind, EvidenceReference
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
)
from ai_engine.governance.contracts import (
    Action,
    DefectClass,
    ReviewFinding,
    ReviewReport,
    ReviewStatus,
    Severity,
)

_APPROVAL_WORDING = re.compile(
    r"\b(approved|accepted by|signed off|sign-off|materiality (?:is|=)|final estimate"
    r"|sow (?:is )?signed)\b",
    re.IGNORECASE,
)
_VERIFIED = frozenset({EvidenceStatus.VERIFIED, EvidenceStatus.PARTIALLY_VERIFIED})
_LABELLED = frozenset(
    {EvidenceStatus.UNVERIFIED, EvidenceStatus.CONFLICTING, EvidenceStatus.NOT_APPLICABLE}
)
_NON_BACKING_CLAIM = frozenset({EvidenceStatus.CONFLICTING, EvidenceStatus.NOT_APPLICABLE})
_VERIFIABLE_KINDS = frozenset(
    {EvidenceKind.APPROVED_INTERNAL, EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION}
)
_TERM = re.compile(r"[a-z0-9]+")
_STOP_TERMS = frozenset(
    {
        "about", "after", "also", "been", "before", "could", "each", "from", "have", "into",
        "more", "most", "must", "over", "should", "some", "such", "than", "that", "their",
        "them", "then", "they", "this", "under", "were", "when", "where", "which", "while",
        "will", "with", "would",
    }
)  # fmt: skip
_RANK = {Severity.BLOCKER: 0, Severity.MAJOR: 1, Severity.MINOR: 2, Severity.NOTE: 3}


@dataclass(frozen=True)
class ReviewedOutcome:
    """One specialist category's result, as the reviewer sees it. Plain data, no behaviour."""

    category_id: str
    requirement_ids: tuple[str, ...]
    specialist_status: SpecialistOutputStatus | None
    output: SpecialistInvestigationResult | None
    refusal: str | None = None


@dataclass(frozen=True)
class ReviewInput:
    run_id: str
    project_id: str
    requirements: Mapping[str, AtomicRequirement]
    outcomes: tuple[ReviewedOutcome, ...]
    admitted_evidence: Mapping[str, EvidenceReference]
    as_of: datetime | None = None
    stale_after: timedelta | None = None
    evidence_collections: Mapping[str, str] = field(default_factory=dict)
    authorised_collections: frozenset[str] | None = None
    superseded_by: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Fail closed: refuse malformed input before any review is produced."""
        if not self.run_id or not self.project_id:
            raise ValueError("run_id and project_id are required")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if self.stale_after is not None and self.stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        if self.stale_after is not None and self.as_of is None:
            raise ValueError("stale_after requires as_of; a window cannot be applied without it")
        seen: set[str] = set()
        for outcome in self.outcomes:
            if outcome.category_id in seen:
                raise ValueError(f"duplicate specialist category {outcome.category_id}")
            seen.add(outcome.category_id)
            if outcome.output is not None and (
                outcome.output.specialist_category_id != outcome.category_id
            ):
                raise ValueError(f"output does not belong to category {outcome.category_id}")
        for key, record in self.admitted_evidence.items():
            if record.evidence_id != key:
                raise ValueError(f"admitted evidence key {key} does not match its record")
            if record.checked_at.tzinfo is None:
                raise ValueError(f"checked_at of {key} must be timezone-aware")
            if self.as_of is not None and record.checked_at > self.as_of:
                raise ValueError(f"checked_at of {key} is after as_of")


def _subjects(claim: Claim) -> tuple[str, ...]:
    return tuple(ref.subject_id for ref in claim.subject_refs)


def _has_provenance(record: EvidenceReference) -> bool:
    """The recorded provenance the contract requires, re-checked here because a record built
    without validation (model_copy, model_construct) can omit it."""
    if record.evidence_kind is EvidenceKind.APPROVED_INTERNAL:
        return bool(record.source_id and record.source_version and record.content_hash)
    if record.evidence_kind is EvidenceKind.OFFICIAL_VENDOR_DOCUMENTATION:
        return bool(
            record.publisher
            and record.applies_to_platform_version
            and record.content_hash
            and record.source_url
            and record.source_url.startswith("https://")
        )
    return False


def _is_verifiable(record: EvidenceReference) -> bool:
    """True only for an admitted kind whose own record is verified and carries its provenance."""
    return (
        record.evidence_kind in _VERIFIABLE_KINDS
        and record.evidence_status in _VERIFIED
        and _has_provenance(record)
    )


def _same_record(served: EvidenceReference, admitted: EvidenceReference) -> bool:
    """A served copy must agree with the admitted record on every field except its status.

    The specialist validator refuses verified served statuses. A served status of unverified, or
    equal to the admitted status (approved directive, section C), is accepted. Any other served
    status is a mismatch. The admitted record is the authority for verification.
    """
    if served.evidence_status not in (EvidenceStatus.UNVERIFIED, admitted.evidence_status):
        return False
    return served.model_dump(exclude={"evidence_status"}) == admitted.model_dump(
        exclude={"evidence_status"}
    )


def _served_once(output: SpecialistInvestigationResult) -> dict[str, EvidenceReference]:
    """Served copies keyed by ID, keeping only IDs served exactly once. A duplicated ID is
    ambiguous, so it can never support a finding; it is reported separately."""
    counts = Counter(e.evidence_id for e in output.evidence)
    return {e.evidence_id: e for e in output.evidence if counts[e.evidence_id] == 1}


def _parameters_complete(inp: ReviewInput) -> bool:
    """Backing needs a freshness window and an authorised collection set. Without both, the
    reviewer cannot establish currency or collection authority, so it backs nothing."""
    return (
        inp.as_of is not None
        and inp.stale_after is not None
        and inp.authorised_collections is not None
    )


def _terms(text: str) -> frozenset[str]:
    return frozenset(t for t in _TERM.findall(text.lower()) if len(t) >= 4 and t not in _STOP_TERMS)


def _relevant(claim_text: str, statement: str, record: EvidenceReference) -> bool:
    """Deterministic term screen: the record's summary shares a term with the claim or requirement.

    This is a screen, not semantic relevance. Semantic relevance remains a human decision.
    """
    return bool(_terms(record.relevance_summary) & (_terms(claim_text) | _terms(statement)))


class _Collector:
    def __init__(self, run_id: str) -> None:
        self._run_id = run_id
        self._items: list[
            tuple[DefectClass, Severity, tuple[str, ...], str | None, tuple[str, ...], str, Action]
        ] = []

    def add(
        self,
        defect: DefectClass,
        severity: Severity,
        requirement_ids: Sequence[str],
        category: str | None,
        evidence_ids: Sequence[str],
        summary: str,
        action: Action,
    ) -> None:
        self._items.append(
            (
                defect,
                severity,
                tuple(sorted(set(requirement_ids))),
                category,
                tuple(sorted(set(evidence_ids))),
                summary,
                action,
            )
        )

    def findings(self) -> tuple[ReviewFinding, ...]:
        # Identical observations collapse to one finding, so a defect seen from two checks is
        # reported once.
        ordered = sorted(
            dict.fromkeys(self._items),
            key=lambda i: (_RANK[i[1]], i[0].value, i[2], i[3] or "", i[4], i[5]),
        )
        return tuple(
            ReviewFinding(
                finding_id=f"RVW-{number:03d}",
                run_id=self._run_id,
                defect_class=defect,
                severity=severity,
                requirement_ids=rids,
                category_id=category,
                evidence_ids=evidence,
                summary=summary,
                action=action,
            )
            for number, (defect, severity, rids, category, evidence, summary, action) in enumerate(
                ordered, start=1
            )
        )


def _fingerprint(inp: ReviewInput) -> str:
    """Audit correlation: a SHA-256 over the run's identifiers and review parameters.

    It covers identifiers (requirements, admitted and served evidence IDs, categories, statuses)
    and the caller's review parameters (window, collections, supersession). It does not hash
    claim or evidence content; a content change that keeps the identifiers leaves it unchanged.
    """
    payload = {
        "run_id": inp.run_id,
        "project_id": inp.project_id,
        "requirements": sorted(inp.requirements),
        "admitted": sorted(inp.admitted_evidence),
        "as_of": inp.as_of.isoformat() if inp.as_of else None,
        "stale_after_seconds": inp.stale_after.total_seconds() if inp.stale_after else None,
        "authorised_collections": (
            sorted(inp.authorised_collections) if inp.authorised_collections is not None else None
        ),
        "evidence_collections": sorted(inp.evidence_collections.items()),
        "superseded": sorted(inp.superseded_by.items()),
        "outcomes": [
            {
                "category": o.category_id,
                "requirements": sorted(o.requirement_ids),
                "execution": o.specialist_status.value if o.specialist_status else None,
                "output": o.output.status.value if o.output else None,
                "served": sorted(e.evidence_id for e in o.output.evidence) if o.output else [],
            }
            for o in sorted(inp.outcomes, key=lambda o: o.category_id)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class IndependentReviewer:
    """Reviews a run. Pure function of its input; holds no state between calls."""

    def review(self, review_input: ReviewInput) -> ReviewReport:
        inp = review_input
        collector = _Collector(inp.run_id)
        self._coverage(inp, collector)
        if not _parameters_complete(inp):
            collector.add(
                DefectClass.MISSING_REVIEW_PARAMETER,
                Severity.MINOR,
                (),
                None,
                (),
                "no evidence is backed: the review needs as_of and stale_after, and an "
                "authorised collection set",
                "human_review",
            )
        for outcome in inp.outcomes:
            if outcome.output is None:
                collector.add(
                    DefectClass.COVERAGE_GAP,
                    Severity.MAJOR,
                    outcome.requirement_ids,
                    outcome.category_id,
                    (),
                    f"{outcome.category_id} produced no output"
                    f" ({outcome.refusal or 'no reason recorded'})",
                    "human_review",
                )
                continue
            self._citations(inp, outcome, collector)
            self._claims(inp, outcome, collector)
            self._risks(outcome, collector)
            self._clarification(inp, outcome, collector)
            self._wording(outcome, collector)
        self._cross_specialist(inp, collector)
        findings = collector.findings()
        statuses, traceability = self._statuses(inp, findings)
        return ReviewReport(
            run_id=inp.run_id,
            project_id=inp.project_id,
            findings=findings,
            requirement_status=statuses,
            traceability=traceability,
            input_fingerprint=_fingerprint(inp),
        )

    # --- coverage and traceability

    def _coverage(self, inp: ReviewInput, c: _Collector) -> None:
        routed: set[str] = set()
        for outcome in inp.outcomes:
            routed.update(outcome.requirement_ids)
            for rid in outcome.requirement_ids:
                if rid not in inp.requirements:
                    c.add(
                        DefectClass.UNTRACEABLE,
                        Severity.MAJOR,
                        (rid,),
                        outcome.category_id,
                        (),
                        f"requirement {rid} is not in the review context",
                        "human_review",
                    )
            if outcome.output is not None and set(outcome.output.requirement_ids) != set(
                outcome.requirement_ids
            ):
                missing = sorted(set(outcome.requirement_ids) - set(outcome.output.requirement_ids))
                c.add(
                    DefectClass.COVERAGE_GAP,
                    Severity.MAJOR,
                    missing,
                    outcome.category_id,
                    (),
                    f"{outcome.category_id} did not investigate: "
                    f"{', '.join(missing) or 'unexpected IDs'}",
                    "human_review",
                )
        for rid in sorted(inp.requirements):
            if rid not in routed:
                c.add(
                    DefectClass.COVERAGE_GAP,
                    Severity.MAJOR,
                    (rid,),
                    None,
                    (),
                    f"requirement {rid} was not routed to any specialist",
                    "human_review",
                )

    def _traceability_gap(
        self, inp: ReviewInput, outcome: ReviewedOutcome, claim: Claim, c: _Collector
    ) -> None:
        for rid in _subjects(claim):
            if rid not in outcome.requirement_ids:
                c.add(
                    DefectClass.UNTRACEABLE,
                    Severity.MAJOR,
                    (rid,),
                    outcome.category_id,
                    (),
                    f"claim {claim.proposal_key or claim.claim_id} names {rid}, "
                    "which this category was not given",
                    "correct_specialist_output",
                )

    # --- citations and evidence

    def _collection_ok(self, inp: ReviewInput, eid: str) -> bool:
        """With an authorised set supplied, the record's collection must be known and in it."""
        if inp.authorised_collections is None:
            return True
        collection = inp.evidence_collections.get(eid)
        return collection is not None and collection in inp.authorised_collections

    def _stale(self, inp: ReviewInput, record: EvidenceReference) -> bool:
        return (
            inp.as_of is not None
            and inp.stale_after is not None
            and record.checked_at < inp.as_of - inp.stale_after
        )

    def _citations(self, inp: ReviewInput, outcome: ReviewedOutcome, c: _Collector) -> None:
        output = outcome.output
        if output is None:
            return
        cat = outcome.category_id
        routed = tuple(outcome.requirement_ids)
        counts = Counter(e.evidence_id for e in output.evidence)
        # Every served copy is checked, cited or not.
        for served_copy in output.evidence:
            eid = served_copy.evidence_id
            if served_copy.project_id != inp.project_id:
                c.add(
                    DefectClass.CROSS_PROJECT_CITATION,
                    Severity.BLOCKER,
                    routed,
                    cat,
                    (eid,),
                    f"served evidence {eid} belongs to another project",
                    "correct_specialist_output",
                )
            if counts[eid] > 1:
                c.add(
                    DefectClass.SERVED_RECORD_MISMATCH,
                    Severity.MAJOR,
                    routed,
                    cat,
                    (eid,),
                    f"evidence {eid} is served {counts[eid]} times with ambiguous copies",
                    "correct_specialist_output",
                )
                continue
            record = inp.admitted_evidence.get(eid)
            if record is None:
                c.add(
                    DefectClass.CITATION_OUTSIDE_SERVED,
                    Severity.BLOCKER,
                    routed,
                    cat,
                    (eid,),
                    f"served evidence {eid} is not admitted for this review",
                    "correct_specialist_output",
                )
            elif not _same_record(served_copy, record):
                c.add(
                    DefectClass.SERVED_RECORD_MISMATCH,
                    Severity.MAJOR,
                    routed,
                    cat,
                    (eid,),
                    f"served copy of {eid} differs from the admitted record",
                    "correct_specialist_output",
                )
        served = _served_once(output)
        served_ids = {e.evidence_id for e in output.evidence}
        for claim in output.claims:
            rids = _subjects(claim)
            statement = " ".join(
                inp.requirements[r].normalized_statement for r in rids if r in inp.requirements
            )
            self._traceability_gap(inp, outcome, claim, c)
            for eid in claim.evidence_ids:
                if eid not in served_ids:
                    c.add(
                        DefectClass.CITATION_OUTSIDE_SERVED,
                        Severity.BLOCKER,
                        rids,
                        cat,
                        (eid,),
                        f"claim cites {eid}, which the specialist did not serve",
                        "correct_specialist_output",
                    )
                    continue
                # Admission, project and served-copy problems are reported above, once per copy.
                record = inp.admitted_evidence.get(eid)
                if record is None or eid not in served or not _same_record(served[eid], record):
                    continue
                if record.project_id != inp.project_id:
                    continue
                if not self._collection_ok(inp, eid):
                    c.add(
                        DefectClass.UNAUTHORISED_COLLECTION,
                        Severity.BLOCKER,
                        rids,
                        cat,
                        (eid,),
                        f"claim cites {eid}, whose collection is unknown or not authorised",
                        "correct_specialist_output",
                    )
                if eid in inp.superseded_by:
                    c.add(
                        DefectClass.SUPERSEDED_EVIDENCE_CITED,
                        Severity.MAJOR,
                        rids,
                        cat,
                        (eid,),
                        f"claim cites {eid}, which is superseded by {inp.superseded_by[eid]}",
                        "human_review",
                    )
                if self._stale(inp, record):
                    c.add(
                        DefectClass.STALE_EVIDENCE_CITED,
                        Severity.MAJOR,
                        rids,
                        cat,
                        (eid,),
                        f"claim cites {eid}, which is older than the caller's staleness window",
                        "human_review",
                    )
                if _is_verifiable(record) and not _relevant(claim.claim_text, statement, record):
                    c.add(
                        DefectClass.RELEVANCE_NOT_ESTABLISHED,
                        Severity.MAJOR,
                        rids,
                        cat,
                        (eid,),
                        f"claim cites {eid}, but its summary shares no term with the claim "
                        "or requirement",
                        "human_review",
                    )

    def _claims(self, inp: ReviewInput, outcome: ReviewedOutcome, c: _Collector) -> None:
        output = outcome.output
        if output is None:
            return
        conflict_keys = {conflict.proposal_key for conflict in output.conflicts}
        for claim in output.claims:
            rids = _subjects(claim)
            label = claim.proposal_key or claim.claim_id or "claim"
            if claim.evidence_status in _VERIFIED:
                verifiable = any(
                    eid in inp.admitted_evidence and _is_verifiable(inp.admitted_evidence[eid])
                    for eid in claim.evidence_ids
                )
                if not verifiable:
                    c.add(
                        DefectClass.UNSUPPORTED_VERIFIED_CLAIM,
                        Severity.BLOCKER,
                        rids,
                        outcome.category_id,
                        claim.evidence_ids,
                        f"{label} is {claim.evidence_status.value} without verifiable evidence",
                        "correct_specialist_output",
                    )
            if not claim.evidence_ids and claim.evidence_status not in _LABELLED:
                c.add(
                    DefectClass.UNCITED_UNLABELLED_CLAIM,
                    Severity.MAJOR,
                    rids,
                    outcome.category_id,
                    (),
                    f"{label} has no citation and is not labelled unverified or conflicting",
                    "correct_specialist_output",
                )
            conflicting = (
                claim.evidence_status is EvidenceStatus.CONFLICTING
                or claim.feasibility_status is FeasibilityStatus.CONFLICTING
            )
            if conflicting and not claim.conflict_refs:
                c.add(
                    DefectClass.UNREPORTED_CONFLICT,
                    Severity.MAJOR,
                    rids,
                    outcome.category_id,
                    claim.evidence_ids,
                    f"{label} is conflicting but no conflict entry is attached",
                    "correct_specialist_output",
                )
            for ref in claim.conflict_refs:
                if ref not in conflict_keys:
                    c.add(
                        DefectClass.UNREPORTED_CONFLICT,
                        Severity.MAJOR,
                        rids,
                        outcome.category_id,
                        (),
                        f"{label} refers to conflict {ref}, which is not in the result",
                        "correct_specialist_output",
                    )
        claim_keys = {claim.proposal_key for claim in output.claims}
        for conflict in output.conflicts:
            for key in conflict.claim_proposal_keys:
                if key not in claim_keys:
                    c.add(
                        DefectClass.UNTRACEABLE,
                        Severity.MINOR,
                        conflict.related_requirement_ids,
                        outcome.category_id,
                        conflict.evidence_ids,
                        f"conflict {conflict.proposal_key} names missing claim {key}",
                        "correct_specialist_output",
                    )

    # --- risks, clarification, wording

    def _risks(self, outcome: ReviewedOutcome, c: _Collector) -> None:
        output = outcome.output
        if output is None:
            return
        covered = {rid for risk in output.risks for rid in risk.related_requirement_ids}
        flagged: set[str] = set()
        for claim in output.claims:
            if claim.claim_type not in (ClaimType.SECURITY, ClaimType.API_BEHAVIOR):
                continue
            for rid in _subjects(claim):
                if rid not in covered and rid not in flagged:
                    flagged.add(rid)
                    c.add(
                        DefectClass.MISSING_RISK,
                        Severity.MAJOR,
                        (rid,),
                        outcome.category_id,
                        (),
                        f"{claim.claim_type.value} claim for {rid} has no structured risk",
                        "correct_specialist_output",
                    )

    def _clarification(self, inp: ReviewInput, outcome: ReviewedOutcome, c: _Collector) -> None:
        output = outcome.output
        if output is None:
            return
        question_rids = {
            rid for q in output.clarification_questions for rid in q.related_requirement_ids
        }
        served = {e.evidence_id for e in output.evidence}
        for q in output.clarification_questions:
            if q.status.value != "open":
                c.add(
                    DefectClass.MISSING_CLARIFICATION,
                    Severity.MINOR,
                    q.related_requirement_ids,
                    outcome.category_id,
                    (),
                    "a clarification question is not in the open state",
                    "request_clarification",
                )
        conflicted = {
            rid for conflict in output.conflicts for rid in conflict.related_requirement_ids
        }
        for rid in outcome.requirement_ids:
            if rid not in inp.requirements:
                continue
            cited_admitted = self._cited_admitted(inp, output, rid, served)
            if rid in conflicted or not cited_admitted:
                if rid not in question_rids:
                    c.add(
                        DefectClass.MISSING_CLARIFICATION,
                        Severity.MAJOR,
                        (rid,),
                        outcome.category_id,
                        (),
                        f"{rid} has a gap or conflict but no clarification question",
                        "request_clarification",
                    )
            if not cited_admitted and rid not in conflicted:
                if output.status is SpecialistOutputStatus.COMPLETED and not output.evidence:
                    c.add(
                        DefectClass.NOT_EVIDENCE_VERIFIED,
                        Severity.MAJOR,
                        (rid,),
                        outcome.category_id,
                        (),
                        f"{outcome.category_id} reports COMPLETED with zero evidence for {rid}; "
                        "it cannot be treated as evidence-verified",
                        "human_review",
                    )
                else:
                    c.add(
                        DefectClass.MISSING_EVIDENCE,
                        Severity.MINOR,
                        (rid,),
                        outcome.category_id,
                        (),
                        f"no admitted evidence is cited for {rid}",
                        "human_review",
                    )

    def _cited_admitted(
        self,
        inp: ReviewInput,
        output: SpecialistInvestigationResult,
        rid: str,
        served: set[str],
    ) -> set[str]:
        """Admitted, served, same-project evidence cited for ``rid``. Used for gap reporting."""
        cited: set[str] = set()
        for claim in output.claims:
            if rid not in _subjects(claim):
                continue
            for eid in claim.evidence_ids:
                record = inp.admitted_evidence.get(eid)
                if eid in served and record is not None and record.project_id == inp.project_id:
                    cited.add(eid)
        return cited

    def _backing_citations(
        self, inp: ReviewInput, output: SpecialistInvestigationResult, rid: str
    ) -> set[str]:
        """Evidence that independently supports ``rid``. Every gate must hold; a citation alone
        is not enough, and the upstream claim's verified status is never consulted."""
        if not _parameters_complete(inp):
            return set()
        served = _served_once(output)
        statement = inp.requirements[rid].normalized_statement if rid in inp.requirements else ""
        backed: set[str] = set()
        for claim in output.claims:
            if rid not in _subjects(claim) or claim.evidence_status in _NON_BACKING_CLAIM:
                continue
            for eid in claim.evidence_ids:
                record = inp.admitted_evidence.get(eid)
                served_copy = served.get(eid)
                if record is None or served_copy is None or not _is_verifiable(record):
                    continue
                if record.project_id != inp.project_id or not _same_record(served_copy, record):
                    continue
                if eid in inp.superseded_by or not self._collection_ok(inp, eid):
                    continue
                if self._stale(inp, record):
                    continue
                if not _relevant(claim.claim_text, statement, record):
                    continue
                backed.add(eid)
        return backed

    def _wording(self, outcome: ReviewedOutcome, c: _Collector) -> None:
        output = outcome.output
        if output is None:
            return
        texts: list[tuple[str, tuple[str, ...], str]] = []
        for claim in output.claims:
            texts.append((claim.claim_text, _subjects(claim), "claim"))
        for question in output.clarification_questions:
            texts.append(
                (question.question_text, tuple(question.related_requirement_ids), "question")
            )
        for risk in output.risks:
            texts.append((risk.description, tuple(risk.related_requirement_ids), "risk"))
        for solution in output.candidate_solutions:
            texts.append((solution.summary, tuple(solution.related_requirement_ids), "solution"))
        for text in output.dependencies:
            texts.append((text, tuple(outcome.requirement_ids), "dependency"))
        for text, rids, source in texts:
            if _APPROVAL_WORDING.search(text):
                c.add(
                    DefectClass.UNSUPPORTED_WORDING,
                    Severity.MAJOR,
                    rids,
                    outcome.category_id,
                    (),
                    f"approval-style wording in a specialist {source}",
                    "correct_specialist_output",
                )

    # --- cross-specialist consistency

    def _cross_specialist(self, inp: ReviewInput, c: _Collector) -> None:
        seen: dict[str, dict[str, set[FeasibilityStatus]]] = {}
        for outcome in inp.outcomes:
            if outcome.output is None:
                continue
            for claim in outcome.output.claims:
                if claim.feasibility_status is FeasibilityStatus.UNKNOWN:
                    continue
                for rid in _subjects(claim):
                    seen.setdefault(rid, {}).setdefault(outcome.category_id, set()).add(
                        claim.feasibility_status
                    )
        for rid in sorted(seen):
            per_category = seen[rid]
            statuses = {status for values in per_category.values() for status in values}
            if len(statuses) > 1:
                c.add(
                    DefectClass.CROSS_SPECIALIST_DIVERGENCE,
                    Severity.MAJOR,
                    (rid,),
                    None,
                    (),
                    f"specialists disagree on feasibility for {rid}: "
                    + "; ".join(
                        f"{cat}={','.join(sorted(s.value for s in vals))}"
                        for cat, vals in sorted(per_category.items())
                    ),
                    "human_review",
                )

    # --- statuses

    def _statuses(
        self, inp: ReviewInput, findings: tuple[ReviewFinding, ...]
    ) -> tuple[dict[str, ReviewStatus], dict[str, tuple[str, ...]]]:
        statuses: dict[str, ReviewStatus] = {}
        traceability: dict[str, tuple[str, ...]] = {}
        blocked = {
            rid for f in findings if f.severity is Severity.BLOCKER for rid in f.requirement_ids
        }
        disputed = {
            rid
            for f in findings
            if f.defect_class is DefectClass.CROSS_SPECIALIST_DIVERGENCE
            for rid in f.requirement_ids
        }
        for rid in sorted(inp.requirements):
            categories = sorted(
                {
                    o.category_id
                    for o in inp.outcomes
                    if o.output is not None and rid in o.requirement_ids
                }
            )
            traceability[rid] = tuple(categories)
            conflicted = rid in disputed
            backed = False
            produced = False
            for outcome in inp.outcomes:
                output = outcome.output
                if output is None or rid not in outcome.requirement_ids:
                    continue
                produced = True
                if any(rid in conflict.related_requirement_ids for conflict in output.conflicts):
                    conflicted = True
                if self._backing_citations(inp, output, rid):
                    backed = True
            if rid in blocked:
                statuses[rid] = ReviewStatus.UNSUPPORTED
            elif conflicted:
                statuses[rid] = ReviewStatus.CONFLICTED
            elif backed:
                statuses[rid] = ReviewStatus.EVIDENCE_BACKED
            elif produced:
                statuses[rid] = ReviewStatus.NOT_EVIDENCE_VERIFIED
            else:
                statuses[rid] = ReviewStatus.UNSUPPORTED
        return statuses, traceability
