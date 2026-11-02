"""Regression tests for Phase 4 defects, approved status classes and EML offsets (no database).

Each test builds its input in memory and names the defect or requirement it guards.
Expectations follow the approved specification (REQUIREMENT_SCHEMA section 4,
EVAL-F14b) and the WDS ruling QA-02, not the earlier implementation.
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
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from tests.support.parse_corpus import build_pdf
from webdesk.intake import limits, parsers
from webdesk.intake.parse_service import _outcome_detail
from webdesk.intake.parsers import (
    PDF_FILTER_UNSUPPORTED,
    ParseResult,
    ParserFailure,
    SegmentDraft,
    _bounded_stream,
    _check_archive,
    _DecodeMeter,
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


# --- Approved status classes (QA-02 ruling) ---------------------------------------------------


def test_a_fully_valid_extraction_is_succeeded_with_no_flagged_region() -> None:
    result = parse_pdf(build_pdf(["first page", "second page"]))
    assert result.status == "succeeded"
    assert result.flagged_regions == []
    assert len(result.segments) == 2


def test_partial_needs_at_least_one_committed_segment_and_one_flagged_region() -> None:
    result = parse_pdf(build_pdf(["readable page", None]))
    assert result.status == "partial"
    assert [s.locator for s in result.segments] == [{"page_number": 1}]
    assert result.flagged_regions == ["pdf_page:2"]


def test_d1_an_image_only_pdf_with_no_text_is_unsupported_and_keeps_its_page_as_metadata() -> None:
    """QA-01: ARCHITECTURE section 13 and EVAL-F14b(c) require unsupported, never partial."""
    result = parse_pdf(build_pdf([None]))
    assert result.status == "unsupported"
    assert result.segments == []
    assert result.flagged_regions == ["pdf_page:1"]


def test_d1_an_html_only_email_without_subject_is_unsupported_with_its_region() -> None:
    """QA-02: zero committed segments can never be partial."""
    data = b"From: a@wds-test.example\nTo: b@wds-test.example\n"
    data += b"Content-Type: text/html; charset=utf-8\n\n<p>only html</p>\n"
    result = parse_eml(data)
    assert result.status == "unsupported"
    assert result.segments == []
    assert result.flagged_regions == ["eml_part:body_html_only"]


def test_an_html_only_email_with_a_subject_is_partial_beside_its_subject_segment() -> None:
    data = (
        b"Subject: status\nFrom: a@wds-test.example\n"
        b"Content-Type: text/html; charset=utf-8\n\n<p>x</p>\n"
    )
    result = parse_eml(data)
    assert result.status == "partial"
    assert [s.locator["eml_part"] for s in result.segments] == ["subject"]
    assert result.flagged_regions == ["eml_part:body_html_only"]


def test_a_clean_file_with_no_text_and_no_flag_stays_unsupported() -> None:
    result = parse_pdf(build_pdf([""]))
    assert result.status == "unsupported"
    assert result.flagged_regions == []


def test_a_corrupt_file_is_a_parser_failure_and_is_never_returned_as_a_status() -> None:
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(b"%PDF-1.4 not a document")
    assert exc.value.reason == "corrupt_structure"


def test_persisted_outcome_detail_keeps_partial_and_unsupported_metadata_under_distinct_keys() -> (
    None
):
    partial = ParseResult(
        "partial", [SegmentDraft("pdf_page", {"page_number": 1}, "x")], ["pdf_page:2"]
    )
    unsupported = ParseResult("unsupported", [], ["pdf_page:1"])
    clean = ParseResult("unsupported", [], [])
    succeeded = ParseResult("succeeded", [SegmentDraft("pdf_page", {"page_number": 1}, "x")], [])
    assert _outcome_detail(partial) == {"class": "partial", "flagged_regions": ["pdf_page:2"]}
    assert _outcome_detail(unsupported) == {
        "class": "unsupported",
        "unextractable_regions": ["pdf_page:1"],
    }
    assert _outcome_detail(clean) is None
    assert _outcome_detail(succeeded) is None


# --- D2: DOCX expansion is measured on actual bytes, never on declared sizes. -----------------


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


# --- D3: a table nested in a cell is reported, not silently dropped. --------------------------


def _docx_with_nested(outer_text: str | None) -> bytes:
    document = Document()
    table = document.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    if outer_text is not None:
        cell.text = outer_text
    inner = cell.add_table(rows=1, cols=1)
    inner.rows[0].cells[0].text = "inner nested text"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_d3_a_nested_table_is_a_flagged_region_and_its_text_is_not_invented() -> None:
    result = parse_docx(_docx_with_nested("outer cell text"))
    assert result.status == "partial"
    assert result.flagged_regions == ["docx_nested_table:1.1.1.1"]
    assert [segment.text for segment in result.segments] == ["outer cell text"]


def test_d3_a_nested_table_with_no_other_text_is_unsupported_with_its_region_as_metadata() -> None:
    result = parse_docx(_docx_with_nested(None))
    assert result.status == "unsupported"
    assert result.segments == []
    assert result.flagged_regions == ["docx_nested_table:1.1.1.1"]


# --- F-3: DOCX text boxes are extracted; headers and footers are flagged, not extracted. -----

_DRAWING_NS = (
    'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
)


def _textbox_run(inner: str) -> str:
    """A run holding a DrawingML text box whose w:txbxContent is ``inner``."""
    return (
        f'<w:r {nsdecls("w")} {_DRAWING_NS}><w:drawing><wp:inline>'
        '<wp:extent cx="1" cy="1"/><a:graphic><a:graphicData '
        'uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
        f"<wps:wsp><wps:txbx><w:txbxContent>{inner}</w:txbxContent></wps:txbx></wps:wsp>"
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
    )


def _paragraph_xml(text: str) -> str:
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


def _docx_bytes(document: Any) -> bytes:
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_f3_a_text_box_paragraph_is_a_segment_with_a_textbox_locator() -> None:
    document = Document()
    document.add_paragraph("Visible body paragraph.")
    document.paragraphs[-1]._p.append(parse_xml(_textbox_run(_paragraph_xml("BOX_REQUIREMENT"))))
    result = parse_docx(_docx_bytes(document))
    assert [segment.text for segment in result.segments] == [
        "Visible body paragraph.",
        "BOX_REQUIREMENT",
    ]
    assert result.segments[1].locator == {"paragraph_index": 1, "textbox_index": 1}
    assert result.flagged_regions == []
    assert result.status == "succeeded"


def test_f3_a_text_box_in_a_table_cell_is_extracted_once() -> None:
    document = Document()
    cell = document.add_table(rows=1, cols=1).rows[0].cells[0]
    cell.paragraphs[0]._p.append(parse_xml(_textbox_run(_paragraph_xml("CELL_BOX_TEXT"))))
    result = parse_docx(_docx_bytes(document))
    assert [segment.text for segment in result.segments] == ["CELL_BOX_TEXT"]
    assert result.flagged_regions == []


def test_f3_a_text_box_offered_as_a_fallback_and_a_choice_is_extracted_once() -> None:
    """A Word text box is stored twice: a DrawingML choice and a VML fallback. Only the choice is
    read, so its text is not committed twice."""
    alternate = (
        '<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:v="urn:schemas-microsoft-com:vml">'
        f'<mc:Choice Requires="wps">{_textbox_run(_paragraph_xml("ONCE_ONLY_TEXT"))}</mc:Choice>'
        "<mc:Fallback><w:r><w:pict><v:shape><v:textbox><w:txbxContent>"
        f"{_paragraph_xml('ONCE_ONLY_TEXT')}"
        "</w:txbxContent></v:textbox></v:shape></w:pict></w:r></mc:Fallback>"
        "</mc:AlternateContent>"
    )
    document = Document()
    document.add_paragraph("Body.")
    document.paragraphs[-1]._p.append(parse_xml(f"<w:wrap {nsdecls('w')}>{alternate}</w:wrap>")[0])
    result = parse_docx(_docx_bytes(document))
    assert [segment.text for segment in result.segments] == ["Body.", "ONCE_ONLY_TEXT"]


def test_f3_a_text_box_holding_a_table_is_flagged_not_dropped() -> None:
    document = Document()
    document.add_paragraph("Body.")
    table = "<w:tbl><w:tblPr/><w:tblGrid/><w:tr><w:tc>" + _paragraph_xml("T") + "</w:tc></w:tr></w:tbl>"
    document.paragraphs[-1]._p.append(parse_xml(_textbox_run(table)))
    result = parse_docx(_docx_bytes(document))
    assert result.flagged_regions == ["docx_textbox:1"]
    assert result.status == "partial"


def test_f3_footer_text_is_flagged_as_an_unextracted_region_and_not_extracted() -> None:
    document = Document()
    document.add_paragraph("Visible body paragraph.")
    document.sections[0].footer.paragraphs[0].text = "FOOTER_REQUIREMENT_TEXT"
    result = parse_docx(_docx_bytes(document))
    assert [segment.text for segment in result.segments] == ["Visible body paragraph."]
    assert "FOOTER_REQUIREMENT_TEXT" not in [segment.text for segment in result.segments]
    assert result.flagged_regions == ["docx_footer:1"]
    assert result.status == "partial"


def test_f3_header_text_is_flagged_as_an_unextracted_region() -> None:
    document = Document()
    document.add_paragraph("Visible body paragraph.")
    document.sections[0].header.paragraphs[0].text = "HEADER_TEXT"
    result = parse_docx(_docx_bytes(document))
    assert result.flagged_regions == ["docx_header:1"]


def test_f3_an_empty_header_and_footer_are_not_flagged() -> None:
    """Negative control: a header or footer with no text is not an unextracted region."""
    document = Document()
    document.add_paragraph("Visible body paragraph.")
    document.sections[0].header.paragraphs[0].text = "   "
    document.sections[0].footer.paragraphs[0].text = ""
    result = parse_docx(_docx_bytes(document))
    assert result.status == "succeeded"
    assert result.flagged_regions == []


# --- D4: PDF expansion is bounded before any reader holds it in memory. ----------------------


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
    # The meter refuses the expansion while it is produced, so the expanded bytes are never all held
    # in memory.
    meter = _DecodeMeter(len(compressed))
    with pytest.raises(ParserFailure) as exc:
        _bounded_stream(_FakeStream(compressed, filters="/FlateDecode"), budget, meter)
    assert exc.value.reason == limits.ARCHIVE_RATIO_LIMIT


def test_d4_a_page_whose_decoded_content_exceeds_the_per_page_limit_is_refused() -> None:
    # Incompressible content: the file check passes, so the per-page limit decides.
    compressed = zlib.compress(os.urandom(11 * MiB))
    data = _assemble(
        _pdf_objects(b"/Font << /F1 5 0 R >>", compressed, content_filter=b"/Filter /FlateDecode")
    )
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(data)
    assert exc.value.reason == limits.PDF_STREAM_LIMIT


def test_d4_a_compressible_expansion_is_refused_by_the_file_level_ratio_before_any_reader() -> None:
    compressed = zlib.compress(b" " * (12 * MiB))
    data = _assemble(
        _pdf_objects(b"/Font << /F1 5 0 R >>", compressed, content_filter=b"/Filter /FlateDecode")
    )
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(data)
    assert exc.value.reason == limits.ARCHIVE_RATIO_LIMIT


def test_d4_form_xobject_text_is_flagged_and_zero_text_is_unsupported() -> None:
    body = b"BT (hidden) Tj ET"
    form = b"<< /Type /XObject /Subtype /Form /BBox [0 0 10 10] /Length %d >>\nstream\n" % len(body)
    form += body + b"\nendstream"
    objects = _pdf_objects(b"/XObject << /Fm0 6 0 R >>", b"q /Fm0 Do Q")
    objects[6] = form
    result = parse_pdf(_assemble(objects))
    assert result.status == "unsupported"
    assert result.segments == []
    assert result.flagged_regions == ["pdf_page:1"]


def test_d4_an_lzw_page_stream_flags_its_page_and_is_never_decoded() -> None:
    objects = _pdf_objects(b"/Font << /F1 5 0 R >>", b"BT ET", content_filter=b"/Filter /LZWDecode")
    result = parse_pdf(_assemble(objects))
    assert result.status == "unsupported"
    assert result.flagged_regions == ["pdf_page:1"]


def test_d4_the_unsupported_filter_is_the_named_refusal_for_a_page_stream() -> None:
    with pytest.raises(ParserFailure) as exc:
        _bounded_stream(_FakeStream(b"x", filters="/LZWDecode"), 10, _DecodeMeter(1))
    assert exc.value.reason == PDF_FILTER_UNSUPPORTED


def test_d4_a_predictor_stream_is_not_decoded_unbounded() -> None:
    with pytest.raises(ParserFailure) as exc:
        _bounded_stream(
            _FakeStream(b"x", filters="/FlateDecode", decode_parms=True), 10, _DecodeMeter(1)
        )
    assert exc.value.reason == PDF_FILTER_UNSUPPORTED


def test_d4_a_modest_flate_content_stream_within_the_limits_is_accepted() -> None:
    compressed = zlib.compress(b"BT /F1 12 Tf 72 720 Td (within limits) Tj ET")
    data = _assemble(
        _pdf_objects(b"/Font << /F1 5 0 R >>", compressed, content_filter=b"/Filter /FlateDecode")
    )
    result = parse_pdf(data)
    assert result.status == "succeeded"
    assert "within limits" in result.segments[0].text


def _object_stream_pdf(padding: int) -> bytes:
    """Page objects in a flate object stream that expands by ``padding`` bytes."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>",
    ]
    header = b""
    body = b""
    for index, obj in enumerate(objs, start=1):
        header += f"{index} {len(body)} ".encode()
        body += obj + b" "
    stream_data = header + body + b" " * padding
    compressed = zlib.compress(stream_data, 9)
    objstm = (
        (
            f"<< /Type /ObjStm /N 3 /First {len(header)} /Filter /FlateDecode "
            f"/Length {len(compressed)} >>\nstream\n"
        ).encode()
        + compressed
        + b"\nendstream"
    )
    content = b"BT ET"
    content_obj = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
    out = bytearray(b"%PDF-1.5\n")
    offsets: dict[int, int] = {}
    offsets[4] = len(out)
    out += b"4 0 obj\n" + objstm + b"\nendobj\n"
    offsets[5] = len(out)
    out += b"5 0 obj\n" + content_obj + b"\nendobj\n"
    rows = b"".join(
        [struct.pack(">BIH", 0, 0, 65535)]
        + [struct.pack(">BIH", 2, 4, index) for index in range(3)]
        + [struct.pack(">BIH", 1, offsets[4], 0), struct.pack(">BIH", 1, offsets[5], 0)]
    )
    xref_offset = len(out)
    rows += struct.pack(">BIH", 1, xref_offset, 0)
    xc = zlib.compress(rows, 9)
    out += (
        (
            b"6 0 obj\n<< /Type /XRef /Size 7 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode "
            b"/Length %d >>\nstream\n" % len(xc)
        )
        + xc
        + b"\nendstream\nendobj\n"
    )
    out += b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(out)


