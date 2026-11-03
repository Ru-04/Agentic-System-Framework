"""WebDesk-to-AI-Engine adapter, contract version 0.3 (Sprint 6, contract section 6.3, OPEN-03).

Adapter 0.3 is a breaking change to 0.2. Version 0.2 stays as built for the isolated synthetic
slice (D-3), and it is not imported here except for the shared capability and action checks.

What changed from 0.2:
- The request has no ``actor_id`` and no ``operator_confirmed``. Foundation sets both. The actor is
  derived from the authenticated proof and reaches the harness only through the verifier.
- The request carries ``confirmation_ref``, an opaque single-use reference issued by Foundation.
  The adapter refuses unless the injected ``ConfirmationVerifier`` verifies it for the exact
  binding of this envelope. The default verifier, ``RefuseAllConfirmations``, refuses everything.
- Every finding carries a ``check_outcome`` (OPEN-08). A citation count alone is never SUPPORTED.
- A refusal is an explicit ``error`` object, not a free-text unknown.
- Version handling is strict: any other ``adapter_contract_version`` is refused, with no fallback.

The adapter never widens a permission, never approves a finding, and never enables a live model.
Every call goes through the shared harness (``run_specialist``).

Confidence: WebDesk has no confidence field. Every response states ``confidence_status
= "not_assessed"`` and carries no numeric value.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Final, Literal, Protocol
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)

from webdesk.specialists.adapter_v02 import (
    ERROR_AUTHORIZATION_REFUSED,
    ERROR_CAPABILITY_MISMATCH,
    ERROR_REQUEST_INVALID,
    check_allowed_actions,
    resolve_capability,
)
from webdesk.specialists.catalog import SpecialistId
from webdesk.specialists.contract import CONTRACT_VERSION, EvidenceRef, NonBlank
from webdesk.specialists.errors import SpecialistError
from webdesk.specialists.harness import SpecialistProvider, run_specialist

ADAPTER_CONTRACT_VERSION: Final[Literal["0.3"]] = "0.3"

# Version label of AGENT_REGISTRY.yaml as read in this repository (header of the registry file).
REGISTRY_VERSION: Final[str] = "0.3.10-foundation-gate1-review"

CONFIDENCE_STATUS: Final[Literal["not_assessed"]] = "not_assessed"

ERROR_VERSION_UNSUPPORTED: Final[str] = "adapter_version_unsupported"
ERROR_CONFIRMATION_NOT_VERIFIED: Final[str] = "confirmation_not_verified"


class CheckOutcome(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


REQUIREMENT_REF_PATTERN: Final[str] = r"^REQ-[0-9]{3,}$"

RequirementRef = Annotated[str, StringConstraints(pattern=REQUIREMENT_REF_PATTERN)]


class AdapterRequest(BaseModel):
    """Envelope WebDesk sends to the adapter. Unknown fields are refused, including actor fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_contract_version: Literal["0.3"]
    request_id: NonBlank
    workspace_id: NonBlank
    run_id: UUID
    project_id: UUID
    specialist_id: SpecialistId
    capability_id: NonBlank
    # Run-scoped requirement references: each is REQ-NNN, and the run is run_id (contract 7).
    requirement_refs: tuple[RequirementRef, ...] = Field(min_length=1)
    evidence_refs: tuple[EvidenceRef, ...] = ()
    task: NonBlank
    allowed_actions: tuple[NonBlank, ...] = Field(min_length=1)
    confirmation_ref: NonBlank


class AdapterFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement: NonBlank
    evidence_status: Literal["cited", "unverified"]
    check_outcome: CheckOutcome
    evidence_refs: tuple[EvidenceRef, ...] = ()


class AdapterError(BaseModel):
    """Explicit refusal. The code is a fixed adapter or harness code, never caller text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: NonBlank


class AdapterResponse(BaseModel):
    """Envelope the adapter returns. Findings are unverified proposals unless cited and checked."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_contract_version: Literal["0.3"]
    specialist_contract_version: Literal["1.0.0"]
    request_id: NonBlank
    workspace_id: NonBlank
    specialist_id: SpecialistId
    capability_id: NonBlank
    registry_version: NonBlank
    status: Literal["completed", "incomplete", "failed"]
    findings: tuple[AdapterFinding, ...] = ()
    unknowns: tuple[NonBlank, ...] = ()
    error: AdapterError | None = None
    confidence: None = None
    confidence_status: Literal["not_assessed"] = CONFIDENCE_STATUS

    @model_validator(mode="after")
    def _error_means_failed(self) -> AdapterResponse:
        if self.error is not None and self.status != "failed":
            raise ValueError("a response with an error must have status failed")
        return self


