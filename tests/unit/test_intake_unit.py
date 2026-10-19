"""Phase C unit tests: upload validation (I-3) and typed parsers (I-6). No database.

Documents are generated in the test. No client file is stored in the repository.
"""

from __future__ import annotations

import io
import zipfile
from email.message import EmailMessage
from typing import Any

import pytest
from docx import Document
from pypdf import PdfWriter

from webdesk.intake import parsers
from webdesk.intake.parsers import (
    ParserFailure,
    parse_docx,
    parse_eml,
    parse_markdown,
    parse_pdf,
    parse_text,
)
from webdesk.intake.validation import DOCX_MIME, UploadRefusal, validate_upload

PDF_MIME = "application/pdf"


def _text_pdf(words: str) -> bytes:
    body = f"BT /F1 18 Tf 20 60 Td ({words}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=144)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=144)
    writer.encrypt("not-a-real-secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _docx(*paragraphs: str) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _eml(with_attachment: bool) -> bytes:
    message = EmailMessage()
    message["Subject"] = "Inventory sync question"
    message["From"] = "client@wds-test.example"
    message["To"] = "sales@wds-test.example"
    message.set_content("Please confirm the sync frequency.")
    if with_attachment:
        message.add_attachment(
            b"%PDF-1.4 attachment bytes",
            maintype="application",
            subtype="pdf",
            filename="spec.pdf",
        )
    return message.as_bytes()


# --- I-3: validation --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "mime", "data"),
    [
        ("brief.txt", "text/plain", b"Client wants inventory sync.\n"),
        ("notes.md", "text/markdown", b"# Heading\n\nBody text.\n"),
        ("mail.eml", "message/rfc822", _eml(False)),
        ("spec.pdf", PDF_MIME, _text_pdf("Hello")),
        ("doc.docx", DOCX_MIME, _docx("A paragraph.")),
    ],
    ids=["txt", "md", "eml", "pdf", "docx"],
)
def test_each_permitted_type_is_accepted(filename: str, mime: str, data: bytes) -> None:
    accepted = validate_upload(filename, mime, data)
    assert accepted.mime_type == mime


def test_a_pdf_declared_as_plain_text_is_a_mime_mismatch() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("spec.pdf", "text/plain", _text_pdf("Hi"))
    assert (exc.value.status, exc.value.reason) == (415, "mime_mismatch")


def test_bytes_that_are_not_a_pdf_under_a_pdf_name_are_a_spoof() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("spec.pdf", PDF_MIME, b"Just plain text, not a PDF at all")
    assert (exc.value.status, exc.value.reason) == (415, "signature_mismatch")


def test_oversized_upload_is_413() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("big.txt", "text/plain", b"a" * (20 * 1024 * 1024 + 1))
    assert (exc.value.status, exc.value.reason) == (413, "too_large")


def test_empty_upload_is_422() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("empty.txt", "text/plain", b"")
    assert (exc.value.status, exc.value.reason) == (422, "empty")


@pytest.mark.parametrize("name", ["tool.exe", "image.png", "archive.zip"])
def test_unpermitted_extensions_are_415(name: str) -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload(name, "application/octet-stream", b"data")
    assert (exc.value.status, exc.value.reason) == (415, "unsupported_type")


def test_executables_and_scripts_are_refused_even_with_a_permitted_name() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("notes.txt", "text/plain", b"MZ\x90\x00 executable body")
    assert exc.value.reason == "executable_not_permitted"
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("notes.txt", "text/plain", b"#!/bin/sh\necho hi\n")
    assert exc.value.reason == "executable_not_permitted"


def test_a_zip_archive_renamed_to_docx_structure_is_corrupt() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("random.txt", "not a word document")
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("doc.docx", DOCX_MIME, buffer.getvalue())
    assert (exc.value.status, exc.value.reason) == (422, "corrupt_structure")


def test_corrupt_pdf_structure_is_422() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("spec.pdf", PDF_MIME, b"%PDF-1.4 truncated and broken")
    assert exc.value.status in (422, 415)


def test_encrypted_pdf_is_refused() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("locked.pdf", PDF_MIME, _encrypted_pdf())
    assert (exc.value.status, exc.value.reason) == (422, "encrypted_not_permitted")


