"""
Synthetic placeholder evidence for the AI-S05 standalone and middleware specialists.

Nothing here is vendor, framework or platform documentation. Every record is a SYNTHETIC_MOCK
placeholder, so each one is ``unverified`` by contract and names no publisher. Contradictions are a
test-fixture ``conflict_group`` beside each record, not text inside the evidence. Stale records are
dated well before the staleness window, so the investigation can report them.

Each record is also tagged with the topic phrases it bears on. The specialist cites a record for a
topic only when that tag is present. Matching by word substring is not enough: a record can contain
a search word and still be about something else.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from ai_engine.contracts.common import EvidenceStatus
from ai_engine.contracts.evidence import EvidenceKind, EvidenceReference
from ai_engine.evidence.lookup import CollectedEvidence

STANDALONE_EVIDENCE_COLLECTION = "standalone_synthetic_patterns"
MIDDLEWARE_EVIDENCE_COLLECTION = "middleware_synthetic_patterns"
AUTH_CONFLICT_GROUP = "synthetic-application-auth-model"
SYNC_CONFLICT_GROUP = "synthetic-sync-direction"
_CHECKED_AT = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
_STALE_CHECKED_AT = datetime(2019, 1, 1, tzinfo=UTC)

_LIMITATION = (
    "Synthetic placeholder; not vendor, framework or platform documentation and not checked."
)

# (evidence_id, summary, conflict_group, checked_at). Each summary carries its topic term.
_Record = tuple[str, str, str | None, datetime]

_STANDALONE: tuple[_Record, ...] = (
    (
        "EVD-STD-SYN-0001",
        "Synthetic placeholder: an existing application may meet the requirement through "
        "configuration rather than custom code.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0002",
        "Synthetic placeholder: a custom application may need a separate frontend and backend "
        "deployment.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0003",
        "Synthetic placeholder: login may use an identity provider; the authentication model is "
        "not decided.",
        AUTH_CONFLICT_GROUP,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0004",
        "Synthetic placeholder: login may use the framework's built-in authentication only.",
        AUTH_CONFLICT_GROUP,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0005",
        "Synthetic placeholder: a database schema needs migration tooling for each change to the "
        "data model.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0006",
        "Synthetic placeholder: external API calls need timeouts and bounded retries.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0007",
        "Synthetic placeholder: hosting and deployment choices depend on the scalability and "
        "availability target.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-STD-SYN-0008",
        "Synthetic placeholder: a security baseline for application hosting, dated before the "
        "staleness window.",
        None,
        _STALE_CHECKED_AT,
    ),
)

_MIDDLEWARE: tuple[_Record, ...] = (
    (
        "EVD-MID-SYN-0001",
        "Synthetic placeholder: webhooks and events may be delivered more than once and need "
        "idempotent handlers.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0002",
        "Synthetic placeholder: retries need an idempotency key on every write to the target.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0003",
        "Synthetic placeholder: synchronisation direction may be one-way or bidirectional, and "
        "conflicts need a rule.",
        SYNC_CONFLICT_GROUP,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0004",
        "Synthetic placeholder: synchronisation may be one-way only, with the source system as "
        "owner.",
        SYNC_CONFLICT_GROUP,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0005",
        "Synthetic placeholder: API rate limits may throttle bulk synchronisation.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0006",
        "Synthetic placeholder: field mapping and transformation need a documented schema.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0007",
        "Synthetic placeholder: credentials for connected systems should be rotated and kept out "
        "of code.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0008",
        "Synthetic placeholder: failed integration messages need monitoring and an error queue.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0009",
        "Synthetic placeholder: an older mapping note, dated before the staleness window.",
        None,
        _STALE_CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0010",
        "Synthetic placeholder: API access depends on the connected system version and its "
        "scopes.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0012",
        "Synthetic placeholder: an integration between two systems needs an agreed data owner and "
        "a written contract.",
        None,
        _CHECKED_AT,
    ),
    (
        "EVD-MID-SYN-0011",
        "Synthetic placeholder: personal data in transit must be encrypted and needs a "
        "retention rule.",
        None,
        _CHECKED_AT,
    ),
)

# The topic phrases each record bears on. Keys are evidence IDs; values are Topic.phrase strings.
STANDALONE_RECORD_TOPICS: Mapping[str, frozenset[str]] = {
    "EVD-STD-SYN-0001": frozenset({"an existing or off-the-shelf application"}),
    "EVD-STD-SYN-0002": frozenset({"frontend architecture", "backend architecture"}),
    "EVD-STD-SYN-0003": frozenset({"authentication and authorisation"}),
    "EVD-STD-SYN-0004": frozenset({"authentication and authorisation"}),
    "EVD-STD-SYN-0005": frozenset({"data models and persistence"}),
    "EVD-STD-SYN-0006": frozenset({"external APIs and service integrations"}),
    "EVD-STD-SYN-0007": frozenset({"hosting and deployment", "scalability and reliability"}),
    "EVD-STD-SYN-0008": frozenset({"security considerations"}),
}

MIDDLEWARE_RECORD_TOPICS: Mapping[str, frozenset[str]] = {
    "EVD-MID-SYN-0001": frozenset({"webhooks and event delivery", "event-driven delivery"}),
    "EVD-MID-SYN-0002": frozenset({"retries and idempotency"}),
    "EVD-MID-SYN-0003": frozenset({"synchronisation direction and frequency"}),
    "EVD-MID-SYN-0004": frozenset({"synchronisation direction and frequency"}),
    "EVD-MID-SYN-0005": frozenset({"API access", "rate limits and operational dependencies"}),
    "EVD-MID-SYN-0006": frozenset({"data mapping and transformation"}),
    "EVD-MID-SYN-0007": frozenset({"authentication and credentials"}),
    "EVD-MID-SYN-0008": frozenset({"monitoring and error handling", "failure recovery"}),
    "EVD-MID-SYN-0009": frozenset({"data mapping and transformation"}),
    "EVD-MID-SYN-0010": frozenset({"API access"}),
    "EVD-MID-SYN-0011": frozenset({"integration security and data protection"}),
    "EVD-MID-SYN-0012": frozenset({"integration between systems"}),
}


def _records(
    collection: str,
    records: tuple[_Record, ...],
    project_id: str,
) -> list[CollectedEvidence]:
    return [
        CollectedEvidence(
            collection=collection,
            record=EvidenceReference(
                evidence_id=evidence_id,
                project_id=project_id,
                evidence_kind=EvidenceKind.SYNTHETIC_MOCK,
                evidence_status=EvidenceStatus.UNVERIFIED,
                checked_at=checked_at,
                relevance_summary=summary,
                limitations=_LIMITATION,
            ),
            conflict_group=group,
        )
        for evidence_id, summary, group, checked_at in records
    ]


def synthetic_standalone_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the standalone synthetic collection."""
    return _records(STANDALONE_EVIDENCE_COLLECTION, _STANDALONE, project_id)


def synthetic_middleware_evidence(project_id: str) -> list[CollectedEvidence]:
    """Mock records for one project, all tagged with the middleware synthetic collection."""
    return _records(MIDDLEWARE_EVIDENCE_COLLECTION, _MIDDLEWARE, project_id)
