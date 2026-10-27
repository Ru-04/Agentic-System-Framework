"""
AI-S10 evaluation scenario catalogue.

Every scenario has an identifier, a classification, a status and a dependency. Only ``executed``
scenarios run. Every other status is reported as it is and is never counted as a pass:

- ``executed``: run by the runner against the real engine APIs.
- ``delegated``: covered by an accepted sprint test file. Not re-run here; the gate runs that file.
- ``blocked``: needs an external dependency (Foundation, provider, vendor source, platform,
  approval).
- ``open_limitation``: a known open blocker. The executor checks the limitation is still present.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class Classification(StrEnum):
    SYNTHETIC = "A-isolated-synthetic"
    FOUNDATION = "B-foundation-integration"
    REAL_PROVIDER = "C-real-provider"
    VENDOR_DOCUMENTATION = "D-vendor-documentation-or-sandbox"
    HUMAN_WORKFLOW = "E-full-platform-human-workflow"
    PRODUCTION = "F-production-security-readiness"


class Status(StrEnum):
    EXECUTED = "executed"
    DELEGATED = "delegated"
    BLOCKED = "blocked"
    OPEN_LIMITATION = "open_limitation"


@dataclass(frozen=True)
class Check:
    """An executor's answer. ``passed`` means the expected behaviour was observed."""

    passed: bool
    actual: str


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    area: str
    classification: Classification
    status: Status
    references: tuple[str, ...]
    fixture: str
    expected: str
    dependency: str
    severity: Literal["critical", "major", "minor", "info"]
    executor: str | None = None


Executor = Callable[[], Check]


def _ex(
    scenario_id: str,
    title: str,
    area: str,
    refs: tuple[str, ...],
    fixture: str,
    expected: str,
    severity: Literal["critical", "major", "minor", "info"],
    executor: str,
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        title=title,
        area=area,
        classification=Classification.SYNTHETIC,
        status=Status.EXECUTED,
        references=refs,
        fixture=fixture,
        expected=expected,
        dependency="none (isolated synthetic)",
        severity=severity,
        executor=executor,
    )


def _ext(
    scenario_id: str,
    title: str,
    area: str,
    classification: Classification,
    refs: tuple[str, ...],
    expected: str,
    dependency: str,
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        title=title,
        area=area,
        classification=classification,
        status=Status.BLOCKED,
        references=refs,
        fixture="none (external)",
        expected=expected,
        dependency=dependency,
        severity="major",
    )


def _delegated(
    scenario_id: str, title: str, area: str, refs: tuple[str, ...], test_file: str
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        title=title,
        area=area,
        classification=Classification.SYNTHETIC,
        status=Status.DELEGATED,
        references=refs,
        fixture=test_file,
        expected="covered by the named accepted test file, which the committed gate runs",
        dependency=f"not re-executed by AI-S10; see {test_file}",
        severity="info",
    )


def _limitation(
    scenario_id: str,
    title: str,
    area: str,
    refs: tuple[str, ...],
    expected: str,
    dependency: str,
    executor: str | None,
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        title=title,
        area=area,
        classification=Classification.SYNTHETIC,
        status=Status.OPEN_LIMITATION,
        references=refs,
        fixture="synthetic" if executor else "none",
        expected=expected,
        dependency=dependency,
        severity="critical",
        executor=executor,
    )


SPECIALIST_DOMAINS = (
    ("shopify", "Shopify"),
    ("woocommerce", "WooCommerce/WordPress"),
    ("bigcommerce", "BigCommerce"),
    ("shift4shop", "Shift4Shop (legacy identity)"),
    ("magento", "Magento Open Source/Adobe Commerce"),
    ("standalone", "Standalone applications"),
    ("middleware", "Middleware applications"),
)