def test_d4_an_object_stream_that_expands_hugely_is_refused_before_the_reader_decodes_it() -> None:
    """QA-05: pypdf decodes object streams while the reader is opened, before the page limits.

    A 60 MiB padding in a flate object stream costs about 60 KB of file. On the baseline it peaked
    137 MiB of traced memory before any check. The expansion pass must refuse it first.
    """
    data = _object_stream_pdf(60 * MiB)
    assert len(data) < 200 * 1024
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(data)
    assert exc.value.reason == limits.ARCHIVE_RATIO_LIMIT


def test_d4_a_small_object_stream_is_read_normally() -> None:
    result = parse_pdf(_object_stream_pdf(0))
    assert result.status == "unsupported"
    assert result.flagged_regions == []


# --- EML offsets (approved P4-GOV-2026-10-28; field names aligned to the schema, QA-03). -------


def test_eml_offsets_are_relative_to_the_nfc_normalized_part_text() -> None:
    decomposed = "Café plan"  # "e" followed by a combining acute accent
    data = f"Subject: {decomposed}\nFrom: a@wds-test.example\n\nbody\n".encode()
    subject = parse_eml(data).segments[0]
    assert subject.text == "Café plan"
    assert subject.locator["start_offset"] == 0
    assert subject.locator["end_offset"] == len(subject.text) == 9


