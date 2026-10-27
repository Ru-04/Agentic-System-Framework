"""
Middleware Applications specialist (AI-S05, CAP-MIDDLEWARE-APPLICATIONS).

The specialist runs only when an operator explicitly selects it. It investigates the integration
layer between applications or platforms: APIs, webhooks, data mapping, synchronisation, credentials,
retries, idempotency, rate limits, monitoring and integration security. It produces unverified
options, hypotheses, risks and clarification questions. It never selects an option, verifies a
claim, authorises an external write, or sets materiality. It reads only the evidence the context
serves.
"""

from __future__ import annotations

from ai_engine.applications.common import Profile, Topic, investigate
from ai_engine.applications.synthetic_evidence import (
    MIDDLEWARE_EVIDENCE_COLLECTION,
    MIDDLEWARE_RECORD_TOPICS,
)
from ai_engine.contracts.evidence import ClaimType
from ai_engine.contracts.specialist import (
    ApproachType,
    SpecialistInvestigationResult,
    SpecialistTask,
)
from ai_engine.specialists.base import SpecialistContext

CAPABILITY_ID = "CAP-MIDDLEWARE-APPLICATIONS"
SPECIALIST_CATEGORY_ID = "middleware_applications_specialist"
PLATFORM_ID = "middleware"

