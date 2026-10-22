"""Common retrieval interface, workspace-scoped search and bounded retries (M1 S2).

Two outcomes are kept apart on purpose:
- ``NO_EVIDENCE``: the search ran and found nothing approved. The specialist reports a gap.
- ``RetrievalError``: the search could not run. The specialist reports a failure, not a gap.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from webdesk.evidence.sources import SourceKind, SourceRecord


class RetrievalError(Exception):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class RetrievalStatus(StrEnum):
    HITS = "hits"
    NO_EVIDENCE = "no_evidence"


@dataclass(frozen=True)
class RetrievalQuery:
    workspace_id: str
    text: str
    kinds: frozenset[SourceKind]
    limit: int = 5

    def __post_init__(self) -> None:
        if not self.workspace_id.strip():
            raise ValueError("workspace_id must not be blank")
        if self.limit < 1:
            raise ValueError("limit must be at least 1")


@dataclass(frozen=True)
class Passage:
    source: SourceRecord
    start: int
    end: int

    @property
    def text(self) -> str:
        return self.source.text[self.start : self.end]


@dataclass(frozen=True)
class RetrievalResult:
    status: RetrievalStatus
    passages: tuple[Passage, ...] = ()


class Retriever(Protocol):
    def search(self, query: RetrievalQuery) -> RetrievalResult: ...


_TERM = re.compile(r"[a-z0-9]{3,}")
_LINE = re.compile(r"[^\n]+")


def _terms(text: str) -> set[str]:
    return {match.group(0) for match in _TERM.finditer(text.lower())}


class InMemoryRetriever:
    """Keyword retriever over a fixed set of sources. Used for tests and for local fixtures only."""

    def __init__(self, sources: Iterable[SourceRecord]) -> None:
        self._sources = tuple(sources)

    def search(self, query: RetrievalQuery) -> RetrievalResult:
        query_terms = _terms(query.text)
        scored: list[tuple[int, Passage]] = []
        for source in self._sources:
            if source.workspace_id != query.workspace_id or source.kind not in query.kinds:
                continue
            for match in _LINE.finditer(source.text):
                if not match.group(0).strip():
                    continue
                hits = len(query_terms & _terms(match.group(0)))
                if hits:
                    scored.append((hits, Passage(source, match.start(), match.end())))
        if not scored:
            return RetrievalResult(RetrievalStatus.NO_EVIDENCE)
        scored.sort(key=lambda item: (-item[0], item[1].source.source_id, item[1].start))
        return RetrievalResult(
            RetrievalStatus.HITS, tuple(passage for _, passage in scored[: query.limit])
        )


def search_with_retry(
    retriever: Retriever,
    query: RetrievalQuery,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> RetrievalResult:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    last: RetrievalError | None = None
    for attempt in range(attempts):
        try:
            return retriever.search(query)
        except RetrievalError as exc:
            if not exc.retryable:
                raise
            last = exc
            if attempt + 1 < attempts:
                sleep(0.5 * (2**attempt))
    if last is None:
        raise ValueError("no attempt was made")
    raise last
