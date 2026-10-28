"""Offline, fail-closed client for the Foundation AI read contract (``ai-read/v1``).

The contract is documented in ``docs/AI_FOUNDATION_READ_CONTRACT_v1.md`` on the Foundation branches
``feature/foundation-phase-4`` and ``feature/increment-1-foundation``. This module:

- issues only ``GET`` requests to the five documented endpoints;
- sends the ``AI-Principal`` credential and the contract-version header on every request;
- validates every response against the contract and refuses anything outside it;
- never imports an HTTP library. The transport is injected, so the client is testable offline.

It does not create, persist or infer requirements, evidence, grants or approvals. The v1 contract
has no routes for them (contract sections 8 and 12). The caller reports them as unavailable;
this module does not emulate them.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "ai-read/v1"
CONTRACT_TAG = "ai-read/v1"
MAX_SEGMENT_TEXT = 4000
MAX_CONTENT_BYTES = 10 * 1024 * 1024
SOURCE_LIMIT_RANGE = (1, 100)
SOURCE_LIMIT_DEFAULT = 50
SEGMENT_LIMIT_RANGE = (1, 200)
SEGMENT_LIMIT_DEFAULT = 100
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class AiReadError(Exception):
    """Base class. ``reason`` is safe to log: it holds no credential and no response body."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AiReadRefused(AiReadError):
    """The response violated the contract, or the request was outside the contract."""


class AiReadNotFound(AiReadError):
    """Used for every cross-scope denial: existence is never disclosed (contract section 7)."""


@dataclass(frozen=True)
class AiReadResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class AiReadTransport(Protocol):
    """The only route to the outside. Implementations must send exactly what they are given."""

    def get(self, path: str, headers: Mapping[str, str]) -> AiReadResponse: ...


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_M = TypeVar("_M", bound=_Strict)


class AiRunMetadata(_Strict):
    contract: Literal["ai-read/v1"]
    run_id: str
    project_id: str
    state: str
    status: Literal[
        "queued",
        "running",
        "waiting_human",
        "blocked_pending_decision",
        "completed",
        "failed",
        "cancelled",
    ]
    revision: int = Field(ge=0)
    is_stale: bool
    failure_class: str | None
    created_at: str
    updated_at: str


class AiProjectMetadata(_Strict):
    contract: Literal["ai-read/v1"]
    project_id: str
    name: str
    data_classification: str
    status: Literal["active", "archived"]
    revision: int = Field(ge=0)


class AiSourceVersion(_Strict):
    source_version_id: str
    source_id: str
    version: int = Field(ge=1)
    scan_status: str
    parse_status: str
    access_classification: str
    revision: int = Field(ge=0)
    mime_type: str
    file_size_bytes: int = Field(ge=0)


class AiSourceVersionPage(_Strict):
    contract: Literal["ai-read/v1"]
    items: tuple[AiSourceVersion, ...]
    next_cursor: str | None


class AiSegment(_Strict):
    segment_id: str
    locator_type: str
    locator: str
    text_content: str
    text_truncated: bool


