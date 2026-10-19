"""T5 unit tests: contact email normalization and fail-closed WDS policy."""

from __future__ import annotations

import pytest

from webdesk.config import ConfigurationError, Settings
from webdesk.identity.email import ContactEmailPolicy, EmailPolicyError, policy_from_settings

POLICY = ContactEmailPolicy(
    allowed_domains=frozenset({"wds-test.example"}),
    alias_denylist=frozenset({"admin", "root"}),
)


def test_mixed_case_and_outer_whitespace_normalize_to_one_address() -> None:
    assert POLICY.normalize("  Ada.Lovelace@WDS-Test.example  ") == "ada.lovelace@wds-test.example"
    assert POLICY.normalize("ADA.LOVELACE@wds-test.example") == POLICY.normalize(
        "ada.lovelace@wds-test.example"
    )


def test_nfc_is_applied_before_checks() -> None:
    # Decomposed "e" + combining acute stays non-ASCII after NFC, so the local part is refused.
    with pytest.raises(EmailPolicyError) as exc:
        POLICY.normalize("josé@wds-test.example")
    assert exc.value.reason == "non_ascii"


def test_non_ascii_local_part_is_refused() -> None:
    with pytest.raises(EmailPolicyError) as exc:
        POLICY.normalize("josé@wds-test.example")
    assert exc.value.reason == "non_ascii"


def test_plus_subaddress_is_refused() -> None:
    with pytest.raises(EmailPolicyError) as exc:
        POLICY.normalize("ada+tag@wds-test.example")
    assert exc.value.reason == "plus_subaddress"


def test_domain_outside_allowlist_is_refused() -> None:
    with pytest.raises(EmailPolicyError) as exc:
        POLICY.normalize("ada@gmail.example")
    assert exc.value.reason == "domain_not_allowed"


def test_denylisted_alias_is_refused_case_insensitively() -> None:
    with pytest.raises(EmailPolicyError) as exc:
        POLICY.normalize("Admin@wds-test.example")
    assert exc.value.reason == "alias_denied"


@pytest.mark.parametrize(
    "raw", ["", "   ", "no-at-sign", "two@@wds-test.example", "@wds-test.example"]
)
def test_malformed_addresses_are_refused(raw: str) -> None:
    with pytest.raises(EmailPolicyError) as exc:
        POLICY.normalize(raw)
    assert exc.value.reason == "malformed"


def test_empty_allowlist_is_deny_all() -> None:
    deny_all = ContactEmailPolicy(allowed_domains=frozenset(), alias_denylist=frozenset())
    with pytest.raises(EmailPolicyError) as exc:
        deny_all.normalize("ada@wds-test.example")
    assert exc.value.reason == "domain_not_allowed"


def test_policy_fails_closed_when_allowlist_unset() -> None:
    with pytest.raises(ConfigurationError, match="ALLOWLIST"):
        policy_from_settings(Settings(_env_file=None, email_alias_denylist=""))


def test_policy_fails_closed_when_denylist_unset() -> None:
    with pytest.raises(ConfigurationError, match="DENYLIST"):
        policy_from_settings(Settings(_env_file=None, email_domain_allowlist="wds-test.example"))


def test_policy_built_from_configured_settings() -> None:
    settings = Settings(
        _env_file=None,
        email_domain_allowlist="WDS-Test.example",
        email_alias_denylist="root",
    )
    policy = policy_from_settings(settings)
    assert policy.normalize("Ada@wds-test.example") == "ada@wds-test.example"
    with pytest.raises(EmailPolicyError):
        policy.normalize("root@wds-test.example")
