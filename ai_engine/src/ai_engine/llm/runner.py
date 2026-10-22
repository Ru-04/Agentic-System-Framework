"""Structured-call runner (AI-S02): one port call, one parse, explicit bounded retries.

Approval: ``call_structured`` is a public path to a provider, so it requires an exact
``ApprovalGuard`` just as the agents do. A bare port is refused with ``TypeError`` before any call.

Retry policy, by failure kind:
- ``LLMTimeoutError``: retried up to ``max_attempts``, then ``FAILED_TIMEOUT``.
- Invalid reply (over the length limit, repeated JSON key, not JSON, schema violation, or failed
  check): retried, then ``INVALID_REPLY_EXHAUSTED``.
- ``LLMProviderError`` and any other ``LLMError``: not retried, ``PROVIDER_ERROR``.
- ``ProviderNotApprovedError``: not retried, ``NOT_APPROVED``.
- Any other exception from the port, or a response whose ``text`` is not a string: not retried,
  ``UNEXPECTED_PORT_ERROR``.

Each attempt receives its own copy of the request, so a port that mutates what it is given cannot
change later attempts or the caller's object. Outcomes never carry exception messages: only the
exception class name is kept in ``errors``. A value is returned only when the whole reply passes
every check. Duplicate JSON keys are rejected while decoding, before schema validation.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ai_engine.llm.adapters import ApprovalGuard, require_guard
from ai_engine.llm.port import (
    LLMError,
    LLMRequest,
    LLMTimeoutError,
    ProviderNotApprovedError,
    fresh_request,
)

DEFAULT_MAX_ATTEMPTS = 3

ReplyT = TypeVar("ReplyT", bound=BaseModel)


class CallStatus(StrEnum):
    SUCCESS = "success"
    FAILED_TIMEOUT = "failed_timeout"
    INVALID_REPLY_EXHAUSTED = "invalid_reply_exhausted"
    PROVIDER_ERROR = "provider_error"
    NOT_APPROVED = "not_approved"
    UNEXPECTED_PORT_ERROR = "unexpected_port_error"


class DuplicateKeyError(ValueError):
    """A JSON object repeats a key. The reply is refused, not resolved by picking one value."""


@dataclass(frozen=True)
class CallOutcome(Generic[ReplyT]):
    status: CallStatus
    value: ReplyT | None
    attempts: int
    errors: tuple[str, ...] = ()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def _parse_reply(
    text: str,
    request: LLMRequest,
    reply_model: type[ReplyT],
    check: Callable[[ReplyT], list[str]] | None,
) -> tuple[ReplyT | None, list[str]]:
    if len(text) > request.max_reply_chars:
        return None, [f"reply is {len(text)} characters; the limit is {request.max_reply_chars}"]
    try:
        data = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
        value = reply_model.model_validate(data)
    except DuplicateKeyError:
        # Report the fact only: the repeated key name is untrusted reply text.
        return None, ["reply repeats a JSON key"]
    except ValidationError as exc:
        # Report the count only: validation messages can echo untrusted reply text.
        return None, [f"reply does not match {reply_model.__name__}: {exc.error_count()} error(s)"]
    except (ValueError, RecursionError):
        return None, ["reply is not a well-formed JSON object"]
    problems = check(value) if check is not None else []
    if problems:
        return None, problems
    return value, []


def call_structured(
    port: ApprovalGuard,
    request: LLMRequest,
    reply_model: type[ReplyT],
    *,
    check: Callable[[ReplyT], list[str]] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> CallOutcome[ReplyT]:
    guard = require_guard(port)
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    status = CallStatus.FAILED_TIMEOUT
    errors: tuple[str, ...] = ()
    for attempt in range(1, max_attempts + 1):
        # A fresh copy per attempt: a port that mutates its argument cannot poison later attempts.
        attempt_request = fresh_request(request)
        try:
            text = guard.complete(attempt_request).text
        except ProviderNotApprovedError as exc:
            return CallOutcome(CallStatus.NOT_APPROVED, None, attempt, (type(exc).__name__,))
        except LLMTimeoutError as exc:
            status, errors = CallStatus.FAILED_TIMEOUT, (type(exc).__name__,)
            continue
        except LLMError as exc:
            return CallOutcome(CallStatus.PROVIDER_ERROR, None, attempt, (type(exc).__name__,))
        except Exception as exc:
            # Covers None, dict or other shapes returned by a port (no .text), and any crash.
            return CallOutcome(
                CallStatus.UNEXPECTED_PORT_ERROR, None, attempt, (type(exc).__name__,)
            )
        if not isinstance(text, str):
            return CallOutcome(CallStatus.UNEXPECTED_PORT_ERROR, None, attempt, ("NonTextReply",))
        try:
            value, problems = _parse_reply(text, request, reply_model, check)
        except Exception as exc:
            # A check that raises is a bug in the agent, not a reply problem. Refuse, do not crash.
            return CallOutcome(
                CallStatus.UNEXPECTED_PORT_ERROR, None, attempt, (type(exc).__name__,)
            )
        if value is not None:
            return CallOutcome(CallStatus.SUCCESS, value, attempt)
        status, errors = CallStatus.INVALID_REPLY_EXHAUSTED, tuple(problems)
    return CallOutcome(status, None, max_attempts, errors)
