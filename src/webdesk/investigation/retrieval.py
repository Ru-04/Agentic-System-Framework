"""Controlled, non-production retrieval of approved official documentation (Sprint 4).

Order of checks for every URL, and no request is made unless every earlier check passes:
1. The source boundary for the platform and edition is activated (``engine.ACTIVE_BOUNDARIES``).
2. A transport has been supplied by an authorized caller. The package ships no default transport,
   so importing this module cannot cause a network request.
3. The URL is inside the approved boundary (exact host and path, no query, no encoding).
4. Redirects are not followed. A redirect response is refused.
5. The body is bounded, decodes as UTF-8, and is screened for instruction-like content. Flagged
   content is quarantined: its text is discarded and only a count is kept.

Outcomes never carry the URL, the page text or the transport error text. Failures are reported
as sanitized categories. A retrieved page is not evidence until the engine accepts it, and the
engine labels a page as verified only when its boundary is active and its version is stated.
"""

from __future__ import annotations

import hashlib
import http.client
import re
import urllib.error
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from html.parser import HTMLParser
from typing import Final

from webdesk.evidence.http_vendor import _LOOKS_LIKE_HTML, Opener
from webdesk.evidence.untrusted import flag_instruction_like
from webdesk.investigation import engine
from webdesk.investigation.engine import Edition, Page

TIMEOUT_SECONDS: Final[float] = 10.0
MAX_BYTES: Final[int] = 2_000_000


class FetchStatus(StrEnum):
    FETCHED = "fetched"
    # Not activated, or no transport configured. Evidence unavailability, not a breach.
    INACTIVE = "inactive"
    # Outside the approved boundary, a redirect, an oversize or non-UTF-8 body. Refusal.
    REFUSED = "refused"
    # The vendor could not be reached or returned an error. Evidence unavailability.
    UNAVAILABLE = "unavailable"
    # Instruction-like content was found and its text discarded.
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class FetchRecord:
    """Sanitized provenance for one requested URL. Carries no URL and no page text."""

    status: FetchStatus
    reason: str
    content_sha256: str | None = None
    source_id: str | None = None
    retrieved_at: datetime | None = None


@dataclass(frozen=True)
class RetrievalOutcome:
    pages: tuple[Page, ...]
    records: tuple[FetchRecord, ...]

    def count(self, status: FetchStatus) -> int:
        return sum(1 for record in self.records if record.status is status)


def retrieve_approved_pages(
    *,
    platform: str,
    edition: Edition,
    urls: Sequence[str],
    workspace_id: str,
    version: str | None,
    opener: Opener | None,
    source_id: str,
    now: datetime,
) -> RetrievalOutcome:
    """Fetch approved pages, or record why each one was not fetched. Makes no request otherwise."""
    if now.tzinfo is None:
        raise ValueError("retrieval timestamp must be timezone-aware")
    if not source_id.strip():
        raise ValueError("source_id must not be blank")
    key = (platform, edition)
    boundary = engine.BOUNDARIES.get(key)
    pages: list[Page] = []
    records: list[FetchRecord] = []
    for url in urls:
        if boundary is None or key not in engine.ACTIVE_BOUNDARIES:
            records.append(FetchRecord(FetchStatus.INACTIVE, "source is not activated"))
            continue
        if opener is None:
            records.append(FetchRecord(FetchStatus.INACTIVE, "no transport is configured"))
            continue
        if not boundary.permits(url):
            records.append(FetchRecord(FetchStatus.REFUSED, "url is outside the approved boundary"))
            continue
        body = _read_bounded(url, opener, records)
        if body is None:
            continue
        raw = _decode(body, records)
        if raw is None:
            continue
        # Sprint 5 Decision 3 (2 Nov 2026): only substantive blocks form the text, so headings,
        # titles and navigation cannot supply a passage. Plain text is used as it is.
        text = _substantive_text(raw) if _LOOKS_LIKE_HTML.search(raw) else raw
        if _is_not_found(text):
            # A 200 response whose body is a not-found page is not documentation. Excluded.
            records.append(FetchRecord(FetchStatus.UNAVAILABLE, "page not found; not usable"))
            continue
        if flag_instruction_like(text):
            records.append(
                FetchRecord(FetchStatus.QUARANTINED, "instruction-like content was quarantined")
            )
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        pages.append(
            Page(
                url=url,
                final_url=url,
                platform=platform,
                edition=edition,
                version=version,
                workspace_id=workspace_id,
                text=text,
                synthetic=False,
                source_id=source_id,
                retrieved_at=now.isoformat(),
                title=_page_title(raw),
            )
        )
        records.append(
            FetchRecord(
                FetchStatus.FETCHED,
                "retrieved",
                content_sha256=digest,
                source_id=source_id,
                retrieved_at=now,
            )
        )
    return RetrievalOutcome(tuple(pages), tuple(records))


