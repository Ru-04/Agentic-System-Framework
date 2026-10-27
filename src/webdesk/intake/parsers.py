"""Typed-locator parsers for the five permitted types (I-6; ARCH §13; SCHEMA §4.2; EVAL-F04).

Each parser returns draft segments with a locator of the type its file format requires. A whole-file
failure raises ``ParserFailure`` and commits nothing (I-7). A single unreadable region is
recorded as ``flagged_regions`` and the parse becomes ``partial``. A file with no extractable
text is ``unsupported``. There is no OCR. Attachments are listed, never parsed. Only the subject and
body of an EML message become segments.

Locator extensions (H-33; proposed defaults pending H-DEC-5 and H-DEC-6): ``txt_line_range`` carries
character offsets into the decoded UTF-8 text; a ``docx_paragraph`` inside a table carries
``table_index``, ``row`` and ``cell``; ``eml_part`` carries the message's ``message_id`` as
provenance. The locator CHECK (migration 0007) requires only the keys named there, so the extra
keys are admitted.

Libraries (approved defaults D-1): pypdf 5.1.0, python-docx 1.1.2. Markdown, TXT and EML use the
standard library.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any, cast

from docx import Document
from pypdf import PdfReader

from webdesk.intake import limits

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


def _has_image(page: Any) -> bool:
    """True when the page's resources include an image XObject."""
    resources = page.get("/Resources")
    if resources is None:
        return False
    xobjects = resources.get_object().get("/XObject")
    if xobjects is None:
        return False
    return any(
        obj.get_object().get("/Subtype") == "/Image" for obj in xobjects.get_object().values()
    )


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
    if len(pages) > limits.MAX_PDF_PAGES:
        raise ParserFailure(limits.PDF_PAGE_LIMIT)

    segments: list[SegmentDraft] = []
    flagged: list[str] = []
    for number, page in enumerate(pages, start=1):
        try:
            stream = page.get_contents()
            if stream is not None and len(stream.get_data()) > limits.MAX_PDF_PAGE_STREAM_BYTES:
                raise ParserFailure(limits.PDF_STREAM_LIMIT)
            text = (page.extract_text() or "").strip()
        except ParserFailure:
            raise
        except Exception:
            flagged.append(f"pdf_page:{number}")
            continue
        if text:
            segments.append(SegmentDraft("pdf_page", {"page_number": number}, text))
        elif _has_image(page):
            # H-33: an image-only page holds content that is not text. There is no OCR, so it is
            # reported as unextractable rather than read as blank.
            flagged.append(f"pdf_page:{number}")
    return ParseResult(_status(segments, flagged), segments, flagged)


def _check_archive(data: bytes) -> None:
    """Refuse a ZIP container whose uncompressed size or inflate ratio exceeds the limits (H-31)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise ParserFailure("corrupt_structure") from exc
    uncompressed = sum(info.file_size for info in infos)
    compressed = max(1, sum(info.compress_size for info in infos))
    if uncompressed > limits.MAX_ARCHIVE_UNCOMPRESSED_BYTES:
        raise ParserFailure(limits.ARCHIVE_SIZE_LIMIT)
    if uncompressed / compressed > limits.MAX_ARCHIVE_RATIO:
        raise ParserFailure(limits.ARCHIVE_RATIO_LIMIT)


def parse_docx(data: bytes) -> ParseResult:
    _check_archive(data)
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise ParserFailure("corrupt_structure") from exc

    # Merged cells repeat across a row in python-docx. Each underlying cell element is read once.
    tables: list[list[list[Any]]] = []
    seen: set[int] = set()
    for table in document.tables:
        rows: list[list[Any]] = []
        for row in table.rows:
            cells: list[Any] = []
            for cell in row.cells:
                if id(cell._tc) in seen:
                    cells.append(None)
                else:
                    seen.add(id(cell._tc))
                    cells.append(cell)
            rows.append(cells)
        tables.append(rows)

    cell_paragraphs = sum(
        len(cell.paragraphs) for rows in tables for cells in rows for cell in cells if cell
    )
    if len(document.paragraphs) + cell_paragraphs > limits.MAX_DOCX_ELEMENTS:
        raise ParserFailure(limits.DOCX_ELEMENT_LIMIT)

    segments = [
        SegmentDraft("docx_paragraph", {"paragraph_index": index}, paragraph.text.strip())
        for index, paragraph in enumerate(document.paragraphs, start=1)
        if paragraph.text.strip()
    ]
    for table_index, rows in enumerate(tables, start=1):
        for row_index, cells in enumerate(rows, start=1):
            for cell_index, cell in enumerate(cells, start=1):
                if cell is None:
                    continue
                for paragraph_index, paragraph in enumerate(cell.paragraphs, start=1):
                    text = paragraph.text.strip()
                    if text:
                        locator = {
                            "paragraph_index": paragraph_index,
                            "table_index": table_index,
                            "row": row_index,
                            "cell": cell_index,
                        }
                        segments.append(SegmentDraft("docx_paragraph", locator, text))
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
    """Lines split on ``\\n`` only (H-33). Offsets are code-point offsets into the decoded text.

    ``decoded[char_start:char_end]`` equals the segment text exactly, so no location is fabricated.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParserFailure("invalid_utf8") from exc
    segments: list[SegmentDraft] = []
    cursor = 0
    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if stripped:
            char_start = cursor + (len(line) - len(line.lstrip()))
            locator = {
                "line_start": number,
                "line_end": number,
                "char_start": char_start,
                "char_end": char_start + len(stripped),
            }
            segments.append(SegmentDraft("txt_line_range", locator, stripped))
        cursor += len(line) + 1
    return ParseResult(_status(segments, []), segments, [])


def parse_eml(data: bytes) -> ParseResult:
    try:
        message = cast(EmailMessage, BytesParser(policy=email_policy.default).parsebytes(data))
    except Exception as exc:
        raise ParserFailure("corrupt_structure") from exc
    if not (message.get("subject") or message.get("from") or message.get("to")):
        raise ParserFailure("corrupt_structure")

    # The Message-ID is provenance on the locator, never part of the segment text.
    provenance: dict[str, Any] = {}
    message_id = str(message.get("message-id", "")).strip()
    if message_id:
        provenance["message_id"] = message_id

    segments: list[SegmentDraft] = []
    flagged: list[str] = []
    subject = str(message.get("subject", "")).strip()
    if subject:
        segments.append(SegmentDraft("eml_part", {"eml_part": "subject", **provenance}, subject))
    body_part = message.get_body(preferencelist=("plain",))
    if body_part is not None:
        body = body_part.get_content().strip()
        if body:
            segments.append(SegmentDraft("eml_part", {"eml_part": "body", **provenance}, body))
    elif message.get_body(preferencelist=("html",)) is not None:
        # H-DEC-6 (proposed default): an HTML-only body is reported as unextractable, not dropped.
        flagged.append("eml_part:body_html_only")

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
    return ParseResult(_status(segments, flagged), segments, flagged, attachments)


PARSERS = {
    "application/pdf": parse_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": parse_docx,
    "text/markdown": parse_markdown,
    "text/plain": parse_text,
    "message/rfc822": parse_eml,
}
