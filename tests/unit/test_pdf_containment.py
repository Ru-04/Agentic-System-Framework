"""PDF resource containment (QA-05) and nested-form completeness (QA-06).
Synthetic, bounded, no database.

Each adversarial fixture is small on disk and expands, on request, to a bounded amount. The
expansion is refused
inside the parser, before the expanded bytes reach the reader. The containment guarantee and its
limits are recorded in
docs/PHASE4_PDF_CONTAINMENT.md.
"""

from __future__ import annotations

import io
import struct
import zlib

import pytest

from tests.support.parse_corpus import build_pdf
from webdesk.intake import limits
from webdesk.intake.isolation import run_isolated
from webdesk.intake.parsers import PDF_FILTER_UNSUPPORTED, ParserFailure, parse_pdf

MiB = 1024 * 1024
CATALOG = b"<< /Type /Catalog /Pages 2 0 R >>"
PAGES = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"


def _page(resources: bytes = b"<< >>", contents: int = 4) -> bytes:
    return (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R /Resources %s >>"
        % (contents, resources)
    )


def _stream(extra: bytes, data: bytes, eol: bytes = b"\n", length: int | None = None) -> bytes:
    declared = len(data) if length is None else length
    return b"<< /Length %d %s >>stream%s" % (declared, extra, eol) + data + b"\nendstream"


