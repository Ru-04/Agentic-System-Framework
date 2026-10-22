"""AI-S02 LLM port and structured-call runner: retries, explicit failure states, guard default."""

from __future__ import annotations

import json

import pytest

from ai_engine.contracts.semantic import IntakeResult
from ai_engine.llm.adapters import ApprovalGuard, DeterministicLLM, ScriptedLLM
from ai_engine.llm.port import (
    LLMProviderError,
    LLMRequest,
    LLMTimeoutError,
)
from ai_engine.llm.runner import CallStatus, call_structured

REQUEST = LLMRequest(purpose="test", system_prompt="system", user_payload="{}", max_reply_chars=500)
VALID = json.dumps(
    {"project_id": "PRJ-TEST-0001", "items": [], "unclassified_segment_ids": ["SEG-TEST-0001"]}
)


def test_success_on_first_attempt() -> None:
    port = ScriptedLLM([VALID])
    outcome = call_structured(ApprovalGuard(port, approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.SUCCESS
    assert outcome.attempts == 1
    assert outcome.value is not None
    assert port.call_count == 1


def test_timeout_then_success_retries_once() -> None:
    port = ScriptedLLM([LLMTimeoutError("slow"), VALID])
    outcome = call_structured(ApprovalGuard(port, approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.SUCCESS
    assert outcome.attempts == 2
    assert port.call_count == 2


def test_timeouts_exhausted_report_timeout_state() -> None:
    port = ScriptedLLM([LLMTimeoutError("t1"), LLMTimeoutError("t2"), LLMTimeoutError("t3")])
    outcome = call_structured(
        ApprovalGuard(port, approved=True), REQUEST, IntakeResult, max_attempts=3
    )
    assert outcome.status is CallStatus.FAILED_TIMEOUT
    assert outcome.value is None
    assert outcome.attempts == 3
    assert port.call_count == 3
    assert outcome.errors == ("LLMTimeoutError",)


def test_provider_error_is_not_retried() -> None:
    port = ScriptedLLM([LLMProviderError("provider down"), VALID])
    outcome = call_structured(ApprovalGuard(port, approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.PROVIDER_ERROR
    assert outcome.attempts == 1
    assert port.call_count == 1


def test_default_guard_refuses_with_zero_provider_calls() -> None:
    inner = DeterministicLLM(lambda request: VALID)
    guard = ApprovalGuard(inner)
    outcome = call_structured(guard, REQUEST, IntakeResult)
    assert outcome.status is CallStatus.NOT_APPROVED
    assert outcome.value is None
    assert outcome.attempts == 1
    assert inner.call_count == 0


def test_not_approved_is_not_retried() -> None:
    inner = ScriptedLLM([VALID, VALID, VALID])
    outcome = call_structured(ApprovalGuard(inner), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.NOT_APPROVED
    assert outcome.attempts == 1
    assert inner.call_count == 0


def test_approved_guard_forwards_the_call() -> None:
    inner = ScriptedLLM([VALID])
    outcome = call_structured(ApprovalGuard(inner, approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.SUCCESS
    assert inner.call_count == 1


def test_guard_default_is_not_approved() -> None:
    assert ApprovalGuard(ScriptedLLM([])).approved is False


def test_invalid_json_then_success_retries() -> None:
    port = ScriptedLLM(["{not json", VALID])
    outcome = call_structured(ApprovalGuard(port, approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.SUCCESS
    assert outcome.attempts == 2


def test_invalid_json_exhausted_reports_invalid_reply() -> None:
    port = ScriptedLLM(["{not json", "{still not", "[]"])
    outcome = call_structured(
        ApprovalGuard(port, approved=True), REQUEST, IntakeResult, max_attempts=3
    )
    assert outcome.status is CallStatus.INVALID_REPLY_EXHAUSTED
    assert outcome.value is None
    assert outcome.attempts == 3


def test_schema_violation_is_an_invalid_reply() -> None:
    port = ScriptedLLM([json.dumps({"project_id": "PRJ-TEST-0001", "approved": True})] * 3)
    outcome = call_structured(
        ApprovalGuard(port, approved=True), REQUEST, IntakeResult, max_attempts=3
    )
    assert outcome.status is CallStatus.INVALID_REPLY_EXHAUSTED
    assert outcome.errors == ("reply does not match IntakeResult: 3 error(s)",)


def test_oversized_reply_is_refused_before_parsing() -> None:
    small_request = LLMRequest(
        purpose="t", system_prompt="s", user_payload="{}", max_reply_chars=50
    )
    port = ScriptedLLM([VALID, VALID])
    outcome = call_structured(
        ApprovalGuard(port, approved=True), small_request, IntakeResult, max_attempts=2
    )
    assert outcome.status is CallStatus.INVALID_REPLY_EXHAUSTED
    assert outcome.errors == (f"reply is {len(VALID)} characters; the limit is 50",)


def test_failed_check_is_an_invalid_reply() -> None:
    outcome = call_structured(
        ApprovalGuard(ScriptedLLM([VALID] * 2), approved=True),
        REQUEST,
        IntakeResult,
        check=lambda reply: ["forced failure"],
        max_attempts=2,
    )
    assert outcome.status is CallStatus.INVALID_REPLY_EXHAUSTED
    assert outcome.errors == ("forced failure",)
    assert outcome.value is None


def test_scripted_adapter_with_no_reply_left_is_a_provider_error() -> None:
    outcome = call_structured(ApprovalGuard(ScriptedLLM([]), approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.PROVIDER_ERROR


def test_max_attempts_below_one_is_a_programming_error() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        call_structured(
            ApprovalGuard(ScriptedLLM([VALID]), approved=True),
            REQUEST,
            IntakeResult,
            max_attempts=0,
        )


def test_scripted_step_can_build_the_reply_from_the_request() -> None:
    port = ScriptedLLM([lambda request: VALID])
    outcome = call_structured(ApprovalGuard(port, approved=True), REQUEST, IntakeResult)
    assert outcome.status is CallStatus.SUCCESS
    assert port.calls[0] == REQUEST  # a fresh copy per attempt, equal in value
