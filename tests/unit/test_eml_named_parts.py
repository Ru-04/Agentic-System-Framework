"""H-64: EML parts named by a Content-Type ``name=`` parameter.

Ruled by WDS in chat on 2 November 2026 ("Treat as attachment"): a MIME part that carries a
Content-Type ``name=`` parameter is an attachment and is never chosen as the body, even with no
Content-Disposition and even when it is the first ``text/plain`` part.
"""

from __future__ import annotations

from webdesk.intake.parsers import parse_eml

HEADERS = (
    "From: a@wds-test.example\r\nTo: b@wds-test.example\r\nSubject: Hello\r\n"
    "Message-ID: <named-part@wds-test.example>\r\nMIME-Version: 1.0\r\n"
)


def _multipart(*parts: tuple[str, str]) -> bytes:
    text = HEADERS + "Content-Type: multipart/mixed; boundary=BOUND\r\n\r\n"
    for headers, body in parts:
        text += f"--BOUND\r\n{headers}\r\n\r\n{body}\r\n"
    return (text + "--BOUND--\r\n").encode("utf-8")


def _texts(data: bytes) -> list[str]:
    return [segment.text for segment in parse_eml(data).segments]


def _attachment_names(data: bytes) -> list[str]:
    return [item["filename"] for item in parse_eml(data).unprocessed_attachments]


def test_a_first_named_text_part_is_not_the_body_and_is_reported_as_an_attachment() -> None:
    data = _multipart(
        ('Content-Type: text/plain; name="notes.txt"', "attached notes, not the body"),
        ("Content-Type: text/plain", "the real body"),
    )
    assert _texts(data) == ["Hello", "the real body"]
    assert _attachment_names(data) == ["notes.txt"]


def test_a_named_text_part_alone_gives_no_body_and_is_an_attachment() -> None:
    data = _multipart(('Content-Type: text/plain; name="notes.txt"', "attached notes only"))
    result = parse_eml(data)
    assert [segment.text for segment in result.segments] == ["Hello"]
    assert [item["filename"] for item in result.unprocessed_attachments] == ["notes.txt"]
    assert result.status == "succeeded"


def test_a_single_part_message_named_by_its_content_type_has_no_body() -> None:
    data = (HEADERS + 'Content-Type: text/plain; name="notes.txt"\r\n\r\nattached\r\n').encode()
    result = parse_eml(data)
    assert [segment.text for segment in result.segments] == ["Hello"]
    assert [item["filename"] for item in result.unprocessed_attachments] == ["notes.txt"]


def test_an_unnamed_text_part_is_still_the_body() -> None:
    data = _multipart(
        ("Content-Type: text/plain", "the real body"),
        ('Content-Type: application/pdf; name="spec.pdf"', "not decoded here"),
    )
    assert _texts(data) == ["Hello", "the real body"]
    assert _attachment_names(data) == ["spec.pdf"]


def test_an_unnamed_single_part_message_is_still_the_body() -> None:
    data = (HEADERS + "Content-Type: text/plain\r\n\r\nplain body\r\n").encode()
    assert _texts(data) == ["Hello", "plain body"]
    assert _attachment_names(data) == []


def test_a_named_html_part_is_not_an_html_only_body() -> None:
    data = _multipart(('Content-Type: text/html; name="page.html"', "<p>attached page</p>"))
    result = parse_eml(data)
    assert result.flagged_regions == []
    assert [item["filename"] for item in result.unprocessed_attachments] == ["page.html"]
