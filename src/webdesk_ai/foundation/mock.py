"""In-memory stand-in for Foundation ``ai-read/v1``, used only for contract tests and the demo.

It implements the response shapes and error table of ``docs/AI_FOUNDATION_READ_CONTRACT_v1.md``
(sections 6, 7, 9 and 10). It is not Foundation and must never be pointed at real data. Its
fixtures are synthetic, and it enforces the same denial rules as the contract: quarantined and
restricted versions are invisible, and an expired or revoked credential is refused neutrally.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from webdesk_ai.foundation.client import (
    CONTRACT_HEADER,
    CONTRACT_ID,
    MAX_CONTENT_BYTES,
    RESPONSE_CONTRACT_HEADER,
    ReadRequest,
    ReadResponse,
)

SEGMENT_TEXT_LIMIT = 4000
_RUN = re.compile(r"^/v1/ai/runs/(?P<run>[^/]+)$")
_PROJECT = re.compile(r"^/v1/ai/runs/(?P<run>[^/]+)/project$")
_VERSIONS = re.compile(r"^/v1/ai/runs/(?P<run>[^/]+)/source-versions$")
_SEGMENTS = re.compile(r"^/v1/ai/runs/(?P<run>[^/]+)/source-versions/(?P<sv>[^/]+)/segments$")
_CONTENT = re.compile(r"^/v1/ai/runs/(?P<run>[^/]+)/source-versions/(?P<sv>[^/]+)/content$")


@dataclass
class MockVersion:
    source_version_id: UUID
    source_id: UUID
    version: int
    scan_status: str = "not_scanned"
    parse_status: str = "succeeded"
    access_classification: str = "confidential"
    mime_type: str | None = "text/plain"
    content: bytes = b""
    segments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MockFoundation:
    """Serves one run. ``now`` is injected so expiry is deterministic in tests."""

    token: str
    run_id: UUID
    project_id: UUID
    project_name: str
    versions: list[MockVersion]
    now: Callable[[], datetime]
    expires_at: datetime
    bound_user_active: bool = True
    revoked: bool = False
    run_state: str = "running"
    run_status: str = "running"
    is_stale: bool = False
    project_override_id: UUID | None = None
    _log: list[dict[str, str]] = field(default_factory=list)

    @property
    def audit_log(self) -> list[dict[str, str]]:
        """Audit rows the real service would write. Never contains token values or content."""
        return list(self._log)

    def send(self, request: ReadRequest) -> ReadResponse:
        if request.headers.get(CONTRACT_HEADER) != CONTRACT_ID:
            return _error(400, "contract_version_unsupported")
        if not self._credential_valid(request.headers.get("Authorization", "")):
            self._audit("ai.read.denied", "ai-principal:" + str(self.run_id), "credential")
            return _error(401, "ai_credential_invalid")
        if request.method != "GET":
            return _error(405, "method_not_allowed")
        return self._route(request.path)

    # ----- routing ----------------------------------------------------------------------------

    def _route(self, path: str) -> ReadResponse:
        route = path.partition("?")[0]
        match = _RUN.match(route)
        if match:
            return self._run_for(match.group("run"))
        match = _PROJECT.match(route)
        if match:
            return self._project_for(match.group("run"))
        match = _VERSIONS.match(route)
        if match:
            return self._versions_for(match.group("run"), path)
        match = _SEGMENTS.match(route)
        if match:
            return self._segments_for(match.group("run"), match.group("sv"), path)
        match = _CONTENT.match(route)
        if match:
            return self._content_for(match.group("run"), match.group("sv"))
        return _error(404, "not_found")

    def _run_for(self, run: str) -> ReadResponse:
        if run != str(self.run_id):
            return _error(404, "not_found")
        now = self.now()
        body = {
            "contract": CONTRACT_ID,
            "run_id": str(self.run_id),
            "project_id": str(self.project_id),
            "state": self.run_state,
            "status": self.run_status,
            "revision": 1,
            "is_stale": self.is_stale,
            "failure_class": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        return _json(200, body)

    def _project_for(self, run: str) -> ReadResponse:
        if run != str(self.run_id):
            return _error(404, "not_found")
        project = self.project_override_id or self.project_id
        return _json(
            200,
            {
                "contract": CONTRACT_ID,
                "project_id": str(project),
                "name": self.project_name,
                "data_classification": "confidential",
                "status": "active",
                "revision": 1,
            },
        )

    def _versions_for(self, run: str, path: str) -> ReadResponse:
        if run != str(self.run_id):
            return _error(404, "not_found")
        limit, after = _query(path, default_limit=50, maximum=100)
        if limit is None:
            return _error(400, "invalid_request")
        readable = sorted(
            (v for v in self.versions if _readable(v)), key=lambda v: str(v.source_version_id)
        )
        if after is not None:
            readable = [v for v in readable if str(v.source_version_id) > after]
        page = readable[:limit]
        more = len(readable) > limit
        items = [
            {
                "source_version_id": str(v.source_version_id),
                "source_id": str(v.source_id),
                "version": v.version,
                "scan_status": v.scan_status,
                "parse_status": v.parse_status,
                "access_classification": v.access_classification,
                "revision": 1,
                "mime_type": v.mime_type,
                "file_size_bytes": len(v.content),
            }
            for v in page
        ]
        cursor = str(page[-1].source_version_id) if more and page else None
        return _json(200, {"contract": CONTRACT_ID, "items": items, "next_cursor": cursor})

    def _segments_for(self, run: str, sv: str, path: str) -> ReadResponse:
        version = self._version(run, sv)
        if version is None:
            return _error(404, "not_found")
        limit, after = _query(path, default_limit=100, maximum=200)
        if limit is None:
            return _error(400, "invalid_request")
        rows = sorted(version.segments, key=lambda s: str(s["segment_id"]))
        if after is not None:
            rows = [s for s in rows if str(s["segment_id"]) > after]
        page = rows[:limit]
        more = len(rows) > limit
        items = []
        for seg in page:
            text = str(seg["text"])
            items.append(
                {
                    "segment_id": str(seg["segment_id"]),
                    "locator_type": seg["locator_type"],
                    "locator": seg["locator"],
                    "text_content": text[:SEGMENT_TEXT_LIMIT],
                    "text_truncated": len(text) > SEGMENT_TEXT_LIMIT,
                }
            )
        cursor = str(page[-1]["segment_id"]) if more and page else None
        return _json(
            200,
            {
                "contract": CONTRACT_ID,
                "source_version_id": str(version.source_version_id),
                "items": items,
                "next_cursor": cursor,
            },
        )

    def _content_for(self, run: str, sv: str) -> ReadResponse:
        version = self._version(run, sv)
        if version is None:
            return _error(404, "not_found")
        if len(version.content) > MAX_CONTENT_BYTES:
            return _error(413, "response_too_large")
        return ReadResponse(
            status=200,
            headers={
                "Content-Type": version.mime_type or "application/octet-stream",
                RESPONSE_CONTRACT_HEADER: CONTRACT_ID,
            },
            body=version.content,
        )

    # ----- scope and credential checks ----------------------------------------------------------

    def _version(self, run: str, sv: str) -> MockVersion | None:
        if run != str(self.run_id):
            return None
        for version in self.versions:
            if str(version.source_version_id) == sv and _readable(version):
                return version
        return None

    def _credential_valid(self, authorization: str) -> bool:
        if not authorization.startswith("AI-Principal "):
            return False
        presented = authorization[len("AI-Principal ") :]
        return (
            presented == self.token
            and not self.revoked
            and self.now() < self.expires_at
            and self.bound_user_active
            and self.run_status in ("queued", "running", "waiting_human")
        )

    def _audit(self, event: str, actor: str, reason: str) -> None:
        self._log.append({"event_type": event, "actor": actor, "error_class": reason})

    # ----- fault injection helpers for tests ------------------------------------------------

    def revoke(self) -> None:
        self.revoked = True

    def expire_now(self) -> None:
        self.expires_at = self.now() - timedelta(seconds=1)


def _readable(version: MockVersion) -> bool:
    return version.scan_status != "quarantined" and version.access_classification != "restricted"


def _query(path: str, *, default_limit: int, maximum: int) -> tuple[int | None, str | None]:
    query = path.partition("?")[2]
    params: dict[str, str] = {}
    for pair in filter(None, query.split("&")):
        key, _, value = pair.partition("=")
        params[key] = value
    raw_limit = params.get("limit", str(default_limit))
    if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= maximum:
        return None, None
    return int(raw_limit), params.get("after") or None


def _json(status: int, body: dict[str, Any]) -> ReadResponse:
    return ReadResponse(
        status=status,
        headers={"Content-Type": "application/json", RESPONSE_CONTRACT_HEADER: CONTRACT_ID},
        body=json.dumps(body).encode("utf-8"),
    )


def _error(status: int, code: str) -> ReadResponse:
    return ReadResponse(
        status=status,
        headers={"Content-Type": "application/json", RESPONSE_CONTRACT_HEADER: CONTRACT_ID},
        body=json.dumps({"contract": CONTRACT_ID, "error": code}).encode("utf-8"),
    )


def segment_row(
    segment_id: UUID, locator_type: str, locator: dict[str, Any], text: str
) -> dict[str, Any]:
    return {
        "segment_id": segment_id,
        "locator_type": locator_type,
        "locator": locator,
        "text": text,
    }
