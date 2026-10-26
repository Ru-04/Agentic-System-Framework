"""Structured-output model port. Production adapters are out of scope until approved.

Only deterministic scripted responses ship in this increment. No provider client, credential or
network call exists here, which matches the rule that no production model credentials are used
and no source content is sent to an external AI provider.
"""

from __future__ import annotations

from collections.abc import Sequence


class StructuredLLM:
    """Port: take a prompt, return model text that must parse as the draft JSON schema."""

    def complete(self, prompt: str) -> str:  # pragma: no cover - interface only
        raise NotImplementedError


class ScriptedLLM(StructuredLLM):
    """Returns queued responses in order and records every prompt it was given."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self._responses:
            raise RuntimeError("scripted model has no response left")
        return self._responses.pop(0)
