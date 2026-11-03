"""Shared specialist architecture: contract, errors, authority, workspace scope and harness."""

from webdesk.specialists.catalog import REGISTRY_CAPABILITY_IDS, SpecialistId
from webdesk.specialists.contract import CONTRACT_VERSION, SpecialistInput, SpecialistOutput
from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode
from webdesk.specialists.harness import SpecialistProvider, run_specialist
from webdesk.specialists.mock import MockSpecialist

__all__ = [
    "CONTRACT_VERSION",
    "REGISTRY_CAPABILITY_IDS",
    "MockSpecialist",
    "SpecialistError",
    "SpecialistErrorCode",
    "SpecialistId",
    "SpecialistInput",
    "SpecialistOutput",
    "SpecialistProvider",
    "run_specialist",
]
