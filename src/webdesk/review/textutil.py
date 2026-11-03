"""Exact-type text and collection checks for the Sprint 7 review models.

Every boundary accepts exact types only. A subclass of str, Decimal, datetime, or a duck-typed
stand-in for a model class is refused, because a subclass can override comparisons and defeat a
check that depends on them. Values are compared only after they have been reduced to exact types.

Two cleaners, with different purposes:
- clean_key: identifiers, references and reviewer identities. Format characters (zero-width spaces,
  joiners, byte-order marks) are removed everywhere, so an invisible character cannot make two
  references differ.
- clean_text: free text such as a requirement, reason, title or assumption. Format characters are
  kept inside the text (they are needed for emoji sequences and for Persian joiners) and removed
  only at the edges, where they would make an empty value look non-empty.

Both refuse lone surrogates, because such text cannot be encoded for export.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from enum import StrEnum
from typing import Any, TypeVar

_T = TypeVar("_T")
_E = TypeVar("_E", bound=StrEnum)


def _trim(text: str) -> str:
    start, end = 0, len(text)
    while start < end and _is_edge_noise(text[start]):
        start += 1
    while end > start and _is_edge_noise(text[end - 1]):
        end -= 1
    return text[start:end]


def _is_edge_noise(char: str) -> bool:
    return char.isspace() or unicodedata.category(char) == "Cf"


def _checked(text: str, message: str) -> str:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(message) from error
    return text


def clean_key(value: object, message: str) -> str:
    """Return a cleaned identifier. Invisible format characters are removed everywhere."""
    if type(value) is not str:
        raise ValueError(message)
    normalised = unicodedata.normalize("NFKC", value)
    visible = "".join(char for char in normalised if unicodedata.category(char) != "Cf")
    stripped = _trim(visible)
    if not stripped:
        raise ValueError(message)
    return _checked(stripped, message)


def clean_text(value: object, message: str) -> str:
    """Return cleaned free text. Invisible characters inside the text are kept."""
    if type(value) is not str:
        raise ValueError(message)
    stripped = _trim(unicodedata.normalize("NFKC", value))
    if not stripped:
        raise ValueError(message)
    return _checked(stripped, message)


def exact(value: object, cls: type[_T], message: str) -> _T:
    """Return ``value`` only when its type is exactly ``cls`` (no subclass, no duck type)."""
    if type(value) is not cls:
        raise ValueError(message)
    return value


def enum_of(value: object, cls: type[_E], message: str) -> _E:
    """Return the enum member for an exact member or an exact str value; refuse anything else."""
    if type(value) is cls:
        return value
    if type(value) is str:
        try:
            return cls(str(value))
        except ValueError as error:
            raise ValueError(message) from error
    raise ValueError(message)


def items_of(values: object, cls: type[_T], message: str) -> tuple[_T, ...]:
    """Copy a collection into a tuple of exact ``cls`` items. A string is refused."""
    items = _collect(values, message)
    if not all(type(item) is cls for item in items):
        raise ValueError(message)
    return items


def text_items(values: object, message: str) -> tuple[str, ...]:
    """Copy a collection of exact str into a tuple. A bare string is refused."""
    items = _collect(values, message)
    if not all(type(item) is str for item in items):
        raise ValueError(message)
    return items


def _collect(values: object, message: str) -> tuple[Any, ...]:
    # A string is an iterable of characters, so it is refused as a collection. A generator that
    # raises partway is reported as a ValueError, not as the raw exception.
    if isinstance(values, str | bytes) or not isinstance(values, Iterable):
        raise ValueError(message)
    try:
        return tuple(values)
    except Exception as error:
        raise ValueError(message) from error