class AiSegmentPage(_Strict):
    contract: Literal["ai-read/v1"]
    source_version_id: str
    items: tuple[AiSegment, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class AiReadClient:
    """Read-only, run-scoped client. One instance serves one run and one AI principal."""

    transport: AiReadTransport
    run_id: str
    principal_token: str = field(repr=False)
    _headers: dict[str, str] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        if not _UUID.match(self.run_id):
            raise AiReadRefused("run identifier is not a UUID")
        if not self.principal_token:
            raise AiReadRefused("AI principal credential is missing")
        # The credential is held only here; it is never returned or placed in an error message.
        object.__setattr__(
            self,
            "_headers",
            {
                "Authorization": f"AI-Principal {self.principal_token}",
                "X-AI-Contract-Version": CONTRACT_VERSION,
            },
        )

    # --- endpoints ---

    def run(self) -> AiRunMetadata:
        data = self._get_json(f"/v1/ai/runs/{self.run_id}", AiRunMetadata)
        if data.run_id != self.run_id:
            raise AiReadRefused("run response names a different run")
        return data

    def project(self) -> AiProjectMetadata:
        run = self.run()
        data = self._get_json(f"/v1/ai/runs/{self.run_id}/project", AiProjectMetadata)
        if data.project_id != run.project_id:
            raise AiReadRefused("project response does not match the run's project")
        return data

    def source_versions(
        self, *, limit: int = SOURCE_LIMIT_DEFAULT, after: str | None = None
    ) -> AiSourceVersionPage:
        _check_limit(limit, SOURCE_LIMIT_RANGE, "source-version")
        query = _query(limit, after)
        page = self._get_json(
            f"/v1/ai/runs/{self.run_id}/source-versions{query}", AiSourceVersionPage
        )
        for item in page.items:
            # Section 5: only not_scanned or clean versions that are not restricted are ever listed.
            if item.scan_status not in ("not_scanned", "clean"):
                raise AiReadRefused("source-version list contained an unreadable scan status")
            if item.access_classification == "restricted":
                raise AiReadRefused(
                    "source-version list contained a version outside the read rules"
                )
        _check_cursor(page.next_cursor, page.items[-1].source_version_id if page.items else None)
        return page

    def segments(
        self,
        source_version_id: str,
        *,
        limit: int = SEGMENT_LIMIT_DEFAULT,
        after: str | None = None,
    ) -> AiSegmentPage:
        _check_limit(limit, SEGMENT_LIMIT_RANGE, "segment")
        _check_uuid(source_version_id, "source-version")
        query = _query(limit, after)
        page = self._get_json(
            f"/v1/ai/runs/{self.run_id}/source-versions/{source_version_id}/segments{query}",
            AiSegmentPage,
        )
        if page.source_version_id != source_version_id:
            raise AiReadRefused("segment response names a different source version")
        for item in page.items:
            if len(item.text_content) > MAX_SEGMENT_TEXT:
                raise AiReadRefused("segment text exceeds the contract limit")
            if item.text_truncated and len(item.text_content) != MAX_SEGMENT_TEXT:
                raise AiReadRefused("truncation flag is inconsistent with the segment text")
        _check_cursor(page.next_cursor, page.items[-1].segment_id if page.items else None)
        return page

    def content(self, source_version_id: str) -> tuple[bytes, str]:
        _check_uuid(source_version_id, "source-version")
        path = f"/v1/ai/runs/{self.run_id}/source-versions/{source_version_id}/content"
        response = self._send(path)
        if response.status == 413:
            raise AiReadRefused("content exceeds the contract size limit")
        _check_status(response.status)
        if len(response.body) > MAX_CONTENT_BYTES:
            raise AiReadRefused("content exceeds the contract size limit")
        if response.headers.get("X-AI-Contract") != CONTRACT_TAG:
            raise AiReadRefused("content response lacks the contract tag")
        mime = response.headers.get("Content-Type", "")
        if not mime:
            raise AiReadRefused("content response lacks a Content-Type")
        return response.body, mime

    # --- internals ---

    def _send(self, path: str) -> AiReadResponse:
        # Only GET is ever issued, and the path is always under the run's scope.
        response = self.transport.get(path, self._headers)
        if response.headers.get("X-AI-Contract-Version", CONTRACT_VERSION) != CONTRACT_VERSION:
            raise AiReadRefused("response declares another contract version")
        return response

    def _get_json(self, path: str, model: type[_M]) -> _M:
        response = self._send(path)
        _check_status(response.status)
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AiReadRefused("response body is not valid JSON") from error
        if not isinstance(payload, dict):
            raise AiReadRefused("response body is not an object")
        if payload.get("contract") not in (None, CONTRACT_TAG):
            raise AiReadRefused("response declares another contract")
        payload.setdefault("contract", CONTRACT_TAG)
        try:
            return model.model_validate(payload)
        except (
            Exception
        ) as error:  # the validation message names fields, never values or credentials
            raise AiReadRefused("response does not match the contract schema") from error


def _check_status(status: int) -> None:
    if status == 200:
        return
    if status == 404:
        raise AiReadNotFound("not found")
    if status == 405:
        raise AiReadRefused("method not allowed on the AI read contract")
    if status == 401:
        raise AiReadRefused("AI principal credential is not valid")
    raise AiReadRefused(f"unexpected status {status}")


def _check_limit(limit: int, bounds: tuple[int, int], kind: str) -> None:
    low, high = bounds
    if not (low <= limit <= high):
        raise AiReadRefused(f"{kind} limit must be between {low} and {high}")


def _check_uuid(value: str, kind: str) -> None:
    if not _UUID.match(value):
        raise AiReadRefused(f"{kind} identifier is not a UUID")


def _check_cursor(next_cursor: str | None, last_id: str | None) -> None:
    # The cursor is the last identifier returned, or null (contract section 6.1).
    if next_cursor is not None and next_cursor != last_id:
        raise AiReadRefused("next cursor does not match the last returned identifier")


def _query(limit: int, after: str | None) -> str:
    if after is None:
        return f"?limit={limit}"
    return f"?limit={limit}&after={after}"