def test_eml_body_offsets_follow_the_stripped_text_and_span_it_exactly() -> None:
    result = parse_eml(b"Subject: s\nFrom: a@wds-test.example\n\n   hello there   \n")
    body = result.segments[-1]
    assert body.text == "hello there"
    assert body.locator == {"eml_part": "body", "start_offset": 0, "end_offset": 11}
    assert body.text[body.locator["start_offset"] : body.locator["end_offset"]] == body.text


def test_eml_locators_use_the_schema_names_and_never_the_superseded_ones() -> None:
    result = parse_eml(
        b"Subject: s\nMessage-ID: <m@wds-test.example>\nFrom: a@wds-test.example\n\nbody\n"
    )
    for segment in result.segments:
        assert {"start_offset", "end_offset", "eml_part", "message_id"} <= set(segment.locator)
        assert "char_start" not in segment.locator and "char_end" not in segment.locator
        assert segment.locator["message_id"] == "<m@wds-test.example>"


def test_eml_zero_length_parts_produce_no_segment_and_a_zero_offset_is_never_emitted() -> None:
    data = b"Subject:    \nFrom: a@wds-test.example\n\n   \n"
    result = parse_eml(data)
    assert result.segments == []
    assert result.status == "unsupported"


def test_the_parser_module_exposes_the_stable_filter_class() -> None:
    assert parsers.PDF_FILTER_UNSUPPORTED == "pdf_filter_unsupported"