@dataclass(frozen=True)
class ConfirmationBinding:
    """The exact tuple a Foundation confirmation must cover (contract section 6.3)."""

    run_id: UUID
    project_id: UUID
    specialist_id: SpecialistId
    capability_id: str
    requirement_refs_digest: str
    allowed_actions_digest: str


@dataclass(frozen=True)
class VerifiedConfirmation:
    """A successful verification. ``actor_ref`` comes from the proof, never the envelope."""

    actor_ref: str


class ConfirmationVerifier(Protocol):
    """Foundation-side check of a confirmation reference against an exact binding.

    Return a ``VerifiedConfirmation`` only when the reference is valid, unexpired, unconsumed and
    issued for this binding. Return ``None`` to refuse. Any exception is treated as a refusal.
    """

    def verify(
        self, confirmation_ref: str, binding: ConfirmationBinding
    ) -> VerifiedConfirmation | None: ...


class RefuseAllConfirmations:
    """Fail-closed default. With no Foundation verifier wired in, no specialist runs."""

    def verify(
        self, confirmation_ref: str, binding: ConfirmationBinding
    ) -> VerifiedConfirmation | None:
        return None


@dataclass(frozen=True)
class CitationAssessment:
    """One citation's check against one claim, made by the check step (OPEN-08, AI Engine)."""

    # Provenance and quote checks passed (OPEN-14).
    verified: bool
    # The passage's platform, version and edition apply to the claim.
    applicable: bool
    # The passage addresses the claim's specific subject, platform and edition.
    substantiates: bool
    # The passage establishes a limitation or unsupported behaviour for the claim.
    limits: bool


class ClaimAssessor(Protocol):
    def assess(
        self, statement: str, evidence_refs: tuple[EvidenceRef, ...]
    ) -> Sequence[CitationAssessment]: ...