def _assemble(objects: dict[int, bytes]) -> bytes:
    """A classic cross-reference table. Used for fixtures without object streams."""
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
        out.write(
            f"{offsets[number]:010d} 00000 n \n".encode()
            if number in offsets
            else b"0000000000 65535 f \n"
        )
    out.write(f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


def _object_stream_bomb(
    padding: int, eol: bytes = b"\n", hide_endstream: bool = False, length: int | None = None
) -> bytes:
    """Pages inside a flate object stream that expands by ``padding`` bytes, indexed by a flate xref
    stream."""
    members = [CATALOG, PAGES, _page(contents=5)]
    header = body = b""
    for index, member in enumerate(members, start=1):
        header += f"{index} {len(body)} ".encode()
        body += member + b" "
    raw = header + body + b" " * padding
    if hide_endstream:
        # A stored deflate block carrying the bytes "endstream", then the rest of the data as one
        # compressed block.
        marker = b"endstream"
        stored = b"\x00" + struct.pack("<HH", len(marker), (~len(marker)) & 0xFFFF) + marker
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        tail = compressor.compress(raw) + compressor.flush()
        compressed = b"\x78\x9c" + stored + tail + struct.pack(">I", zlib.adler32(marker + raw))
    else:
        compressed = zlib.compress(raw, 9)
    declared = len(compressed) if length is None else length
    objstm = b"<< /Type /ObjStm /N 3 /First %d /Filter /FlateDecode /Length %d >>stream%s" % (
        len(header),
        declared,
        eol,
    )
    objstm += compressed + b"\nendstream"
    content = b"BT ET"
    out = bytearray(b"%PDF-1.5\n")
    offsets: dict[int, int] = {}
    offsets[4] = len(out)
    out += b"4 0 obj\n" + objstm + b"\nendobj\n"
    offsets[5] = len(out)
    out += b"5 0 obj\n" + _stream(b"", content) + b"\nendobj\n"
    rows = b"".join(
        [struct.pack(">BIH", 0, 0, 65535)]
        + [struct.pack(">BIH", 2, 4, index) for index in range(3)]
        + [struct.pack(">BIH", 1, offsets[4], 0), struct.pack(">BIH", 1, offsets[5], 0)]
    )
    xref_offset = len(out)
    rows += struct.pack(">BIH", 1, xref_offset, 0)
    xref_data = zlib.compress(rows, 9)
    out += b"6 0 obj\n" + _stream(
        b"/Type /XRef /Size 7 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode", xref_data
    )
    out += b"\nendobj\n" + b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(out)


def _ratio_or_size(reason: str) -> bool:
    return reason in (limits.ARCHIVE_RATIO_LIMIT, limits.ARCHIVE_SIZE_LIMIT)


# --- QA-05: the two reproduced bypasses and their variations -------------------------------------


def test_qa05_the_standard_object_stream_bomb_is_refused_before_the_reader_decodes_it() -> None:
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(_object_stream_bomb(60 * MiB))
    assert _ratio_or_size(exc.value.reason)


def test_qa05_bypass_a_cr_only_line_ending_after_stream_is_metered_like_any_other() -> None:
    """Reproduced bypass A: the old pre-scan matched LF only, but the reader decoded CR-only."""
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(_object_stream_bomb(60 * MiB, eol=b"\r"))
    assert _ratio_or_size(exc.value.reason)


def test_qa05_bypass_a_crlf_line_ending_is_metered() -> None:
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(_object_stream_bomb(60 * MiB, eol=b"\r\n"))
    assert _ratio_or_size(exc.value.reason)


def test_qa05_bypass_b_a_hidden_endstream_in_compressed_data_is_metered() -> None:
    """Reproduced bypass B: a literal "endstream" inside the deflate data truncated the pre-scan's
    payload."""
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(_object_stream_bomb(60 * MiB, hide_endstream=True))
    assert _ratio_or_size(exc.value.reason)


def test_qa05_an_indirect_or_wrong_length_does_not_change_the_charge() -> None:
    """The decoder does not trust /Length. A declared length of zero still charges the actual
    expansion."""
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(_object_stream_bomb(60 * MiB, length=0))
    assert _ratio_or_size(exc.value.reason)


def test_qa05_a_cross_reference_stream_bomb_is_metered() -> None:
    rows = struct.pack(">BIH", 0, 0, 65535) + b"".join(
        struct.pack(">BIH", 1, offset, 0) for offset in (16, 60, 100, 140)
    )
    xref = zlib.compress(rows + b" " * (60 * MiB), 9)
    body = b"%PDF-1.5\n" + b"1 0 obj\n" + CATALOG + b"\nendobj\n"
    body += b"2 0 obj\n" + PAGES + b"\nendobj\n" + b"3 0 obj\n" + _page() + b"\nendobj\n"
    body += b"4 0 obj\n" + _stream(b"", b"BT ET") + b"\nendobj\n"
    xref_offset = len(body)
    body += b"5 0 obj\n" + _stream(
        b"/Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode", xref
    )
    body += b"\nendobj\nstartxref\n%d\n%%%%EOF\n" % xref_offset
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(body)
    assert _ratio_or_size(exc.value.reason)


def test_qa05_aggregate_expansion_across_two_streams_is_refused_by_the_cumulative_budget() -> None:
    """Two streams, each under a single-stream limit, whose total exceeds the cumulative limit."""
    half = _stream(b"/Filter /FlateDecode", zlib.compress(b" " * (60 * MiB), 9))
    half2 = _stream(b"/Filter /FlateDecode", zlib.compress(b" " * (60 * MiB), 9))
    resources = b"<< /XObject << /Fm0 6 0 R /Fm1 7 0 R >> >>"
    data = _assemble(
        {
            1: CATALOG,
            2: PAGES,
            3: _page(resources, contents=4),
            4: _stream(b"", b"q /Fm0 Do /Fm1 Do Q"),
            6: _stream(
                b"/Subtype /Form /BBox [0 0 1 1] /Filter /FlateDecode",
                zlib.compress(b" " * (60 * MiB), 9),
            ),
            7: _stream(
                b"/Subtype /Form /BBox [0 0 1 1] /Filter /FlateDecode",
                zlib.compress(b" " * (60 * MiB), 9),
            ),
        }
    )
    assert len(half) and len(half2)
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(data)
    assert _ratio_or_size(exc.value.reason)


def test_qa05_an_lzw_object_stream_refuses_the_file_by_name() -> None:
    """LZW is never decoded. An object or cross-reference stream that uses it refuses the whole
    file."""
    body = b"%PDF-1.5\n" + b"1 0 obj\n" + CATALOG + b"\nendobj\n"
    body += b"2 0 obj\n" + PAGES + b"\nendobj\n" + b"3 0 obj\n" + _page() + b"\nendobj\n"
    body += b"4 0 obj\n" + _stream(b"", b"BT ET") + b"\nendobj\n"
    xref_offset = len(body)
    body += b"5 0 obj\n" + _stream(
        b"/Type /XRef /Size 6 /W [1 4 2] /Root 1 0 R /Filter /LZWDecode", b"xyz"
    )
    body += b"\nendobj\nstartxref\n%d\n%%%%EOF\n" % xref_offset
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(body)
    assert exc.value.reason == PDF_FILTER_UNSUPPORTED


def test_qa05_an_lzw_page_content_stream_flags_its_page_and_is_never_decoded() -> None:
    data = _assemble(
        {
            1: CATALOG,
            2: PAGES,
            3: _page(b"<< /Font << /F1 5 0 R >> >>", contents=4),
            4: _stream(b"/Filter /LZWDecode", b"\x80\x0b\x60"),
            5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )
    result = parse_pdf(data)
    assert result.status == "unsupported"
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa05_a_legitimate_predictor_cross_reference_stream_is_still_read() -> None:
    result = parse_pdf(build_pdf(["ordinary page"]))
    assert result.status == "succeeded"


def test_qa05_a_small_object_stream_is_read_normally() -> None:
    result = parse_pdf(_object_stream_bomb(0))
    assert result.status == "unsupported"
    assert result.flagged_regions == []


def test_qa05_the_child_process_refuses_the_bomb_and_the_parent_survives() -> None:
    """Containment in the isolated child: the refusal returns as a classified failure, not a hang or
    a crash."""
    with pytest.raises(ParserFailure) as exc:
        run_isolated("application/pdf", _object_stream_bomb(60 * MiB))
    assert exc.value.reason != "parser_timeout"
    assert _ratio_or_size(exc.value.reason) or exc.value.reason == "parser_crash"


def test_qa05_the_decoder_patch_is_restored_after_each_parse() -> None:
    from pypdf.filters import FlateDecode

    before = vars(FlateDecode)["decode"]
    with pytest.raises(ParserFailure):
        parse_pdf(_object_stream_bomb(60 * MiB))
    assert vars(FlateDecode)["decode"] is before


# --- QA-06: text inside nested forms, annotations, patterns and Type 3 glyphs is never silently
# omitted ----------


def _nested_form_pdf(
    levels: int, text: bytes = b"BT (nested hidden text) Tj ET", extra_page_text: bool = False
) -> bytes:
    """A page whose content calls form 6, which calls form 7, and so on, down to a form holding
    ``text``."""
    objects: dict[int, bytes] = {1: CATALOG, 2: PAGES}
    objects[3] = _page(b"<< /XObject << /Fm0 6 0 R >> /Font << /F1 5 0 R >> >>", contents=4)
    page_text = b"BT /F1 12 Tf (page text) Tj ET " if extra_page_text else b""
    objects[4] = _stream(b"", b"q /Fm0 Do Q " + page_text)
    objects[5] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for depth in range(levels):
        number = 6 + depth
        nxt = number + 1
        if depth == levels - 1:
            objects[number] = _stream(b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", text)
        else:
            objects[number] = _stream(
                b"/Type /XObject /Subtype /Form /BBox [0 0 10 10] "
                b"/Resources << /XObject << /Fm%d %d 0 R >> >>" % (depth + 1, nxt),
                b"/Fm%d Do" % (depth + 1),
            )
    return _assemble(objects)


def test_qa06_text_two_levels_inside_forms_is_flagged_not_silently_dropped() -> None:
    result = parse_pdf(_nested_form_pdf(levels=2))
    assert result.status == "unsupported"
    assert result.segments == []
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_mixed_ordinary_text_and_nested_form_text_is_partial_with_the_flag() -> None:
    result = parse_pdf(_nested_form_pdf(levels=2, extra_page_text=True))
    assert result.status == "partial"
    assert [s.locator for s in result.segments] == [{"page_number": 1}]
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_a_form_repeated_by_two_pages_does_not_loop_and_both_pages_are_flagged() -> None:
    form = _stream(b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", b"BT (shared) Tj ET")
    objects = {
        1: CATALOG,
        2: b"<< /Type /Pages /Kids [3 0 R 8 0 R] /Count 2 >>",
        3: _page(b"<< /XObject << /Fm0 6 0 R >> >>", contents=4),
        4: _stream(b"", b"q /Fm0 Do Q"),
        6: form,
        8: _page(b"<< /XObject << /Fm0 6 0 R >> >>", contents=9),
        9: _stream(b"", b"q /Fm0 Do Q"),
    }
    result = parse_pdf(_assemble(objects))
    assert result.flagged_regions == ["pdf_page:1", "pdf_page:2"]


def test_qa06_a_cyclic_form_reference_terminates_and_its_text_is_flagged() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: _page(b"<< /XObject << /Fm0 6 0 R >> >>", contents=4),
        4: _stream(b"", b"q /Fm0 Do Q"),
        6: _stream(
            b"/Type /XObject /Subtype /Form /BBox [0 0 10 10] "
            b"/Resources << /XObject << /Fm0 6 0 R >> >>",
            b"BT (cycle) Tj ET /Fm0 Do",
        ),
    }
    result = parse_pdf(_assemble(objects))
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_nesting_beyond_the_walk_depth_is_flagged_rather_than_walked_blindly() -> None:
    result = parse_pdf(_nested_form_pdf(levels=12))
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_sibling_forms_are_all_examined_when_one_holds_text() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: _page(b"<< /XObject << /Fa 6 0 R /Fb 7 0 R /Fc 8 0 R >> >>", contents=4),
        4: _stream(b"", b"q /Fa Do /Fb Do /Fc Do Q"),
        6: _stream(b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", b"0 0 m 10 10 l S"),
        7: _stream(b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", b"BT (sibling) Tj ET"),
        8: _stream(b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", b"0 0 m 1 1 l S"),
    }
    result = parse_pdf(_assemble(objects))
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_a_vector_only_form_is_not_flagged() -> None:
    """Negative control: a form with no text block is not reported as hidden text."""
    objects = {
        1: CATALOG,
        2: PAGES,
        3: _page(b"<< /XObject << /Fm0 6 0 R >> /Font << /F1 5 0 R >> >>", contents=4),
        4: _stream(b"", b"BT /F1 12 Tf (visible) Tj ET q /Fm0 Do Q"),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: _stream(b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", b"0 0 m 10 10 l S"),
    }
    result = parse_pdf(_assemble(objects))
    assert result.status == "succeeded"
    assert result.flagged_regions == []


def test_qa06_text_in_an_annotation_appearance_is_flagged() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Annots [6 0 R] >>",
        4: _stream(b"", b"q Q"),
        6: b"<< /Type /Annot /Subtype /FreeText /Rect [0 0 10 10] /AP << /N 7 0 R >> >>",
        7: _stream(
            b"/Type /XObject /Subtype /Form /BBox [0 0 10 10]", b"BT (annotation text) Tj ET"
        ),
    }
    result = parse_pdf(_assemble(objects))
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_text_in_a_type3_glyph_procedure_is_flagged() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: _page(b"<< /Font << /F1 6 0 R >> >>", contents=4),
        4: _stream(b"", b"BT /F1 12 Tf (x) Tj ET"),
        6: b"<< /Type /Font /Subtype /Type3 /FontBBox [0 0 1 1] /FontMatrix [1 0 0 1 0 0] "
        b"/FirstChar 120 /LastChar 120 /Widths [1] /Encoding << /Differences [120 /g] >> "
        b"/CharProcs << /g 7 0 R >> >>",
        7: _stream(b"", b"BT (glyph text) Tj ET"),
    }
    result = parse_pdf(_assemble(objects))
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_a_pattern_stream_holding_text_is_flagged() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: _page(b"<< /Pattern << /P1 6 0 R >> >>", contents=4),
        4: _stream(b"", b"/Pattern cs /P1 scn 0 0 10 10 re f"),
        6: _stream(
            b"/PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 10 10] /XStep 10 /YStep 10",
            b"BT (pattern) Tj ET",
        ),
    }
    result = parse_pdf(_assemble(objects))
    assert result.flagged_regions == ["pdf_page:1"]


def test_qa06_a_nested_form_inside_an_object_stream_is_still_walked() -> None:
    result = parse_pdf(_object_stream_bomb(0))
    assert result.flagged_regions == []
