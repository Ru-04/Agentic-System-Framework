"""Allowlisted vendor-document fetch (M1 S2, decision D08).

The allowlist is checked before any network call. Redirects are not followed, so a permitted host
cannot send the fetch on to a host that is not on the list. Failures are classified: a refused or
malformed document is not retryable, while a timeout or connection error is.
"""

from __future__ import annotations

import http.client
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from html.parser import HTMLParser
from http.client import HTTPMessage
from typing import IO, Final, cast

from webdesk.evidence.allowlist import VendorAllowlist
from webdesk.evidence.retrieval import RetrievalError
from webdesk.evidence.sources import SourceKind, SourceRecord

Opener = Callable[[str, float], IO[bytes]]

# Markup anywhere in the body, not only near the start, means the body is HTML.
_LOOKS_LIKE_HTML: Final[re.Pattern[str]] = re.compile(
    r"<\s*(!doctype|html|body|head|script|style|p|div|span|a|table)\b", re.IGNORECASE
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        # Returning None stops the redirect. urllib then raises HTTPError for the 3xx response.
        return None


def build_vendor_opener() -> urllib.request.OpenerDirector:
    # Proposal P2 (approved 22 October 2026). Passing a ProxyHandler instance makes urllib skip its
    # default handler, which reads HTTP_PROXY and HTTPS_PROXY. The empty instance installs no proxy
    # handler of its own, so no proxy is used and the allowlist controls the destination.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirectHandler)


def _default_opener(url: str, timeout: float) -> IO[bytes]:
    return cast(IO[bytes], build_vendor_opener().open(url, timeout=timeout))


class _TextExtractor(HTMLParser):
    _SKIP = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def _text_from_html(raw: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(raw)
    extractor.close()
    return "\n".join(extractor.parts)


def fetch_vendor_document(
    url: str,
    *,
    allowlist: VendorAllowlist,
    workspace_id: str,
    source_id: str,
    title: str,
    now: datetime,
    opener: Opener = _default_opener,
    timeout: float = 10.0,
    max_bytes: int = 2_000_000,
    version: str | None = None,
) -> SourceRecord:
    if not allowlist.permits(url):
        raise RetrievalError("url is not on the approved vendor allowlist", retryable=False)
    try:
        response = opener(url, timeout)
        try:
            body = response.read(max_bytes + 1)
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        retryable = exc.code >= 500 or exc.code == 429
        raise RetrievalError(f"vendor returned HTTP {exc.code}", retryable=retryable) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RetrievalError("vendor connection failed", retryable=True) from None
    except http.client.IncompleteRead:
        raise RetrievalError("vendor response was truncated", retryable=True) from None
    except (http.client.HTTPException, ValueError):
        raise RetrievalError("vendor request was malformed or refused", retryable=False) from None
    if len(body) > max_bytes:
        raise RetrievalError("vendor document exceeds the size limit", retryable=False)
    try:
        raw = body.decode("utf-8")
    except UnicodeDecodeError:
        raise RetrievalError("vendor document is not valid UTF-8", retryable=False) from None
    text = _text_from_html(raw) if _LOOKS_LIKE_HTML.search(raw) else raw
    return SourceRecord(
        source_id=source_id,
        kind=SourceKind.VENDOR_DOC,
        workspace_id=workspace_id,
        origin=url,
        title=title,
        text=text,
        retrieved_at=now,
        version=version,
    )
