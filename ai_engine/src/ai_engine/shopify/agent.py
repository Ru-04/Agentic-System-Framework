"""Shopify Specialist Agent (AI-3, amended in AI-4.1).

The agent runs only when an operator explicitly selects it through AI-2 (automatic routing is
disabled, C-05). It produces structured, unverified implementation options for Shopify-specific
requirements: native, third-party app, custom, and API/integration. It never selects one, never
verifies a claim, and never accepts scope.

Keyword checks below decide whether a requirement describes Shopify-specific behaviour so the agent
can refuse unrelated work. They are the agent's own relevance test. They do not route, and they do
not read the requirement's specialist-category proposal.

AI-4.1 changes: premises are reported as assumptions rather than dependencies; contradictions are
explicit conflict records that cite both evidence items and link to their claims; contradiction
groups come from lookup metadata rather than tags inside evidence text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from ai_engine.contracts.clarification import ClarificationQuestion
from ai_engine.contracts.common import EvidenceStatus, FeasibilityStatus, RequirementType
from ai_engine.contracts.evidence import (
    Claim,
    ClaimType,
    EvidenceReference,
    SubjectRef,
    SubjectType,
)
from ai_engine.contracts.requirement import AtomicRequirement
from ai_engine.contracts.specialist import (
    ApproachType,
    CandidateSolution,
    RiskProposal,
    SpecialistAssumption,
    SpecialistConflict,
    SpecialistInvestigationResult,
    SpecialistOutputStatus,
    SpecialistTask,
)
from ai_engine.shopify.synthetic_evidence import SHOPIFY_EVIDENCE_COLLECTION
from ai_engine.specialists.base import SpecialistContext, UnsupportedRequestError

CAPABILITY_ID = "CAP-ECOMMERCE"
SPECIALIST_CATEGORY_ID = "shopify_specialist"

_RELEVANCE_RE = re.compile(
    r"\b(shopify|storefront|checkout|theme|apps?|catalog|inventory|orders?|gift cards?|"
    r"wishlists?|discounts?|payments?|customer accounts?|products?|product pages?)\b",
    re.IGNORECASE,
)
# Ordered (keyword, phrase). The keyword is both the matcher and the evidence search term.
_TOPICS: tuple[tuple[str, str], ...] = (
    ("wishlist", "wishlist functionality"),
    ("gift card", "gift card sales"),
    ("discount", "discount codes"),
    ("checkout", "checkout behaviour"),
    ("product page", "product page content"),
    ("inventory", "inventory levels"),
    ("erp", "ERP integration"),
    ("order", "order data"),
    ("payment", "payment handling"),
    ("storefront", "storefront presentation"),
    ("faster", "checkout performance"),
)
_INTEGRATION_KEYWORDS = frozenset({"erp", "inventory"})
_CUSTOM_KEYWORDS = frozenset({"product page", "storefront", "checkout"})
_PLACEHOLDER_NOTE = "not verified; no Shopify documentation was consulted"


def is_shopify_relevant(statement: str) -> bool:
    return _RELEVANCE_RE.search(statement) is not None


def topic_matches(statement: str) -> list[tuple[str, str]]:
    lowered = statement.lower()
    return [(keyword, phrase) for keyword, phrase in _TOPICS if keyword in lowered]


@dataclass
class _Keys:
    counts: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        count = self.counts.get(prefix, 0) + 1
        self.counts[prefix] = count
        return f"{prefix}-{count:03d}"


class ShopifySpecialist:
    """Implements the AI-2 specialist protocol for the Shopify category."""

    capability_id = CAPABILITY_ID
    specialist_category_id = SPECIALIST_CATEGORY_ID

    def run(
        self, task: SpecialistTask, context: SpecialistContext
    ) -> SpecialistInvestigationResult:
        if task.platform_context.platform_id != "shopify":
            raise UnsupportedRequestError("this specialist investigates Shopify only")
        requirements = [
            context.requirements[rid] for rid in task.requirement_ids if rid in context.requirements
        ]
        relevant = [r for r in requirements if is_shopify_relevant(r.normalized_statement)]
        if not relevant:
            raise UnsupportedRequestError(
                "no requirement in this task describes Shopify-specific behaviour"
            )

        builder = _Builder(task, context)
        for requirement in relevant:
            builder.add_requirement(requirement)
        relevant_ids = [r.requirement_id for r in relevant if r.requirement_id is not None]
        skipped = [rid for rid in task.requirement_ids if rid not in relevant_ids]
        if skipped:
            builder.dependencies.append(
                "Not investigated because they are outside Shopify scope: "
                + ", ".join(skipped)
                + "."
            )
        return builder.result(relevant_ids, skipped)


class _Builder:
    def __init__(self, task: SpecialistTask, context: SpecialistContext) -> None:
        self.task = task
        self.context = context
        self.keys = _Keys()
        self.solutions: list[CandidateSolution] = []
        self.claims: list[Claim] = []
        self.conflicts: list[SpecialistConflict] = []
        self.assumptions: list[SpecialistAssumption] = []
        self.risks: list[RiskProposal] = []
        self.dependencies: list[str] = []
        self.questions: list[ClarificationQuestion] = []
        self.served: dict[str, EvidenceReference] = {}

    def add_requirement(self, requirement: AtomicRequirement) -> None:
        rid = requirement.requirement_id or ""
        topics = topic_matches(requirement.normalized_statement)
        phrase = ", ".join(p for _, p in topics[:2]) or "the requested storefront behaviour"
        keywords = {k for k, _ in topics}
        query = " ".join(k for k, _ in topics) or "shopify"
        found = self.context.evidence.search(
            project_id=self.task.project_id,
            allowed_collections=self.task.allowed_evidence_collections,
            query=query,
        )
        for item in found:
            self.served[item.evidence_id] = item
        evidence_ids = [item.evidence_id for item in found]
        conflict_ids = self._contested_ids(found)
        integration = requirement.requirement_type is RequirementType.INTEGRATION or bool(
            keywords & _INTEGRATION_KEYWORDS
        )
        subject = [
            SubjectRef(
                subject_type=SubjectType.REQUIREMENT,
                subject_id=rid,
                project_id=self.task.project_id,
            )
        ]

        self._options(rid, phrase, keywords, integration)
        self._assumptions(rid, integration)
        conflict_key = self.keys.next("CONF") if conflict_ids else None
        hypothesis_key = self._claims(rid, phrase, subject, evidence_ids, conflict_key, integration)
        if conflict_key is not None:
            self.conflicts.append(
                SpecialistConflict(
                    proposal_key=conflict_key,
                    description=(
                        f"Synthetic records in one contradiction group disagree on availability "
                        f"for {phrase}; both records are cited."
                    ),
                    related_requirement_ids=[rid],
                    claim_proposal_keys=[hypothesis_key],
                    evidence_ids=conflict_ids,
                )
            )
        self._risks(rid, phrase, found, conflict_key is not None)
        if integration:
            self.dependencies.append(
                f"External system access for {rid} is not provided; "
                "no credentials are used in this prototype."
            )
        self._questions(rid, phrase, keywords, integration, conflict_key is not None, bool(found))

    def _contested_ids(self, found: list[EvidenceReference]) -> list[str]:
        """Evidence IDs from the first contradiction group that has two or more served records."""
        groups: dict[str, list[str]] = {}
        for item in found:
            group = self.context.evidence.conflict_group_of(item.evidence_id)
            if group is not None:
                groups.setdefault(group, []).append(item.evidence_id)
        for ids in groups.values():
            if len(ids) >= 2:
                return sorted(ids)
        return []

    def _assumptions(self, rid: str, integration: bool) -> None:
        self.assumptions.append(
            SpecialistAssumption(
                proposal_key=self.keys.next("SASM"),
                statement=(
                    f"The Shopify plan, staff permissions and API version are sufficient for {rid}."
                ),
                rationale=(
                    "Native and app options only apply on a plan that supports them; "
                    "not verified."
                ),
                impact_if_false="Options may be unavailable; scope and approach would change.",
                owner_to_confirm="client",
                related_requirement_ids=[rid],
            )
        )
        if integration:
            self.assumptions.append(
                SpecialistAssumption(
                    proposal_key=self.keys.next("SASM"),
                    statement=(
                        f"The external system named in {rid} exposes an API for the data "
                        "exchanged."
                    ),
                    rationale=(
                        "Integration feasibility depends on an interface that has not been "
                        "verified."
                    ),
                    impact_if_false="The integration approach and estimate would change.",
                    owner_to_confirm="client",
                    related_requirement_ids=[rid],
                )
            )

    def _options(self, rid: str, phrase: str, keywords: set[str], integration: bool) -> None:
        shapes: list[tuple[ApproachType, str]] = [
            (ApproachType.NATIVE_PLATFORM, f"Native Shopify option for {phrase}"),
            (ApproachType.THIRD_PARTY_APP, f"Third-party app option for {phrase}"),
            (
                ApproachType.PLATFORM_EXTENSION
                if keywords & _CUSTOM_KEYWORDS
                else ApproachType.CUSTOM_BACKEND,
                f"Custom theme or application option for {phrase}",
            ),
        ]
        if integration:
            shapes.append((ApproachType.API_INTEGRATION, f"API integration option for {phrase}"))
        for approach, label in shapes:
            self.solutions.append(
                CandidateSolution(
                    proposal_key=self.keys.next("SOLP"),
                    project_id=self.task.project_id,
                    summary=f"{label}; not selected, {_PLACEHOLDER_NOTE}.",
                    approach_type=approach,
                    feasibility_status=FeasibilityStatus.UNKNOWN,
                    evidence_status=EvidenceStatus.UNVERIFIED,
                    related_requirement_ids=[rid],
                    limitations=[f"Feasibility and limits for {phrase} are not established."],
                    prerequisites=["Shopify plan and staff permissions confirmed by the client."],
                    verification_tasks=["Confirm against current official Shopify documentation."],
                )
            )

    def _claims(
        self,
        rid: str,
        phrase: str,
        subject: list[SubjectRef],
        evidence_ids: list[str],
        conflict_key: str | None,
        integration: bool,
    ) -> str:
        """Append the claims for one requirement and return the hypothesis claim's key."""
        conflict = conflict_key is not None
        hypothesis_key = self.keys.next("CLM")
        self.claims.append(
            Claim(
                proposal_key=hypothesis_key,
                project_id=self.task.project_id,
                claim_text=(
                    f"Native Shopify functionality may cover {phrase}; "
                    "this is an unverified hypothesis."
                ),
                claim_type=ClaimType.PLATFORM_CAPABILITY,
                evidence_status=EvidenceStatus.CONFLICTING
                if conflict
                else EvidenceStatus.UNVERIFIED,
                feasibility_status=(
                    FeasibilityStatus.CONFLICTING if conflict else FeasibilityStatus.UNKNOWN
                ),
                subject_refs=subject,
                evidence_ids=evidence_ids,
                platform_context=self.task.platform_context,
                conflict_refs=[conflict_key] if conflict_key is not None else [],
                verification_task=(
                    "Resolve the opposing synthetic records, then confirm against official "
                    "documentation."
                    if conflict
                    else "Confirm against official Shopify documentation (not accessed in this "
                    "prototype)."
                ),
            )
        )
        self.claims.append(
            Claim(
                proposal_key=self.keys.next("CLM"),
                project_id=self.task.project_id,
                claim_text=f"Feasibility and limitations for {phrase} are not established.",
                claim_type=ClaimType.IMPLEMENTATION,
                evidence_status=EvidenceStatus.UNVERIFIED,
                subject_refs=subject,
                verification_task=(
                    "Establish feasibility and limitations from verified documentation."
                ),
            )
        )
        if integration:
            self.claims.append(
                Claim(
                    proposal_key=self.keys.next("CLM"),
                    project_id=self.task.project_id,
                    claim_text=(
                        f"Integration for {phrase} depends on API behaviour "
                        "that has not been verified."
                    ),
                    claim_type=ClaimType.API_BEHAVIOR,
                    evidence_status=EvidenceStatus.UNVERIFIED,
                    subject_refs=subject,
                    evidence_ids=evidence_ids,
                    platform_context=self.task.platform_context,
                    verification_task=(
                        "Check current official Admin API documentation, rate limits and webhook "
                        "behaviour (not accessed in this prototype)."
                    ),
                )
            )
        return hypothesis_key

    def _risks(self, rid: str, phrase: str, found: list[EvidenceReference], conflict: bool) -> None:
        risks = [
            f"Synthetic placeholders are unverified; options for {phrase} may not hold "
            "on the live platform."
        ]
        if conflict:
            risks.append(
                f"Synthetic evidence contradicts itself on {phrase}; "
                "resolve before any scope decision."
            )
        if not found:
            risks.append(
                f"No synthetic evidence matched {phrase}; options rest on hypothesis alone."
            )
        for text in risks:
            self.risks.append(
                RiskProposal(
                    proposal_key=self.keys.next("RSKP"),
                    description=text,
                    related_requirement_ids=[rid],
                )
            )

    def _questions(
        self,
        rid: str,
        phrase: str,
        keywords: set[str],
        integration: bool,
        conflict: bool,
        has_evidence: bool,
    ) -> None:
        asks: list[tuple[str, str]] = [
            (
                "Which Shopify plan, staff permissions and API version apply to this store?",
                "Native and app options depend on plan and permissions.",
            )
        ]
        if "faster" in keywords:
            asks.append(
                (
                    "What measurable checkout performance target and baseline apply?",
                    "A performance term without a measurable target needs client agreement.",
                )
            )
        if integration:
            asks.append(
                (
                    "Which system is the source of truth for this data, "
                    "and in which direction does it sync?",
                    "Integration ownership and direction are not stated.",
                )
            )
        if conflict:
            asks.append(
                (
                    f"Which availability of {phrase} is correct for this store?",
                    "Synthetic records in one contradiction group disagree.",
                )
            )
        if not has_evidence:
            asks.append(
                (
                    "Which authorised documentation source may this specialist consult?",
                    "No authorised source returned results; the allowlist decision D-02 is open.",
                )
            )
        for text, reason in asks:
            self.questions.append(
                ClarificationQuestion(
                    proposal_key=self.keys.next("QPROP"),
                    project_id=self.task.project_id,
                    question_text=text,
                    reason=reason,
                    related_requirement_ids=[rid],
                )
            )

    def result(self, relevant_ids: list[str], skipped: list[str]) -> SpecialistInvestigationResult:
        if not self.task.allowed_evidence_collections:
            status = SpecialistOutputStatus.EVIDENCE_UNAVAILABLE
        elif skipped:
            status = SpecialistOutputStatus.PARTIAL
        else:
            status = SpecialistOutputStatus.COMPLETED
        cited: Mapping[str, EvidenceReference] = dict(sorted(self.served.items()))
        return SpecialistInvestigationResult(
            task_id=self.task.task_id,
            project_id=self.task.project_id,
            capability_id=self.task.capability_id,
            specialist_category_id=self.task.specialist_category_id,
            requirement_ids=relevant_ids,
            candidate_solutions=self.solutions,
            claims=self.claims,
            risks=self.risks,
            dependencies=self.dependencies,
            assumptions=self.assumptions,
            conflicts=self.conflicts,
            clarification_questions=self.questions,
            evidence=list(cited.values()),
            status=status,
            registry_version=self.task.registry_version,
            catalog_version=self.task.catalog_version,
        )


__all__ = [
    "CAPABILITY_ID",
    "SHOPIFY_EVIDENCE_COLLECTION",
    "SPECIALIST_CATEGORY_ID",
    "ShopifySpecialist",
    "is_shopify_relevant",
    "topic_matches",
]
