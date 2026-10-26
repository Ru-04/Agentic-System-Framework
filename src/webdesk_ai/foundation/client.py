"""Versioned read client for Foundation ``ai-read/v1``.

The client is read-only. It never builds a write request, holds no database handle, and sends
exactly one credential, the AI service principal, scoped to one project and one run.

The transport is an injected protocol. No network transport ships in this increment, so the client
cannot reach a Foundation service until a transport is supplied and independent contract
acceptance is complete (see ``docs/AI_FOUNDATION_READ_CONTRACT_v1.md``, sections 6 and 9).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from webdesk_ai.contracts import ProjectContext, SourceSegment, SourceVersionReference

_M = TypeVar("_M", bound=BaseModel)

CONTRACT_ID = "ai-read/v1"
CONTRACT_HEADER = "X-AI-Contract-Version"
RESPONSE_CONTRACT_HEADER = "X-AI-Contract"
MAX_CONTENT_BYTES = 10 * 1024 * 1024
MAX_PAGES = 1000
SEGMENT_LIMIT_MAX = 200
VERSION_LIMIT_MAX = 100
FORBIDDEN_VERSION_FIELDS = frozenset(
    {"storage_key", "content_hash", "ingested_by_user_id", "text_content_hash"}
)
WITHHELD_SCAN_STATUS = "quarantined"
WITHHELD_CLASSIFICATION = "restricted"


class FoundationReadError(Exception):
    """Base class for every read-adapter failure."""


class CredentialRejectedError(FoundationReadError):
    """The principal is invalid, revoked, expired or no longer permitted. Deliberately neutral."""


class CredentialExpiredError(CredentialRejectedError):
    """The client's own clock shows the credential has expired. No request was sent."""


class ResourceUnavailableError(FoundationReadError):
    """404: outside scope, quarantined, restricted or not readable. Existence is not disclosed."""


class VersionMismatchError(FoundationReadError):
    """The server answered with a contract version other than ai-read/v1."""


class ScopeMismatchError(FoundationReadError):
    """A response identifies a run or project other than the one this client was bound to."""


class ContractViolationError(FoundationReadError):
    """A response does not match the ai-read/v1 shape or limits."""


class ResponseTooLargeError(FoundationReadError):
    """Content exceeds the 10 MiB contract limit."""


class FoundationUnavailableError(FoundationReadError):
    """Any other server-side failure."""


@dataclass(frozen=True)
class ReadRequest:
    method: str
    path: str
    headers: Mapping[str, str]


@dataclass(frozen=True)
class ReadResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class ReadTransport(Protocol):
    def send(self, request: ReadRequest) -> ReadResponse: ...


@dataclass(frozen=True)
class PrincipalCredential:
    """One AI principal token. ``repr`` never shows the token value."""

    token: str
    expires_at: datetime

    def __repr__(self) -> str:
        return f"PrincipalCredential(expires_at={self.expires_at.isoformat()})"


class _WireModel(BaseModel):
    # Additive fields are allowed within v1 (contract section 13); unknown fields are ignored.
    model_config = ConfigDict(extra="ignore", frozen=True)


class RunMetadata(_WireModel):
    contract: str
    run_id: UUID
    project_id: UUID
    state: str
    status: str
    revision: int
    is_stale: bool
    failure_class: str | None
    created_at: datetime
    updated_at: datetime


class _Page(_WireModel):
    contract: str
    next_cursor: str | None


class _VersionItem(_WireModel):
    source_version_id: UUID
    source_id: UUID
    version: int
    scan_status: str
    parse_status: str
    access_classification: str
    revision: int
    mime_type: str | None
    file_size_bytes: int | None


class _VersionPage(_Page):
    items: list[dict[str, Any]]


class _SegmentItem(_WireModel):
    segment_id: UUID
    locator_type: str
    locator: dict[str, Any]
    text_content: str
    text_truncated: bool


class _SegmentPage(_Page):
    source_version_id: UUID
    items: list[dict[str, Any]]


