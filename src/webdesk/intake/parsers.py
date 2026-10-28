"""Typed-locator parsers for the five permitted types (I-6; ARCH §13; SCHEMA §4.2; EVAL-F04).

Each parser returns draft segments with a locator of the type its file format requires. A whole-file
failure raises ``ParserFailure`` and commits nothing (I-7). The result status follows the approved
requirement schema (REQUIREMENT_SCHEMA section 4, ARCHITECTURE section 13, EVAL-F14b), and only the
following classes are returned:

- ``succeeded``: at least one segment and no flagged region.
- ``partial``: at least one committed segment AND at least one flagged region.
- ``unsupported``: no committed segment. Flagged regions, if any, are kept as
  ``unextractable_regions`` metadata. ``partial`` is never used for a zero-segment result
  (WDS ruling, QA-02).
- ``failed``: raised as ``ParserFailure``, never returned.

There is no OCR. Attachments are listed, never parsed. Only the subject and body of an EML message
become segments.

Locator extensions (H-33; approved under P4-GOV-2026-10-28): ``txt_line_range`` and ``eml_part``
carry ``start_offset`` and ``end_offset`` (the approved schema names; code points, zero-based,
end-exclusive). A ``docx_paragraph`` inside a table carries ``table_index``, ``row`` and ``cell``.
``eml_part`` also carries the message's ``message_id`` as provenance. The locator CHECK (migration
0007) requires only the keys named there, so the extra keys are admitted.

Libraries (approved defaults D-1): pypdf 5.1.0, python-docx 1.1.2. Markdown, TXT and EML use the
standard library.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from email import policy as email_policy
from email.message import EmailMessage
from email.parser import BytesParser
from typing import Any, cast

from docx import Document
from pypdf import PdfReader
from pypdf.filters import (
    CCITTFaxDecode,
    DCTDecode,
    FlateDecode,
    JPXDecode,
    LZWDecode,
    RunLengthDecode,
)
from pypdf.generic import ArrayObject

from webdesk.intake import limits

EXTRACTION_VERSION = "v1"
PARSER_LIBRARY_VERSION = "pypdf-5.1.0+python-docx-1.1.2"

# A PDF stream filter this parser cannot bound before its expansion is held in memory (D4).
PDF_FILTER_UNSUPPORTED = "pdf_filter_unsupported"


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
    status: str  # succeeded | partial | unsupported (failed is raised, see ParserFailure)
    segments: list[SegmentDraft] = field(default_factory=list)
    flagged_regions: list[str] = field(default_factory=list)
    unprocessed_attachments: list[dict[str, Any]] = field(default_factory=list)


def _status(segments: list[SegmentDraft], flagged: list[str]) -> str:
    """The approved classes (EVAL-F14b, QA-02 ruling). Partial requires a committed segment."""
    if segments:
        return "partial" if flagged else "succeeded"
    return "unsupported"


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


_TEXT_BLOCK = re.compile(rb"(?<![A-Za-z0-9])BT(?![A-Za-z0-9])")
_MAX_GRAPH_DEPTH = 8
_MAX_GRAPH_OBJECTS = 512

# Filters that are never decoded by this parser. Refusal happens at the decoder, so every spelling
# of the name
# (including #-escapes) is covered, not only the ones a byte search would find.
_REFUSED_FILTERS = ("LZWDecode", "RunLengthDecode", "DCTDecode", "JPXDecode", "CCITTFaxDecode")


class _DecodeMeter:
    """One cumulative budget for every flate decode in a PDF parse (QA-05).

    The reader calls ``FlateDecode.decode`` through ``decode_stream_data`` for every stream it
    decodes: while it opens
    the file (cross-reference and object streams), while it resolves objects, and while it extracts
    text. Metering that
    one call charges the actual decoded bytes, whatever the stream delimiters look like. Each
    distinct compressed buffer
    is charged once, so repeated reads of one stream do not consume the budget twice. Expansion is
    refused as soon as
    the running total would exceed the archive limits, before the expanded bytes are returned to the
    reader.
    """

    def __init__(self, input_size: int) -> None:
        self.input_size = input_size
        self.total = 0
        self.refusal: str | None = (
            None  # a whole-file refusal (size or ratio), kept so it is never reclassified
        )
        self.filter_refusals = 0  # a stream the reader asked to decode with a refused filter
        self._charged: dict[int, bytes] = {}  # keeps charged buffers alive so their ids stay unique

    def charge_flate(self, data: bytes) -> None:
        if self.refusal is not None:
            raise ParserFailure(self.refusal)
        if id(data) in self._charged:
            return
        size_room = limits.MAX_ARCHIVE_UNCOMPRESSED_BYTES - self.total
        ratio_room = limits.MAX_ARCHIVE_RATIO * self.input_size - self.total
        room = min(size_room, ratio_room)
        try:
            produced = zlib.decompressobj().decompress(data, room + 1)
        except zlib.error as exc:
            raise ParserFailure("corrupt_structure") from exc
        if len(produced) > room:
            self.refusal = (
                limits.ARCHIVE_SIZE_LIMIT if size_room <= ratio_room else limits.ARCHIVE_RATIO_LIMIT
            )
            raise ParserFailure(self.refusal)
        self.total += len(produced)
        self._charged[id(data)] = data


@contextmanager
def _metered_pdf_decoding(meter: _DecodeMeter) -> Iterator[None]:
    """Route every flate decode through ``meter`` and refuse the filters this parser never decodes.

    Patches the pypdf classes the reader dispatches to. The original attributes are restored on
    exit. The parser runs
    in its own child process (ARCHITECTURE section 13, H-32), so the patch does not leak into other
    work.
    """

    def refuse_filter(*_args: Any, **_kwargs: Any) -> bytes:
        # Per-stream refusal: the caller decides whether the page or the file fails.
        meter.filter_refusals += 1
        raise ParserFailure(PDF_FILTER_UNSUPPORTED)

    original_flate = vars(FlateDecode)["decode"]
    original_lzw = vars(LZWDecode)["_decodeb"]
    original_rl = vars(RunLengthDecode)["decode"]
    original_dct = vars(DCTDecode)["decode"]
    original_jpx = vars(JPXDecode)["decode"]
    original_ccitt = vars(CCITTFaxDecode)["decode"]

    original_flate_fn: Any = original_flate.__func__  # the plain function behind the staticmethod

    def metered_flate(data: bytes, decode_parms: Any = None, **kwargs: Any) -> bytes:
        meter.charge_flate(data)
        decoded: bytes = original_flate_fn(data, decode_parms, **kwargs)
        return decoded

    type.__setattr__(FlateDecode, "decode", staticmethod(metered_flate))
    type.__setattr__(LZWDecode, "_decodeb", staticmethod(refuse_filter))
    type.__setattr__(RunLengthDecode, "decode", staticmethod(refuse_filter))
    type.__setattr__(DCTDecode, "decode", staticmethod(refuse_filter))
    type.__setattr__(JPXDecode, "decode", staticmethod(refuse_filter))
    type.__setattr__(CCITTFaxDecode, "decode", staticmethod(refuse_filter))
    try:
        yield
    finally:
        type.__setattr__(FlateDecode, "decode", original_flate)
        type.__setattr__(LZWDecode, "_decodeb", original_lzw)
        type.__setattr__(RunLengthDecode, "decode", original_rl)
        type.__setattr__(DCTDecode, "decode", original_dct)
        type.__setattr__(JPXDecode, "decode", original_jpx)
        type.__setattr__(CCITTFaxDecode, "decode", original_ccitt)


class _Unbounded(Exception):
    """The reachable graph of a page exceeds this parser's walk. The page is flagged, not blank."""


