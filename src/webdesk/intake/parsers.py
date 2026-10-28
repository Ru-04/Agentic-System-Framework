"""Typed-locator parsers for the five permitted types (I-6; ARCH §13; SCHEMA §4.2; EVAL-F04).

Each parser returns draft segments with a locator of the type its file format requires. A whole-file
failure raises ``ParserFailure`` and commits nothing (I-7). A single unreadable region is
recorded as ``flagged_regions`` and the parse becomes ``partial``, even when no text segment is
produced, so the gap is never silent. A file with no flagged region and no extractable text is
``unsupported``. There is no OCR. Attachments are listed, never parsed. Only the subject and
body of an EML message become segments.

Locator extensions (H-33; approved under P4-GOV-2026-10-28): ``txt_line_range`` carries character
offsets into the decoded UTF-8 text; a ``docx_paragraph`` inside a table carries ``table_index``,
``row`` and ``cell``; ``eml_part`` carries ``char_start`` and ``char_end`` (code points,
end-exclusive, relative to the normalized part text) and the message's ``message_id`` as
provenance. The locator CHECK (migration 0007) requires only the keys named there, so the extra
keys are admitted.

Libraries (approved defaults D-1): pypdf 5.1.0, python-docx 1.1.2. Markdown, TXT and EML use the
standard library.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass, field
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any, cast

from docx import Document
from pypdf import PdfReader
from pypdf.generic import ArrayObject

from webdesk.intake import limits

EXTRACTION_VERSION = "v1"
PARSER_LIBRARY_VERSION = "pypdf-5.1.0+python-docx-1.1.2"

# A PDF stream filter this parser cannot bound before its expansion is held in memory (D4).
PDF_FILTER_UNSUPPORTED = "pdf_filter_unsupported"
_TEXT_BLOCK = re.compile(rb"(?:^|\s)BT(?:\s|$)")


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
    """Any flagged region makes the result partial, with or without segments (D1, H-34)."""
    if flagged:
        return "partial"
    return "succeeded" if segments else "unsupported"


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


def _bounded_stream(stream: Any, budget: int) -> bytes:
    """Decoded bytes of one stream, never more than ``budget + 1`` (D4, H-31).

    Only two forms can be bounded before their expansion is held in memory: an unfiltered stream,
    and a FlateDecode stream without predictor parameters, which is decompressed with an output
    bound. Any other filter raises ``PDF_FILTER_UNSUPPORTED``.
    """
    obj = stream.get_object()
    raw = bytes(obj._data)
    if "/DecodeParms" in obj or "/DP" in obj:
        names = None
    else:
        filters = obj.get("/Filter")
        if filters is None:
            names = []
        elif isinstance(filters, ArrayObject):
            names = [str(item.get_object()) for item in filters]
        else:
            names = [str(filters)]
    if names == []:
        return raw[: budget + 1]
    if names == ["/FlateDecode"]:
        try:
            return zlib.decompressobj().decompress(raw, budget + 1)
        except zlib.error as exc:
            raise ParserFailure("corrupt_structure") from exc
    raise ParserFailure(PDF_FILTER_UNSUPPORTED)


def _direct_forms(page: Any) -> list[Any]:
    """Form XObjects named directly in the page's resources. Nested forms are not followed."""
    resources = page.get("/Resources")
    if resources is None:
        return []
    xobjects = resources.get_object().get("/XObject")
    if xobjects is None:
        return []
    return [
        obj
        for obj in (ref.get_object() for ref in xobjects.get_object().values())
        if obj.get("/Subtype") == "/Form"
    ]


