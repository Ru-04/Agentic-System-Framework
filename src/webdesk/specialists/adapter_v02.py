"""WebDesk-to-AI-Engine adapter, contract version 0.2 (INT-01, approved 26 October 2026).

The adapter is the only entry point for an AI Engine specialist component. WebDesk stays the
authority for workspace, actor, allowed actions, evidence admission and audit. The adapter never
widens a permission, never approves a finding, and never enables a live model.

Every call goes through the existing shared harness (``run_specialist``), so the WebDesk contract
1.0.0 checks still apply. The adapter adds: its own versioned envelope, operator confirmation,
allowed-action checks, capability resolution, and error mapping.

Confidence: WebDesk has no confidence field. The adapter does not invent one. Every response
states ``confidence_status = "not_assessed"`` and carries no numeric value.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from webdesk.specialists.authority import FORBIDDEN_ACTIONS, Action
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.contract import CONTRACT_VERSION, EvidenceRef, NonBlank
from webdesk.specialists.errors import SpecialistError
from webdesk.specialists.harness import SpecialistProvider, run_specialist

ADAPTER_CONTRACT_VERSION: Final[Literal["0.2"]] = "0.2"

# Version label of AGENT_REGISTRY.yaml as read in this repository (header of the registry file).
REGISTRY_VERSION: Final[str] = "0.3.10-foundation-gate1-review"

CONFIDENCE_STATUS: Final[Literal["not_assessed"]] = "not_assessed"

ERROR_OPERATOR_CONFIRMATION_REQUIRED: Final[str] = "operator_confirmation_required"
ERROR_ACTION_FORBIDDEN: Final[str] = "action_forbidden"
ERROR_ACTION_UNKNOWN: Final[str] = "action_unknown"
ERROR_CAPABILITY_MISMATCH: Final[str] = "capability_mismatch"
ERROR_REQUEST_INVALID: Final[str] = "request_invalid"
# Every capability was refused by an authorization or source-boundary rule (SOURCE-REFUSAL-01).
ERROR_AUTHORIZATION_REFUSED: Final[str] = "authorization_refused"


class AdapterRequest(BaseModel):
    """Envelope WebDesk sends to the adapter. Unknown fields are refused."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_contract_version: Literal["0.2"]
    request_id: NonBlank
    workspace_id: NonBlank
    actor_id: NonBlank
    specialist_id: SpecialistId
    capability_id: NonBlank
    requirement_ids: tuple[NonBlank, ...] = Field(min_length=1)
    evidence_refs: tuple[EvidenceRef, ...] = ()
    task: NonBlank
    allowed_actions: tuple[NonBlank, ...] = Field(min_length=1)
    operator_confirmed: bool


class AdapterFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: NonBlank
    evidence_status: Literal["cited", "unverified"]
    evidence_refs: tuple[EvidenceRef, ...] = ()


