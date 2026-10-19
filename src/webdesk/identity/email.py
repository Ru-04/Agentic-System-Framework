"""Contact email normalization and WDS domain policy (T5).

Rules from REQUIREMENT_SCHEMA §3.1 and GOVERNANCE §11 (P-GATE1-CONTACT-01):
- Unicode NFC, then trim outer whitespace, then lowercase.
- Local part and domain must be ASCII. Gate 1 local parts are ASCII only.
- ``+`` sub-addressing is rejected.
- The domain must be in the configured WDS allowlist. An empty allowlist is deny-all.
- A configured alias denylist entry rejects that local part.
- Missing allowlist or denylist configuration fails closed (ConfigurationError).

Domain allowlisting is not proof of ownership. Ownership is established by the independent
approval procedure (T8), not by this function.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from webdesk.config import ConfigurationError, Settings

MAX_EMAIL_LENGTH = 254
_LOCAL_RE = re.compile(r"^[a-z0-9._-]+$")
_DOMAIN_RE = re.compile(r"^[a-z0-9.-]+$")


class EmailPolicyError(ValueError):
    """A contact address was refused. ``reason`` is a stable machine-readable code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ContactEmailPolicy:
    allowed_domains: frozenset[str]
    alias_denylist: frozenset[str]

    def normalize(self, raw: str) -> str:
        value = unicodedata.normalize("NFC", raw).strip()
        if not value or len(value) > MAX_EMAIL_LENGTH or value.count("@") != 1:
            raise EmailPolicyError("malformed")
        local, domain = value.split("@")
        if not local.isascii() or not domain.isascii():
            raise EmailPolicyError("non_ascii")
        local = local.lower()
        domain = domain.lower()
        if "+" in local:
            raise EmailPolicyError("plus_subaddress")
        if not _LOCAL_RE.fullmatch(local) or not _DOMAIN_RE.fullmatch(domain):
            raise EmailPolicyError("malformed")
        if domain not in self.allowed_domains:
            raise EmailPolicyError("domain_not_allowed")
        if local in self.alias_denylist:
            raise EmailPolicyError("alias_denied")
        return f"{local}@{domain}"


def policy_from_settings(settings: Settings) -> ContactEmailPolicy:
    """Build the policy, failing closed when the WDS configuration is absent."""
    if settings.email_domain_allowlist is None:
        raise ConfigurationError("WEBDESK_EMAIL_DOMAIN_ALLOWLIST is not configured")
    if settings.email_alias_denylist is None:
        raise ConfigurationError("WEBDESK_EMAIL_ALIAS_DENYLIST is not configured")
    return ContactEmailPolicy(
        allowed_domains=settings.allowed_email_domains,
        alias_denylist=settings.alias_denylist,
    )