def _bound_page(page: Any) -> bool:
    """Bound the decoded size of a page's content and direct form streams together (D4, H-31).

    Raises ``ParserFailure(PDF_STREAM_LIMIT)`` when the decoded total exceeds the limit. Returns
    True when a direct form holds a text block, which pypdf does not extract.
    """
    budget = limits.MAX_PDF_PAGE_STREAM_BYTES
    used = 0
    contents = page.get("/Contents")
    if contents is not None:
        resolved = contents.get_object()
        streams = list(resolved) if isinstance(resolved, ArrayObject) else [resolved]
        for stream in streams:
            used += len(_bounded_stream(stream, budget - used))
            if used > budget:
                raise ParserFailure(limits.PDF_STREAM_LIMIT)
    hidden_text = False
    for form in _direct_forms(page):
        data = _bounded_stream(form, budget - used)
        used += len(data)
        if used > budget:
            raise ParserFailure(limits.PDF_STREAM_LIMIT)
        if _TEXT_BLOCK.search(data):
            hidden_text = True
    return hidden_text


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
            hidden_text = _bound_page(page)
            text = (page.extract_text() or "").strip()
        except ParserFailure as exc:
            if exc.reason == PDF_FILTER_UNSUPPORTED:
                # The page cannot be bounded: report its region and keep the rest of the file.
                flagged.append(f"pdf_page:{number}")
                continue
            raise
        except Exception:
            flagged.append(f"pdf_page:{number}")
            continue
        if text:
            segments.append(SegmentDraft("pdf_page", {"page_number": number}, text))
        if hidden_text or (not text and _has_image(page)):
            # H-33: an image-only page holds content that is not text, and text inside a form
            # XObject is not extracted. There is no OCR, so both are reported as unextractable,
            # not read as blank.
            flagged.append(f"pdf_page:{number}")
    return ParseResult(_status(segments, flagged), segments, flagged)


def _check_archive(data: bytes) -> None:
    """Bound a ZIP container by the bytes it actually expands to (H-31, D2).

    Declared sizes in the central directory are not trusted. Every member is read in full, with
    the total counted as it is read, so a crafted header cannot understate the expansion. A member
    whose actual size differs from its declared size is refused as malformed. The inflate ratio is
    measured against the whole container.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ParserFailure("corrupt_structure") from exc
    total = 0
    with archive:
        for info in archive.infolist():
            actual = 0
            try:
                with archive.open(info) as member:
                    while chunk := member.read(65536):
                        actual += len(chunk)
                        total += len(chunk)
                        if total > limits.MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                            raise ParserFailure(limits.ARCHIVE_SIZE_LIMIT)
                        if total > limits.MAX_ARCHIVE_RATIO * len(data):
                            raise ParserFailure(limits.ARCHIVE_RATIO_LIMIT)
            except ParserFailure:
                raise
            except (
                zipfile.BadZipFile,
                RuntimeError,
                NotImplementedError,
                OSError,
                zlib.error,
            ) as exc:
                raise ParserFailure("corrupt_structure") from exc
            if actual != info.file_size:
                raise ParserFailure("corrupt_structure")


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
    flagged: list[str] = []
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
                # A table nested in a cell has no approved locator. Report it; do not drop it (D3).
                for nested_index, _ in enumerate(cell.tables, start=1):
                    flagged.append(
                        f"docx_nested_table:{table_index}.{row_index}.{cell_index}.{nested_index}"
                    )
    return ParseResult(_status(segments, flagged), segments, flagged)


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


def _normalized(text: str) -> str:
    """The normalized part text that EML offsets refer to: NFC, without surrounding whitespace."""
    return unicodedata.normalize("NFC", text).strip()


def _eml_part(part: str, text: str, provenance: dict[str, Any]) -> SegmentDraft:
    """An ``eml_part`` segment. Offsets are 0 and the normalized text length (approved P4-GOV)."""
    locator = {"eml_part": part, "char_start": 0, "char_end": len(text), **provenance}
    return SegmentDraft("eml_part", locator, text)


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
    subject = _normalized(str(message.get("subject", "")))
    if subject:
        segments.append(_eml_part("subject", subject, provenance))
    body_part = message.get_body(preferencelist=("plain",))
    if body_part is not None:
        body = _normalized(str(body_part.get_content()))
        if body:
            segments.append(_eml_part("body", body, provenance))
    elif message.get_body(preferencelist=("html",)) is not None:
        # H-DEC-6 (approved): an HTML-only body is partial and unextractable. The region is kept.
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