def _read_bounded(url: str, opener: Opener, records: list[FetchRecord]) -> bytes | None:
    try:
        response = opener(url, TIMEOUT_SECONDS)
        try:
            body = response.read(MAX_BYTES + 1)
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        # Redirects are not followed, so a 3xx arrives here and is refused.
        if 300 <= exc.code < 400:
            records.append(FetchRecord(FetchStatus.REFUSED, "redirect was not followed"))
        else:
            records.append(FetchRecord(FetchStatus.UNAVAILABLE, "vendor returned an error"))
        return None
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
        records.append(FetchRecord(FetchStatus.UNAVAILABLE, "vendor could not be reached"))
        return None
    if len(body) > MAX_BYTES:
        records.append(FetchRecord(FetchStatus.REFUSED, "document exceeds the size limit"))
        return None
    return body


def _decode(body: bytes, records: list[FetchRecord]) -> str | None:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        records.append(FetchRecord(FetchStatus.REFUSED, "document is not valid UTF-8"))
        return None


# Not-found bodies that some vendors return with HTTP 200. Matched case-insensitively.
_NOT_FOUND_MARKERS: Final[tuple[str, ...]] = (
    "page not found",
    "we could not find what you were looking for",
)


def _is_not_found(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _NOT_FOUND_MARKERS)


_TITLE: Final[re.Pattern[str]] = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Blocks that carry substantive content: prose, list items, table cells, code and API specification
# blocks, and documented examples. Headings and titles are not on this list, so they cannot count.
_SUBSTANTIVE_TAGS: Final[frozenset[str]] = frozenset(
    {"p", "li", "td", "th", "pre", "code", "blockquote", "dd", "dt", "caption", "figcaption"}
)
# Never body text, even inside a substantive block.
_NON_BODY_TAGS: Final[frozenset[str]] = frozenset(
    {
        "script",
        "style",
        "title",
        "nav",
        "header",
        "footer",
        "aside",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
)


# A prose block needs at least this many words. A one-word label or a short list item is not a
# passage that can support a claim. Code and API specification blocks are exempt.
_MIN_PROSE_WORDS: Final = 4
_SPECIFICATION_TAGS: Final[frozenset[str]] = frozenset({"pre", "code"})


# Renderers mark code examples with these attributes (for example a highlighted curl sample in a
# documentation page built from divs). Such a block is a rendered documentation example.
_CODE_BLOCK_ATTRIBUTES: Final[frozenset[str]] = frozenset(
    {"data-language", "data-code-highlighted"}
)
_VOID_TAGS: Final[frozenset[str]] = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)


class _SubstantiveExtractor(HTMLParser):
    """Collects one passage per outermost substantive block, and nothing else.

    Each open element is tracked, so the end of a block is the end of its own element. Text inside
    a non-body element (heading, navigation, script) never counts, even inside a substantive block.
    """

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[str] = []
        self._block_depth: int | None = None
        self._specification = False
        self._buffer: list[str] = []
        self.parts: list[str] = []

    def _skipping(self) -> bool:
        # An aside is a side panel. It can hold prose chrome, so prose inside it is skipped. A code
        # example inside it is a documented example, so it is kept.
        skipped = any(tag in _NON_BODY_TAGS and tag != "aside" for tag in self._stack)
        if self._specification:
            return skipped
        return skipped or "aside" in self._stack

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _VOID_TAGS:
            return
        code_block = tag in _SPECIFICATION_TAGS or any(
            name in _CODE_BLOCK_ATTRIBUTES for name, _ in attrs
        )
        substantive = code_block or tag in _SUBSTANTIVE_TAGS
        if substantive and self._block_depth is None:
            self._block_depth = len(self._stack)
            self._buffer = []
            self._specification = False
        if code_block and self._block_depth is not None:
            self._specification = True
        self._stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS or tag not in self._stack:
            return
        while self._stack:
            name = self._stack.pop()
            if self._block_depth is not None and len(self._stack) == self._block_depth:
                self._flush()
                self._block_depth = None
            if name == tag:
                return

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text and self._block_depth is not None and not self._skipping():
            self._buffer.append(text)

    def _flush(self) -> None:
        if self._specification:
            block = "\n".join(self._buffer)
        else:
            block = " ".join(self._buffer)
            if len(block.split()) < _MIN_PROSE_WORDS:
                return
        if block:
            self.parts.append(block)


def _substantive_text(raw: str) -> str:
    extractor = _SubstantiveExtractor()
    extractor.feed(raw)
    extractor.close()
    return "\n".join(extractor.parts)


def _page_title(raw: str) -> str:
    """The document title from the HTML title element, bounded in length. Empty if none."""
    match = _TITLE.search(raw)
    if match is None:
        return ""
    return " ".join(match.group(1).split())[:200]
