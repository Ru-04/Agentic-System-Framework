"""Workspace isolation for specialist traffic (M1 S1).

A specialist works inside one workspace. Every evidence reference it reads and every finding it
returns must belong to that workspace. A mismatch is refused, and the refusal does not name the
other workspace.
"""

from __future__ import annotations

from webdesk.specialists.errors import SpecialistError, SpecialistErrorCode


def check_workspace(expected_workspace_id: str, actual_workspace_id: str, subject: str) -> None:
    if actual_workspace_id != expected_workspace_id:
        raise SpecialistError(
            SpecialistErrorCode.WORKSPACE_MISMATCH,
            f"{subject} is outside the request workspace",
        )
