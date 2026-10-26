"""Runs the synthetic dataset through the real workflow and reports per-case and aggregate results.

A case passes only if every stated expectation holds and no traceability, clarification or
approval-boundary check fails. Aggregate metrics each carry a target. The report's gate passes only
when every target is met and every case passes.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from webdesk_ai.catalog import default_registry
from webdesk_ai.contracts import (
    EvidenceReference,
    RequirementStatus,
    SpecialistInvestigationResult,
)
from webdesk_ai.evaluation.cases import CASES, DATASET_VERSION, EvalCase, segment_uuid
from webdesk_ai.foundation.client import FoundationReadClient, PrincipalCredential
from webdesk_ai.foundation.mock import MockFoundation, MockVersion, segment_row
from webdesk_ai.models import ScriptedModel
from webdesk_ai.orchestration import (
    ReviewPackage,
    WorkflowConfig,
    count_unsupported_claims,
    run_workflow,
)
from webdesk_ai.specialists.base import EvidenceProvider, SpecialistDescriptor, SpecialistRegistry
from webdesk_ai.specialists.doubles import InvalidClaimSpecialist, SlowSpecialist
from webdesk_ai.specialists.shopify import SyntheticShopifyEvidence

NOW = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
TOKEN = "synthetic-eval-token-not-a-secret"  # noqa: S105 - synthetic evaluation fixture
PROJECT = UUID("10000000-0000-4000-8000-0000000000ee")
RUN = UUID("20000000-0000-4000-8000-0000000000ee")

TARGETS: dict[str, float] = {
    "decomposition_accuracy": 1.0,
    "traceability_rate": 1.0,
    "hallucinated_refs_in_output": 0.0,
    "clarification_completeness": 1.0,
    "unsupported_claims_accepted": 0.0,
    "verified_claims_in_outputs": 0.0,
    "routing_accuracy": 1.0,
    "invalid_schema_detection_rate": 1.0,
    "approval_boundary_violations": 0.0,
    "review_flags_fixed": 1.0,
}
# Metrics whose target is a maximum rather than a minimum.
CEILING_METRICS = frozenset(
    {
        "hallucinated_refs_in_output",
        "unsupported_claims_accepted",
        "verified_claims_in_outputs",
        "approval_boundary_violations",
    }
)


class _NoEvidence:
    """Evidence provider that returns nothing. Used to test the missing-evidence path."""

    def lookup(self, platform_id: str, topic_keys: Sequence[str]) -> tuple[EvidenceReference, ...]:
        return ()


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    category: str
    status: str
    passed: bool
    failures: tuple[str, ...]
    requirements: int
    llm_calls: int
    content_attempts: int
    rejected_attempts: int
    schema_failures: int
    refs_total: int
    refs_traceable: int
    refs_hallucinated: int
    flagged: int
    flagged_with_question: int
    routing_checks: int
    routing_matched: int
    unsupported_claims: int
    verified_claims: int
    approval_violations: int
    flags_fixed: bool


@dataclass(frozen=True)
class EvalReport:
    dataset_version: str
    cases: tuple[CaseResult, ...]
    metrics: dict[str, float]
    failed_metrics: tuple[str, ...] = field(default=())

    @property
    def gate_passed(self) -> bool:
        return not self.failed_metrics and all(case.passed for case in self.cases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "gate_passed": self.gate_passed,
            "metrics": {
                name: {
                    "value": value,
                    "target": TARGETS[name],
                    "passed": name not in self.failed_metrics,
                }
                for name, value in self.metrics.items()
            },
            "cases": [
                {
                    "case_id": c.case_id,
                    "category": c.category,
                    "status": c.status,
                    "passed": c.passed,
                    "failures": list(c.failures),
                    "requirements": c.requirements,
                    "llm_calls": c.llm_calls,
                    "rejected_attempts": c.rejected_attempts,
                }
                for c in self.cases
            ],
        }


def _registry(kind: str) -> SpecialistRegistry:
    base = default_registry()
    if kind == "default":
        return base
    factory = InvalidClaimSpecialist if kind == "invalid_specialist" else SlowSpecialist
    others = tuple(d for d in base.descriptors if d.category_id != "shopify_specialist")
    shopify = SpecialistDescriptor(
        category_id="shopify_specialist",
        display_name="Shopify Specialist",
        platform_ids=frozenset({"shopify"}),
        factory=factory,
    )
    return SpecialistRegistry(version=base.version, descriptors=(shopify, *others))


def _foundation(case: EvalCase) -> MockFoundation:
    versions: list[MockVersion] = []
    for version in case.versions:
        source = segment_uuid(case.case_id, f"source:{version.label}")
        version_id = segment_uuid(case.case_id, f"version:{version.label}")
        segments = [
            segment_row(
                segment_uuid(case.case_id, label),
                "txt_line_range",
                {"line_start": index, "line_end": index},
                text,
            )
            for index, (label, text) in enumerate(version.segments, start=1)
        ]
        versions.append(
            MockVersion(
                source_version_id=version_id,
                source_id=source,
                version=1,
                scan_status=version.scan_status,
                access_classification=version.access_classification,
                mime_type="text/plain",
                content=b"",
                segments=segments,
            )
        )
    return MockFoundation(
        token=TOKEN,
        run_id=RUN,
        project_id=PROJECT,
        project_name=case.case_id,
        versions=versions,
        now=lambda: NOW,
        expires_at=NOW + timedelta(minutes=15),
    )


def _visible_text(case: EvalCase) -> dict[UUID, str]:
    visible: dict[UUID, str] = {}
    for version in case.versions:
        if version.scan_status == "quarantined" or version.access_classification == "restricted":
            continue
        for label, text in version.segments:
            visible[segment_uuid(case.case_id, label)] = text
    return visible


def run_case(case: EvalCase) -> CaseResult:
    fdn = _foundation(case)
    client = FoundationReadClient(
        transport=fdn,
        credential=PrincipalCredential(token=TOKEN, expires_at=NOW + timedelta(minutes=15)),
        run_id=RUN,
        project_id=PROJECT,
        clock=lambda: NOW,
    )
    ids: Mapping[str, UUID] = {
        label: segment_uuid(case.case_id, label)
        for version in case.versions
        for label, _ in version.segments
    }
    model = ScriptedModel(outcomes=case.responses(ids))
    evidence: EvidenceProvider
    if case.evidence == "synthetic":
        evidence = SyntheticShopifyEvidence()
    else:
        evidence = _NoEvidence()
    config = WorkflowConfig(
        model=model,
        registry=_registry(case.registry),
        evidence=evidence,
        authorized_categories=case.authorized,
        model_timeout_seconds=30.0,
        specialist_timeout_seconds=case.specialist_timeout_seconds,
    )
    package = run_workflow(client=client, config=config)
    return _check(case, package, _visible_text(case))


def _check(case: EvalCase, package: ReviewPackage, visible: dict[UUID, str]) -> CaseResult:
    analysis = package.analysis
    expect = case.expect
    failures: list[str] = []

    if analysis.status is not expect.status:
        failures.append(f"status {analysis.status.value} != {expect.status.value}")
    if (
        expect.requirement_count is not None
        and len(analysis.requirements) != expect.requirement_count
    ):
        failures.append(f"requirements {len(analysis.requirements)} != {expect.requirement_count}")
    if len(analysis.clarification_questions) < expect.min_questions:
        failures.append("fewer clarification questions than expected")
    if expect.llm_calls is not None and analysis.llm_calls != expect.llm_calls:
        failures.append(f"model calls {analysis.llm_calls} != {expect.llm_calls}")
    if (
        expect.rejected_attempts is not None
        and analysis.rejected_attempts != expect.rejected_attempts
    ):
        failures.append(f"rejected {analysis.rejected_attempts} != {expect.rejected_attempts}")

    pairs = {
        frozenset({req.requirement_id, other})
        for req in analysis.requirements
        for other in req.related_requirement_ids
    }
    if expect.schema_failures is not None and analysis.schema_failures != expect.schema_failures:
        failures.append(f"schema failures {analysis.schema_failures} != {expect.schema_failures}")
    if expect.related_pairs is not None and len(pairs) != expect.related_pairs:
        failures.append(f"related pairs {len(pairs)} != {expect.related_pairs}")

    routing_actual = {(r.category_id, r.outcome.value) for r in analysis.routing_recommendations}
    routing_checks = 0
    routing_matched = 0
    if expect.routing is not None:
        routing_checks = 1
        if expect.routing <= routing_actual:
            routing_matched = 1
        else:
            failures.append(f"routing missing {sorted(expect.routing - routing_actual)}")

    specialist_actual = {
        (r.agent_id.split(":", 1)[1], r.status.value) for r in package.specialist_results
    }
    if not expect.specialist_statuses <= specialist_actual:
        failures.append(f"specialist statuses {sorted(specialist_actual)}")
    skipped_actual = {(s.category_id, s.reason) for s in package.skipped_categories}
    if not expect.skipped <= skipped_actual:
        failures.append(f"skipped {sorted(skipped_actual)}")

    refs_total = refs_ok = refs_bad = 0
    for req in analysis.requirements:
        for ref in req.source_refs:
            refs_total += 1
            text = visible.get(ref.segment_id)
            if text is None:
                refs_bad += 1
            elif req.original_wording in text:
                refs_ok += 1

    flagged = [
        r for r in analysis.requirements if r.ambiguities or r.missing_information or r.conflict_ids
    ]
    flagged_with_question = [r for r in flagged if r.clarification_question_ids]
    if package.clarification_gaps:
        failures.append(f"clarification gaps {package.clarification_gaps}")

    accepted = [
        r.output
        for r in package.specialist_results
        if isinstance(r.output, SpecialistInvestigationResult)
    ]
    unsupported = sum(count_unsupported_claims(output) for output in accepted)
    verified = sum(
        1
        for output in accepted
        for claim in output.claims
        if claim.evidence_status.value == "verified"
    )
    approval_violations = sum(
        1
        for req in analysis.requirements
        if req.status in (RequirementStatus.VERIFIED, RequirementStatus.ACCEPTED_FOR_SCOPE)
        or req.materiality != "unassessed"
    )
    flags_fixed = (
        package.flags.scope_approved is False and package.flags.requirements_approved is False
    )

    rendered = package.model_dump_json()
    for text in expect.forbidden_texts:
        if text in rendered:
            failures.append(f"forbidden content appeared in output: {text}")
    if refs_bad:
        failures.append(f"{refs_bad} source reference(s) do not resolve to visible segments")
    if refs_total != refs_ok + refs_bad:
        failures.append("traceability accounting mismatch")
    if approval_violations:
        failures.append("requirement status crossed the approval boundary")
    if unsupported:
        failures.append(f"{unsupported} unsupported claim(s) in accepted output")
    if verified:
        failures.append(f"{verified} claim(s) marked verified from synthetic evidence")

    return CaseResult(
        case_id=case.case_id,
        category=case.category,
        status=analysis.status.value,
        passed=not failures,
        failures=tuple(failures),
        requirements=len(analysis.requirements),
        llm_calls=analysis.llm_calls,
        content_attempts=analysis.content_attempts,
        rejected_attempts=analysis.rejected_attempts,
        schema_failures=analysis.schema_failures,
        refs_total=refs_total,
        refs_traceable=refs_ok,
        refs_hallucinated=refs_bad,
        flagged=len(flagged),
        flagged_with_question=len(flagged_with_question),
        routing_checks=routing_checks,
        routing_matched=routing_matched,
        unsupported_claims=unsupported,
        verified_claims=verified,
        approval_violations=approval_violations,
        flags_fixed=flags_fixed,
    )


def _meets(name: str, value: float) -> bool:
    if name in CEILING_METRICS:
        return value <= TARGETS[name]
    return value >= TARGETS[name]


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def run_dataset(cases: tuple[EvalCase, ...] = CASES) -> EvalReport:
    results = tuple(run_case(case) for case in cases)
    decomposition = [
        r for r, c in zip(results, cases, strict=True) if c.expect.requirement_count is not None
    ]
    decomposition_ok = sum(
        1
        for r, c in zip(results, cases, strict=True)
        if c.expect.requirement_count is not None and r.requirements == c.expect.requirement_count
    )
    metrics: dict[str, float] = {
        "decomposition_accuracy": _ratio(decomposition_ok, len(decomposition)),
        "traceability_rate": _ratio(
            sum(r.refs_traceable for r in results), sum(r.refs_total for r in results)
        ),
        "hallucinated_refs_in_output": float(sum(r.refs_hallucinated for r in results)),
        "clarification_completeness": _ratio(
            sum(r.flagged_with_question for r in results), sum(r.flagged for r in results)
        ),
        "unsupported_claims_accepted": float(sum(r.unsupported_claims for r in results)),
        "verified_claims_in_outputs": float(sum(r.verified_claims for r in results)),
        "routing_accuracy": _ratio(
            sum(r.routing_matched for r in results), sum(r.routing_checks for r in results)
        ),
        "invalid_schema_detection_rate": _ratio(
            sum(
                min(r.schema_failures, c.expect.schema_failures or 0)
                for r, c in zip(results, cases, strict=True)
            ),
            sum(c.expect.schema_failures or 0 for c in cases),
        ),
        "approval_boundary_violations": float(sum(r.approval_violations for r in results)),
        "review_flags_fixed": _ratio(sum(r.flags_fixed for r in results), len(results)),
    }
    failed = tuple(name for name, value in metrics.items() if not _meets(name, value))
    return EvalReport(
        dataset_version=DATASET_VERSION,
        cases=results,
        metrics=metrics,
        failed_metrics=failed,
    )


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: python -m webdesk_ai.evaluation.runner <report.json>" + "\n")
        return 2
    report = run_dataset()
    Path(argv[1]).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    passed = sum(case.passed for case in report.cases)
    gate = "PASS" if report.gate_passed else "FAIL"
    sys.stdout.write(
        f"dataset={report.dataset_version} cases={len(report.cases)} passed={passed} gate={gate}"
        + "\n"
    )
    return 0 if report.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
