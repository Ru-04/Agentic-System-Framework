"""Versioned synthetic parse corpus (Phase 4 synthetic fixtures).

Every file is generated here, byte for byte, from code. Nothing binary is checked in, and no real
client document is used. ``CORPUS_VERSION`` changes whenever a generator changes its output. The
``manifest()`` SHA-256 values are checked by the tests, so an accidental change to a fixture fails
the build instead of silently moving the expected results.

Categories: valid, invalid, partial, oversized, restricted, quarantined. The quarantined cases are
refused by the database before any parser runs, so they carry no parser expectation here; the
database test exercises them.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage

from docx import Document

from webdesk.intake import limits

CORPUS_VERSION = "2"


@dataclass(frozen=True)
class Case:
    case_id: str
    category: str
    mime: str
    filename: str
    data: bytes
    expected_status: str  # succeeded | partial | failed | refused
    expected_class: str | None = None  # the error class or flagged region, when one applies


TXT = "text/plain"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
EML = "message/rfc822"


def _pdf_string(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return escaped.encode("ascii")


def build_pdf(pages: list[str | None], *, encrypted: bool = False) -> bytes:
    """A minimal PDF. A ``str`` is a text page, ``None`` is an image-only page, ``""`` is blank."""
    count = len(pages)
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids ["
        + b" ".join(f"{4 + 3 * i} 0 R".encode() for i in range(count))
        + f"] /Count {count} >>".encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for index, page in enumerate(pages):
        page_no, content_no, image_no = 4 + 3 * index, 5 + 3 * index, 6 + 3 * index
        if page is None:
            resources = f"/XObject << /Im1 {image_no} 0 R >>".encode()
            content = b"q 72 0 0 72 72 720 cm /Im1 Do Q"
            image = (
                b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1"
                b" /ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\nstream\n\x80"
                b"\nendstream"
            )
            objects[image_no] = image
        else:
            resources = b"/Font << /F1 3 0 R >>"
            content = b"BT /F1 12 Tf 72 720 Td (" + _pdf_string(page) + b") Tj ET" if page else b""
        objects[content_no] = (
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
        objects[page_no] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_no} 0 R"
            f" /Resources << {resources.decode()} >> >>".encode()
        )

    trailer_extra = b" /Encrypt 90 0 R" if encrypted else b""
    if encrypted:
        objects[90] = b"<< /Filter /Standard /V 1 /R 2 /O <00> /U <00> /P -4 >>"

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = out.tell()
        out.write(f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n")
    xref = out.tell()
    size = max(objects) + 1
    out.write(f"xref\n0 {size}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for number in range(1, size):
        if number in offsets:
            out.write(f"{offsets[number]:010d} 00000 n \n".encode())
        else:
            out.write(b"0000000000 65535 f \n")
    out.write(f"trailer\n<< /Size {size} /Root 1 0 R{trailer_extra.decode()} >>\n".encode())
    out.write(f"startxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


FIXED_TIME = datetime(2026, 1, 1, 0, 0, 0)


def _stable_zip(data: bytes) -> bytes:
    """Rewrite a ZIP with a fixed entry timestamp, so the same content yields the same bytes."""
    source = zipfile.ZipFile(io.BytesIO(data))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            entry = zipfile.ZipInfo(info.filename, date_time=FIXED_TIME.timetuple()[:6])
            entry.compress_type = zipfile.ZIP_DEFLATED
            target.writestr(entry, source.read(info.filename))
    return buffer.getvalue()


def build_docx(paragraphs: list[str], table: list[list[str]] | None = None) -> bytes:
    document = Document()
    document.core_properties.created = FIXED_TIME
    document.core_properties.modified = FIXED_TIME
    document.core_properties.last_modified_by = "synthetic"
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    if table is not None:
        grid = document.add_table(rows=len(table), cols=len(table[0]))
        for row_index, row in enumerate(table):
            for column_index, value in enumerate(row):
                grid.cell(row_index, column_index).text = value
    buffer = io.BytesIO()
    document.save(buffer)
    return _stable_zip(buffer.getvalue())


def build_eml(*, html_only: bool) -> bytes:
    message = EmailMessage()
    message["Subject"] = "Synthetic status note"
    message["From"] = "sender@example.test"
    message["To"] = "reader@example.test"
    message["Message-ID"] = "<synthetic-0001@example.test>"
    if html_only:
        message.set_content("<p>Only an HTML body here.</p>", subtype="html")
    else:
        message.set_content("Plain body line one.\nPlain body line two.")
    return message.as_bytes()


def _zip_bomb() -> bytes:
    """A ZIP whose content inflates far beyond its compressed size (ratio refusal)."""
    buffer = io.BytesIO()
    entry = zipfile.ZipInfo("word/document.xml", date_time=FIXED_TIME.timetuple()[:6])
    entry.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(entry, b"\x00" * (2 * 1024 * 1024))
    return buffer.getvalue()


def corpus() -> list[Case]:
    txt_valid = "Alpha line\n\n  Beta line with spaces  \r\nGamma   split\u0085 kept\n".encode()
    return [
        Case("valid-txt", "valid", TXT, "valid.txt", txt_valid, "succeeded"),
        Case(
            "valid-pdf",
            "valid",
            PDF,
            "valid.pdf",
            build_pdf(["Quarterly summary", "Second page text"]),
            "succeeded",
        ),
        Case(
            "valid-docx",
            "valid",
            DOCX,
            "valid.docx",
            build_docx(["Opening paragraph", "Closing paragraph"], [["Cell A", "Cell B"]]),
            "succeeded",
        ),
        Case(
            "invalid-txt",
            "invalid",
            TXT,
            "bad.txt",
            b"caf\xe9 not utf-8\n",
            "failed",
            "invalid_utf8",
        ),
        Case(
            "invalid-pdf",
            "invalid",
            PDF,
            "bad.pdf",
            b"%PDF-1.4\ngarbage only",
            "failed",
            "corrupt_structure",
        ),
        Case(
            "invalid-docx",
            "invalid",
            DOCX,
            "bad.docx",
            b"not a zip container",
            "failed",
            "corrupt_structure",
        ),
        Case(
            "partial-pdf-image-page",
            "partial",
            PDF,
            "partial.pdf",
            build_pdf(["Readable first page", None, "Readable third page"]),
            "partial",
            "pdf_page:2",
        ),
        Case(
            "partial-eml-html-only",
            "partial",
            EML,
            "html-only.eml",
            build_eml(html_only=True),
            "partial",
            "eml_part:body_html_only",
        ),
        Case(
            "oversized-txt",
            "oversized",
            TXT,
            "big.txt",
            b"x" * (limits.MAX_INPUT_BYTES + 1),
            "failed",
            limits.INPUT_TOO_LARGE,
        ),
        Case(
            "oversized-pdf",
            "oversized",
            PDF,
            "big.pdf",
            build_pdf(["page"]) + b"\n" * (limits.MAX_INPUT_BYTES + 1),
            "failed",
            limits.INPUT_TOO_LARGE,
        ),
        Case(
            "oversized-docx-archive",
            "oversized",
            DOCX,
            "bomb.docx",
            _zip_bomb(),
            "failed",
            limits.ARCHIVE_RATIO_LIMIT,
        ),
        Case(
            "restricted-pdf-encrypted",
            "restricted",
            PDF,
            "restricted.pdf",
            build_pdf(["Protected text"], encrypted=True),
            "failed",
            "encrypted_not_permitted",
        ),
        Case(
            "restricted-txt-classified",
            "restricted",
            TXT,
            "restricted.txt",
            b"Restricted classification does not block parsing.\n",
            "succeeded",
        ),
        Case(
            "restricted-docx-classified",
            "restricted",
            DOCX,
            "restricted.docx",
            build_docx(["Restricted classification paragraph"]),
            "succeeded",
        ),
        Case(
            "quarantined-txt",
            "quarantined",
            TXT,
            "quarantined.txt",
            b"Quarantined content is never parsed.\n",
            "refused",
            "quarantined",
        ),
        Case(
            "quarantined-pdf",
            "quarantined",
            PDF,
            "quarantined.pdf",
            build_pdf(["Quarantined page"]),
            "refused",
            "quarantined",
        ),
        Case(
            "quarantined-docx",
            "quarantined",
            DOCX,
            "quarantined.docx",
            build_docx(["Quarantined paragraph"]),
            "refused",
            "quarantined",
        ),
    ]


def manifest() -> dict[str, str]:
    """Case ID to SHA-256 of the generated bytes. The tests compare this with a pinned copy."""
    return {case.case_id: hashlib.sha256(case.data).hexdigest() for case in corpus()}