def build_catalog() -> tuple[Scenario, ...]:
    scenarios: list[Scenario] = []
    # ---------------------------------------------------------------- seven specialists
    scenarios.append(
        _ex(
            "SPEC-01",
            "Registry identities are complete and compatible",
            "specialists",
            ("AI-S04", "AI-S05", "AI-S06"),
            "registry_map.IDENTITIES",
            "seven identities; verify_identities passes",
            "critical",
            "spec_identities",
        )
    )
    scenarios.append(
        _ex(
            "SPEC-02",
            "Legacy Shift4Shop identity is preserved",
            "specialists",
            ("AI-S04", "AI-S06"),
            "registry_map.IDENTITIES",
            "category three_d_cart_shift_shopify_specialist keeps capability "
            "CAP-3D-CART-SHIFT-SHOPIFY",
            "critical",
            "spec_legacy_shift4shop",
        )
    )
    for index, (key, label) in enumerate(SPECIALIST_DOMAINS, start=1):
        scenarios.append(
            _ex(
                f"SPEC-R{index:02d}",
                f"Requirement routes to {label} only",
                "specialists",
                ("AI-S06",),
                f"AI-S06 statement for {key}",
                "the proposal routes exactly the matching category",
                "critical",
                f"spec_route_{index}",
            )
        )
    scenarios.append(
        _ex(
            "SPEC-08",
            "No execution without operator confirmation (all seven)",
            "specialists",
            ("AI-S06",),
            "AI-S06 seven-requirement proposal",
            "execute refuses when no confirmation is recorded",
            "critical",
            "spec_no_execution_unconfirmed",
        )
    )
    scenarios.append(
        _ex(
            "SPEC-09",
            "Confirmed execution yields one outcome per routed category",
            "specialists",
            ("AI-S06",),
            "AI-S06 seven-requirement proposal",
            "outcomes cover every confirmed category exactly once",
            "major",
            "spec_confirmed_outcomes",
        )
    )
    scenarios.append(
        _ex(
            "SPEC-10",
            "Unsupported platform request is refused (no category routed)",
            "specialists",
            ("AI-S06",),
            "synthetic Wix request",
            "no category is routed for an unsupported platform",
            "major",
            "spec_unsupported_refused",
        )
    )
    scenarios.append(
        _ex(
            "SPEC-11",
            "Multi-specialist overlap routes every matching category",
            "specialists",
            ("AI-S06",),
            "synthetic Shopify and BigCommerce request",
            "both categories are routed and the requirement is listed for each",
            "major",
            "spec_overlap",
        )
    )
    scenarios.append(
        _ex(
            "SPEC-12",
            "Synthetic evidence is labelled as mock, never as verified vendor evidence",
            "specialists",
            ("AI-S04", "AI-S05"),
            "identity.make_evidence for seven identities",
            "every seeded record is synthetic mock evidence",
            "critical",
            "spec_mock_evidence_only",
        )
    )
    scenarios.append(
        _ex(
            "SPEC-13",
            "Specialist claim may not assert VERIFIED status (contract)",
            "specialists",
            ("AI-2", "AI-S07"),
            "synthetic investigation output",
            "validation refuses a VERIFIED claim from a specialist",
            "critical",
            "spec_no_self_verified",
        )
    )
    scenarios.append(
        _delegated(
            "SPEC-14",
            "Partial and failed investigations; transient retry bounded",
            "specialists",
            ("AI-S06",),
            "tests/test_ai_s06_orchestration.py",
        )
    )
    scenarios.append(
        _ext(
            "SPEC-15",
            "Real vendor-documentation validation for each of the seven specialists",
            "specialists",
            Classification.VENDOR_DOCUMENTATION,
            ("AI-S04", "D-02"),
            "each specialist's claims checked against approved official vendor documentation",
            "approved source-access matrix and per-vendor allowlist (D-02); none granted",
        )
    )
    scenarios.append(
        _ext(
            "SPEC-16",
            "Real-platform acceptance for each of the seven platforms",
            "specialists",
            Classification.HUMAN_WORKFLOW,
            ("AI-S10 spec section 10",),
            "end-to-end run against each approved platform sandbox",
            "platform approval; no sandbox or test store authorised",
        )
    )
    # ---------------------------------------------------------------- integrated pipeline
    scenarios.append(
        _ex(
            "PIPE-01",
            "Full synthetic pipeline: routing, confirmation, execution, review, estimate, SOW",
            "pipeline",
            ("AI-S06", "AI-S07", "AI-S08", "AI-S09"),
            "seven-requirement fixture",
            "each stage yields its output; governance fingerprint carried to estimate and SOW",
            "critical",
            "pipe_full",
        )
    )
    scenarios.append(
        _ex(
            "PIPE-02",
            "Governance blocker stays visible through estimate and SOW",
            "pipeline",
            ("AI-S07", "AI-S08", "AI-S09"),
            "blocker on one requirement",
            "blocked readiness in estimate and in SOW risks",
            "critical",
            "pipe_blocker_visible",
        )
    )
    scenarios.append(
        _ex(
            "PIPE-03",
            "EVIDENCE_BACKED is not approval (no approval reached downstream)",
            "pipeline",
            ("AI-S07", "AI-S09"),
            "backed requirement fixture",
            "reviewer authorises nothing; SOW approval stays pending",
            "critical",
            "pipe_not_approval",
        )
    )
    scenarios.append(
        _delegated(
            "PIPE-04",
            "Lead intake and semantic requirement analysis",
            "pipeline",
            ("AI-1", "AI-2"),
            "tests/test_requirement_analysis.py",
        )
    )
    scenarios.append(
        _delegated(
            "PIPE-05",
            "Evidence retrieval over the admitted index",
            "pipeline",
            ("AI-S03",),
            "tests/test_ai_s03_retrieval.py",
        )
    )
    # ---------------------------------------------------------------- security and authorisation
    scenarios.append(
        _ex(
            "SEC-01",
            "Cross-project requirement access refused by the SOW",
            "security",
            ("AI-S09",),
            "two synthetic projects",
            "SOW refuses a requirement from another project",
            "critical",
            "sec_cross_project_requirement",
        )
    )
    scenarios.append(
        _ex(
            "SEC-02",
            "Cross-collection evidence refused by the reviewer",
            "security",
            ("AI-S07",),
            "authorised set excludes the evidence collection",
            "claim cannot back; unauthorised collection blocker",
            "critical",
            "sec_cross_collection",
        )
    )
    scenarios.append(
        _ex(
            "SEC-03",
            "Unauthorised source reference gives no estimate numbers",
            "security",
            ("AI-S08",),
            "cross-project basis without authorisation",
            "line is needs_inputs with no numbers",
            "critical",
            "sec_unauthorised_source",
        )
    )
    scenarios.append(
        _ex(
            "SEC-04",
            "Requirement revision mismatch is reported as stale",
            "security",
            ("AI-S08", "AI-S09"),
            "estimate built on revision 2, SOW on revision 1",
            "stale revision is an integrity issue",
            "major",
            "sec_revision_mismatch",
        )
    )
    scenarios.append(
        _ex(
            "SEC-05",
            "Forged (mock) confirmation refused on the production path",
            "security",
            ("AI-S06",),
            "confirmation marked mock on production orchestrator",
            "ConfirmationRefused",
            "critical",
            "sec_forged_confirmation",
        )
    )
    scenarios.append(
        _ex(
            "SEC-06",
            "Replayed confirmation refused on a second use",
            "security",
            ("AI-S06",),
            "same confirmation submitted twice",
            "second confirmation refused",
            "critical",
            "sec_replay",
        )
    )
    scenarios.append(
        _ex(
            "SEC-07",
            "Expired confirmation refused",
            "security",
            ("AI-S06",),
            "confirmation with expiry before the clock",
            "ConfirmationRefused",
            "critical",
            "sec_expired",
        )
    )
    scenarios.append(
        _ex(
            "SEC-08",
            "Confirmation bound to another run is refused",
            "security",
            ("AI-S06",),
            "confirmation carrying a different run identifier",
            "ConfirmationRefused",
            "critical",
            "sec_wrong_run",
        )
    )
    scenarios.append(
        _limitation(
            "SEC-09",
            "Direct specialist execution bypass (legacy run_specialist ungated) — R-1",
            "security",
            ("R-1",),
            "run_specialist takes no confirmation or actor; limitation present",
            "R-1 open: not a production authorisation boundary",
            "sec_r1_present",
        )
    )
    scenarios.append(
        _ex(
            "SEC-10",
            "Prompt injection in client requirement text is data, not instruction",
            "security",
            ("AI-S09",),
            "requirement text with an approval instruction",
            "flagged; approval state unchanged",
            "critical",
            "sec_injection_client",
        )
    )
    scenarios.append(
        _ex(
            "SEC-11",
            "Prompt injection in retrieved evidence does not change review status",
            "security",
            ("AI-S07",),
            "evidence summary with an instruction to mark verified",
            "review status and authorisation unchanged",
            "critical",
            "sec_injection_evidence",
        )
    )
    scenarios.append(
        _ex(
            "SEC-12",
            "Malformed or contradictory specialist output is refused",
            "security",
            ("AI-2", "AI-S07"),
            "output with VERIFIED claim and no evidence",
            "validation refuses the output",
            "critical",
            "sec_malformed_output",
        )
    )
    scenarios.append(
        _ex(
            "SEC-13",
            "Approval-state promotion is refused at every input and status boundary",
            "security",
            ("AI-S08", "AI-S09"),
            "approval fields in SOW input; approved estimate status",
            "refused",
            "critical",
            "sec_approval_promotion",
        )
    )
    scenarios.append(
        _ex(
            "SEC-14",
            "Unsupported verified-claim assertion is refused",
            "security",
            ("AI-S07",),
            "VERIFIED claim citing no evidence",
            "reviewer flags unsupported verified claim",
            "critical",
            "sec_unsupported_verified",
        )
    )
    scenarios.append(
        _ex(
            "SEC-15",
            "Unauthorised historical estimate reference is refused",
            "security",
            ("AI-S08",),
            "historical basis from another project, no authorisation",
            "no numbers",
            "critical",
            "sec_historical_reference",
        )
    )
    scenarios.append(
        _ex(
            "SEC-16",
            "Error messages do not leak sentinel secrets",
            "security",
            ("AI-S08", "AI-S09"),
            "sentinel in mapping keys and extra fields",
            "sentinel absent from messages",
            "critical",
            "sec_error_leakage",
        )
    )
    scenarios.append(
        _ex(
            "SEC-17",
            "Inputs to reviewer and estimator are not mutated",
            "security",
            ("AI-S07", "AI-S08"),
            "reviewed and estimated inputs",
            "inputs unchanged after execution",
            "major",
            "sec_no_mutation",
        )
    )
    scenarios.append(
        _ext(
            "SEC-18",
            "Durable, tamper-evident audit of runs, confirmations and refusals",
            "security",
            Classification.FOUNDATION,
            ("AI-S06",),
            "every run and refusal persisted and tamper-evident",
            "Foundation audit and run-state persistence; not implemented",
        )
    )
    # ---------------------------------------------------------------- evidence and governance
    scenarios.append(
        _ex(
            "EVID-01",
            "COMPLETED specialist output with zero evidence is not evidence-verified",
            "evidence",
            ("AI-S07",),
            "COMPLETED output, no evidence",
            "NOT_EVIDENCE_VERIFIED with MAJOR finding",
            "critical",
            "evid_zero_evidence",
        )
    )
    scenarios.append(
        _ex(
            "EVID-02",
            "Valid verified provenance backs a relevant claim",
            "evidence",
            ("AI-S07",),
            "admitted approved record with provenance",
            "EVIDENCE_BACKED",
            "major",
            "evid_valid_backs",
        )
    )
    scenarios.append(
        _ex(
            "EVID-03",
            "Stripped provenance does not back",
            "evidence",
            ("AI-S07",),
            "verified record with content_hash removed",
            "not backed",
            "critical",
            "evid_stripped_provenance",
        )
    )
    scenarios.append(
        _ex(
            "EVID-04",
            "Missing authorised collection set prevents backing",
            "evidence",
            ("AI-S07",),
            "authorised_collections omitted",
            "not backed; MISSING_REVIEW_PARAMETER",
            "critical",
            "evid_missing_collection_set",
        )
    )
    scenarios.append(
        _ex(
            "EVID-05",
            "Missing freshness window prevents backing",
            "evidence",
            ("AI-S07",),
            "as_of or stale_after omitted",
            "not backed",
            "critical",
            "evid_missing_window",
        )
    )
    scenarios.append(
        _ex(
            "EVID-06",
            "Mismatched served record is reported and does not back",
            "evidence",
            ("AI-S07",),
            "served content_hash differs",
            "SERVED_RECORD_MISMATCH; not backed",
            "critical",
            "evid_served_mismatch",
        )
    )
    scenarios.append(
        _ex(
            "EVID-07",
            "Stale evidence does not back",
            "evidence",
            ("AI-S07",),
            "record one microsecond older than the window",
            "STALE_EVIDENCE_CITED; not backed",
            "major",
            "evid_stale",
        )
    )
    scenarios.append(
        _ex(
            "EVID-08",
            "Superseded evidence does not back",
            "evidence",
            ("AI-S07",),
            "superseded_by names a successor",
            "SUPERSEDED_EVIDENCE_CITED; not backed",
            "major",
            "evid_superseded",
        )
    )
    scenarios.append(
        _ex(
            "EVID-09",
            "Conflicting evidence yields CONFLICTED",
            "evidence",
            ("AI-S07", "AI-S08"),
            "conflict entry references the claim",
            "CONFLICTED",
            "critical",
            "evid_conflict",
        )
    )
    scenarios.append(
        _ex(
            "EVID-10",
            "Unverified hypothesis with citations does not back",
            "evidence",
            ("AI-S07",),
            "unverified synthetic record cited",
            "not backed",
            "critical",
            "evid_unverified_hypothesis",
        )
    )
    scenarios.append(
        _ex(
            "EVID-11",
            "Fabricated citation of an unserved record is a blocker",
            "evidence",
            ("AI-S07",),
            "claim cites a record the specialist did not serve",
            "CITATION_OUTSIDE_SERVED blocker",
            "critical",
            "evid_fabricated_citation",
        )
    )
    scenarios.append(
        _ex(
            "EVID-12",
            "Insufficient requirement coverage is reported",
            "evidence",
            ("AI-S07",),
            "a requirement routed to no specialist",
            "COVERAGE_GAP",
            "major",
            "evid_coverage_gap",
        )
    )
    scenarios.append(
        _ex(
            "EVID-13",
            "Missing clarification is reported for an evidence gap",
            "evidence",
            ("AI-S07",),
            "requirement with no admitted evidence and no question",
            "MISSING_CLARIFICATION",
            "major",
            "evid_missing_clarification",
        )
    )
    scenarios.append(
        _ex(
            "EVID-14",
            "Reviewer findings do not alter original specialist outputs",
            "evidence",
            ("AI-S07",),
            "review of a populated output",
            "output dump unchanged",
            "critical",
            "evid_no_output_change",
        )
    )
    scenarios.append(
        _ex(
            "EVID-15",
            "Governance blockers cannot be silently erased downstream",
            "evidence",
            ("AI-S07", "AI-S08", "AI-S09"),
            "blocking requirement",
            "blocker present in estimate and SOW",
            "critical",
            "evid_blocker_not_erased",
        )
    )
    scenarios.append(
        _limitation(
            "EVID-16",
            "Evidence sufficiency is lexical, not semantic (AI-S07 relevance screen)",
            "evidence",
            ("AI-S07",),
            "a relevant-sounding but off-topic summary backs; screen is lexical",
            "semantic relevance requires human or approved model review (governance decision)",
            "evid_lexical_limit",
        )
    )
    # ---------------------------------------------------------------- estimation (AI-S08)
    scenarios.append(
        _ex(
            "EST-01",
            "Low/Likely/High oracle: hand-computed totals",
            "estimation",
            ("AI-S08",),
            "three estimated tasks with known hours",
            "sums equal the oracle exactly",
            "critical",
            "est_oracle",
        )
    )
    scenarios.append(
        _ex(
            "EST-02",
            "Ordering is enforced; unordered hours refused",
            "estimation",
            ("AI-S08",),
            "low > likely and likely > high",
            "refused",
            "critical",
            "est_ordering",
        )
    )
    scenarios.append(
        _ex(
            "EST-03",
            "Duplicate work counted once in project totals",
            "estimation",
            ("AI-S08",),
            "two tasks sharing one implementation key",
            "counted once",
            "critical",
            "est_duplicate",
        )
    )
    scenarios.append(
        _ex(
            "EST-04",
            "Missing estimate lines are excluded and listed; totals incomplete",
            "estimation",
            ("AI-S08",),
            "task with no hours",
            "excluded line listed; complete False",
            "critical",
            "est_missing_lines",
        )
    )
    scenarios.append(
        _ex(
            "EST-05",
            "Governance traceability and fingerprint carried to the draft",
            "estimation",
            ("AI-S07", "AI-S08"),
            "governance summary",
            "fingerprint and requirement revisions recorded",
            "major",
            "est_traceability",
        )
    )
    scenarios.append(
        _ex(
            "EST-06",
            "Unverified numerical basis gives no numbers",
            "estimation",
            ("AI-S08",),
            "synthetic basis when not permitted",
            "needs_inputs, no numbers",
            "critical",
            "est_unverified_basis",
        )
    )
    scenarios.append(
        _ex(
            "EST-07",
            "Requirement revision mismatch makes the line stale",
            "estimation",
            ("AI-S08",),
            "task on an older revision",
            "needs_inputs (stale)",
            "major",
            "est_revision",
        )
    )
    scenarios.append(
        _ex(
            "EST-08",
            "Estimate has no rates, weighting or contingency",
            "estimation",
            ("AI-S08",),
            "estimate and totals schemas",
            "no such field exists",
            "critical",
            "est_no_rates",
        )
    )
    scenarios.append(
        _ex(
            "EST-09",
            "Draft-only estimate state",
            "estimation",
            ("AI-S08",),
            "all outputs",
            "draft_status constant; no approved status",
            "critical",
            "est_draft_only",
        )
    )
    scenarios.append(
        _ex(
            "EST-10",
            "Zero-hour boundary counted as a numeric zero, not as missing",
            "estimation",
            ("AI-S08",),
            "0.0 / 0.0 / 0.0 task",
            "indicative and complete",
            "major",
            "est_zero_boundary",
        )
    )
    # ---------------------------------------------------------------- SOW (AI-S09)
    scenarios.append(
        _ex(
            "SOW-01",
            "All supported sections are present",
            "sow",
            ("AI-S09",),
            "full SOW fixture",
            "twelve section identifiers including overview",
            "major",
            "sow_sections",
        )
    )
    scenarios.append(
        _ex(
            "SOW-02",
            "Requirement-to-deliverable coverage and traceability",
            "sow",
            ("AI-S09",),
            "requirements with and without deliverables",
            "unrepresented listed; traceability rows",
            "critical",
            "sow_coverage",
        )
    )
    scenarios.append(
        _ex(
            "SOW-03",
            "In-scope and out-of-scope are represented accurately",
            "sow",
            ("AI-S09",),
            "one proposed exclusion",
            "exclusion labelled as proposal requiring confirmation",
            "major",
            "sow_scope_accuracy",
        )
    )
    scenarios.append(
        _ex(
            "SOW-04",
            "Unsupported sections are explicitly unsupported, not filled",
            "sow",
            ("AI-S09",),
            "SOW with no milestones or assumptions",
            "explicit not_supported labels",
            "critical",
            "sow_unsupported_explicit",
        )
    )
    scenarios.append(
        _ex(
            "SOW-05",
            "Governance blockers carried through the SOW",
            "sow",
            ("AI-S07", "AI-S09"),
            "blocked requirement",
            "blocker in risks and deliverable readiness",
            "critical",
            "sow_blocker",
        )
    )
    scenarios.append(
        _ex(
            "SOW-06",
            "Provisional estimates remain provisional",
            "sow",
            ("AI-S08", "AI-S09"),
            "unverified hypothesis",
            "provisional readiness shown",
            "major",
            "sow_provisional",
        )
    )
    scenarios.append(
        _ex(
            "SOW-07",
            "needs_inputs values remain nonnumeric in the SOW",
            "sow",
            ("AI-S08", "AI-S09"),
            "task without hours",
            "no number for the line or its deliverable",
            "critical",
            "sow_nonnumeric",
        )
    )
    scenarios.append(
        _ex(
            "SOW-08",
            "Incomplete totals are visibly identified",
            "sow",
            ("AI-S08", "AI-S09"),
            "partial estimate",
            "banner PARTIAL; complete False",
            "critical",
            "sow_incomplete_visible",
        )
    )
    scenarios.append(
        _ex(
            "SOW-09",
            "No invented milestones dates, fixed calendar dates or durations",
            "sow",
            ("AI-S09",),
            "milestones with no dates",
            "no date pattern in output",
            "critical",
            "sow_no_dates",
        )
    )
    scenarios.append(
        _ex(
            "SOW-10",
            "No fabricated pricing or rate fields",
            "sow",
            ("AI-S09",),
            "SOW output schema",
            "no price, rate, discount, signature fields",
            "critical",
            "sow_no_pricing",
        )
    )
    scenarios.append(
        _ex(
            "SOW-11",
            "No autonomous approval; draft lifecycle",
            "sow",
            ("AI-S09",),
            "SOW output",
            "pending_human_approval; approver None",
            "critical",
            "sow_draft_lifecycle",
        )
    )
    scenarios.append(
        _ex(
            "SOW-12",
            "Client text is rendered as data, injection-safe",
            "sow",
            ("AI-S09",),
            "injection in several fields",
            "flagged; approval unchanged",
            "critical",
            "sow_injection_data",
        )
    )
    scenarios.append(
        _ext(
            "SOW-13",
            "WDS house-template fidelity and DOCX/PDF export",
            "sow",
            Classification.HUMAN_WORKFLOW,
            ("D-10",),
            "output matches the approved house template and renders to DOCX/PDF",
            "D-10 approved template, section contract and export tests",
        )
    )
    # ---------------------------------------------------------------- external and production gates
    scenarios.append(
        _ext(
            "EXT-01",
            "Real-provider semantic evaluation of requirement analysis",
            "external",
            Classification.REAL_PROVIDER,
            ("D-12",),
            "provider results meet approved thresholds",
            "LLM provider and model decision (D-12) and live-call approval",
        )
    )
    scenarios.append(
        _ext(
            "EXT-02",
            "Authorised test-store and sandbox investigation",
            "external",
            Classification.VENDOR_DOCUMENTATION,
            ("D-02", "AI-S04"),
            "sandbox behaviour matches vendor docs",
            "source-access approval and sandbox credentials; none granted",
        )
    )
    scenarios.append(
        _ext(
            "EXT-03",
            "Full-platform human workflow and UAT",
            "external",
            Classification.HUMAN_WORKFLOW,
            ("AI-S10 spec section 3",),
            "human reviewers complete the workflow",
            "Foundation UI and human participants; not available",
        )
    )
    scenarios.append(
        _ext(
            "EXT-04",
            "Production security and readiness checks",
            "external",
            Classification.PRODUCTION,
            ("GOVERNANCE",),
            "penetration and configuration review passes",
            "production environment, configuration decisions and external review",
        )
    )
    scenarios.append(
        _ext(
            "EXT-05",
            "Foundation requirement and evidence APIs (authoritative reads)",
            "external",
            Classification.FOUNDATION,
            ("AI-S02", "AI-S04"),
            "reads return authoritative records",
            "Foundation API not available to the engine",
        )
    )
    scenarios.append(
        _ext(
            "EXT-06",
            "Authenticated operator confirmations (R-2)",
            "external",
            Classification.FOUNDATION,
            ("R-2",),
            "confirmations issued by a Foundation operator session",
            "Foundation-issued operator authorisation not implemented",
        )
    )
    scenarios.append(
        _ext(
            "EXT-07",
            "Skipped Foundation integration tests (three)",
            "external",
            Classification.FOUNDATION,
            ("AI-S02", "AI-S04"),
            "three tests pass in the Foundation environment",
            "Foundation test environment and approval; tests are skipped, not passed",
        )
    )
    scenarios.append(
        _limitation(
            "EXT-08",
            "Governance decisions still open (A-4, C-15, GP-1, D-05, D-06/D-07)",
            "governance",
            ("A-4", "C-15", "GP-1", "D-05", "D-06", "D-07"),
            "each decision is recorded as open in the governance register",
            "WDS decisions",
            None,
        )
    )
    scenarios.extend(
        [
            _ex(
                "REC-01",
                "Transient specialist failure is retried, and the retry is bounded",
                "recovery",
                ("AI-S06",),
                "synthetic seven-category run; specialist call replaced by FAILED_TRANSIENT",
                "every category makes exactly max_attempts (2) calls and ends transient",
                "major",
                "rec_transient_bounded",
            ),
            _ex(
                "REC-02",
                "Permanent specialist refusal is not retried",
                "recovery",
                ("AI-S06",),
                "synthetic seven-category run; specialist call replaced by FAILED_VALIDATION",
                "every category makes one call; no retry follows a permanent status",
                "major",
                "rec_permanent_no_retry",
            ),
            _ex(
                "REC-03",
                "Partial authorisation refuses the affected category with no fallback",
                "recovery",
                ("AI-S06", "AI-S07"),
                "synthetic run with one collection withheld from the authorised set",
                "the withheld category uses no evidence and reports evidence_unavailable; "
                "no other collection is substituted; the other categories run",
                "critical",
                "rec_partial_authorisation",
            ),
        ]
    )
    return tuple(scenarios)


def executor_names(catalog: tuple[Scenario, ...]) -> tuple[str, ...]:
    return tuple(sorted({s.executor for s in catalog if s.executor is not None}))
