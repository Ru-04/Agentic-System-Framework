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
from dataclasses import dataclass, replace
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
    # The component whose refusal produced this result, if the check observed one. A scenario that
    # declares an enforcement point passes only when this matches it (see runner._judge).
    enforced_by: str | None = None


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
    # Name of the protective function that must raise the refusal (e.g. ``consume``). None means the
    # scenario asserts behaviour that is not a refusal at a single enforcement point.
    enforcement: str | None = None


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
            "execute refused with 'no operator confirmation is in force for this run' at execute; "
            "no specialist runs; a confirmed run executes all seven",
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
            "refused with reason 'mock confirmation is not permitted on the production path' at "
            "verify_confirmation; a valid human-shaped confirmation is accepted",
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
            "same confirmation submitted twice to verification, sharing one ledger",
            "second use refused with 'confirmation ID was already used' at the ledger (consume)",
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
            "refused with reason 'confirmation has expired' at verify_confirmation; an unexpired "
            "confirmation is accepted",
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
            "refused with reason 'confirmation is bound to another run' at "
            "verify_confirmation; the "
            "correct run is accepted",
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
            "a direct call to run_specialist with no confirmation, actor or proposal returns an "
            "execution status; the limitation is still present",
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
            "output with a VERIFIED claim and no evidence",
            "refused by the Claim contract at construction (the Claim model is the "
            "enforcement point)",
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
                "for each permanent variant (validation, permission, unsupported) every category "
                "makes one call and no retry follows",
                "major",
                "rec_permanent_no_retry",
            ),
            _ex(
                "REC-04",
                "Recovery: a transient failure followed by a successful retry",
                "recovery",
                ("AI-S06",),
                "synthetic seven-category run; the first attempt of one category fails transient",
                "that category succeeds on its second attempt; every category ends succeeded; "
                "eight specialist calls in total (seven categories, one retried)",
                "major",
                "rec_recovery_after_transient",
            ),
            _ex(
                "REC-05",
                "A raised specialist exception is recorded as a failure and never retried",
                "recovery",
                ("AI-S06",),
                "synthetic seven-category run; specialist call raises RuntimeError",
                "every category makes one call and its outcome records 'specialist raised "
                "RuntimeError' as the failure",
                "major",
                "rec_exception_not_retried",
            ),
        ]
    )
    scenarios.append(
        _limitation(
            "REC-03",
            "Partial authorisation: a withheld collection is refused before any attempt, with no "
            "fallback",
            "recovery",
            ("AI-S06", "AI-S07", "C-15"),
            "the withheld category is refused before any specialist attempt; no evidence is used; "
            "no other collection is substituted",
            "C-15 OPEN: the execution envelope reports succeeded when the output is "
            "evidence_unavailable. The observed behaviour is recorded here as the limitation; it "
            "is not a pass of the expectation above",
            "rec_partial_authorisation",
        )
    )
    scenarios.extend(_remediation_rows())
    return tuple(replace(s, enforcement=ENFORCEMENT.get(s.scenario_id)) for s in scenarios)


