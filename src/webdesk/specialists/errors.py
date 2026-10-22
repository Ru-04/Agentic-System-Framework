"""Specialist error model (M1 S1).

Every refusal or failure in the specialist harness carries one of these codes. Only provider
failures are retryable here; retry policy beyond that belongs to the orchestrator (M3 S6).
"""

from __future__ import annotations

from enum import StrEnum


class SpecialistErrorCode(StrEnum):
    CONTRACT_VERSION_UNSUPPORTED = "contract_version_unsupported"
    INPUT_INVALID = "input_invalid"
    OUTPUT_INVALID = "output_invalid"
    SPECIALIST_MISMATCH = "specialist_mismatch"
    WORKSPACE_MISMATCH = "workspace_mismatch"
    CAPABILITY_DENIED = "capability_denied"
    PROVIDER_FAILURE = "provider_failure"


RETRYABLE_CODES = frozenset({SpecialistErrorCode.PROVIDER_FAILURE})


class SpecialistError(Exception):
    def __init__(self, code: SpecialistErrorCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE_CODES