def test_text_must_be_valid_utf8_without_control_bytes() -> None:
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("bad.txt", "text/plain", b"\xff\xfe broken")
    assert exc.value.reason == "invalid_utf8"
    with pytest.raises(UploadRefusal) as exc:
        validate_upload("bin.txt", "text/plain", b"text with \x00 NUL byte")
    assert exc.value.reason == "binary_content"


# --- I-6: typed parsers -----------------------------------------------------------------------


def test_pdf_text_becomes_pdf_page_segments() -> None:
    result = parse_pdf(_text_pdf("Hello WDS"))
    assert result.status == "succeeded"
    assert result.segments[0].locator_type == "pdf_page"
    assert result.segments[0].locator == {"page_number": 1}
    assert "Hello" in result.segments[0].text


def test_a_pdf_with_no_text_is_unsupported_not_failed() -> None:
    result = parse_pdf(_blank_pdf())
    assert result.status == "unsupported"
    assert result.segments == []


def test_an_unreadable_page_gives_partial_and_keeps_the_good_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Page:
        def __init__(self, text: str | None) -> None:
            self._text = text

        def extract_text(self) -> str:
            if self._text is None:
                raise RuntimeError("bad page")
            return self._text

    class Reader:
        is_encrypted = False

        def __init__(self, _stream: Any) -> None:
            self.pages = [Page("Good first page"), Page(None)]

    monkeypatch.setattr(parsers, "PdfReader", Reader)
    result = parse_pdf(b"ignored")
    assert result.status == "partial"
    assert [s.locator for s in result.segments] == [{"page_number": 1}]
    assert result.flagged_regions == ["pdf_page:2"]


def test_a_corrupt_pdf_is_a_whole_file_failure() -> None:
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(b"%PDF-1.4 this is not a readable document at all")
    assert exc.value.reason == "corrupt_structure"


def test_docx_paragraphs_keep_their_index() -> None:
    result = parse_docx(_docx("First", "", "Third"))
    assert [s.locator for s in result.segments] == [
        {"paragraph_index": 1},
        {"paragraph_index": 3},
    ]


def test_markdown_records_its_heading_path_and_paragraph_index() -> None:
    source = b"# Scope\n\nAlpha paragraph.\n\nBeta paragraph.\n\n## Detail\n\nGamma.\n"
    result = parse_markdown(source)
    assert result.segments[0].locator == {"heading_path": ["Scope"], "paragraph_index": 1}
    assert result.segments[1].locator == {"heading_path": ["Scope"], "paragraph_index": 2}
    assert result.segments[2].locator == {"heading_path": ["Scope", "Detail"], "paragraph_index": 1}


def test_text_lines_get_line_range_locators() -> None:
    result = parse_text(b"first line\n\nthird line\n")
    assert [s.locator for s in result.segments] == [
        {"line_start": 1, "line_end": 1},
        {"line_start": 3, "line_end": 3},
    ]


def test_eml_yields_subject_and_body_and_lists_attachments_without_ingesting_them() -> None:
    result = parse_eml(_eml(with_attachment=True))
    parts = [s.locator for s in result.segments]
    assert {"eml_part": "subject"} in parts
    assert {"eml_part": "body"} in parts
    assert len(result.unprocessed_attachments) == 1
    attachment = result.unprocessed_attachments[0]
    assert attachment["filename"] == "spec.pdf"
    assert attachment["disposition"] == "unprocessed"
    assert all("attachment bytes" not in s.text for s in result.segments)


def test_a_message_without_headers_is_a_corrupt_structure_failure() -> None:
    with pytest.raises(ParserFailure) as exc:
        parse_eml(b"just some words with no headers at all")
    assert exc.value.reason == "corrupt_structure"


def test_every_parser_emits_only_the_five_permitted_locator_types() -> None:
    allowed = {"pdf_page", "docx_paragraph", "md_heading_paragraph", "txt_line_range", "eml_part"}
    produced = {
        s.locator_type
        for result in (
            parse_pdf(_text_pdf("x")),
            parse_docx(_docx("y")),
            parse_markdown(b"# h\n\nz\n"),
            parse_text(b"w\n"),
            parse_eml(_eml(False)),
        )
        for s in result.segments
    }
    assert produced <= allowed
