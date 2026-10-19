"""F-CFG-01: profile validation fails closed without production configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from webdesk.config import ConfigurationError, Settings

FULL_ONBOARDING: dict[str, object] = {
    "email_domain_allowlist": "wds-test.example",
    "email_alias_denylist": "admin,root",
    "email_transport": "capture",
    "rl_login_failures_per_account_ip": 5,
    "rl_login_window_minutes": 15,
    "rl_ip_requests_per_window": 100,
    "rl_contact_actions_per_window": 5,
    "rl_contact_ip_requests_per_window": 100,
    "rl_window_minutes": 15,
    "outbox_dead_letter_threshold": 5,
    "outbox_encryption_key": "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",  # 32 x 0x01, test only
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("WEBDESK_"):
            monkeypatch.delenv(key, raising=False)


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_default_profile_is_development_and_fails_closed() -> None:
    s = _settings()
    assert s.env == "development"
    assert s.onboarding_capability().enabled is False
    assert s.ceremony_capability().enabled is False
    s.validate_for_profile()  # development starts without production config


def test_onboarding_lists_every_missing_item() -> None:
    report = _settings().onboarding_capability()
    joined = " ".join(report.missing)
    for name in [
        "WEBDESK_EMAIL_DOMAIN_ALLOWLIST",
        "WEBDESK_EMAIL_ALIAS_DENYLIST",
        "WEBDESK_EMAIL_TRANSPORT",
        "WEBDESK_RL_LOGIN_FAILURES_PER_ACCOUNT_IP",
        "WEBDESK_RL_CONTACT_IP_REQUESTS_PER_WINDOW",
        "WEBDESK_OUTBOX_DEAD_LETTER_THRESHOLD",
    ]:
        assert name in joined


def test_fully_configured_test_profile_enables_onboarding() -> None:
    s = _settings(env="test", **FULL_ONBOARDING)
    assert s.onboarding_capability().enabled is True


def test_each_single_missing_onboarding_item_disables_onboarding() -> None:
    for key in FULL_ONBOARDING:
        overrides = {k: v for k, v in FULL_ONBOARDING.items() if k != key}
        s = _settings(env="test", **overrides)
        assert s.onboarding_capability().enabled is False, key


def test_empty_allowlist_is_deny_all_not_allow_all() -> None:
    s = _settings(env="test", **{**FULL_ONBOARDING, "email_domain_allowlist": ""})
    assert s.allowed_email_domains == frozenset()
    assert s.onboarding_capability().enabled is True  # configured, but permits nothing
    # the empty allowlist itself is caught by the domain check at approval time (T5)


def test_allowlist_and_denylist_are_normalized() -> None:
    s = _settings(
        env="test",
        **{**FULL_ONBOARDING, "email_domain_allowlist": " WDS-Test.example , x.test "},
    )
    assert s.allowed_email_domains == frozenset({"wds-test.example", "x.test"})
    assert s.alias_denylist == frozenset({"admin", "root"})


def test_ceremony_requires_readable_owner_key(tmp_path: Path) -> None:
    assert _settings().ceremony_capability().enabled is False
    missing_file = tmp_path / "absent.pub"
    report = _settings(owner_public_key_path=missing_file).ceremony_capability()
    assert report.enabled is False
    key = tmp_path / "owner.pub"
    key.write_text("placeholder", encoding="utf-8")
    assert _settings(owner_public_key_path=key).ceremony_capability().enabled is True


def test_production_without_configuration_refuses_to_start() -> None:
    with pytest.raises(ConfigurationError) as exc:
        _settings(env="production").validate_for_profile()
    message = str(exc.value)
    assert "WEBDESK_DATABASE_URL" in message
    assert "WEBDESK_APP_DATABASE_URL" in message
    assert "WEBDESK_OWNER_PUBLIC_KEY_PATH" in message
    assert "WEBDESK_EMAIL_TRANSPORT" in message


def test_production_refuses_capture_sink_even_when_otherwise_complete(tmp_path: Path) -> None:
    key = tmp_path / "owner.pub"
    key.write_text("placeholder", encoding="utf-8")
    s = _settings(
        env="production",
        database_url="postgresql+psycopg://u:p@db/x",
        app_database_url="postgresql+psycopg://a:p@db/x",
        owner_public_key_path=key,
        **FULL_ONBOARDING,
    )
    with pytest.raises(ConfigurationError, match="capture"):
        s.validate_for_profile()


def test_production_still_refuses_without_a_delivery_provider(tmp_path: Path) -> None:
    # Production email delivery is an open prerequisite; transport "none" must fail closed.
    key = tmp_path / "owner.pub"
    key.write_text("placeholder", encoding="utf-8")
    overrides = {**FULL_ONBOARDING, "email_transport": "none"}
    s = _settings(
        env="production",
        database_url="postgresql+psycopg://u:p@db/x",
        app_database_url="postgresql+psycopg://a:p@db/x",
        owner_public_key_path=key,
        **overrides,
    )
    with pytest.raises(ConfigurationError, match="WEBDESK_EMAIL_TRANSPORT"):
        s.validate_for_profile()


def test_secrets_are_not_rendered() -> None:
    s = _settings(database_url="postgresql+psycopg://u:SUPERSECRET@db/x")
    assert "SUPERSECRET" not in repr(s)
    assert "SUPERSECRET" not in str(s.model_dump())


def test_unknown_setting_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, bogus_setting="x")  # type: ignore[call-arg]
