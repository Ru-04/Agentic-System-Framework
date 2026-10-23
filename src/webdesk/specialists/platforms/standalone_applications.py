"""Standalone Applications specialist foundation (M2 Sprint 3; isolated, non-production; authorized
23 Oct 2026).

Profile only. No evidence source is approved for this platform yet, so no retrieval is attempted
and no platform capability is asserted. Adding a source requires an approved allowlist entry
(D08).
"""

from __future__ import annotations

from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.platforms.generic import PlatformProfile, PlatformSpecialist

PROFILE = PlatformProfile(
    specialist_id=SpecialistId.STANDALONE_APPLICATIONS,
    label="Standalone Applications",
    capability_topics={
        "authentication and accounts": ("login", "authentication", "account"),
        "data and storage": ("database", "storage", "schema"),
        "interfaces": ("api", "endpoint", "interface"),
        "deployment and operations": ("deploy", "hosting", "monitor"),
    },
    plan_or_version_terms=(),
    approved_source=None,
    notes=(
        "Not primarily a commerce-platform customisation. Analysable without an eCommerce "
        "specialist (GOVERNANCE 5.3).",
    ),
)


class StandaloneApplicationsSpecialist(PlatformSpecialist):
    profile = PROFILE
