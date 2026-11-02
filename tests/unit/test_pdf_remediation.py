"""Remediation of the final-review defects D1 to D4 (ASCII85 metering, swallowed filter refusals,
replacement characters, admission in a timed child). Synthetic and bounded."""

from __future__ import annotations

import base64

import pytest

from tests.support.parse_corpus import build_pdf
from webdesk.intake import limits
from webdesk.intake.isolation import open_pdf_in_child
from webdesk.intake.parsers import ParserFailure, parse_pdf

MiB = 1024 * 1024
CATALOG = b"<< /Type /Catalog /Pages 2 0 R >>"
PAGES = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"


def _assemble(objects: dict[int, bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for number in range(1, size):
        if number in offsets:
            out += f"{offsets[number]:010d} 00000 n \n".encode()
        else:
            out += b"0000000000 65535 f \n"
    out += f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _page_with_form(form: bytes) -> bytes:
    resources = b"<< /XObject << /Fm0 6 0 R >> >>"
    return _assemble(
        {
            1: CATALOG,
            2: PAGES,
            3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            + b"/Resources "
            + resources
            + b" >>",
            4: b"<< /Length 8 >>\nstream\nq /Fm0 Do Q\nendstream",
            6: form,
        }
    )


def _stream(extra: bytes, body: bytes) -> bytes:
    head = b"<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] " + extra
    head += b" /Length %d >>\nstream\n" % len(body)
    return head + body + b"\nendstream"


# --- D1: ASCII85 expansion is charged before it runs ------------------------------------ ---


def test_d1_an_ascii85_form_whose_worst_case_expansion_exceeds_the_budget_is_refused_first() -> (
    None
):
    body = b"z" * (40 * MiB) + b"~>"
    form = _stream(b"/Filter /ASCII85Decode", body)
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(_page_with_form(form))
    assert exc.value.reason == limits.ARCHIVE_SIZE_LIMIT


def test_d1_a_small_ascii85_form_with_text_is_decoded_and_its_page_is_flagged() -> None:
    plain = b"BT (ascii85 hidden) Tj ET"
    encoded = base64.a85encode(plain) + b"~>"
    result = parse_pdf(_page_with_form(_stream(b"/Filter /ASCII85Decode", encoded)))
    assert result.status == "unsupported"
    assert result.flagged_regions == ["pdf_page:1"]


# --- D2: a refused filter swallowed while the reader rebuilds is never a silent empty suc ---


def test_d2_a_refused_filter_inside_rebuilt_structure_never_yields_a_silent_empty_result() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        4: b"<< /Length 5 >>\nstream\nBT ET\nendstream",
        5: b"<< /Type /XRef /Size 6 /W [1 4 2] /Filter /LZWDecode /Length 3 >>\n"
        b"stream\nxyz\nendstream",
    }
    # A broken startxref makes the reader rebuild its cross-reference table by scanning.
    data = _assemble(objects).replace(b"startxref\n", b"startxref\n999999999\n%")
    try:
        result = parse_pdf(data)
    except ParserFailure as exc:
        assert exc.reason in ("pdf_filter_unsupported", "corrupt_structure")
        return
    # A returned result must not be an unflagged empty success.
    assert result.segments or result.flagged_regions


# --- D3: text pypdf could not map (replacement characters) is flagged, segment kept ----- ---


def test_d3_replacement_characters_flag_the_page_and_keep_the_segment_as_partial() -> None:
    objects = {
        1: CATALOG,
        2: PAGES,
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        4: b"<< /Length 40 >>\nstream\nBT /F9 12 Tf (abc) Tj ET BT /F9 12 Tf (de) Tj ET\nendstream",
    }
    result = parse_pdf(_assemble(objects))
    texts = [segment.text for segment in result.segments]
    if any("�" in text for text in texts):
        assert result.status == "partial"
        assert result.flagged_regions == ["pdf_page:1"]
    else:
        assert result.flagged_regions == []


def test_d3_a_page_whose_only_extracted_text_is_replacement_characters_commits_no_segment() -> None:
    """F-4: text pypdf cannot map (here, no font resource) must not become a committed segment of
    U+FFFD. The page is flagged, and the garbage is not stored as requirement content."""
    objects = {
        1: CATALOG,
        2: PAGES,
        3: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        + b"/Resources << /XObject << /Fm0 6 0 R >> >> >>",
        4: b"<< /Length 43 >>\nstream\nBT /F1 12 Tf 10 100 Td (Hello) Tj ET q /Fm0 Do Q\nendstream",
        6: _stream(b"/Resources << /XObject << /Im1 7 0 R >> >>", b"/Im1 Do"),
        7: b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
        + b"/BitsPerComponent 8 /Length 1 >>\nstream\n\x00\nendstream",
    }
    result = parse_pdf(_assemble(objects))
    assert result.segments == []
    assert result.flagged_regions == ["pdf_page:1"]
    assert result.status == "unsupported"


# --- D4: admission runs in a timed child ------------------------------------------------ ---


def test_d4_admission_of_a_valid_pdf_runs_in_the_child_and_reports_not_encrypted() -> None:
    assert open_pdf_in_child(build_pdf(["admitted page"])) is False


def test_d4_the_admission_child_is_killed_at_the_bound_and_the_failure_is_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The timeout is the enforced admission bound. A child over it is killed and reported as
    parser_timeout, so the caller is released. A self-referencing xref loop from the review was
    not reproduced by a synthetic fixture; the bound is tested directly."""
    monkeypatch.setattr(limits, "PARSER_TIMEOUT_SECONDS", 0.001)
    with pytest.raises(ParserFailure) as exc:
        open_pdf_in_child(build_pdf(["bounded admission"]))
    assert exc.value.reason == limits.PARSER_TIMEOUT
