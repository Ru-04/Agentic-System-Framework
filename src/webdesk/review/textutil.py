"""Shared text checks for the Sprint 7 review models.

Identifiers and reviewer text are cleaned before they are compared or stored. Cleaning applies NFKC
normalisation, removes format characters (zero-width spaces and joiners) and trims whitespace, so
that an invisible character cannot make two references differ. Collections of text must be real
sequences of text: a bare string is refused, because iterating it would split it into characters.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable


def clean(value: object, message: str) -> str:
    """Return the cleaned text, or raise ValueError with ``message`` if nothing is left."""
    if not isinstance(value, str):
        raise ValueError(message)
    normalised = unicodedata.normalize("NFKC", value)
    visible = "".join(char for char in normalised if unicodedata.category(char) != "Cf")
    stripped = visible.strip()
    if not stripped:
        raise ValueError(message)
    return stripped


def text_tuple(values: object, message: str) -> tuple[str, ...]:
    """Copy a collection of text into a tuple. A bare string or non-text item is refused."""
    if isinstance(values, str) or not isinstance(values, Iterable):
        raise ValueError(message)
    items = tuple(values)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(message)
    return items
