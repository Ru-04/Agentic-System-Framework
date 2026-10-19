"""Domain refusals known to the HTTP layer and the transaction runner (C-1, C-2).

Kept in their own module so the app, the routes and the transaction runner can each import it
without importing one another.
"""

from __future__ import annotations

from typing import Any

from webdesk.auth.service import AuthError
from webdesk.ceremony.install import InstallationError
from webdesk.ceremony.recovery import RecoveryError
from webdesk.idempotency.service import IdempotencyError
from webdesk.identity.contacts import ContactServiceError
from webdesk.intake.ingest import IngestError
from webdesk.intake.reparse import ReparseError
from webdesk.projects.service import ProjectServiceError
from webdesk.rbac.assign import RoleServiceError
from webdesk.runs.errors import RunError
from webdesk.tokens.service import TokenError

NEUTRAL_REASONS = (AuthError, TokenError)
DOMAIN_ERRORS: tuple[type[Exception], ...] = (
    ContactServiceError,
    ProjectServiceError,
    RoleServiceError,
    IdempotencyError,
    RecoveryError,
    AuthError,
    TokenError,
    InstallationError,
    IngestError,
    RunError,
    ReparseError,
)


def body_for(exc: Any) -> dict[str, str]:
    if isinstance(exc, NEUTRAL_REASONS):
        return {"error": "request_refused"}
    return {"error": str(exc.reason)}


def status_for(exc: Any) -> int:
    if isinstance(exc, AuthError):
        return 401
    if isinstance(exc, TokenError):
        return 400
    return int(getattr(exc, "status", 409))