class FoundationReadClient:
    """Reads one run's scope from Foundation under the ai-read/v1 contract."""

    def __init__(
        self,
        *,
        transport: ReadTransport,
        credential: PrincipalCredential,
        run_id: UUID,
        project_id: UUID,
        clock: Callable[[], datetime],
        correlation_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._transport = transport
        self._credential = credential
        self._run_id = run_id
        self._project_id = project_id
        self._clock = clock
        self._correlation_id = correlation_id

    # ----- public read operations -------------------------------------------------------------

    def get_run(self) -> RunMetadata:
        body = self._json(f"/v1/ai/runs/{self._run_id}")
        run = self._parse(RunMetadata, body)
        if run.run_id != self._run_id or run.project_id != self._project_id:
            raise ScopeMismatchError("run metadata is outside the bound run or project")
        return run

    def get_project(self) -> ProjectContext:
        body = self._json(f"/v1/ai/runs/{self._run_id}/project")
        project = self._parse(_ProjectWire, body)
        if project.project_id != self._project_id:
            raise ScopeMismatchError("project metadata is outside the bound project")
        return self._parse(
            ProjectContext,
            {
                "project_id": project.project_id,
                "name": project.name,
                "data_classification": project.data_classification,
                "status": project.status,
                "revision": project.revision,
            },
        )

    def iter_source_versions(self, *, page_limit: int = 50) -> Iterator[SourceVersionReference]:
        """Yield readable source versions. Withheld items are dropped, never returned."""
        self._check_limit(page_limit, VERSION_LIMIT_MAX)
        after: str | None = None
        seen: set[UUID] = set()
        for _ in range(MAX_PAGES):
            query = f"?limit={page_limit}" + (f"&after={after}" if after else "")
            page = self._parse(
                _VersionPage, self._json(f"/v1/ai/runs/{self._run_id}/source-versions{query}")
            )
            for raw in page.items:
                version = self._version(raw)
                if version is None or version.source_version_id in seen:
                    continue
                seen.add(version.source_version_id)
                yield version
            if page.next_cursor is None:
                return
            if after is not None and page.next_cursor <= after:
                raise ContractViolationError("pagination cursor did not advance")
            after = page.next_cursor
        raise ContractViolationError("pagination exceeded the page guard")

    def iter_segments(
        self,
        version: SourceVersionReference,
        *,
        page_limit: int = 100,
    ) -> Iterator[SourceSegment]:
        self._check_limit(page_limit, SEGMENT_LIMIT_MAX)
        after: str | None = None
        seen: set[UUID] = set()
        for _ in range(MAX_PAGES):
            query = f"?limit={page_limit}" + (f"&after={after}" if after else "")
            path = (
                f"/v1/ai/runs/{self._run_id}/source-versions/"
                f"{version.source_version_id}/segments{query}"
            )
            page = self._parse(_SegmentPage, self._json(path))
            if page.source_version_id != version.source_version_id:
                raise ScopeMismatchError("segment page belongs to another source version")
            if len(page.items) > page_limit:
                raise ContractViolationError("segment page exceeds the requested limit")
            for raw in page.items:
                item = self._parse(_SegmentItem, raw)
                if item.segment_id in seen:
                    continue
                seen.add(item.segment_id)
                yield SourceSegment(
                    segment_id=item.segment_id,
                    source_id=version.source_id,
                    source_version_id=version.source_version_id,
                    version=version.version,
                    locator_type=item.locator_type,
                    locator=item.locator,
                    text_content=item.text_content,
                    text_truncated=item.text_truncated,
                )
            if page.next_cursor is None:
                return
            if after is not None and page.next_cursor <= after:
                raise ContractViolationError("pagination cursor did not advance")
            after = page.next_cursor
        raise ContractViolationError("pagination exceeded the page guard")

    def read_content(self, source_version_id: UUID) -> bytes:
        """Return the stored bytes of one readable version, at most 10 MiB."""
        request = self._request(
            f"/v1/ai/runs/{self._run_id}/source-versions/{source_version_id}/content"
        )
        response = self._send(request)
        self._raise_for_status(response)
        if response.headers.get(RESPONSE_CONTRACT_HEADER) != CONTRACT_ID:
            raise VersionMismatchError("content response is not ai-read/v1")
        if len(response.body) > MAX_CONTENT_BYTES:
            raise ResponseTooLargeError("content exceeds the 10 MiB contract limit")
        return response.body

    # ----- internals --------------------------------------------------------------------------

    def _version(self, raw: dict[str, Any]) -> SourceVersionReference | None:
        if FORBIDDEN_VERSION_FIELDS & raw.keys():
            raise ContractViolationError("version metadata carried a forbidden field")
        item = self._parse(_VersionItem, raw)
        if item.scan_status == WITHHELD_SCAN_STATUS:
            return None
        if item.access_classification == WITHHELD_CLASSIFICATION:
            return None
        return self._parse(
            SourceVersionReference,
            {
                "source_version_id": item.source_version_id,
                "source_id": item.source_id,
                "version": item.version,
                "scan_status": item.scan_status,
                "parse_status": item.parse_status,
                "access_classification": item.access_classification,
                "mime_type": item.mime_type,
                "file_size_bytes": item.file_size_bytes,
            },
        )

    def _json(self, path: str) -> dict[str, Any]:
        response = self._send(self._request(path))
        self._raise_for_status(response)
        try:
            parsed = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractViolationError("response body is not JSON") from exc
        if not isinstance(parsed, dict):
            raise ContractViolationError("response body is not an object")
        contract = parsed.get("contract")
        if contract != CONTRACT_ID:
            raise VersionMismatchError(f"server answered with contract {contract!r}")
        return parsed

    def _request(self, path: str) -> ReadRequest:
        return ReadRequest(
            method="GET",
            path=path,
            headers={
                "Authorization": f"AI-Principal {self._credential.token}",
                CONTRACT_HEADER: CONTRACT_ID,
                "X-Correlation-Id": self._correlation_id(),
                "Accept": "application/json",
            },
        )

    def _send(self, request: ReadRequest) -> ReadResponse:
        if self._clock() >= self._credential.expires_at:
            raise CredentialExpiredError("the principal credential has expired")
        try:
            return self._transport.send(request)
        except FoundationReadError:
            raise
        except Exception as exc:
            raise FoundationUnavailableError("transport failure") from exc

    @staticmethod
    def _raise_for_status(response: ReadResponse) -> None:
        if 200 <= response.status < 300:
            return
        error = _error_code(response.body)
        if response.status == 400 and error == "contract_version_unsupported":
            raise VersionMismatchError("server does not support ai-read/v1")
        if response.status == 400:
            raise ContractViolationError("request rejected as invalid")
        if response.status == 401:
            raise CredentialRejectedError("credential rejected")
        if response.status == 404:
            raise ResourceUnavailableError("resource is not available to this principal")
        if response.status == 405:
            raise ContractViolationError("method not allowed by ai-read/v1")
        if response.status == 413:
            raise ResponseTooLargeError("response exceeds the contract size limit")
        raise FoundationUnavailableError(f"foundation returned status {response.status}")

    @staticmethod
    def _check_limit(value: int, maximum: int) -> None:
        if not 1 <= value <= maximum:
            raise ContractViolationError(f"limit must be between 1 and {maximum}")

    @staticmethod
    def _parse(model: type[_M], raw: Any) -> _M:
        try:
            if isinstance(raw, dict):
                return model.model_validate(raw)
            return model.model_validate_json(raw)
        except ValidationError as exc:
            raise ContractViolationError(f"{model.__name__} failed validation") from exc


class _ProjectWire(_WireModel):
    contract: str
    project_id: UUID
    name: str
    data_classification: str
    status: str
    revision: int


def _error_code(body: bytes) -> str | None:
    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    value = parsed.get("error") if isinstance(parsed, dict) else None
    return value if isinstance(value, str) else None