def _remediation_rows() -> list[Scenario]:
    """Stage 3 rows: replay enforcement, stale input, upstream defect, cross-project, AI-S01,
    requirement extraction and pipeline traceability."""
    rows: list[Scenario] = [
        _ex(
            "RPL-01",
            "First valid use of a confirmation is accepted by verification",
            "replay",
            ("AI-S06",),
            "production-configured proposal; human-shaped confirmation (mock=False); fresh ledger",
            "verification accepts the first use",
            "critical",
            "rpl_first_use_accepted",
        ),
        _ex(
            "RPL-02",
            "Reuse in another run is refused at binding, and consumes nothing",
            "replay",
            ("AI-S06",),
            "valid confirmation re-presented with a different run identifier",
            "refused with 'confirmation is bound to another run' at verify_confirmation; a later "
            "valid use is still accepted",
            "critical",
            "rpl_reuse_in_another_run",
        ),
        _ex(
            "RPL-03",
            "Reuse in another project is refused at binding, and consumes nothing",
            "replay",
            ("AI-S06",),
            "valid confirmation presented for a different project identifier",
            "refused with 'confirmation is bound to another project' at "
            "verify_confirmation; a later "
            "valid use is still accepted",
            "critical",
            "rpl_reuse_in_another_project",
        ),
        _ex(
            "RPL-04",
            "Reuse with a changed specialist selection is refused by the ledger",
            "replay",
            ("AI-S06",),
            "same confirmation ID and nonce with a narrowed confirmed selection",
            "refused with 'confirmation ID was already used' at consume",
            "critical",
            "rpl_reuse_with_changed_selection",
        ),
        _ex(
            "RPL-05",
            "Reuse after expiry is refused, and the refused attempt consumes nothing",
            "replay",
            ("AI-S06",),
            "expired copy of a valid confirmation, then the valid confirmation",
            "refused with 'confirmation has expired' at verify_confirmation; "
            "the valid confirmation "
            "is then accepted",
            "critical",
            "rpl_reuse_after_expiry",
        ),
        _ex(
            "RPL-06",
            "The ledger port refuses a second consume of the same confirmation",
            "replay",
            ("AI-S06",),
            "direct ConfirmationLedger.consume called twice",
            "second consume refused with 'confirmation ID was already used' at consume",
            "critical",
            "rpl_direct_ledger_port",
        ),
        _ex(
            "RPL-07",
            "A fresh ID with a reused nonce is refused by the ledger",
            "replay",
            ("AI-S06",),
            "consumed confirmation with a new ID but the same nonce",
            "refused with 'confirmation nonce was already used (replay)' at consume",
            "critical",
            "rpl_nonce_reuse_with_fresh_id",
        ),
        _ex(
            "STL-01",
            "Current requirement revisions are accepted without a stale-revision issue",
            "stale",
            ("AI-S08", "AI-S09"),
            "SOW requirement revisions equal the estimate's revisions",
            "no stale-revision integrity issue",
            "major",
            "stl_current_revision_accepted",
        ),
        _ex(
            "STL-02",
            "A stale requirement revision is reported and not presented as complete",
            "stale",
            ("AI-S08", "AI-S09"),
            "estimate built against revision 2; SOW requirement at revision 1",
            "reported as an integrity issue for the requirement; its deliverable is not complete",
            "critical",
            "stl_stale_revision_excluded",
        ),
        _ex(
            "STL-03",
            "A missing requirement revision is reported per contract, not raised as an exception",
            "stale",
            ("AI-S09",),
            "estimate with no revision for one requirement",
            "integrity issue reported; the SOW is still produced",
            "major",
            "stl_missing_revision_handled",
        ),
        _ex(
            "STL-04",
            "A stale operator selection is rejected before any agent runs",
            "stale",
            ("AI-S01",),
            "operator selection made on project revision 1; project now at revision 2",
            "StaleSelectionError raised at run_investigation; the agent never runs",
            "critical",
            "stl_stale_operator_selection_rejected",
        ),
        _ex(
            "STL-05",
            "Stale inputs are flagged, excluded from authoritative use and carried as findings",
            "stale",
            ("AI-S07", "AI-S08", "AI-S09", "AI-S10 spec section 8"),
            "synthetic stale estimate line, stale evidence and stale SOW revision under the "
            "approved stale-input policy (2026-10-28)",
            "no authoritative numbers from the stale input; stale evidence does not back; the "
            "stale requirement is named in an integrity finding; the approval stays pending",
            "critical",
            "stl05_policy_flag_exclude_track",
        ),
        _ex(
            "STL-06",
            "Flagged stale input does not produce a completed or approved outcome",
            "stale",
            ("AI-S09",),
            "stale revision in the estimate",
            "approval stays pending_human_approval; the draft is not approved; project totals "
            "stay incomplete",
            "critical",
            "stl_no_false_completion",
        ),
        _ex(
            "UD-01",
            "SOW detects an estimate tied to a different governance review (B-1, AI-S09 "
            "correction)",
            "upstream",
            ("AI-S09", "AI-S08"),
            "synthetic SOW request with matched and mismatched estimate governance fingerprints",
            "matched fingerprints give no finding; a mismatched estimate is reported as an "
            "integrity finding, its values are excluded, and the SOW is not complete or approved",
            "critical",
            "ud01_fingerprint_mismatch_detected",
        ),
        _ex(
            "XP-01",
            "Specialist evidence access excludes records of another project",
            "cross-project",
            ("AI-S06",),
            "one lookup holding records of PRJ-SYN-0001 and PRJ-SYN-0002",
            "no outcome cites a record of the other project",
            "critical",
            "xp01_specialist_foreign_evidence_invisible",
        ),
        _ex(
            "XP-02",
            "The Governance Reviewer refuses a cross-project citation",
            "cross-project",
            ("AI-S07",),
            "verified foreign-project record cited by a same-project requirement",
            "CROSS_PROJECT_CITATION is reported and the requirement is not backed",
            "critical",
            "xp02_reviewer_foreign_citation_refused",
        ),
        _ex(
            "XP-03",
            "The estimate refuses governance from another project",
            "cross-project",
            ("AI-S08",),
            "governance summary for PRJ-SYN-0002 in a PRJ-SYN-0001 request",
            "refused with 'governance review belongs to another project' at estimate",
            "critical",
            "xp03_estimate_foreign_governance_refused",
        ),
        _ex(
            "XP-04",
            "The estimate refuses a requirement snapshot from another project",
            "cross-project",
            ("AI-S08",),
            "requirement snapshot for PRJ-SYN-0002 in a PRJ-SYN-0001 request",
            "refused with 'a requirement snapshot belongs to another project' at estimate",
            "critical",
            "xp04_estimate_foreign_snapshot_refused",
        ),
        _ex(
            "XP-05",
            "The SOW refuses governance from another project",
            "cross-project",
            ("AI-S09",),
            "governance summary for PRJ-SYN-0002 in a PRJ-SYN-0001 SOW request",
            "refused with 'governance review belongs to another project' at _require_governance",
            "critical",
            "xp05_sow_foreign_governance_refused",
        ),
        _ex(
            "XP-06",
            "The SOW refuses an estimate from another project",
            "cross-project",
            ("AI-S09",),
            "estimate draft for PRJ-SYN-0002 in a PRJ-SYN-0001 SOW request",
            "refused with 'estimate belongs to another project' at generate",
            "critical",
            "xp06_sow_foreign_estimate_refused",
        ),
        _ex(
            "S01-01",
            "Invisible or control characters are refused as operator identity",
            "security",
            ("AI-S01",),
            "zero-width and control characters in the actor identifier",
            "SelectionError at build_operator_selection for each identity",
            "critical",
            "s01_control_character_identity_refused",
        ),
        _ex(
            "S01-02",
            "An agent requesting an unallowed collection is denied by the wrapper",
            "security",
            ("AI-S01",),
            "probe agent searching a collection outside the authorised set",
            "PERMISSION_DENIED with no output",
            "critical",
            "s01_unallowed_collection_denied",
        ),
        _ex(
            "S01-03",
            "An agent requesting another project is denied by the wrapper",
            "security",
            ("AI-S01",),
            "probe agent searching with a foreign project identifier",
            "PERMISSION_DENIED with no output",
            "critical",
            "s01_foreign_project_denied",
        ),
        _ex(
            "S01-04",
            "An agent cannot change the requirements it was given",
            "security",
            ("AI-S01",),
            "probe agent appending a category to a requirement it received",
            "the caller's requirement is unchanged",
            "major",
            "s01_agent_cannot_change_requirements",
        ),
        _ex(
            "S01-05",
            "A model-constructed verified candidate is refused at the contract boundary",
            "security",
            ("AI-S01",),
            "candidate solution constructed with status VERIFIED",
            "ValidationError naming the verified-candidate rule",
            "critical",
            "s01_model_verified_candidate_refused",
        ),
        _ex(
            "S01-06",
            "A fabricated verified record outside the authorised set fails validation",
            "security",
            ("AI-S01",),
            "agent output citing an UNVERIFIED record the lookup never served to this run",
            "FAILED_VALIDATION with the reason 'was not served to this run' "
            "(the served-record check)",
            "critical",
            "s01_fabricated_evidence_refused",
        ),
        _ex(
            "S01-07",
            "Any reviewed content change makes an operator selection stale",
            "security",
            ("AI-S01",),
            "analysis whose project revision changed after the decision",
            "StaleSelectionError raised at verify_selection",
            "critical",
            "s01_reviewed_change_makes_selection_stale",
        ),
        _ex(
            "LLM-01",
            "LLM-backed lead intake accepts a correct reply on the synthetic fixture (offline)",
            "extraction",
            ("AI-S02",),
            "deterministic offline LLM port; approved guard; synthetic brief fixture",
            "status accepted with a successful call",
            "major",
            "llm01_intake_accepts_fixture",
        ),
        _ex(
            "LLM-02",
            "LLM-backed intake refuses a hallucinated quote after retries",
            "extraction",
            ("AI-S02",),
            "scripted offline LLM returning a quote absent from the source, three times",
            "status failed; no result; call INVALID_REPLY_EXHAUSTED; no segment analysed",
            "critical",
            "llm02_hallucinated_quote_refused",
        ),
        _ex(
            "LLM-03",
            "Untrusted segment text stays out of the LLM system prompt",
            "extraction",
            ("AI-S02",),
            "deterministic offline LLM capturing the first request",
            "no segment text in the system prompt; the system prompt is the registered prompt",
            "critical",
            "llm03_untrusted_text_stays_out_of_system_prompt",
        ),
        _ex(
            "REQ-01",
            "Valid requirement extraction preserves each wording as an exact source quote",
            "extraction",
            ("requirement_analysis",),
            "synthetic brief fixture (adapter, offline)",
            "six client requirements; each original wording is an exact substring of its segment",
            "major",
            "req01_valid_extraction",
        ),
        _ex(
            "REQ-02",
            "Ambiguous wording becomes an open clarification question",
            "extraction",
            ("requirement_analysis",),
            "synthetic brief fixture containing vague terms",
            "questions for 'faster' and 'immediately' exist and all are open",
            "major",
            "req02_ambiguity_becomes_open_question",
        ),
        _ex(
            "REQ-03",
            "Malformed input (no segments) is refused at analysis",
            "extraction",
            ("requirement_analysis",),
            "empty segment list",
            "refused at analyze",
            "major",
            "req03_malformed_input_refused",
        ),
        _ex(
            "REQ-04",
            "A segment outside the project is refused at analysis",
            "extraction",
            ("requirement_analysis",),
            "segment carrying another project identifier",
            "refused with 'outside project' at analyze",
            "critical",
            "req04_foreign_segment_refused",
        ),
        _ex(
            "REQ-05",
            "Identifiers are unique and deterministic, and client requirements cite a source",
            "extraction",
            ("requirement_analysis",),
            "synthetic brief fixture analysed twice",
            "proposal keys unique and identical across runs; every client requirement has a source",
            "major",
            "req05_identifiers_and_sources_preserved",
        ),
        _ex(
            "REQ-06",
            "Extraction asserts no verified status, assigns no requirement ID and commits no scope",
            "extraction",
            ("requirement_analysis",),
            "synthetic brief fixture",
            "evidence UNVERIFIED; no requirement IDs; human review required; scope not committed",
            "critical",
            "req06_no_unsupported_certainty",
        ),
        _ex(
            "REQ-07",
            "Instruction-like text in a source segment is data and accepts nothing",
            "extraction",
            ("requirement_analysis",),
            "source segment containing an instruction to approve all requirements",
            "no requirement is accepted for scope; scope not committed; no requirement IDs",
            "critical",
            "req07_instruction_in_source_is_data",
        ),
        _ex(
            "REQ-08",
            "Inferred follow-up requirements are never accepted for scope",
            "extraction",
            ("requirement_analysis",),
            "synthetic brief fixture with integration gaps",
            "inferred requirements exist and none is accepted for scope",
            "critical",
            "req08_inferred_requirements_never_accepted",
        ),
        _ex(
            "SEC-19",
            "Confirmation selecting a category that was not proposed is refused",
            "security",
            ("AI-S06",),
            "confirmation with one unproposed category added",
            "refused with 'confirmation selects categories that were not proposed' at "
            "verify_confirmation; a proposed selection is accepted",
            "critical",
            "sec_categories_not_proposed",
        ),
        _ex(
            "RAG-01",
            "AI-S03 RAG index filters chunks by project at the search boundary (component level)",
            "cross-project",
            ("AI-S03",),
            "identical chunk text in two projects, one collection; search for each project",
            "each project receives only its own chunk",
            "critical",
            "rag01_project_filter_index_boundary",
        ),
        _limitation(
            "FP-01",
            "Estimate with no governance fingerprint is used as authoritative (AI-S09 gap)",
            "upstream",
            ("AI-S09", "AI-S10 integration readiness"),
            "a null-fingerprint estimate supplies values with no fingerprint finding; gap present",
            "OPEN: live integration must tie each estimate to a governance review; no decision yet",
            "fp01_null_fingerprint_is_authoritative",
        ),
        _ex(
            "TRC-01",
            "Requirement identifiers stay correlated through specialist, estimate and governance",
            "traceability",
            ("AI-S06", "AI-S07", "AI-S08", "AI-S09"),
            "seven-requirement offline run, governance fingerprint f*64",
            "specialist outcomes, estimate revisions and the governance fingerprint agree",
            "critical",
            "trc01_identifiers_correlated",
        ),
        _ext(
            "TRC-02",
            "Foundation-fed requirement-to-SOW path (no integrated adapter)",
            "traceability",
            Classification.FOUNDATION,
            ("AI-S06", "AI-S09", "AI-S10 spec section 10"),
            "a Foundation-fed run reaches a SOW through the integrated adapter",
            "no integrated Foundation adapter path exists; the offline pipeline uses synthetic "
            "fixtures; Foundation approval required",
        ),
    ]
    return rows


