"""Exit mapping for database errors in the Phase 6 CLIs (H-50, H-51).

A permission denial is a refusal (status 2) that the operator must fix, not an outage. Anything
else is reported as an unavailable database (status 3).
"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError

INSUFFICIENT_PRIVILEGE = "42501"


def database_refusal(exc: SQLAlchemyError) -> tuple[str, int]:
    """Return the message and exit status for a database error."""
    if getattr(getattr(exc, "orig", None), "sqlstate", None) == INSUFFICIENT_PRIVILEGE:
        return "refused: insufficient_privilege", 2
    return "refused: database_unavailable", 3
