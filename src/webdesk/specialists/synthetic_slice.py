"""Deterministic, test-only vertical slice through the adapter (INT-02, approved 26 October 2026).

This is NOT platform verification. The provider below returns fixed, honest "no evidence" output
for the synthetic fixture. It cites nothing and asserts no capability. It exists to exercise the
adapter path end to end. No live model, no retrieval and no real client data are involved.

Production integration is blocked until the QA-07 runtime authorization restriction is met
(M3 Sprint 6). This slice is the controlled test harness only.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from webdesk.specialists.adapter_v02 import (
    ADAPTER_CONTRACT_VERSION,
    AdapterRequest,
    AdapterResponse,
    audit_record,
    call_adapter,
)
from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.contract import SpecialistInput

FIXTURE_PATH: Final[Path] = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "governance"
    / "fixtures"
    / "synthetic_vertical_slice_fixture.json"
)

# Labels used in the synthetic unknowns. Only the Shopify label is needed by the fixture.
_LABELS: Final[dict[SpecialistId, str]] = {SpecialistId.SHOPIFY: "Shopify"}

_SLICE_ACTIONS: Final[frozenset[str]] = frozenset(
    {"read_evidence", "propose_candidates", "declare_unknowns"}
)


class SyntheticSliceProvider:
    """Deterministic test-only specialist. Returns no findings and no citations."""

    declared_actions: frozenset[str] = _SLICE_ACTIONS

    def __init__(self, specialist_id: SpecialistId) -> None:
        self._specialist_id = specialist_id

    @property
    def specialist_id(self) -> SpecialistId:
        return self._specialist_id

    def run(self, request: SpecialistInput) -> Mapping[str, object]:
        label = _LABELS.get(self._specialist_id, self._specialist_id.value)
        return {
            "contract_version": "1.0.0",
            "request_id": request.request_id,
            "workspace_id": request.workspace_id,
            "specialist_id": self._specialist_id.value,
            "status": "incomplete",
            "findings": [],
            "unknowns": [
                f"no approved evidence source is configured for {label}; "
                "no retrieval was attempted",
                "feasibility is not determined",
                "CLARIFY: confirm the platform plan or edition and the store setup "
                "this requirement assumes",
            ],
        }


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, object]:
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("fixture must be a JSON object")
    return loaded


def build_request(fixture: Mapping[str, object], *, operator_confirmed: bool) -> AdapterRequest:
    """Build the adapter envelope from the synthetic fixture and the operator's confirmation."""
    raw_request = fixture["request"]
    if not isinstance(raw_request, dict):
        raise ValueError("fixture request must be a JSON object")
    specialist_id = SpecialistId(str(raw_request["specialist_id"]))
    return AdapterRequest(
        adapter_contract_version=ADAPTER_CONTRACT_VERSION,
        request_id=str(raw_request["request_id"]),
        workspace_id=str(raw_request["workspace_id"]),
        actor_id=str(raw_request["actor_id"]),
        specialist_id=specialist_id,
        capability_id=REGISTRY_CAPABILITY_IDS[specialist_id],
        requirement_ids=tuple(str(item) for item in raw_request["requirement_ids"]),
        evidence_refs=(),
        task=str(raw_request["task"]),
        allowed_actions=tuple(str(item) for item in raw_request["allowed_actions"]),
        operator_confirmed=operator_confirmed,
    )


def run_slice(
    fixture: Mapping[str, object], *, operator_confirmed: bool
) -> tuple[AdapterResponse, dict[str, str]]:
    """Run the synthetic slice. Returns the normalized response and the audit record."""
    request = build_request(fixture, operator_confirmed=operator_confirmed)
    provider = SyntheticSliceProvider(request.specialist_id)
    response = call_adapter(provider, request)
    return response, audit_record(request, response)
