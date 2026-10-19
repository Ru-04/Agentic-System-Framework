"""Runtime settings with profile-based, fail-closed validation (T2 / F-CFG-01).

Rules:
- ``production`` refuses to start unless every required production setting is present
  and the non-production email capture sink is not used.
- ``development`` and ``test`` start, but onboarding and ceremonies report themselves as
  disabled, with the missing items named, until the configuration is complete.
- An empty ``WEBDESK_EMAIL_DOMAIN_ALLOWLIST`` is deny-all, not allow-all.
- Secrets are wrapped in ``SecretStr`` so they never appear in ``repr`` or logs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Raised at startup when the selected profile is not safely configured."""


@dataclass(frozen=True)
class CapabilityReport:
    """Whether a sensitive capability may run, and why not if it may not."""

    enabled: bool
    missing: tuple[str, ...] = field(default_factory=tuple)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WEBDESK_",
        env_file=".env",
        extra="forbid",
    )

    env: Literal["development", "test", "production"] = "development"

    database_url: SecretStr | None = None
    app_database_url: SecretStr | None = None

    # None = not configured (fails closed). "" = configured as empty, which is deny-all.
    email_domain_allowlist: str | None = None
    email_alias_denylist: str | None = None

    owner_public_key_path: Path | None = None

    # "none" is the fail-closed default. "capture" is the non-production sink only.
    email_transport: Literal["capture", "none"] = "none"

    rl_login_failures_per_account_ip: int | None = None
    rl_login_window_minutes: int | None = None
    rl_ip_requests_per_window: int | None = None
    rl_contact_actions_per_window: int | None = None
    rl_contact_ip_requests_per_window: int | None = None
    rl_window_minutes: int | None = None

    outbox_dead_letter_threshold: int | None = None

    # Base64 of 32 random bytes. Seals prior contact addresses in the outbox (AES-256-GCM).
    outbox_encryption_key: SecretStr | None = None

    # Absolute directory for uploaded bytes. Outside the repository (D-7). Unset = intake disabled.
    storage_root: Path | None = None

    # ----- derived views -------------------------------------------------------------

    @property
    def allowed_email_domains(self) -> frozenset[str]:
        if not self.email_domain_allowlist:
            return frozenset()
        return frozenset(
            d.strip().lower() for d in self.email_domain_allowlist.split(",") if d.strip()
        )

    @property
    def alias_denylist(self) -> frozenset[str]:
        if not self.email_alias_denylist:
            return frozenset()
        return frozenset(
            a.strip().lower() for a in self.email_alias_denylist.split(",") if a.strip()
        )

    def _rate_limits_missing(self) -> list[str]:
        required = {
            "WEBDESK_RL_LOGIN_FAILURES_PER_ACCOUNT_IP": self.rl_login_failures_per_account_ip,
            "WEBDESK_RL_LOGIN_WINDOW_MINUTES": self.rl_login_window_minutes,
            "WEBDESK_RL_IP_REQUESTS_PER_WINDOW": self.rl_ip_requests_per_window,
            "WEBDESK_RL_CONTACT_ACTIONS_PER_WINDOW": self.rl_contact_actions_per_window,
            "WEBDESK_RL_CONTACT_IP_REQUESTS_PER_WINDOW": (self.rl_contact_ip_requests_per_window),
            "WEBDESK_RL_WINDOW_MINUTES": self.rl_window_minutes,
        }
        return [name for name, value in required.items() if value is None]

    def onboarding_capability(self) -> CapabilityReport:
        """Contact approval, activation, reset and withdrawal need all of these."""
        missing: list[str] = []
        if self.email_domain_allowlist is None:
            missing.append("WEBDESK_EMAIL_DOMAIN_ALLOWLIST")
        if self.email_alias_denylist is None:
            missing.append("WEBDESK_EMAIL_ALIAS_DENYLIST")
        if self.email_transport == "none":
            missing.append("WEBDESK_EMAIL_TRANSPORT (no delivery transport configured)")
        missing.extend(self._rate_limits_missing())
        if self.outbox_dead_letter_threshold is None:
            missing.append("WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD")
        if self.outbox_encryption_key is None:
            missing.append("WEBDESK_OUTBOX_ENCRYPTION_KEY")
        return CapabilityReport(enabled=not missing, missing=tuple(missing))

    def intake_capability(self) -> CapabilityReport:
        """Source upload needs an absolute storage root that already exists or can be created."""
        missing: list[str] = []
        if self.storage_root is None:
            missing.append("WEBDESK_STORAGE_ROOT")
        elif not self.storage_root.is_absolute():
            missing.append("WEBDESK_STORAGE_ROOT (must be absolute)")
        return CapabilityReport(enabled=not missing, missing=tuple(missing))

    def ceremony_capability(self) -> CapabilityReport:
        """Installation and recovery ceremonies need a configured, readable owner key."""
        missing: list[str] = []
        if self.owner_public_key_path is None:
            missing.append("WEBDESK_OWNER_PUBLIC_KEY_PATH")
        elif not self.owner_public_key_path.is_file():
            missing.append("WEBDESK_OWNER_PUBLIC_KEY_PATH (file not readable)")
        return CapabilityReport(enabled=not missing, missing=tuple(missing))

    def validate_for_profile(self) -> None:
        """Fail at startup in production. Other profiles start and report capabilities."""
        if self.env != "production":
            return

        missing: list[str] = []
        if self.database_url is None:
            missing.append("WEBDESK_DATABASE_URL")
        if self.app_database_url is None:
            missing.append("WEBDESK_APP_DATABASE_URL")
        missing.extend(self.onboarding_capability().missing)
        missing.extend(self.ceremony_capability().missing)

        if self.email_transport == "capture":
            raise ConfigurationError(
                "WEBDESK_EMAIL_TRANSPORT=capture is a non-production sink and is refused "
                "when WEBDESK_ENV=production"
            )
        if missing:
            raise ConfigurationError(
                "production configuration incomplete; missing: " + ", ".join(missing)
            )
