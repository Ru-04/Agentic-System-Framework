"""Test and guard adapters for the LLM port. None of them contacts a provider."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ai_engine.llm.port import (
    LLMError,
    LLMPort,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    ProviderNotApprovedError,
)

# A scripted step is a reply text, an error to raise, or a function that builds the reply.
ScriptStep = str | LLMError | Callable[[LLMRequest], str]


class ScriptedLLM:
    """Replays a fixed script, one step per call, and records every request it receives."""

    def __init__(self, script: Sequence[ScriptStep]) -> None:
        self._script = list(script)
        self.calls: list[LLMRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if not self._script:
            raise LLMProviderError("scripted adapter has no reply left")
        step = self._script.pop(0)
        if isinstance(step, LLMError):
            raise step
        if isinstance(step, str):
            return LLMResponse(text=step)
        return LLMResponse(text=step(request))


class DeterministicLLM:
    """Answers every call with a pure function of the request. Used for the evaluation runs."""

    def __init__(self, rules: Callable[[LLMRequest], str]) -> None:
        self._rules = rules
        self.calls: list[LLMRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return LLMResponse(text=self._rules(request))


@dataclass(frozen=True)
class ApprovalGuard:
    """AI-local execution gate: refuses every provider call unless ``approved`` is set.

    What this is: a review gate inside the AI Engine. Every public structured entry point requires
    an exact ApprovalGuard (see ``require_guard``), so an unapproved port cannot reach a provider
    through this package.

    What this is not: Foundation authentication or authorization. It does not identify an operator,
    check a permission, or record who approved a provider. Those belong to Foundation and are
    not implemented here. Until Foundation supplies them, ``approved=True`` is set only by test code
    and by no production path.

    Limits: the guard is frozen, so ordinary assignment raises. ``object.__setattr__`` can still
    change a frozen dataclass, and code in the same process can call the wrapped port directly.
    The guard does not sandbox code. See docs/AI_ENGINE_AI_S02_REMEDIATION.md.
    """

    inner: LLMPort
    approved: bool = False

    def complete(self, request: LLMRequest) -> LLMResponse:
        if not self.approved:
            raise ProviderNotApprovedError(
                "no LLM provider is approved for this call; WDS approval is required"
            )
        return self.inner.complete(request)


def require_guard(port: object) -> ApprovalGuard:
    """Refuse anything that is not exactly an ApprovalGuard.

    ``type(port) is`` is used rather than ``isinstance``: isinstance honours a spoofed
    ``__class__`` property, and a subclass could override ``complete``. Both are refused.
    Every entry point that reaches a provider calls this first.
    """
    if type(port) is ApprovalGuard:
        return port
    raise TypeError("AI-S02 calls accept only an exact ApprovalGuard wrapping the port")
