"""Typed-locator parsers for the five permitted types (I-6; ARCH §13; SCHEMA §4.2; EVAL-F04).

Each parser returns draft segments with a locator of the type its file format requires. A whole-file
failure raises ``ParserFailure`` and commits nothing (I-7). A single unreadable region is
recorded as ``flagged_regions`` and the parse becomes ``partial``. A file with no extractable
text is
``unsupported``. There is no OCR. Attachments are listed, never parsed. Only the subject and body of
an EML message become segments.

Libraries (approved defaults D-1): pypdf 5.1.0, python-docx 1.1.2. Markdown, TXT and EML use the
standard library.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any, cast

from docx import Document
from pypdf import PdfReader

EXTRACTION_VERSION = "v1"
PARSER_LIBRARY_VERSION = "pypdf-5.1.0+python-docx-1.1.2"


class ParserFailure(Exception):
    """The whole file could not be parsed. ``reason`` is stable and stored on the version."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SegmentDraft:
    locator_type: str
    locator: dict[str, Any]
    text: str


@dataclass
class ParseResult:
    status: str  # succeeded | partial | unsupported
    segments: list[SegmentDraft] = field(default_factory=list)
    flagged_regions: list[str] = field(default_factory=list)
    unprocessed_attachments: list[dict[str, Any]] = field(default_factory=list)


def _status(segments: list[SegmentDraft], flagged: list[str]) -> str:
    if not segments:
        return "unsupported"
    return "partial" if flagged else "succeeded"


def parse_pdf(data: bytes) -> ParseResult:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParserFailure("encrypted_not_permitted")
        pages = list(reader.pages)
    except ParserFailure:
        raise
    except Exception as exc:
        raise ParserFailure("corrupt_structure") from exc

    segments: list[SegmentDraft] = []
    flagged: list[str] = []
    for number, page in enumerate(pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception:
            flagged.append(f"pdf_page:{number}")
            continue
        if text:
            segments.append(SegmentDraft("pdf_page", {"page_number": number}, text))
    return ParseResult(_status(segments, flagged), segments, flagged)


def parse_docx(data: bytes) -> ParseResult:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise ParserFailure("corrupt_structure") from exc
    segments = [
        SegmentDraft("docx_paragraph", {"paragraph_index": index}, paragraph.text.strip())
        for index, paragraph in enumerate(document.paragraphs, start=1)
        if paragraph.text.strip()
    ]
    return ParseResult(_status(segments, []), segments, [])


_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_markdown(data: bytes) -> ParseResult:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParserFailure("invalid_utf8") from exc

    segments: list[SegmentDraft] = []
    heading_path: list[str] = []
    counters: dict[tuple[str, ...], int] = {}
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        body = "\n".join(block).strip()
        block.clear()
        if not body:
            return
        key = tuple(heading_path)
        counters[key] = counters.get(key, 0) + 1
        segments.append(
            SegmentDraft(
                "md_heading_paragraph",
                {"heading_path": list(key), "paragraph_index": counters[key]},
                body,
            )
        )

    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            heading_path[:] = heading_path[: level - 1]
            heading_path.append(match.group(2))
        elif not line.strip():
            flush()
        else:
            block.append(line)
    flush()
    return ParseResult(_status(segments, []), segments, [])


def parse_text(data: bytes) -> ParseResult:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParserFailure("invalid_utf8") from exc
    segments = [
        SegmentDraft("txt_line_range", {"line_start": number, "line_end": number}, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]
    return ParseResult(_status(segments, []), segments, [])


def parse_eml(data: bytes) -> ParseResult:
    try:
        message = cast(EmailMessage, BytesParser(policy=email_policy.default).parsebytes(data))
    except Exception as exc:
        raise ParserFailure("corrupt_structure") from exc
    if not (message.get("subject") or message.get("from") or message.get("to")):
        raise ParserFailure("corrupt_structure")

    segments: list[SegmentDraft] = []
    subject = str(message.get("subject", "")).strip()
    if subject:
        segments.append(SegmentDraft("eml_part", {"eml_part": "subject"}, subject))
    body_part = message.get_body(preferencelist=("plain",))
    body = body_part.get_content().strip() if body_part is not None else ""
    if body:
        segments.append(SegmentDraft("eml_part", {"eml_part": "body"}, body))

    attachments: list[dict[str, Any]] = []
    for part in message.iter_attachments():
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "filename": str(part.get_filename() or "attachment"),
                "declared_mime_type": part.get_content_type(),
                "declared_size_bytes": len(payload),
                "disposition": "unprocessed",
            }
        )
    return ParseResult(_status(segments, []), segments, [], attachments)


PARSERS = {
    "application/pdf": parse_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": parse_docx,
    "text/markdown": parse_markdown,
    "text/plain": parse_text,
    "message/rfc822": parse_eml,
}
