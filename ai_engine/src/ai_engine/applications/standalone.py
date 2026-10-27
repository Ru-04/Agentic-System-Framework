"""
Standalone Applications specialist (AI-S05, CAP-STANDALONE-APPLICATIONS).

The specialist runs only when an operator explicitly selects it. It investigates whether an
existing application or service could satisfy a requirement, and what a custom standalone
application would need. It produces unverified options, hypotheses, risks and clarification
questions. It never selects an option, verifies a claim, or sets materiality. It reads only the
evidence the context serves.
"""

from __future__ import annotations

from ai_engine.applications.common import Profile, Topic, investigate
from ai_engine.applications.synthetic_evidence import (
    STANDALONE_EVIDENCE_COLLECTION,
    STANDALONE_RECORD_TOPICS,
)
from ai_engine.contracts.evidence import ClaimType
from ai_engine.contracts.specialist import (
    ApproachType,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from ai_engine.specialists.base import SpecialistContext

CAPABILITY_ID = "CAP-STANDALONE-APPLICATIONS"
SPECIALIST_CATEGORY_ID = "standalone_applications_specialist"
PLATFORM_ID = "standalone_application"

# Keywords are regular expressions written as raw strings. Each one matches the start of a word.
PROFILE = Profile(
    capability_id=CAPABILITY_ID,
    category_id=SPECIALIST_CATEGORY_ID,
    platform_id=PLATFORM_ID,
    collection=STANDALONE_EVIDENCE_COLLECTION,
    record_topics=STANDALONE_RECORD_TOPICS,
    topics=(
        Topic(
            keyword=(
                r"(?:web|mobile|custom|internal|online|software|business) ?applications?\b|"
                r"(?:build|create|develop|need|needs) (?:an? |the )?(?:applications?|apps?)\b|"
                r"apps?\b|websites?\b|web ?portals?\b|(?:customer|client|member|partner|staff|"
                r"employee|internal) portals?\b|saas\b|existing (?:\w+ )?(?:systems?|"
                r"applications?|software|tools?|platforms?)\b|off-the-shelf"
            ),
            phrase="an existing or off-the-shelf application",
            term="application",
            layer="product",
            claim_type=ClaimType.PLATFORM_CAPABILITY,
            question="Does an existing application or service already meet this requirement, "
            "and which version or plan would be used?",
            reason="A reuse option must be compared with a custom build before either is chosen.",
        ),
        Topic(
            keyword=(r"front-?\s?ends?\b"),
            phrase="frontend architecture",
            term="frontend",
            layer="frontend",
            claim_type=ClaimType.IMPLEMENTATION,
            question="Which frontend technology and which browser or device targets are required?",
            reason="The frontend choice determines the build, testing and hosting effort.",
        ),
        Topic(
            keyword=(r"back-?\s?ends?\b"),
            phrase="backend architecture",
            term="backend",
            layer="backend",
            claim_type=ClaimType.IMPLEMENTATION,
            question="Which backend runtime and service boundaries are expected?",
            reason="Service boundaries change the number of components to build and operate.",
        ),
        Topic(
            keyword=(
                r"users? (?:must |can |will )?(?:be )?(?:sign|log)[- ]?(?:in|ged in)\b|"
                r"single sign-on|\bsso\b|authenticat\w*|authori[sz]\w*|user roles?\b|role-based|"
                r"roles? (?:and|for) (?:users?|permissions?)|permissions?\b"
            ),
            phrase="authentication and authorisation",
            term="authentication",
            layer="security",
            claim_type=ClaimType.SECURITY,
            question="Which identity source and which user roles must the application support?",
            reason="The identity model decides the login flow, role design and access tests.",
        ),
        Topic(
            keyword=(r"database|data model|data store|schema|persist\w*"),
            phrase="data models and persistence",
            term="database",
            layer="data",
            claim_type=ClaimType.IMPLEMENTATION,
            question="What data must be stored, how long must it be kept, and who owns it?",
            reason="The data model and retention rules drive persistence design and privacy.",
        ),
        Topic(
            keyword=(
                r"\bapis?\b|endpoints?\b|external services?|third[- ]party (?:services?|"
                r"providers?|tools?)|integrat\w* (?:with|to|between|the) (?:\w+ )?(?:erp|crm|api|"
                r"systems?|payments?|providers?|services?|platforms?)\b"
            ),
            phrase="external APIs and service integrations",
            term="external",
            layer="integration",
            claim_type=ClaimType.API_BEHAVIOR,
            question="Which external services must the application call, and with what keys?",
            reason="Each external dependency adds an access, rate-limit and failure surface.",
            integration=True,
        ),
        Topic(
            keyword=(
                r"deploy(?:ed|ment|s)? (?:the |our |a |an |it |to )?(?:applications?|app|site|"
                r"website|system|software|service|platform|code|release)\b|deployment\b|"
                r"deployed\b|host(?:s|ed)? (?:the |our |a |an )?(?:site|website|applications?|app|"
                r"system|software|service|platform|servers?|on|in)\b|hosted\b|hosting\b|aws\b|"
                r"azure\b|cloud\b|servers?\b"
            ),
            phrase="hosting and deployment",
            term="hosting",
            layer="operations",
            claim_type=ClaimType.IMPLEMENTATION,
            question="Where must the application be hosted, and which deployment process applies?",
            reason="Hosting and deployment decide the running arrangement and the release path.",
        ),
        Topic(
            keyword=(
                r"scalab\w*|scale (?:up|out) (?:the )?(?:system|application|platform|service|"
                r"site)s?\b|scale to \d|concurrent users?|reliab\w*|highly available|"
                r"high availability|availability (?:target|requirement|of the (?:system|"
                r"application|service|site))|uptime"
            ),
            phrase="scalability and reliability",
            term="availability",
            layer="operations",
            claim_type=ClaimType.PERFORMANCE,
            question="What concurrent load and availability target applies?",
            reason="Load and availability targets set the architecture and the test plan.",
        ),
        Topic(
            keyword=(
                r"application security|system security|security (?:standard|baseline|review|"
                r"requirement|control|policy|of the (?:system|application|platform))|"
                r"secure (?:login|access|authentication|the (?:system|application|site|data))|"
                r"data security|security duties?"
            ),
            phrase="security considerations",
            term="security",
            layer="security",
            claim_type=ClaimType.SECURITY,
            question="Which security standards and data-protection duties apply here?",
            reason="Security duties constrain every layer and must be confirmed before design.",
        ),
    ),
    options=(
        (ApproachType.THIRD_PARTY_APP, "Existing application or service option for {phrase}"),
        (ApproachType.CUSTOM_BACKEND, "Custom standalone application option for {phrase}"),
        (ApproachType.MANUAL_PROCESS, "Manual process option for {phrase}"),
    ),
    out_of_scope=(
        "this specialist investigates standalone applications only; no requirement in this task "
        "describes an application, its architecture or its supporting services"
    ),
    assumption=(
        "The user count, data volume, existing systems and hosting constraints are not known."
    ),
    assumption_impact="Options for reuse or custom build could change once these are known.",
    risk="Synthetic placeholders are unverified; options may not hold for the client's setup.",
    integration_dependency=(
        "External service access for {rid} is not provided; no credentials are used in this "
        "prototype."
    ),
)


class StandaloneApplicationSpecialist:
    """Implements the AI-2 specialist protocol for the standalone applications category."""

    capability_id = CAPABILITY_ID
    specialist_category_id = SPECIALIST_CATEGORY_ID

    def __init__(self, profile: Profile = PROFILE) -> None:
        self._profile = profile

    def run(
        self, task: SpecialistTask, context: SpecialistContext
    ) -> SpecialistInvestigationResult:
        return investigate(self._profile, task, context)


__all__ = [
    "CAPABILITY_ID",
    "PLATFORM_ID",
    "SPECIALIST_CATEGORY_ID",
    "StandaloneApplicationSpecialist",
]
