"""
WordPress and WooCommerce specialist agent (AI-S04, increment 1).

The agent runs only when an operator explicitly selects it (automatic routing is disabled, C-05).
It produces structured, unverified implementation options for WordPress and WooCommerce
requirements. CMS concerns (plugins, themes) and commerce concerns (checkout, orders, products,
payments, shipping) are labelled in every claim, so they stay distinguishable under one specialist
identity. The agent never selects an option, never verifies a claim and never accepts scope. It
reads only the evidence the context serves, and it reaches no live source.
"""

from __future__ import annotations

import re
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
from ai_engine.specialists.base import SpecialistContext, UnsupportedRequestError
from ai_engine.woocommerce.synthetic_evidence import WOOCOMMERCE_EVIDENCE_COLLECTION

CAPABILITY_ID = "CAP-WORDPRESS-WOOCOMMERCE"
SPECIALIST_CATEGORY_ID = "wordpress_woocommerce_specialist"
PLATFORM_ID = "woocommerce"

_RELEVANCE_RE = re.compile(
    r"\b(woocommerce|woo|wordpress|wp|plugins?|themes?|checkout|carts?|orders?|products?|"
    r"payments?|subscriptions?|shipping|coupons?|discounts?|store)\b",
    re.IGNORECASE,
)
# Ordered (keyword, phrase, layer). The keyword is the matcher and the search term. The layer keeps
# CMS and commerce concerns distinguishable.
_TOPICS: tuple[tuple[str, str, str], ...] = (
    ("plugin", "plugin compatibility", "CMS"),
    ("theme", "theme customisation", "CMS"),
    ("subscription", "subscription products", "commerce"),
    ("coupon", "coupon rules", "commerce"),
    ("discount", "discount rules", "commerce"),
    ("checkout", "checkout behaviour", "commerce"),
    ("shipping", "shipping configuration", "commerce"),
    ("payment", "payment gateway handling", "commerce"),
    ("order", "order data", "commerce"),
    ("product", "product catalogue", "commerce"),
    ("rest api", "REST API access", "commerce"),
    ("api", "API integration", "commerce"),
)
_INTEGRATION_KEYWORDS = frozenset({"rest api", "api"})
_PLACEHOLDER_NOTE = "not verified; no WordPress or WooCommerce documentation was consulted"


def is_woocommerce_relevant(statement: str) -> bool:
    """The agent's own relevance test. It does not route and does not read any category proposal."""
    return _RELEVANCE_RE.search(statement) is not None


def topic_matches(statement: str) -> list[tuple[str, str, str]]:
    lowered = statement.lower()
    return [
        (keyword, phrase, layer)
        for keyword, phrase, layer in _TOPICS
        if re.search(rf"\b{re.escape(keyword)}s?\b", lowered)
    ]


@dataclass
class _Keys:
    counts: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        count = self.counts.get(prefix, 0) + 1
        self.counts[prefix] = count
        return f"{prefix}-{count:03d}"


