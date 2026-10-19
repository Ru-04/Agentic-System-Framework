"""Project-isolated, content-addressed byte store (I-2; ARCH §13; D-7).

- Bytes are stored under ``<root>/<project_id>/<sha256>``. A project cannot read another project's
  files, even when the bytes are identical.
- The storage key is the lowercase SHA-256 of the content. Keys must match that pattern, which
  rules out path traversal. Callers never supply a path.
- Writes go to a temporary file in the same directory and are then atomically renamed.
- Reads verify the hash again, so a modified file is refused.
- Size is capped at 20 MiB (F-3). The root is an absolute directory from configuration (D-7).
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
_KEY_RE = re.compile(r"^[0-9a-f]{64}$")


class ByteStoreError(Exception):
    """A byte-store operation was refused. ``reason`` is a stable code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ContentStore:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ByteStoreError("storage_root_must_be_absolute")
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, project_id: uuid.UUID, key: str) -> Path:
        if not _KEY_RE.fullmatch(key):
            raise ByteStoreError("storage_key_invalid")
        return self._root / str(project_id) / key

    def put(self, project_id: uuid.UUID, data: bytes) -> str:
        if not data:
            raise ByteStoreError("empty_content")
        if len(data) > MAX_BYTES:
            raise ByteStoreError("too_large")
        key = hashlib.sha256(data).hexdigest()
        target = self._path(project_id, key)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != key:
                raise ByteStoreError("integrity_failure")
            return key
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{key}.{uuid.uuid4().hex}.tmp")
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return key

    def get(self, project_id: uuid.UUID, key: str) -> bytes:
        path = self._path(project_id, key)
        if not path.is_file():
            raise ByteStoreError("not_found")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != key:
            raise ByteStoreError("integrity_failure")
        return data