class _GraphWalk:
    def __init__(self) -> None:
        self.seen: set[int] = set()
        self.count = 0

    def visit(self, obj: Any) -> bool:
        if id(obj) in self.seen:
            return False
        self.seen.add(id(obj))
        self.count += 1
        if self.count > _MAX_GRAPH_OBJECTS:
            raise _Unbounded
        return True


def _stream_has_text(stream: Any) -> bool:
    try:
        data = stream.get_data()
    except ParserFailure:
        raise
    except Exception as exc:
        raise _Unbounded from exc
    return _TEXT_BLOCK.search(data) is not None


def _resources_have_text(resources: Any, walk: _GraphWalk, depth: int) -> bool:
    if depth > _MAX_GRAPH_DEPTH:
        raise _Unbounded
    resources = None if resources is None else resources.get_object()
    if resources is None:
        return False
    found = False
    for category in ("/XObject", "/Pattern", "/Font"):
        group = resources.get(category)
        if group is None:
            continue
        for ref in group.get_object().values():
            obj = ref.get_object()
            if not walk.visit(obj):
                continue
            if category == "/XObject" and obj.get("/Subtype") == "/Form":
                found = _stream_has_text(obj) or found
                found = _resources_have_text(obj.get("/Resources"), walk, depth + 1) or found
            elif category == "/Pattern" and obj.get("/PatternType") == 1:
                found = _stream_has_text(obj) or found
                found = _resources_have_text(obj.get("/Resources"), walk, depth + 1) or found
            elif category == "/Font" and obj.get("/Subtype") == "/Type3":
                procs = obj.get("/CharProcs")
                if procs is not None:
                    for proc in procs.get_object().values():
                        proc_obj = proc.get_object()
                        if walk.visit(proc_obj):
                            found = _stream_has_text(proc_obj) or found
                found = _resources_have_text(obj.get("/Resources"), walk, depth + 1) or found
    return found


