"""Source records with provenance, and freshness assessment (M1 S2).

Every piece of evidence the specialists read is a SourceRecord. It carries where it came from, when
it was retrieved, which workspace owns it, and a SHA-256 of its text. Citations are checked against
that hash, so a changed or substituted source cannot be cited as if it were the original.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from webdesk.evidence.allowlist import PROPOSED_SHOPIFY_ALLOWLIST

VENDOR_ALLOWLIST = PROPOSED_SHOPIFY_ALLOWLIST
INTERNAL_ORIGIN_PREFIX = "internal:"


class SourceKind(StrEnum):
    INTERNAL_RAG = "internal_rag"
    VENDOR_DOC = "vendor_doc"


class Freshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    kind: SourceKind
    workspace_id: str
    origin: str
    title: str
    text: str
    retrieved_at: datetime
    version: str | None = None

    def __post_init__(self) -> None:
        for name in ("source_id", "workspace_id", "origin", "title"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be blank")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")
        # Approved-source rule (proposal P1, approved 22 October 2026): the origin itself decides
        # whether a record may be treated as approved evidence, whatever retriever built it.
        if self.kind is SourceKind.VENDOR_DOC:
            if not VENDOR_ALLOWLIST.permits(self.origin):
                raise ValueError("vendor origin is not on the approved vendor allowlist")
        else:
            identifier = self.origin[len(INTERNAL_ORIGIN_PREFIX) :]
            if not self.origin.startswith(INTERNAL_ORIGIN_PREFIX) or not identifier.strip():
                raise ValueError("internal origin must use the internal: scheme and an identifier")

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def assess_freshness(source: SourceRecord, now: datetime, max_age: timedelta) -> Freshness:
    # A naive clock cannot be compared safely, so freshness cannot be established.
    if now.tzinfo is None:
        return Freshness.UNKNOWN
    # A record dated after "now" means the clock or the record is wrong. It is not treated as fresh.
    if source.retrieved_at > now:
        return Freshness.UNKNOWN
    if now - source.retrieved_at > max_age:
        return Freshness.STALE
    return Freshness.FRESH
