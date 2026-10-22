"""Shared specialist harness: the single path every specialist call takes (M1 S1).

``run_specialist`` validates the request, checks authority and workspace scope, runs the provider,
then validates the response. A provider never reaches the orchestrator unvalidated, and the
harness never returns a response that breaks the contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import ValidationError

from webdesk.specialists.authority import check_actions
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import (
    CONTRACT_VERSION,
    SpecialistInput,
    SpecialistOutput,
)
from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode
from webdesk.specialists.workspace import check_workspace


class SpecialistProvider(Protocol):
    @property
    def specialist_id(self) -> SpecialistId: ...

    @property
    def declared_actions(self) -> frozenset[str]: ...

    def run(self, request: SpecialistInput) -> Mapping[str, object]: ...


def run_specialist(
    provider: SpecialistProvider, raw_request: Mapping[str, object]
) -> SpecialistOutput:
    version = raw_request.get("contract_version")
    if version != CONTRACT_VERSION:
        raise SpecialistError(
            SpecialistErrorCode.CONTRACT_VERSION_UNSUPPORTED,
            f"contract version {version!r} is not supported",
        )
    try:
        request = SpecialistInput.model_validate(raw_request)
    except ValidationError as exc:
        raise SpecialistError(
            SpecialistErrorCode.INPUT_INVALID,
            f"{exc.error_count()} request field error(s)",
        ) from exc
    if request.specialist_id != provider.specialist_id:
        raise SpecialistError(
            SpecialistErrorCode.SPECIALIST_MISMATCH,
            f"request is for {request.specialist_id.value}, provider is "
            f"{provider.specialist_id.value}",
        )
    check_actions(provider.specialist_id, provider.declared_actions)
    for ref in request.evidence_refs:
        check_workspace(request.workspace_id, ref.workspace_id, "evidence reference")

    try:
        raw_output = provider.run(request)
    except SpecialistError:
        raise
    except Exception as exc:
        raise SpecialistError(
            SpecialistErrorCode.PROVIDER_FAILURE,
            f"provider raised {type(exc).__name__}",
        ) from exc

    try:
        output = SpecialistOutput.model_validate(raw_output)
    except ValidationError as exc:
        raise SpecialistError(
            SpecialistErrorCode.OUTPUT_INVALID,
            f"{exc.error_count()} output field error(s)",
        ) from exc
    if output.request_id != request.request_id or output.specialist_id != request.specialist_id:
        raise SpecialistError(
            SpecialistErrorCode.OUTPUT_INVALID,
            "output does not echo the request identity",
        )
    check_workspace(request.workspace_id, output.workspace_id, "output")
    for finding in output.findings:
        for ref in finding.evidence_refs:
            check_workspace(request.workspace_id, ref.workspace_id, "finding evidence")
    return output
