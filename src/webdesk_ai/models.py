"""Provider-independent model adapter: typed requests and responses, error classes, retries, config.

Only deterministic adapters ship here (``scripted`` and the fault-injecting ``sequenced``). Live
provider adapters are deliberately absent: ``build_adapter`` refuses them until WDS approves a
provider, so no API key is read and no external call can be made from this package.

Retries are transport-level only. Content problems (schema or traceability failures) are handled
by the requirement agent's repair attempt, not here.

Logs carry error classes, attempt counts and sizes. They never carry prompts or responses.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

LOGGER = logging.getLogger("webdesk_ai.models")

SUPPORTED_SCRIPTED_PROVIDERS = frozenset({"scripted", "sequenced"})


class ErrorClass(StrEnum):
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    PERMANENT = "permanent"
    REFUSED = "refused"


RETRYABLE: frozenset[ErrorClass] = frozenset(
    {ErrorClass.TRANSIENT, ErrorClass.TIMEOUT, ErrorClass.RATE_LIMITED}
)


class ModelError(Exception):
    """A classified adapter failure. The message is the class only, never provider text."""

    def __init__(self, error_class: ErrorClass) -> None:
        super().__init__(error_class.value)
        self.error_class = error_class

    @property
    def retryable(self) -> bool:
        return self.error_class in RETRYABLE


class InvocationFailed(Exception):
    """Raised when retries are exhausted or the error is not retryable."""

    def __init__(self, error_class: ErrorClass, attempts: int) -> None:
        super().__init__(error_class.value)
        self.error_class = error_class
        self.attempts = attempts


class NotConfiguredError(Exception):
    """The configured provider is not approved in this increment."""


@dataclass(frozen=True)
class ModelRequest:
    purpose: str
    prompt: str
    timeout_seconds: float = 30.0
    max_output_chars: int = 200_000


@dataclass(frozen=True)
class ModelResponse:
    text: str
    provider_id: str
    model_id: str


class ModelAdapter(Protocol):
    provider_id: str
    model_id: str

    def generate(self, request: ModelRequest) -> ModelResponse: ...


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.5

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")


@dataclass(frozen=True)
class InvocationResult:
    response: ModelResponse
    attempts: int


def invoke_with_retry(
    adapter: ModelAdapter,
    request: ModelRequest,
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> InvocationResult:
    """Call the adapter with bounded, classified retries.

    Unexpected exceptions are classified as ``permanent`` and never retried, so an adapter bug
    cannot loop. A response longer than ``max_output_chars`` is a permanent failure.
    """
    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = adapter.generate(request)
        except ModelError as exc:
            error_class = exc.error_class
        except Exception as exc:  # classify, never re-raise with provider detail
            LOGGER.warning("model adapter raised %s; classified as permanent", type(exc).__name__)
            error_class = ErrorClass.PERMANENT
        else:
            if len(response.text) > request.max_output_chars:
                error_class = ErrorClass.PERMANENT
            else:
                LOGGER.info(
                    "model call ok purpose=%s attempt=%d chars=%d",
                    request.purpose,
                    attempt,
                    len(response.text),
                )
                return InvocationResult(response=response, attempts=attempt)
        LOGGER.info(
            "model call failed purpose=%s attempt=%d class=%s",
            request.purpose,
            attempt,
            error_class.value,
        )
        if error_class not in RETRYABLE or attempt == policy.max_attempts:
            raise InvocationFailed(error_class, attempt)
        sleep(policy.backoff_seconds * (2 ** (attempt - 1)))
    raise AssertionError("unreachable: the loop always returns or raises")  # pragma: no cover


@dataclass
class ScriptedModel:
    """Default adapter. Each queued item is a response text or an ``ErrorClass`` to raise."""

    outcomes: Sequence[str | ErrorClass]
    provider_id: str = "scripted"
    model_id: str = "scripted-v1"
    prompts: list[str] = field(default_factory=list)
    _queue: list[str | ErrorClass] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self._queue = list(self.outcomes)

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.prompts.append(request.prompt)
        if not self._queue:
            raise ModelError(ErrorClass.PERMANENT)
        outcome = self._queue.pop(0)
        if isinstance(outcome, ErrorClass):
            raise ModelError(outcome)
        return ModelResponse(text=outcome, provider_id=self.provider_id, model_id=self.model_id)

    @property
    def calls(self) -> int:
        return len(self.prompts)


@dataclass(frozen=True)
class ModelConfig:
    provider: str = "scripted"
    model_id: str = "scripted-v1"
    timeout_seconds: float = 30.0
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 1 and 300")
        if not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> ModelConfig:
        """Reads only non-secret settings. No API key variable is read in this increment."""
        return cls(
            provider=env.get("WEBDESK_AI_PROVIDER", "scripted"),
            model_id=env.get("WEBDESK_AI_MODEL", "scripted-v1"),
            timeout_seconds=float(env.get("WEBDESK_AI_TIMEOUT_SECONDS", "30")),
            max_attempts=int(env.get("WEBDESK_AI_MAX_ATTEMPTS", "3")),
        )

    @property
    def retry_policy(self) -> RetryPolicy:
        return RetryPolicy(max_attempts=self.max_attempts, backoff_seconds=0.0)


def build_adapter(config: ModelConfig, outcomes: Sequence[str | ErrorClass] = ()) -> ModelAdapter:
    if config.provider in SUPPORTED_SCRIPTED_PROVIDERS:
        return ScriptedModel(
            outcomes=outcomes, provider_id=config.provider, model_id=config.model_id
        )
    raise NotConfiguredError(
        f"provider {config.provider!r} is not approved in this increment; "
        "live provider adapters need WDS approval"
    )
