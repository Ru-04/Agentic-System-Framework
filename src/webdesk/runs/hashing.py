"""Input revision hash for runs and derived records (I-10; I-13 part; ARCH §7 F-10).

SHA-256 over RFC 8785 canonical JSON of ``{"config_versions": ..., "inputs": [...]}``.
The inputs are
``{entity_type, entity_id, revision}`` tuples sorted ascending by UTF-8 bytes of (entity_type,
entity_id), with the integer revision as the final tiebreak. Each entity appears once.
The golden digest test lives with the staleness work in I-13.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import rfc8785

from webdesk.intake.parsers import EXTRACTION_VERSION, PARSER_LIBRARY_VERSION


@dataclass(frozen=True)
class InputTuple:
    entity_type: str
    entity_id: str
    revision: int


def input_revision_hash(
    inputs: Iterable[InputTuple],
    config_versions: dict[str, str] | None = None,
) -> str:
    ordered = sorted(
        inputs,
        key=lambda t: (t.entity_type.encode("utf-8"), t.entity_id.encode("utf-8"), t.revision),
    )
    seen: set[tuple[str, str]] = set()
    body: list[dict[str, object]] = []
    for item in ordered:
        key = (item.entity_type, item.entity_id)
        if key in seen:
            raise ValueError("each entity may appear once in the input set")
        seen.add(key)
        body.append(
            {
                "entity_type": item.entity_type,
                "entity_id": item.entity_id,
                "revision": item.revision,
            }
        )
    config: dict[str, str] = config_versions or {
        "extraction_version": EXTRACTION_VERSION,
        "parser_library_version": PARSER_LIBRARY_VERSION,
    }
    document: Any = {"config_versions": config, "inputs": body}
    return hashlib.sha256(rfc8785.dumps(document)).hexdigest()


def version_tuple(source_version_id: uuid.UUID, revision: int) -> InputTuple:
    return InputTuple("SourceVersion", str(source_version_id), revision)
