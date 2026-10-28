"""Enforcement-point detection for AI-S10 scenarios.

A protective refusal is only evidence of a control if it was raised by the control itself. This
module finds the innermost declared enforcement point for a refusal, so a scenario can assert
that the refusal came from the component it claims to test. A refusal from an unrelated
validation layer gets a different name (or None), and the runner then fails the scenario.

Two kinds of point are recognised:

- a Python function on the traceback, for example ``consume`` or ``verify_confirmation``;
- a pydantic contract model, for ``ValidationError``, identified by the error's ``title``. The title
  is the name of the model whose validation refused the input.
"""

from __future__ import annotations

import traceback
from collections.abc import Iterable

from pydantic import ValidationError


def enforced_by(error: BaseException, points: Iterable[str]) -> str | None:
    """Return the innermost declared enforcement point that refused ``error``, else None."""
    wanted = frozenset(points)
    found: str | None = None
    for frame in traceback.extract_tb(error.__traceback__):
        if frame.name in wanted:
            found = frame.name
    if found is None and isinstance(error, ValidationError) and error.title in wanted:
        found = error.title
    return found