def _annotations_have_text(page: Any, walk: _GraphWalk) -> bool:
    annots = page.get("/Annots")
    if annots is None:
        return False
    found = False
    for ref in annots.get_object():
        annot = ref.get_object()
        appearance = annot.get("/AP")
        if appearance is None:
            continue
        normal = appearance.get_object().get("/N")
        if normal is None:
            continue
        normal = normal.get_object()
        streams = list(normal.values()) if not hasattr(normal, "get_data") else [normal]
        for item in streams:
            stream = item.get_object()
            if not walk.visit(stream):
                continue
            found = _stream_has_text(stream) or found
            found = _resources_have_text(stream.get("/Resources"), walk, 1) or found
    return found


def _page_has_hidden_text(page: Any) -> bool:
    """True when a form, pattern, Type 3 glyph or annotation reachable from the page has text.

    pypdf does not extract text from these, so their text would otherwise be lost without a flag.
    Any walk that
    cannot finish within the bounds reports True: the page is then flagged, not read as blank
    (QA-06).
    """
    walk = _GraphWalk()
    try:
        return _resources_have_text(page.get("/Resources"), walk, 0) or _annotations_have_text(
            page, walk
        )
    except _Unbounded:
        return True


def _bounded_stream(stream: Any, budget: int, meter: _DecodeMeter) -> bytes:
    """Decoded bytes of one page content stream, never more than ``budget + 1`` (D4, H-31).

    Used for the per-page content bound. Only an unfiltered stream and a FlateDecode stream without
    predictor
    parameters are bounded here. Any other filter raises ``PDF_FILTER_UNSUPPORTED``.
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
        meter.charge_flate(raw)
        try:
            return zlib.decompressobj().decompress(raw, budget + 1)
        except zlib.error as exc:
            raise ParserFailure("corrupt_structure") from exc
    raise ParserFailure(PDF_FILTER_UNSUPPORTED)


def _bound_page_content(page: Any, meter: _DecodeMeter) -> None:
    """The decoded size of a page's content streams, together, is bounded by the per-page limit (D4,
    H-31)."""
    budget = limits.MAX_PDF_PAGE_STREAM_BYTES
    contents = page.get("/Contents")
    if contents is None:
        return
    resolved = contents.get_object()
    streams = list(resolved) if isinstance(resolved, ArrayObject) else [resolved]
    used = 0
    for stream in streams:
        used += len(_bounded_stream(stream, budget - used, meter))
        if used > budget:
            raise ParserFailure(limits.PDF_STREAM_LIMIT)


def open_pdf_structure(data: bytes) -> bool:
    """Open a PDF the way the parser does, under the same meter, and report whether it is encrypted.

    Upload admission calls this. It is the first place a PDF is opened, so it must not decode
    outside the bound (QA-05).
    Raises ``ParserFailure`` with the same classes the parser uses.
    """
    meter = _DecodeMeter(len(data))
    with _metered_pdf_decoding(meter):
        try:
            reader = PdfReader(io.BytesIO(data))
            encrypted = bool(reader.is_encrypted)
            if not encrypted:
                _ = len(reader.pages)
        except ParserFailure:
            raise
        except Exception as exc:
            if meter.refusal is not None:
                raise ParserFailure(meter.refusal) from exc
            if meter.filter_refusals:
                raise ParserFailure(PDF_FILTER_UNSUPPORTED) from exc
            raise ParserFailure("corrupt_structure") from exc
    if meter.refusal is not None:
        raise ParserFailure(meter.refusal)
    return encrypted


def parse_pdf(data: bytes) -> ParseResult:
    meter = _DecodeMeter(len(data))
    with _metered_pdf_decoding(meter):
        return _parse_pdf_metered(data, meter)


def _parse_pdf_metered(data: bytes, meter: _DecodeMeter) -> ParseResult:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParserFailure("encrypted_not_permitted")
        pages = list(reader.pages)
    except ParserFailure:
        raise
    except Exception as exc:
        # The reader can swallow a refusal while it rebuilds the cross-reference table. The meter
        # keeps it.
        if meter.refusal is not None:
            raise ParserFailure(meter.refusal) from exc
        if meter.filter_refusals:
            raise ParserFailure(PDF_FILTER_UNSUPPORTED) from exc
        raise ParserFailure("corrupt_structure") from exc
    if len(pages) > limits.MAX_PDF_PAGES:
        raise ParserFailure(limits.PDF_PAGE_LIMIT)

    segments: list[SegmentDraft] = []
    flagged: list[str] = []
    for number, page in enumerate(pages, start=1):
        try:
            _bound_page_content(page, meter)
            text = (page.extract_text() or "").strip()
            hidden = _page_has_hidden_text(page)
        except ParserFailure as exc:
            if exc.reason == PDF_FILTER_UNSUPPORTED:
                flagged.append(f"pdf_page:{number}")
                continue
            raise
        except Exception:
            flagged.append(f"pdf_page:{number}")
            continue
        if text:
            segments.append(SegmentDraft("pdf_page", {"page_number": number}, text))
        if hidden or (not text and _has_image(page)):
            # H-33 and QA-06: text that pypdf cannot extract is flagged, never silently omitted. An
            # image-only page
            # holds content that is not text. There is no OCR, so it is reported, not read as blank.
            flagged.append(f"pdf_page:{number}")
    if meter.refusal is not None:
        raise ParserFailure(meter.refusal)
    if meter.refusal is not None:
        raise ParserFailure(meter.refusal)
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

    ``decoded[start_offset:end_offset]`` equals the segment text exactly, so no location is
    fabricated.
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
            start_offset = cursor + (len(line) - len(line.lstrip()))
            locator = {
                "line_start": number,
                "line_end": number,
                "start_offset": start_offset,
                "end_offset": start_offset + len(stripped),
            }
            segments.append(SegmentDraft("txt_line_range", locator, stripped))
        cursor += len(line) + 1
    return ParseResult(_status(segments, []), segments, [])


def _normalized(text: str) -> str:
    """The normalized part text that EML offsets refer to: NFC, without surrounding whitespace."""
    return unicodedata.normalize("NFC", text).strip()


def _eml_part(part: str, text: str, provenance: dict[str, Any]) -> SegmentDraft:
    """An ``eml_part`` segment. Offsets are 0 and the normalized text length (approved P4-GOV)."""
    locator = {"eml_part": part, "start_offset": 0, "end_offset": len(text), **provenance}
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
