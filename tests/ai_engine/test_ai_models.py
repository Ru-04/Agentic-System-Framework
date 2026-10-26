"""Model adapter: error classification, bounded retries, timeouts, configuration and log hygiene."""

from __future__ import annotations

import logging

import pytest

from webdesk_ai import synthetic
from webdesk_ai.models import (
    ErrorClass,
    InvocationFailed,
    ModelConfig,
    ModelError,
    ModelRequest,
    ModelResponse,
    NotConfiguredError,
    RetryPolicy,
    ScriptedModel,
    build_adapter,
    invoke_with_retry,
)

REQUEST = ModelRequest(purpose="test", prompt="SECRET-PROMPT-TEXT", timeout_seconds=5.0)
NO_SLEEP = {"sleep": lambda _seconds: None}


class _Flaky:
    provider_id = "flaky"
    model_id = "flaky-v1"

    def __init__(self, failures: list[ErrorClass | Exception], text: str = "ok") -> None:
        self._failures = list(failures)
        self._text = text
        self.calls = 0

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self._failures:
            item = self._failures.pop(0)
            if isinstance(item, ErrorClass):
                raise ModelError(item)
            raise item
        return ModelResponse(text=self._text, provider_id=self.provider_id, model_id=self.model_id)


def test_transient_failures_are_retried_until_success() -> None:
    adapter = _Flaky([ErrorClass.TRANSIENT, ErrorClass.TIMEOUT])
    result = invoke_with_retry(adapter, REQUEST, RetryPolicy(max_attempts=3), **NO_SLEEP)
    assert result.attempts == 3
    assert result.response.text == "ok"


def test_permanent_and_refused_errors_are_never_retried() -> None:
    for error_class in (ErrorClass.PERMANENT, ErrorClass.REFUSED):
        adapter = _Flaky([error_class, error_class])
        with pytest.raises(InvocationFailed) as raised:
            invoke_with_retry(adapter, REQUEST, RetryPolicy(max_attempts=3), **NO_SLEEP)
        assert adapter.calls == 1
        assert raised.value.error_class is error_class


def test_retries_stop_at_the_bound_and_report_the_class() -> None:
    adapter = _Flaky([ErrorClass.RATE_LIMITED] * 5)
    with pytest.raises(InvocationFailed) as raised:
        invoke_with_retry(adapter, REQUEST, RetryPolicy(max_attempts=2), **NO_SLEEP)
    assert adapter.calls == 2
    assert raised.value.attempts == 2
    assert raised.value.error_class is ErrorClass.RATE_LIMITED


def test_unexpected_adapter_exception_is_classified_permanent_and_not_retried() -> None:
    adapter = _Flaky([RuntimeError("provider internals with SECRET-PROMPT-TEXT")])
    with pytest.raises(InvocationFailed) as raised:
        invoke_with_retry(adapter, REQUEST, RetryPolicy(max_attempts=3), **NO_SLEEP)
    assert adapter.calls == 1
    assert raised.value.error_class is ErrorClass.PERMANENT
    assert "SECRET-PROMPT-TEXT" not in str(raised.value)


def test_oversized_output_is_a_permanent_failure() -> None:
    adapter = _Flaky([], text="x" * 50)
    request = ModelRequest(purpose="test", prompt="p", max_output_chars=10)
    with pytest.raises(InvocationFailed) as raised:
        invoke_with_retry(adapter, request, RetryPolicy(max_attempts=3), **NO_SLEEP)
    assert raised.value.error_class is ErrorClass.PERMANENT


def test_backoff_grows_exponentially_between_retries() -> None:
    waits: list[float] = []
    adapter = _Flaky([ErrorClass.TRANSIENT] * 3)
    invoke_with_retry(
        adapter, REQUEST, RetryPolicy(max_attempts=4, backoff_seconds=0.5), sleep=waits.append
    )
    assert waits == [0.5, 1.0, 2.0]


def test_retry_policy_rejects_unbounded_settings() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=6)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_seconds=-1)


def test_scripted_model_replays_outcomes_and_fails_permanently_when_exhausted() -> None:
    model = ScriptedModel(outcomes=["first", ErrorClass.TRANSIENT])
    assert model.generate(REQUEST).text == "first"
    with pytest.raises(ModelError) as raised:
        model.generate(REQUEST)
    assert raised.value.error_class is ErrorClass.TRANSIENT
    with pytest.raises(ModelError) as exhausted:
        model.generate(REQUEST)
    assert exhausted.value.error_class is ErrorClass.PERMANENT


def test_default_configuration_is_the_scripted_adapter_and_reads_no_key() -> None:
    config = ModelConfig.from_env({})
    assert config.provider == "scripted"
    adapter = build_adapter(config, outcomes=["text"])
    assert adapter.provider_id == "scripted"


def test_live_providers_are_refused_until_approved() -> None:
    config = ModelConfig.from_env({"WEBDESK_AI_PROVIDER": "openai"})
    with pytest.raises(NotConfiguredError):
        build_adapter(config)


def test_environment_settings_are_validated() -> None:
    with pytest.raises(ValueError):
        ModelConfig.from_env({"WEBDESK_AI_TIMEOUT_SECONDS": "0"})
    with pytest.raises(ValueError):
        ModelConfig.from_env({"WEBDESK_AI_MAX_ATTEMPTS": "9"})
    config = ModelConfig.from_env({"WEBDESK_AI_MAX_ATTEMPTS": "2"})
    assert config.retry_policy.max_attempts == 2


def test_logs_carry_classes_and_sizes_never_prompts_or_responses(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="webdesk_ai")
    adapter = _Flaky(
        [ErrorClass.TRANSIENT, RuntimeError("SECRET-PROMPT-TEXT")], text="RESPONSE-BODY"
    )
    with pytest.raises(InvocationFailed):
        invoke_with_retry(adapter, REQUEST, RetryPolicy(max_attempts=3), **NO_SLEEP)
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "class=transient" in logged
    assert "SECRET-PROMPT-TEXT" not in logged
    assert "RESPONSE-BODY" not in logged
    assert synthetic.RUN_ID.hex not in logged


def test_request_timeout_is_carried_to_the_adapter() -> None:
    seen: list[float] = []

    class _Recording(_Flaky):
        def generate(self, request: ModelRequest) -> ModelResponse:
            seen.append(request.timeout_seconds)
            return super().generate(request)

    invoke_with_retry(_Recording([]), REQUEST, RetryPolicy(), **NO_SLEEP)
    assert seen == [5.0]