# Keywords are regular expressions written as raw strings. Each one matches the start of a word.
PROFILE = Profile(
    capability_id=CAPABILITY_ID,
    category_id=SPECIALIST_CATEGORY_ID,
    platform_id=PLATFORM_ID,
    collection=MIDDLEWARE_EVIDENCE_COLLECTION,
    record_topics=MIDDLEWARE_RECORD_TOPICS,
    topics=(
        Topic(
            keyword=(
                r"integrat\w*|connect(?:s|ed|ing)? to (?:the |our )?(?:erp|crm|accounting|"
                r"warehouse|shipping|supplier|payment|system|api)\b|"
                r"exchang\w* (?:\w+ )?(?:between|records?|data|orders?|stock)|"
                r"reconcil\w* (?:\w+ )?with (?:the )?(?:accounting|erp|crm|ledger|bank|payment)|"
                r"between (?:the )?(?:two |our )?systems\b|(?:send|sends|sent|push\w*|pull\w*|"
                r"transfer\w*|import\w*|export\w*|flow\w*|data) .{0,40}\b(?:to|from|into) (?:the |"
                r"our )?(?:erp|crm|accounting|warehouse|shipping|supplier|payment|package|"
                r"system)\b"
            ),
            phrase="integration between systems",
            term="integration",
            layer="integration",
            claim_type=ClaimType.API_BEHAVIOR,
            question="Which systems are connected, and which system owns each data item?",
            reason="Ownership decides which system wins on conflict and who may write.",
            integration=True,
        ),
        Topic(
            keyword=(r"webhooks?\b"),
            phrase="webhooks and event delivery",
            term="webhooks",
            layer="integration",
            claim_type=ClaimType.API_BEHAVIOR,
            question="Does the source system send webhooks or events, and with what signing and "
            "retry behaviour?",
            reason="Delivery guarantees decide whether duplicate and missed events need handling.",
            integration=True,
        ),
        Topic(
            keyword=(
                r"(?:domain|system|business|integration) events?\b|event-driven|event delivery|"
                r"events? (?:must|should) (?:be )?(?:delivered|sent|published)\b"
            ),
            phrase="event-driven delivery",
            term="events",
            layer="integration",
            claim_type=ClaimType.API_BEHAVIOR,
            question="Which events trigger the flow, and what is the expected delivery order?",
            reason="Ordering rules change the handler design and the replay plan.",
            integration=True,
        ),
        Topic(
            keyword=(r"\bapis?\b|endpoints?\b"),
            phrase="API access",
            term="scopes",
            layer="integration",
            claim_type=ClaimType.API_BEHAVIOR,
            question="Which API versions, scopes and rate limits apply to each connected system?",
            reason="Versions, scopes and limits decide what the integration can read and write.",
            integration=True,
        ),
        Topic(
            keyword=(
                r"(?:api|integration|connected system|erp|crm) credentials?\b|credentials? (?:for|"
                r"of) (?:the |each )?(?:connected|external|api|integration|system)|oauth|"
                r"tokens?\b|authenticat\w*|authori[sz]\w*|passwords?\b|secrets?\b|single sign-on|"
                r"\bsso\b"
            ),
            phrase="authentication and credentials",
            term="credentials",
            layer="security",
            claim_type=ClaimType.SECURITY,
            question="Which credential type and rotation policy applies to each connected system?",
            reason="Credential handling decides the secret storage and the access-review process.",
        ),
        Topic(
            keyword=(
                r"maps?\b(?= (?:the |our )?(?:customer|order|field|data|record|product|stock|"
                r"inventory))|mapping\b|transform\w* (?:\w+ )?(?:records?|data|orders?|fields?|"
                r"messages?|payloads?)"
            ),
            phrase="data mapping and transformation",
            term="mapping",
            layer="data",
            claim_type=ClaimType.IMPLEMENTATION,
            question="Which fields map between the systems, and which transformations apply?",
            reason="Each unmapped or transformed field is a defect source and a test case.",
        ),
        Topic(
            keyword=(
                r"synchron\w*|sync\w*|frequenc\w*|cadence|near real[- ]time|(?:send|sent|sync\w*|"
                r"update\w*|push\w*|pull\w*|import\w*|export\w*)\b.{0,60}\b(?:hourly|nightly|"
                r"daily|every \d+ (?:minutes?|hours?|seconds?)|every (?:night|day|hour|morning))\b"
            ),
            phrase="synchronisation direction and frequency",
            term="synchronisation",
            layer="data",
            claim_type=ClaimType.IMPLEMENTATION,
            question="Which direction and frequency of synchronisation is required, and what "
            "happens on conflict?",
            reason="Direction and frequency decide the conflict rule and the load on each system.",
        ),
        Topic(
            keyword=(r"retr(?:y|ies|ied|ying)\b|idempot\w*|duplicat\w*"),
            phrase="retries and idempotency",
            term="retries",
            layer="reliability",
            claim_type=ClaimType.IMPLEMENTATION,
            question="What retry limit and idempotency key apply to each write?",
            reason="Without an idempotency key a retry can duplicate a write in the target system.",
        ),
        Topic(
            keyword=(
                r"outage|recover\w* (?:the |after|from|automatically|messages?|sync\w*|data)|"
                r"fail(?:s|ed|ure|ing)?\b"
            ),
            phrase="failure recovery",
            term="failed",
            layer="reliability",
            claim_type=ClaimType.IMPLEMENTATION,
            question="How must the flow recover after an outage, and which messages are replayed?",
            reason="Recovery rules decide whether messages are lost or duplicated after a failure.",
        ),
        Topic(
            keyword=(
                r"monitored (?:for|and|by) |"
                r"monitor(?:s|ed|ing)? (?:the |failed |failing |integration |sync\w* |errors? |"
                r"messages? |the flow)|monitoring\b|alerts? (?:for|about|on) (?:failed|"
                r"the integration|errors?|messages?|sync\w*)|errors? (?:queue|log|handling|"
                r"alert)\w*|error handling|errors? (?:must be |are |is )?logged|logged (?:in|"
                r"to) (?:the )?(?:queue|integration|log)"
            ),
            phrase="monitoring and error handling",
            term="monitoring",
            layer="operations",
            claim_type=ClaimType.IMPLEMENTATION,
            question="Who receives alerts for failed messages, and what is the escalation process?",
            reason="Failed messages without an owner stay unnoticed and corrupt downstream data.",
        ),
        Topic(
            keyword=(r"rate[- ]limit\w*|throttl\w*|quota\w*"),
            phrase="rate limits and operational dependencies",
            term="rate",
            layer="operations",
            claim_type=ClaimType.PERFORMANCE,
            question="Which rate limit or quota applies, and which operational dependency could "
            "block the flow?",
            reason="A rate limit can throttle the whole flow, so the throughput must be sized.",
            integration=True,
        ),
        Topic(
            keyword=(
                r"integration security|privacy (?:of|in|for) (?:the )?(?:integration|"
                r"data in transit|messages?)|personal (?:\w+ )?(?:data|information) (?:in transit|"
                r"in queues?|through|between|sent|exchanged)|in transit|data protection|gdpr"
            ),
            phrase="integration security and data protection",
            term="encrypted",
            layer="security",
            claim_type=ClaimType.SECURITY,
            question="Which personal data crosses the integration, and what protection and "
            "retention applies?",
            reason="Personal data in transit or in queues carries its own protection duties.",
        ),
    ),
    options=(
        (ApproachType.MIDDLEWARE, "Middleware integration layer option for {phrase}"),
        (ApproachType.API_INTEGRATION, "Direct API integration option for {phrase}"),
        (ApproachType.RULE_BASED_AUTOMATION, "Scheduled rule-based automation option for {phrase}"),
    ),
    out_of_scope=(
        "this specialist investigates integration and middleware only; no requirement in this task "
        "describes a connection between systems, data flow or synchronisation"
    ),
    assumption=(
        "The connected systems, their API versions and their data ownership are not known."
    ),
    assumption_impact="Mapping, direction and limits could change once the systems are confirmed.",
    risk="Synthetic placeholders are unverified; the integration may not hold on client systems.",
    integration_dependency=(
        "External system access for {rid} is not provided; no credentials are used in this "
        "prototype."
    ),
)


class MiddlewareApplicationSpecialist:
    """Implements the AI-2 specialist protocol for the middleware applications category."""

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
    "MiddlewareApplicationSpecialist",
]
