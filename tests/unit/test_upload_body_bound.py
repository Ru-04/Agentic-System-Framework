"""F-2 (D5): an upload body over its bound is refused before the framework buffers it.

Starlette's ``request.form()`` reads the whole body through ``request.stream()`` and has no total
limit. These tests drive the bounded parse with a receive callable that counts the bytes it has
handed out, so they show how much of the body was read before the refusal. No database is needed.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from starlette.requests import Request

from webdesk.api import routes
from webdesk.intake.ingest import IngestError

MiB = 1024 * 1024
CHUNK = 64 * 1024
BOUNDARY = b"WDSBOUNDARY"
CONTENT_TYPE = (b"content-type", b"multipart/form-data; boundary=" + BOUNDARY)


def _multipart(fields: dict[str, bytes], file_bytes: bytes) -> bytes:
    parts = [
        b"--"
        + BOUNDARY
        + b'\r\nContent-Disposition: form-data; name="'
        + name.encode()
        + b'"\r\n\r\n'
        + value
        + b"\r\n"
        for name, value in fields.items()
    ]
    parts.append(
        b"--"
        + BOUNDARY
        + b'\r\nContent-Disposition: form-data; name="file"; filename="big.txt"\r\n'
        + b"Content-Type: text/plain\r\n\r\n"
        + file_bytes
        + b"\r\n"
    )
    parts.append(b"--" + BOUNDARY + b"--\r\n")
    return b"".join(parts)


class _Body:
    """A receive callable that delivers ``body`` in chunks and counts what it has delivered."""

    def __init__(self, body: bytes) -> None:
        self._body = body
        self.delivered = 0
        self.calls = 0

    async def __call__(self) -> dict[str, Any]:
        self.calls += 1
        chunk = self._body[self.delivered : self.delivered + CHUNK]
        self.delivered += len(chunk)
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": self.delivered < len(self._body),
        }


def _request(receive: _Body, headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/projects/x/sources",
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope, receive)


def test_f2_a_body_over_the_limit_is_refused_before_the_rest_of_it_is_read() -> None:
    body = _Body(_multipart({"title": b"t"}, b"x" * (3 * MiB)))
    request = _request(body, [CONTENT_TYPE])
    with pytest.raises(IngestError) as exc:
        asyncio.run(routes._bounded_form(request, MiB))
    assert exc.value.status == 413
    assert exc.value.reason == "too_large"
    # The parser may hold the limit and one chunk more, never the whole 3 MiB body.
    assert body.delivered <= MiB + CHUNK


def test_f2_a_declared_length_over_the_limit_is_refused_without_reading_the_body() -> None:
    body = _Body(_multipart({"title": b"t"}, b"x" * (3 * MiB)))
    request = _request(body, [CONTENT_TYPE, (b"content-length", str(3 * MiB).encode())])
    with pytest.raises(IngestError) as exc:
        asyncio.run(routes._bounded_form(request, MiB))
    assert exc.value.status == 413
    assert body.calls == 0


def test_f2_a_body_within_the_limit_is_parsed_as_before() -> None:
    """Negative control: a normal upload is not refused and its fields and file are intact."""
    payload = b"line one\nline two\n"
    raw = _multipart({"title": b"HTTP notes"}, payload)
    body = _Body(raw)
    request = _request(body, [CONTENT_TYPE, (b"content-length", str(len(raw)).encode())])
    form = asyncio.run(routes._bounded_form(request, MiB))
    assert form.get("title") == "HTTP notes"
    upload = form.get("file")
    assert upload is not None
    assert asyncio.run(upload.read()) == payload