# --- QA-04: one input boundary across upload and parser. --------------------------------------


def test_the_parser_input_limit_is_the_approved_upload_maximum_in_one_unit() -> None:
    from webdesk.storage import content_store

    assert limits.MAX_INPUT_BYTES == content_store.MAX_BYTES == 20 * MiB


def test_upload_admits_exactly_the_maximum_and_refuses_one_byte_more() -> None:
    from webdesk.intake.validation import UploadRefusal, validate_upload

    validate_upload("boundary.txt", "text/plain", b"x" * (20 * MiB))
    with pytest.raises(UploadRefusal) as refused:
        validate_upload("boundary.txt", "text/plain", b"x" * (20 * MiB + 1))
    assert (refused.value.status, refused.value.reason) == (413, "too_large")


def _xref_stream_pdf(padding: int) -> bytes:
    """A file whose cross-reference stream expands by ``padding`` bytes on open."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
    ]
    out = bytearray(b"%PDF-1.5\n")
    offsets: dict[int, int] = {}
    for index, obj in enumerate(objs, start=1):
        offsets[index] = len(out)
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    content = b"BT ET"
    offsets[4] = len(out)
    out += b"4 0 obj\n" + f"<< /Length {len(content)} >>\nstream\n".encode() + content
    out += b"\nendstream\nendobj\n"
    rows = b"".join(
        [struct.pack(">BIH", 0, 0, 65535)]
        + [struct.pack(">BIH", 1, offsets[index], 0) for index in (1, 2, 3, 4)]
    )
    xref_offset = len(out)
    rows += struct.pack(">BIH", 1, xref_offset, 0)
    compressed = zlib.compress(rows + b" " * padding, 9)
    out += (
        b"5 0 obj\n<< /Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode "
        b"/Length %d >>\nstream\n" % len(compressed)
    )
    out += compressed + b"\nendstream\nendobj\n"
    out += b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(out)


def test_d4_a_cross_reference_stream_that_expands_hugely_is_refused_before_the_reader() -> None:
    """QA-05: the cross-reference stream is decoded when the reader opens. It is bounded too."""
    data = _xref_stream_pdf(60 * MiB)
    assert len(data) < 200 * 1024
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(data)
    assert exc.value.reason == limits.ARCHIVE_RATIO_LIMIT


def test_d4_a_plain_cross_reference_file_is_read_normally() -> None:
    result = parse_pdf(_xref_stream_pdf(0))
    assert result.status == "unsupported"
