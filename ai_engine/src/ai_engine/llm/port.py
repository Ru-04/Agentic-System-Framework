"""Provider-neutral LLM port (AI-S02). No provider SDK is imported anywhere under ``ai_engine``.

A real provider adapter may be added only after WDS approves a provider and a test-access policy.
Until then the only adapters are the mock and deterministic ones in ``adapters.py``, and every
real call is blocked by ``ApprovalGuard``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MAX_REPLY_CHARS_LIMIT = 1_000_000


@dataclass(frozen=True)
class LLMRequest:
    """One call. ``user_payload`` carries untrusted segment text; ``system_prompt`` never does.

    Validated on every construction, including the copies made for each attempt.
    """

    purpose: str
    system_prompt: str
    user_payload: str
    max_reply_chars: int

    def __post_init__(self) -> None:
        if not (
            isinstance(self.purpose, str)
            and isinstance(self.system_prompt, str)
            and isinstance(self.user_payload, str)
        ):
            raise TypeError("LLMRequest fields purpose, system_prompt and user_payload must be str")
        if not self.purpose:
            raise ValueError("LLMRequest.purpose must not be empty")
        limit = self.max_reply_chars
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("LLMRequest.max_reply_chars must be an int")
        if not 1 <= limit <= MAX_REPLY_CHARS_LIMIT:
            raise ValueError(f"LLMRequest.max_reply_chars must be 1 to {MAX_REPLY_CHARS_LIMIT}")


def fresh_request(request: LLMRequest) -> LLMRequest:
    """A new, validated request with the same values. Each attempt is handed one of these.

    A port that mutates the copy it receives cannot affect the original or any later attempt.
    """
    return LLMRequest(
        purpose=request.purpose,
        system_prompt=request.system_prompt,
        user_payload=request.user_payload,
        max_reply_chars=request.max_reply_chars,
    )


@dataclass(frozen=True)
class LLMResponse:
    text: str


class LLMPort(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...


class LLMError(Exception):
    """Base class for every failure raised by an LLM port."""


class LLMTimeoutError(LLMError):
    """The provider did not answer in time. The runner may retry."""


class LLMProviderError(LLMError):
    """The provider failed. The runner does not retry: a repeat could duplicate cost or effects."""


class ProviderNotApprovedError(LLMError):
    """No provider is approved for this call. Raised before any provider is contacted."""
