"""Regression tests for the Phase 4 defects D1 to D4 and the approved EML offsets (no database).

Each test builds its input in memory. Each names the defect it guards in its docstring.
"""

from __future__ import annotations

import io
import os
import struct
import zipfile
import zlib
from typing import Any

import pytest
from docx import Document

from tests.support.parse_corpus import build_pdf
from webdesk.intake import limits, parsers
from webdesk.intake.parsers import (
    PDF_FILTER_UNSUPPORTED,
    ParserFailure,
    _bounded_stream,
    _check_archive,
    parse_docx,
    parse_eml,
    parse_pdf,
)

MiB = 1024 * 1024


def _pdf_objects(
    page_resources: bytes, content: bytes, content_filter: bytes = b""
) -> dict[int, bytes]:
    """A one-page PDF whose content stream is ``content`` with an optional filter entry."""
    head = b"<< /Length %d %s >>\nstream\n" % (len(content), content_filter)
    stream = head + content + b"\nendstream"
    return {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << "
        + page_resources
        + b" >> >>",
        4: stream,
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }


def _assemble(objects: dict[int, bytes]) -> bytes:
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = out.tell()
        out.write(f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n")
    xref = out.tell()
    size = max(objects) + 1
    out.write(f"xref\n0 {size}\n0000000000 65535 f \n".encode())
    for number in range(1, size):
        if number in offsets:
            out.write(f"{offsets[number]:010d} 00000 n \n".encode())
        else:
            out.write(b"0000000000 65535 f \n")
    out.write(f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


# D1: flagged regions survive a result with no text segment.


def test_d1_an_html_only_email_with_no_subject_is_partial_and_keeps_its_flag() -> None:
    data = b"From: a@wds-test.example\nTo: b@wds-test.example\n"
    data += b"Content-Type: text/html; charset=utf-8\n\n<p>only html</p>\n"
    result = parse_eml(data)
    assert result.status == "partial"
    assert result.segments == []
    assert result.flagged_regions == ["eml_part:body_html_only"]


def test_d1_an_image_only_pdf_page_is_partial_with_zero_segments() -> None:
    result = parse_pdf(build_pdf([None]))
    assert result.status == "partial"
    assert result.segments == []
    assert result.flagged_regions == ["pdf_page:1"]


def test_d1_a_clean_file_with_no_text_and_no_flag_stays_unsupported() -> None:
    result = parse_pdf(build_pdf([""]))
    assert result.status == "unsupported"
    assert result.flagged_regions == []


# D2: DOCX expansion is measured on actual bytes, never on declared sizes.


def _zip_with(member: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", member)
    return buffer.getvalue()


def test_d2_a_member_whose_declared_size_is_understated_is_refused_as_malformed() -> None:
    data = bytearray(_zip_with(b"A" * (5 * MiB)))
    central = data.rfind(b"PK\x01\x02")
    local = data.find(b"PK\x03\x04")
    data[central + 24 : central + 28] = struct.pack("<I", 10)
    data[local + 22 : local + 26] = struct.pack("<I", 10)
    with pytest.raises(ParserFailure) as exc:
        _check_archive(bytes(data))
    assert exc.value.reason == "corrupt_structure"


def test_d2_an_honest_archive_over_the_uncompressed_limit_is_refused_by_actual_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limits, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1 * MiB)
    # Incompressible content, so the ratio check cannot be the one that fires.
    data = _zip_with(os.urandom(2 * MiB))
    with pytest.raises(ParserFailure) as exc:
        _check_archive(data)
    assert exc.value.reason == limits.ARCHIVE_SIZE_LIMIT


def test_d2_a_small_honest_archive_passes() -> None:
    _check_archive(_zip_with(b"<w:document/>" * 10))


# D3: a table nested in a cell is reported, not silently dropped.


def test_d3_a_nested_table_is_a_flagged_region_and_its_text_is_not_invented() -> None:
    document = Document()
    table = document.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    cell.text = "outer cell text"
    inner = cell.add_table(rows=1, cols=1)
    inner.rows[0].cells[0].text = "inner nested text"
    buffer = io.BytesIO()
    document.save(buffer)

    result = parse_docx(buffer.getvalue())
    assert result.status == "partial"
    assert result.flagged_regions == ["docx_nested_table:1.1.1.1"]
    texts = [segment.text for segment in result.segments]
    assert texts == ["outer cell text"]


# D4: PDF stream expansion is bounded before it is held in memory.


class _FakeStream:
    """The subset of a pypdf stream object the bounded decoder reads."""

    def __init__(self, raw: bytes, filters: Any = None, decode_parms: bool = False) -> None:
        self._data = raw
        self._entries: dict[str, Any] = {}
        if filters is not None:
            self._entries["/Filter"] = filters
        if decode_parms:
            self._entries["/DecodeParms"] = {}

    def get_object(self) -> _FakeStream:
        return self

    def get(self, key: str, default: Any = None) -> Any:
        return self._entries.get(key, default)

    def __contains__(self, key: object) -> bool:
        return key in self._entries


def test_d4_a_flate_stream_expanding_past_the_budget_is_never_held_whole() -> None:
    compressed = zlib.compress(b" " * (60 * MiB))
    budget = limits.MAX_PDF_PAGE_STREAM_BYTES
    decoded = _bounded_stream(_FakeStream(compressed, filters="/FlateDecode"), budget)
    assert len(decoded) == budget + 1


def test_d4_a_page_whose_decoded_content_exceeds_the_limit_is_refused() -> None:
    compressed = zlib.compress(b" " * (12 * MiB))
    data = _assemble(
        _pdf_objects(
            b"/Font << /F1 5 0 R >>",
            compressed,
            content_filter=b"/Filter /FlateDecode",
        )
    )
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(data)
    assert exc.value.reason == limits.PDF_STREAM_LIMIT


def test_d4_text_in_a_form_xobject_is_flagged_not_silently_omitted() -> None:
    body = b"BT (hidden) Tj ET"
    form = b"<< /Type /XObject /Subtype /Form /BBox [0 0 10 10] /Length %d >>\nstream\n" % len(body)
    form += body + b"\nendstream"
    objects = _pdf_objects(b"/XObject << /Fm0 6 0 R >>", b"q /Fm0 Do Q")
    objects[6] = form
    result = parse_pdf(_assemble(objects))
    assert result.status == "partial"
    assert result.flagged_regions == ["pdf_page:1"]


def test_d4_an_unbounded_filter_flags_its_page_and_does_not_fail_the_file() -> None:
    objects = _pdf_objects(b"/Font << /F1 5 0 R >>", b"BT ET", content_filter=b"/Filter /LZWDecode")
    result = parse_pdf(_assemble(objects))
    assert result.status == "partial"
    assert result.flagged_regions == ["pdf_page:1"]


def test_d4_the_unsupported_filter_is_the_named_refusal() -> None:
    with pytest.raises(ParserFailure) as exc:
        _bounded_stream(_FakeStream(b"x", filters="/LZWDecode"), 10)
    assert exc.value.reason == PDF_FILTER_UNSUPPORTED


def test_d4_a_predictor_stream_is_not_decoded_unbounded() -> None:
    with pytest.raises(ParserFailure) as exc:
        _bounded_stream(_FakeStream(b"x", filters="/FlateDecode", decode_parms=True), 10)
    assert exc.value.reason == PDF_FILTER_UNSUPPORTED


# EML offsets (approved P4-GOV-2026-10-28): normalized text, zero-based, end-exclusive.


def test_eml_offsets_are_relative_to_the_nfc_normalized_part_text() -> None:
    decomposed = "Café plan"  # NFD: "e" plus a combining acute accent
    data = f"Subject: {decomposed}\nFrom: a@wds-test.example\n\nbody\n".encode()
    result = parse_eml(data)
    subject = result.segments[0]
    assert subject.text == "Café plan"
    assert subject.locator["char_start"] == 0
    assert subject.locator["char_end"] == len(subject.text) == 9


def test_eml_body_offsets_follow_the_stripped_text() -> None:
    result = parse_eml(b"Subject: s\nFrom: a@wds-test.example\n\n   hello there   \n")
    body = result.segments[-1]
    assert body.text == "hello there"
    assert body.locator == {"eml_part": "body", "char_start": 0, "char_end": 11}
    assert body.text[body.locator["char_start"] : body.locator["char_end"]] == body.text


def test_the_parser_module_exposes_the_stable_filter_class() -> None:
    assert parsers.PDF_FILTER_UNSUPPORTED == "pdf_filter_unsupported"