class AdapterResponse(BaseModel):
    """Envelope the adapter returns. Findings are unverified proposals unless cited."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_contract_version: Literal["0.2"]
    specialist_contract_version: Literal["1.0.0"]
    request_id: NonBlank
    workspace_id: NonBlank
    specialist_id: SpecialistId
    capability_id: NonBlank
    registry_version: NonBlank
    status: Literal["completed", "incomplete", "failed"]
    findings: tuple[AdapterFinding, ...] = ()
    unknowns: tuple[NonBlank, ...] = ()
    error_code: str | None = None
    confidence: None = None
    confidence_status: Literal["not_assessed"] = CONFIDENCE_STATUS


def resolve_capability(specialist_id: SpecialistId, capability_id: str) -> str:
    """Return the canonical capability id, or raise ``ValueError`` if it does not match.

    The Shift4Shop legacy identifier is the canonical id in the catalog today, so no new alias
    is introduced. A change to the identifier needs WDS approval (migration is not authorized).
    """
    canonical = REGISTRY_CAPABILITY_IDS[specialist_id]
    if capability_id != canonical:
        raise ValueError(ERROR_CAPABILITY_MISMATCH)
    return canonical


def check_allowed_actions(
    allowed_actions: tuple[str, ...], provider_actions: frozenset[str]
) -> None:
    """Refuse forbidden or unknown actions, and any action the provider did not declare."""
    known = {action.value for action in Action}
    for action in allowed_actions:
        if action in FORBIDDEN_ACTIONS:
            raise ValueError(ERROR_ACTION_FORBIDDEN)
        if action not in known:
            raise ValueError(ERROR_ACTION_UNKNOWN)
        if action not in provider_actions:
            raise ValueError(ERROR_ACTION_FORBIDDEN)


def _refused(request: AdapterRequest, capability_id: str, error_code: str) -> AdapterResponse:
    return AdapterResponse(
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        specialist_contract_version=CONTRACT_VERSION,
        request_id=request.request_id,
        workspace_id=request.workspace_id,
        specialist_id=request.specialist_id,
        capability_id=capability_id,
        registry_version=REGISTRY_VERSION,
        status="failed",
        unknowns=(f"adapter refused the request: {error_code}",),
        error_code=error_code,
    )


def call_adapter(provider: SpecialistProvider, request: AdapterRequest) -> AdapterResponse:
    """Run one specialist through the adapter. Refusals and provider errors become responses."""
    if not request.operator_confirmed:
        return _refused(request, request.capability_id, ERROR_OPERATOR_CONFIRMATION_REQUIRED)
    try:
        capability_id = resolve_capability(request.specialist_id, request.capability_id)
    except ValueError:
        return _refused(request, request.capability_id, ERROR_CAPABILITY_MISMATCH)
    try:
        check_allowed_actions(request.allowed_actions, provider.declared_actions)
    except ValueError as exc:
        return _refused(request, capability_id, str(exc))

    raw_request: Mapping[str, object] = {
        "contract_version": CONTRACT_VERSION,
        "request_id": request.request_id,
        "workspace_id": request.workspace_id,
        "specialist_id": request.specialist_id.value,
        "requirement_ids": list(request.requirement_ids),
        "evidence_refs": [ref.model_dump() for ref in request.evidence_refs],
        "task": request.task,
    }
    try:
        output = run_specialist(provider, raw_request)
    except SpecialistError as exc:
        return _refused(request, capability_id, exc.code.value)
    except ValidationError:
        return _refused(request, capability_id, "request_invalid")

    findings = tuple(
        AdapterFinding(
            statement=finding.statement,
            evidence_status=finding.evidence_status.value,
            evidence_refs=finding.evidence_refs,
        )
        for finding in output.findings
    )
    return AdapterResponse(
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        specialist_contract_version=CONTRACT_VERSION,
        request_id=output.request_id,
        workspace_id=output.workspace_id,
        specialist_id=output.specialist_id,
        capability_id=capability_id,
        registry_version=REGISTRY_VERSION,
        status=output.status.value,
        findings=findings,
        unknowns=output.unknowns,
        error_code=(
            ERROR_AUTHORIZATION_REFUSED
            if output.status.value == "failed"
            and any(u.startswith("[REFUSE]") for u in output.unknowns)
            else None
        ),
    )


def audit_record(request: AdapterRequest, response: AdapterResponse) -> dict[str, str]:
    """Audit evidence without the task text or any evidence content.

    Only hashes and identifiers are kept, so restricted text is not copied into the log.
    """
    request_bytes = json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
    response_bytes = json.dumps(response.model_dump(mode="json"), sort_keys=True).encode()
    return {
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "request_id": request.request_id,
        "workspace_id": request.workspace_id,
        "actor_id": request.actor_id,
        "specialist_id": request.specialist_id.value,
        "capability_id": response.capability_id,
        "registry_version": REGISTRY_VERSION,
        "status": response.status,
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
    }
