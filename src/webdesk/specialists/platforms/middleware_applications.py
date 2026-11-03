"""Middleware Applications specialist foundation (M2 Sprint 3; isolated, non-production; authorized
23 Oct 2026).

Profile only. No evidence source is approved for this platform yet, so no retrieval is attempted
and no platform capability is asserted. Adding a source requires an approved allowlist entry
(D08).
"""

from __future__ import annotations

from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.platforms.generic import PlatformProfile, PlatformSpecialist

PROFILE = PlatformProfile(
    specialist_id=SpecialistId.MIDDLEWARE_APPLICATIONS,
    label="Middleware Applications",
    capability_topics={
        "orchestration and sync": ("sync", "orchestration", "transform"),
        "webhooks and events": ("webhook", "event", "queue"),
        "retries and idempotency": ("retry", "retries", "idempotent", "idempotency"),
        "authentication and observability": ("oauth", "token", "log", "observability"),
    },
    plan_or_version_terms=(),
    approved_source=None,
    notes=(
        "Technology-neutral: evaluate language and runtime from requirements and evidence "
        "(registry ROUTE-MIDDLEWARE-APPLICATIONS-001).",
    ),
)


class MiddlewareApplicationsSpecialist(PlatformSpecialist):
    profile = PROFILE