class AdapterRequestError(ValueError):
    """The envelope could not be accepted. Carries a fixed code, never the rejected values."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# OPEN-07. Explicit table from the adapter evidence vocabulary to the AI Engine EvidenceStatus
# vocabulary (B-CMN). Every adapter value has its own entry. The mapping is documented many-to-one:
# ``cited`` and ``unverified`` both map to AI ``unverified``. ``cited`` never maps to ``verified``,
# because the citation check is carried by ``check_outcome``. Any value not listed here raises
# ``UnmappedValueError``; nothing is collapsed silently.
AiEvidenceStatus = Literal[
    "verified", "partially_verified", "unverified", "conflicting", "not_applicable"
]

EVIDENCE_STATUS_TO_AI: Final[Mapping[str, AiEvidenceStatus]] = MappingProxyType(
    {
        "cited": "unverified",
        "unverified": "unverified",
    }
)


class UnmappedValueError(ValueError):
    """A vocabulary value has no entry in the mapping table. Values are never collapsed silently."""


def map_evidence_status(adapter_value: str) -> AiEvidenceStatus:
    try:
        return EVIDENCE_STATUS_TO_AI[adapter_value]
    except KeyError:
        raise UnmappedValueError(
            f"no AI evidence status mapping for adapter value {adapter_value!r}"
        ) from None


def check_outcome(assessments: Sequence[CitationAssessment]) -> CheckOutcome:
    """Derive the outcome for one claim (OPEN-08).

    SUPPORTED needs at least one applicable, verified citation that substantiates the claim. A
    count of citations is not evidence of support. Applicable, verified citations that establish a
    limitation give UNSUPPORTED. Both kinds at once are contradictory, and anything else (no
    usable evidence, or none that substantiates) is UNKNOWN.
    """
    usable = [a for a in assessments if a.verified and a.applicable]
    supports = any(a.substantiates for a in usable)
    limits = any(a.limits for a in usable)
    if supports and limits:
        return CheckOutcome.UNKNOWN
    if limits:
        return CheckOutcome.UNSUPPORTED
    if supports:
        return CheckOutcome.SUPPORTED
    return CheckOutcome.UNKNOWN


def _digest(values: Sequence[str]) -> str:
    # Contract v1.1 encoding: SHA-256 hex of the sorted unique JSON array, compact separators.
    canonical = json.dumps(
        sorted(set(values)), separators=(",", ":"), sort_keys=True, ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def binding_for(request: AdapterRequest) -> ConfirmationBinding:
    return ConfirmationBinding(
        run_id=request.run_id,
        project_id=request.project_id,
        specialist_id=request.specialist_id,
        capability_id=request.capability_id,
        requirement_refs_digest=_digest(request.requirement_refs),
        allowed_actions_digest=_digest(request.allowed_actions),
    )


def parse_request(raw: Mapping[str, object]) -> AdapterRequest:
    """Accept one envelope or refuse it. No other adapter version is ever parsed as 0.3."""
    if not isinstance(raw, Mapping):
        raise AdapterRequestError(ERROR_REQUEST_INVALID)
    if raw.get("adapter_contract_version") != ADAPTER_CONTRACT_VERSION:
        raise AdapterRequestError(ERROR_VERSION_UNSUPPORTED)
    try:
        return AdapterRequest.model_validate(raw)
    except ValidationError:
        raise AdapterRequestError(ERROR_REQUEST_INVALID) from None


def _refused(request: AdapterRequest, capability_id: str, code: str) -> AdapterResponse:
    return AdapterResponse(
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        specialist_contract_version=CONTRACT_VERSION,
        request_id=request.request_id,
        workspace_id=request.workspace_id,
        specialist_id=request.specialist_id,
        capability_id=capability_id,
        registry_version=REGISTRY_VERSION,
        status="failed",
        unknowns=(f"adapter refused the request: {code}",),
        error=AdapterError(code=code),
    )


def _finding_outcome(
    finding_status: str,
    statement: str,
    evidence_refs: tuple[EvidenceRef, ...],
    assessor: ClaimAssessor | None,
) -> CheckOutcome:
    # Without an assessor, no check has been made, so the outcome is UNKNOWN. A finding that is not
    # cited has no verified evidence to check, so it is UNKNOWN whatever the assessor says.
    if assessor is None or finding_status != "cited":
        return CheckOutcome.UNKNOWN
    return check_outcome(tuple(assessor.assess(statement, evidence_refs)))


def call_adapter(
    provider: SpecialistProvider,
    request: AdapterRequest,
    verifier: ConfirmationVerifier,
    assessor: ClaimAssessor | None = None,
) -> tuple[AdapterResponse, VerifiedConfirmation | None]:
    """Run one specialist through the adapter. Every refusal happens before the provider runs.

    The verifier is called exactly once, because a Foundation confirmation is single-use. The
    verified actor is returned alongside the response, for the audit record only.
    """
    try:
        verified = verifier.verify(request.confirmation_ref, binding_for(request))
    except Exception:
        # The verifier's own error text is not echoed. An unverifiable confirmation is a refusal.
        verified = None
    if verified is None:
        refusal = _refused(request, request.capability_id, ERROR_CONFIRMATION_NOT_VERIFIED)
        return refusal, None
    # The actor is returned for the audit record only. It never reaches the harness.
    return _run_verified(provider, request, assessor), verified


def _run_verified(
    provider: SpecialistProvider, request: AdapterRequest, assessor: ClaimAssessor | None
) -> AdapterResponse:
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
        "requirement_ids": list(request.requirement_refs),
        "evidence_refs": [ref.model_dump() for ref in request.evidence_refs],
        "task": request.task,
    }
    try:
        output = run_specialist(provider, raw_request)
    except SpecialistError as exc:
        return _refused(request, capability_id, exc.code.value)
    except ValidationError:
        return _refused(request, capability_id, ERROR_REQUEST_INVALID)

    findings = tuple(
        AdapterFinding(
            statement=finding.statement,
            evidence_status=finding.evidence_status.value,
            check_outcome=_finding_outcome(
                finding.evidence_status.value, finding.statement, finding.evidence_refs, assessor
            ),
            evidence_refs=finding.evidence_refs,
        )
        for finding in output.findings
    )
    refused_by_source = output.status.value == "failed" and any(
        u.startswith("[REFUSE]") for u in output.unknowns
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
        error=AdapterError(code=ERROR_AUTHORIZATION_REFUSED) if refused_by_source else None,
    )


def audit_record(
    request: AdapterRequest, response: AdapterResponse, verified: VerifiedConfirmation | None
) -> dict[str, str | None]:
    """Audit evidence without the task text or any evidence content.

    The actor comes from the verified confirmation, never from the envelope; a refusal before
    verification has no actor. Only hashes and identifiers are kept, so restricted text is not
    copied into the log.
    """
    request_bytes = json.dumps(request.model_dump(mode="json"), sort_keys=True).encode()
    response_bytes = json.dumps(response.model_dump(mode="json"), sort_keys=True).encode()
    return {
        "adapter_contract_version": ADAPTER_CONTRACT_VERSION,
        "request_id": request.request_id,
        "workspace_id": request.workspace_id,
        "run_id": str(request.run_id),
        "project_id": str(request.project_id),
        "actor_ref": None if verified is None else verified.actor_ref,
        "specialist_id": request.specialist_id.value,
        "capability_id": response.capability_id,
        "registry_version": REGISTRY_VERSION,
        "status": response.status,
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
    }