ENFORCEMENT: dict[str, str] = {
    "SEC-01": "generate",
    "SEC-05": "verify_confirmation",
    "SEC-06": "consume",
    "SEC-07": "verify_confirmation",
    "SEC-08": "verify_confirmation",
    "SPEC-08": "execute",
    "RPL-02": "verify_confirmation",
    "RPL-03": "verify_confirmation",
    "RPL-04": "consume",
    "RPL-05": "verify_confirmation",
    "RPL-06": "consume",
    "RPL-07": "consume",
    "STL-04": "run_investigation",
    "XP-03": "estimate",
    "XP-04": "estimate",
    "XP-05": "_require_governance",
    "XP-06": "generate",
    "S01-01": "build_operator_selection",
    "S01-07": "verify_selection",
    "SEC-19": "verify_confirmation",
    "REQ-03": "analyze",
    "REQ-04": "analyze",
    "EST-02": "ThreePoint",
    "SEC-12": "Claim",
    "SPEC-13": "SpecialistInvestigationResult",
    "SEC-13": "build_request",
    "S01-05": "SpecialistInvestigationResult",
}


def executor_names(catalog: tuple[Scenario, ...]) -> tuple[str, ...]:
    return tuple(sorted({s.executor for s in catalog if s.executor is not None}))
