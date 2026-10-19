"""Upload validation (I-3; ARCH §13; EVAL-F03).

Checks run in this order, and the first failure stops the upload. Nothing is stored until all pass.

1. Size: over 20 MiB is 413. Empty is 422.
2. Extension must be one of .pdf .docx .txt .md .eml, else 415.
3. Declared MIME must match the extension, else 415. This is the spoofed-MIME case.
4. Archives, executables and scripts are refused (422), whatever the extension.
5. The magic signature must match the declared type, else 415.
6. Structure must parse. A corrupt file is 422. An encrypted PDF or DOCX is 422.

The server never trusts the browser MIME alone. The declared MIME is checked against the
extension and against the bytes.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from email import policy as email_policy
from email.parser import BytesParser

from docx import Document
from pypdf import PdfReader

from webdesk.storage.content_store import MAX_BYTES

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": DOCX_MIME,
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".eml": "message/rfc822",
}
_EXECUTABLE_MAGIC = (
    b"MZ",  # Windows executables
    b"\x7fELF",  # ELF
    b"\xfe\xed\xfa\xce",  # Mach-O
    b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe",
    b"\xcf\xfa\xed\xfe",
    b"#!",  # scripts
)
_CONTROL_RE = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class UploadRefusal(Exception):
    """An upload was refused. ``status`` follows the API contract; ``reason`` is stable."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class ValidatedUpload:
    extension: str
    mime_type: str


def _refuse(status: int, reason: str) -> UploadRefusal:
    return UploadRefusal(status, reason)


def validate_upload(filename: str, declared_mime: str, data: bytes) -> ValidatedUpload:
    if len(data) > MAX_BYTES:
        raise _refuse(413, "too_large")
    if not data:
        raise _refuse(422, "empty")

    lowered = filename.lower()
    extension = next((ext for ext in ALLOWED if lowered.endswith(ext)), None)
    if extension is None:
        raise _refuse(415, "unsupported_type")
    expected_mime = ALLOWED[extension]
    if declared_mime.strip().lower() != expected_mime:
        raise _refuse(415, "mime_mismatch")

    if data.startswith(_EXECUTABLE_MAGIC):
        raise _refuse(422, "executable_not_permitted")
    if data.startswith(b"PK\x03\x04") and extension != ".docx":
        raise _refuse(422, "archive_not_permitted")

    if extension == ".pdf":
        _check_pdf(data)
    elif extension == ".docx":
        _check_docx(data)
    elif extension in (".txt", ".md"):
        _check_text(data)
    else:
        _check_eml(data)
    return ValidatedUpload(extension=extension, mime_type=expected_mime)


def _check_pdf(data: bytes) -> None:
    if not data.startswith(b"%PDF-"):
        raise _refuse(415, "signature_mismatch")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise _refuse(422, "encrypted_not_permitted")
        _ = len(reader.pages)
    except UploadRefusal:
        raise
    except Exception as exc:
        raise _refuse(422, "corrupt_structure") from exc


def _check_docx(data: bytes) -> None:
    if not data.startswith(b"PK\x03\x04"):
        raise _refuse(415, "signature_mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if any(info.flag_bits & 0x1 for info in archive.infolist()):
                raise _refuse(422, "encrypted_not_permitted")
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise _refuse(422, "corrupt_structure")
        Document(io.BytesIO(data))
    except UploadRefusal:
        raise
    except Exception as exc:
        raise _refuse(422, "corrupt_structure") from exc


def _check_text(data: bytes) -> None:
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _refuse(422, "invalid_utf8") from exc
    if _CONTROL_RE.search(data) or "\x00" in text:
        raise _refuse(422, "binary_content")


def _check_eml(data: bytes) -> None:
    try:
        message = BytesParser(policy=email_policy.default).parsebytes(data)
    except Exception as exc:
        raise _refuse(422, "corrupt_structure") from exc
    if not (message.get("subject") or message.get("from") or message.get("to")):
        raise _refuse(422, "corrupt_structure")