class WooCommerceSpecialist:
    """Implements the AI-2 specialist protocol for the WordPress and WooCommerce category."""

    capability_id = CAPABILITY_ID
    specialist_category_id = SPECIALIST_CATEGORY_ID

    def run(
        self, task: SpecialistTask, context: SpecialistContext
    ) -> SpecialistInvestigationResult:
        if task.platform_context.platform_id != PLATFORM_ID:
            raise UnsupportedRequestError("this specialist investigates WooCommerce only")
        requirements = [
            context.requirements[rid] for rid in task.requirement_ids if rid in context.requirements
        ]
        relevant = [r for r in requirements if is_woocommerce_relevant(r.normalized_statement)]
        if not relevant:
            raise UnsupportedRequestError(
                "no requirement in this task describes WordPress or WooCommerce behaviour"
            )

        builder = _Builder(task, context)
        for requirement in relevant:
            builder.add_requirement(requirement)
        relevant_ids = [r.requirement_id for r in relevant if r.requirement_id is not None]
        skipped = [rid for rid in task.requirement_ids if rid not in relevant_ids]
        if skipped:
            builder.dependencies.append(
                "Not investigated because they are outside WordPress and WooCommerce scope: "
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
        phrase = ", ".join(p for _, p, _ in topics[:2]) or "the requested store behaviour"
        keywords = {k for k, _, _ in topics}
        layers = sorted({layer for _, _, layer in topics}) or ["commerce"]
        layer_label = "/".join(layers)
        query = " ".join(k for k, _, _ in topics) or "woocommerce"
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

        self._options(rid, phrase, layers, integration)
        self._assumptions(rid, layer_label)
        conflict_key = self.keys.next("CONF") if conflict_ids else None
        hypothesis_key = self._claims(
            rid, phrase, layer_label, subject, evidence_ids, conflict_key, integration
        )
        if conflict_key is not None:
            self.conflicts.append(
                SpecialistConflict(
                    proposal_key=conflict_key,
                    description=(
                        "Synthetic records in one contradiction group disagree on "
                        f"{phrase}; both records are cited."
                    ),
                    related_requirement_ids=[rid],
                    claim_proposal_keys=[hypothesis_key],
                    evidence_ids=conflict_ids,
                )
            )
        self._risks(rid, phrase)
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
            group = self.context.evidence.conflict_group_of(
                item.evidence_id, project_id=self.task.project_id
            )
            if group is not None:
                groups.setdefault(group, []).append(item.evidence_id)
        for ids in groups.values():
            if len(ids) >= 2:
                return sorted(ids)
        return []

    def _options(self, rid: str, phrase: str, layers: list[str], integration: bool) -> None:
        shapes: list[tuple[ApproachType, str]] = []
        if "CMS" in layers:
            shapes.append((ApproachType.PLATFORM_EXTENSION, f"Theme or plugin option for {phrase}"))
        if "commerce" in layers:
            shapes.append((ApproachType.NATIVE_PLATFORM, f"Native WooCommerce option for {phrase}"))
            shapes.append((ApproachType.THIRD_PARTY_APP, f"Third-party plugin option for {phrase}"))
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
                    verification_tasks=[
                        "Confirm the WooCommerce, WordPress and plugin versions before any "
                        "selection."
                    ],
                )
            )

    def _assumptions(self, rid: str, layer_label: str) -> None:
        self.assumptions.append(
            SpecialistAssumption(
                proposal_key=self.keys.next("SASM"),
                statement=(
                    "The WordPress, WooCommerce and PHP versions and the installed plugin "
                    "set are not known."
                ),
                rationale=f"Options for the {layer_label} concerns depend on them.",
                impact_if_false=(
                    "Plugin and version compatibility could differ from the options " "listed."
                ),
                owner_to_confirm="client",
                related_requirement_ids=[rid],
            )
        )

    def _claims(
        self,
        rid: str,
        phrase: str,
        layer_label: str,
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
                    f"Native WooCommerce functionality may cover {phrase} ({layer_label} layer); "
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
                    "WooCommerce documentation."
                    if conflict
                    else "Confirm against official WooCommerce documentation (not accessed in this "
                    "prototype)."
                ),
            )
        )
        self.claims.append(
            Claim(
                proposal_key=self.keys.next("CLM"),
                project_id=self.task.project_id,
                claim_text=(
                    f"Feasibility and limitations for {phrase} ({layer_label} layer) are "
                    f"not established."
                ),
                claim_type=ClaimType.IMPLEMENTATION,
                evidence_status=EvidenceStatus.UNVERIFIED,
                subject_refs=subject,
                verification_task=(
                    "Establish feasibility and limitations from verified " "documentation."
                ),
            )
        )
        if integration:
            self.claims.append(
                Claim(
                    proposal_key=self.keys.next("CLM"),
                    project_id=self.task.project_id,
                    claim_text=(
                        f"Integration for {phrase} depends on REST API behaviour that has not "
                        f"been verified."
                    ),
                    claim_type=ClaimType.API_BEHAVIOR,
                    evidence_status=EvidenceStatus.UNVERIFIED,
                    subject_refs=subject,
                    evidence_ids=evidence_ids,
                    platform_context=self.task.platform_context,
                    verification_task=(
                        "Check current official REST API documentation, authentication and "
                        "rate limits "
                        "(not accessed in this prototype)."
                    ),
                )
            )
        return hypothesis_key

    def _risks(self, rid: str, phrase: str) -> None:
        self.risks.append(
            RiskProposal(
                proposal_key=self.keys.next("RSKP"),
                description=(
                    f"Synthetic placeholders are unverified; options for {phrase} may not hold on "
                    "the client's WooCommerce, WordPress or plugin versions."
                ),
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
                "Which WordPress, WooCommerce and PHP versions, and which plugins, "
                "apply to this store?",
                "Plugin and version compatibility cannot be assessed without them.",
            )
        ]
        if integration:
            asks.append(
                (
                    "Which system is the source of truth for this data, and in which "
                    "direction does it sync?",
                    "An integration cannot be scoped without its data ownership and direction.",
                )
            )
        if conflict:
            asks.append(
                (
                    f"Which of the opposing records applies to this store for {phrase}?",
                    "The synthetic records disagree, so one reading must be confirmed.",
                )
            )
        if not has_evidence:
            asks.append(
                (
                    f"Is there an approved WooCommerce evidence source for {phrase}?",
                    "No evidence was served for this requirement in the selected collections.",
                )
            )
        for question_text, reason in asks:
            self.questions.append(
                ClarificationQuestion(
                    proposal_key=self.keys.next("QPROP"),
                    project_id=self.task.project_id,
                    question_text=question_text,
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
        cited = dict(sorted(self.served.items()))
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
    "PLATFORM_ID",
    "SPECIALIST_CATEGORY_ID",
    "WOOCOMMERCE_EVIDENCE_COLLECTION",
    "WooCommerceSpecialist",
    "is_woocommerce_relevant",
    "topic_matches",
]
