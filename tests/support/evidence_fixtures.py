"""Test-only construction of evidence fixtures (proposal P1, approved 22 October 2026).

Production code must build SourceRecord through its constructor, which enforces the approved-source
rule on the origin. Fixture records use ``fixture://`` origins and are labelled FIXTURE in their
text. They are built here, and only tests may import this module. This is a convention and a guard
against accidents, not a security boundary against code that deliberately bypasses it.
"""

from __future__ import annotations

from typing import Any

from webdesk.evidence.sources import SourceRecord


def fixture_source(**fields: Any) -> SourceRecord:
    record = object.__new__(SourceRecord)
    for name, value in fields.items():
        object.__setattr__(record, name, value)
    return record
