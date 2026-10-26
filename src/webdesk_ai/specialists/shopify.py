"""Shopify Specialist (``shopify_specialist``, registry ``ROUTE-SHOPIFY-001``).

The specialist separates five kinds of output: native Shopify approaches, third-party app
approaches, custom development, integration dependencies, and claims it cannot support. Every
claim here is backed only by synthetic fixture evidence, so every evidence status stays
``unverified``. Official Shopify documentation has not been retrieved, and nothing in this module
presents it as retrieved.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from webdesk_ai.contracts import (
    AgentStatus,
    ApproachType,
    AtomicRequirement,
    CandidateSolution,
    Claim,
    ClaimType,
    ClarificationQuestion,
    EvidenceOrigin,
    EvidenceReference,
    EvidenceStatus,
    FeasibilityStatus,
    HumanReviewItem,
    IntegrationDependency,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from webdesk_ai.specialists.base import EvidenceProvider

PLATFORM_ID = "shopify"
CATEGORY_ID = "shopify_specialist"
REGISTRY_VERSION = "0.3.10-foundation-gate1-review"


@dataclass(frozen=True)
class Topic:
    key: str
    keywords: tuple[str, ...]
    native: str
    third_party: str
    custom: str
    plan_question: str | None = None


TOPICS: tuple[Topic, ...] = (
    Topic(
        key="storefront_theme",
        keywords=("storefront", "theme", "product page", "collection", "filter", "section"),
        native="Customise the Online Store theme with sections and theme settings.",
        third_party="Install a theme app or filter app from the Shopify App Store.",
        custom="Develop a custom theme section or a headless storefront.",
    ),
    Topic(
        key="checkout_extensibility",
        keywords=("checkout", "delivery date", "delivery-date", "shipping option"),
        native="Use checkout UI extensions where the store plan permits checkout customisation.",
        third_party="Install a delivery-date app that renders at checkout.",
        custom="Build a custom checkout extension; availability depends on the store plan.",
        plan_question="Which Shopify plan is the store on, and does it allow checkout changes?",
    ),
    Topic(
        key="api_integration",
        keywords=("sync", "webhook", "api", "erp", "integrat", "nightly", "order export"),
        native="Use the Shopify Admin API and webhooks for order and product data.",
        third_party="Use an ERP connector app that already synchronises Shopify orders.",
        custom="Build a middleware integration that consumes webhooks and calls the Admin API.",
    ),
    Topic(
        key="app_extensibility",
        keywords=("loyalty", "points", "app", "extension", "widget"),
        native="Use an app extension or a theme app block where the feature needs storefront UI.",
        third_party="Install an existing loyalty or rewards app.",
        custom="Build a Shopify app with its own backend and billing rules.",
    ),
)

_FIRST_QUESTION_NUMBER = 201


def _matched_topics(requirement: AtomicRequirement) -> tuple[Topic, ...]:
    text = f"{requirement.original_wording} {requirement.normalized_statement}"
    return tuple(
        topic
        for topic in TOPICS
        if any(re.search(r"\b" + re.escape(word), text, re.IGNORECASE) for word in topic.keywords)
    )


class ShopifySpecialist:
    category_id = CATEGORY_ID

    def investigate(
        self, task: SpecialistTask, evidence: EvidenceProvider
    ) -> SpecialistInvestigationResult:
        result_evidence: dict[str, EvidenceReference] = {}
        solutions: list[CandidateSolution] = []
        dependencies: list[IntegrationDependency] = []
        claims: list[Claim] = []
        questions: list[ClarificationQuestion] = []
        reviews: list[HumanReviewItem] = []
        unmatched: list[str] = []
        plan_asked = False

        for requirement in task.requirements:
            topics = _matched_topics(requirement)
            if not topics:
                unmatched.append(requirement.requirement_id)
                questions.append(
                    _question(
                        task,
                        len(questions),
                        "Which Shopify capability does this requirement depend on?",
                        "No Shopify topic matched the requirement wording.",
                        (requirement.requirement_id,),
                    )
                )
                continue
            reviews.append(
                HumanReviewItem(
                    item_id=f"REV-{requirement.requirement_id}",
                    reason=(
                        "Confirm each option against official Shopify documentation and the "
                        "store plan before any estimate or scope decision."
                    ),
                    requirement_ids=(requirement.requirement_id,),
                )
            )
            for topic in topics:
                refs = evidence.lookup(PLATFORM_ID, (topic.key,))
                for ref in refs:
                    result_evidence.setdefault(ref.evidence_id, ref)
                ref_ids = tuple(ref.evidence_id for ref in refs)
                if not refs:
                    reviews.append(
                        HumanReviewItem(
                            item_id=f"REV-EVD-{requirement.requirement_id}-{topic.key}",
                            reason="No evidence returned for this topic; options stay unverified.",
                            requirement_ids=(requirement.requirement_id,),
                        )
                    )
                solutions.extend(_solutions(requirement, topic, ref_ids))
                claims.append(
                    Claim(
                        claim_id=f"CLM-{requirement.requirement_id}-{topic.key}",
                        claim_text=(
                            f"Shopify provides a native route for {topic.key.replace('_', ' ')}; "
                            "not verified against official documentation."
                        ),
                        claim_type=ClaimType.PLATFORM_CAPABILITY,
                        evidence_status=EvidenceStatus.UNVERIFIED,
                        feasibility_status=FeasibilityStatus.UNKNOWN,
                        evidence_refs=ref_ids,
                        requirement_ids=(requirement.requirement_id,),
                        platform_context=PLATFORM_ID,
                        uncertainty_note="Synthetic evidence only; no source retrieved.",
                    )
                )
                if topic.key == "api_integration":
                    dependencies.append(
                        IntegrationDependency(
                            dependency_id=f"DEP-{requirement.requirement_id}-ERP",
                            description=(
                                "The external system endpoint, data direction and sync schedule "
                                "must be identified before integration design."
                            ),
                            requirement_ids=(requirement.requirement_id,),
                            evidence_refs=ref_ids,
                        )
                    )
                    questions.append(
                        _question(
                            task,
                            len(questions),
                            "Which ERP system receives the order sync, and what is its API?",
                            "The integration target is named only generically.",
                            (requirement.requirement_id,),
                        )
                    )
                if topic.plan_question and not plan_asked:
                    plan_asked = True
                    questions.append(
                        _question(
                            task,
                            len(questions),
                            topic.plan_question,
                            "Checkout customisation depends on plan and permission.",
                            (requirement.requirement_id,),
                        )
                    )

        return SpecialistInvestigationResult(
            task_id=task.task_id,
            category_id=CATEGORY_ID,
            status=AgentStatus.COMPLETED_WITH_GAPS,
            candidate_solutions=tuple(solutions),
            integration_dependencies=tuple(dependencies),
            claims=tuple(claims),
            evidence=tuple(result_evidence.values()),
            clarification_questions=tuple(questions),
            human_review_items=tuple(reviews),
            assumptions=(
                "The store is a Shopify store (platform stated by the source).",
                "Store plan and admin permissions are unverified.",
            ),
            errors=(tuple(f"no Shopify topic for {req_id}" for req_id in unmatched)),
            registry_version=REGISTRY_VERSION,
        )


def _solutions(
    requirement: AtomicRequirement, topic: Topic, ref_ids: Sequence[str]
) -> list[CandidateSolution]:
    options = (
        (ApproachType.NATIVE, topic.native),
        (ApproachType.THIRD_PARTY_APP, topic.third_party),
        (ApproachType.CUSTOM_DEVELOPMENT, topic.custom),
    )
    return [
        CandidateSolution(
            solution_id=f"SOL-{requirement.requirement_id}-{topic.key}-{approach.value}",
            approach_type=approach,
            summary=summary,
            requirement_ids=(requirement.requirement_id,),
            feasibility_status=FeasibilityStatus.UNKNOWN,
            evidence_status=EvidenceStatus.UNVERIFIED,
            evidence_refs=tuple(ref_ids),
            prerequisites=("Store plan and permissions confirmed",),
            limitations=("Not verified against official Shopify documentation",),
        )
        for approach, summary in options
    ]


def _question(
    task: SpecialistTask,
    offset: int,
    text: str,
    reason: str,
    requirement_ids: tuple[str, ...],
) -> ClarificationQuestion:
    number = _FIRST_QUESTION_NUMBER + offset
    return ClarificationQuestion(
        question_id=f"Q-AI-{number:03d}",
        project_id=task.project_id,
        question_text=text,
        reason=reason,
        related_requirement_ids=requirement_ids,
    )


class SyntheticShopifyEvidence:
    """Evidence provider for tests and the demo. Every item is labelled as synthetic."""

    def lookup(self, platform_id: str, topic_keys: Sequence[str]) -> tuple[EvidenceReference, ...]:
        if platform_id != PLATFORM_ID:
            return ()
        return tuple(
            EvidenceReference(
                evidence_id=f"SYN-SHOPIFY-{key.upper()}",
                origin=EvidenceOrigin.SYNTHETIC_FIXTURE,
                publisher="Synthetic fixture (not an official Shopify source)",
                applies_to_platform=PLATFORM_ID,
                evidence_status=EvidenceStatus.UNVERIFIED,
                relevance_summary=(
                    f"Placeholder for official shopify.dev documentation on {key}; not retrieved."
                ),
                limitations=("No approved retrieval service in this increment",),
            )
            for key in topic_keys
        )
