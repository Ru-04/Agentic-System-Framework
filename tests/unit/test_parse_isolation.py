"""Parser isolation (H-32) and locator completion (H-33). No database; real parsers and children."""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any

import pytest

from tests.support.parse_corpus import (
    TXT,
    Case,
    build_docx,
    build_eml,
    build_pdf,
    corpus,
)
from webdesk.intake import isolation, limits
from webdesk.intake.isolation import child_environment, run_in_process, run_isolated
from webdesk.intake.parsers import ParserFailure, parse_docx, parse_eml, parse_pdf, parse_text

# Oversized cases are refused before any parser runs, and quarantined cases never reach one.
PARSEABLE = [case for case in corpus() if case.category not in {"quarantined", "oversized"}]


# --- H-32: the child environment is an allowlist --------------------------------------------------


def test_the_child_environment_carries_no_database_url_or_storage_secret() -> None:
    source = {
        "WEBDESK_WORKER_DATABASE_URL": "postgresql://worker",
        "WEBDESK_DATABASE_URL": "postgresql://owner",
        "WEBDESK_STORAGE_ROOT": "/srv/store",
        "WEBDESK_OUTBOX_ENCRYPTION_KEY": "secret",
        "PATH": "/bin",
        "SYSTEMROOT": "C:/Windows",
    }
    env = child_environment(source)
    assert set(env) <= {"PATH", "SYSTEMROOT", "PYTHONPATH"}
    assert "PYTHONPATH" in env


def test_a_fault_is_forwarded_to_the_child_only_in_the_test_environment() -> None:
    fault = {"WEBDESK_PARSER_FAULT": "crash"}
    assert "WEBDESK_PARSER_FAULT" not in child_environment({**fault, "WEBDESK_ENV": "prod"})
    assert child_environment({**fault, "WEBDESK_ENV": "test"})["WEBDESK_PARSER_FAULT"] == "crash"


def test_the_memory_cap_is_recorded_as_enforced_only_where_it_applies() -> None:
    assert limits.MEMORY_CAP_ENFORCED is (sys.platform != "win32")


# --- H-32: the child process returns the same result as the in-process parser -------------------


@pytest.mark.parametrize("case", PARSEABLE, ids=lambda case: case.case_id)
def test_the_isolated_result_equals_the_in_process_result(case: Case) -> None:
    if case.expected_status == "failed":
        with pytest.raises(ParserFailure) as isolated_exc:
            run_isolated(case.mime, case.data)
        with pytest.raises(ParserFailure) as direct_exc:
            run_in_process(case.mime, case.data)
        assert isolated_exc.value.reason == direct_exc.value.reason == case.expected_class
        return
    isolated = run_isolated(case.mime, case.data)
    direct = run_in_process(case.mime, case.data)
    assert isolated.status == direct.status
    assert isolated.flagged_regions == direct.flagged_regions
    assert [(s.locator_type, s.locator, s.text) for s in isolated.segments] == [
        (s.locator_type, s.locator, s.text) for s in direct.segments
    ]


def test_an_unknown_mime_type_fails_in_the_child_with_a_stable_class() -> None:
    with pytest.raises(ParserFailure) as exc:
        run_isolated("application/x-unknown", b"data")
    assert exc.value.reason == "unsupported_mime"


# --- H-32: crash, hang and output faults fail the version, not the worker -----------------------


def test_a_crashing_child_fails_with_parser_crash_and_the_parent_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEBDESK_ENV", "test")
    monkeypatch.setenv("WEBDESK_PARSER_FAULT", "crash")
    for _ in range(3):
        with pytest.raises(ParserFailure) as exc:
            run_isolated(TXT, b"line\n")
        assert exc.value.reason == limits.PARSER_CRASH
    monkeypatch.delenv("WEBDESK_PARSER_FAULT")
    assert run_isolated(TXT, b"line\n").status == "succeeded"


def test_a_hanging_child_is_killed_at_the_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEBDESK_ENV", "test")
    monkeypatch.setenv("WEBDESK_PARSER_FAULT", "hang")
    monkeypatch.setattr(limits, "PARSER_TIMEOUT_SECONDS", 2)
    started = time.monotonic()
    with pytest.raises(ParserFailure) as exc:
        run_isolated(TXT, b"line\n")
    elapsed = time.monotonic() - started
    assert exc.value.reason == limits.PARSER_TIMEOUT
    assert elapsed < 20, "the timeout must bound the parse well inside the job lease"


def test_the_fault_switch_is_ignored_outside_the_test_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WEBDESK_ENV", raising=False)
    monkeypatch.setenv("WEBDESK_PARSER_FAULT", "crash")
    assert run_isolated(TXT, b"line\n").status == "succeeded"


def test_an_oversized_child_output_fails_with_the_output_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limits, "PARSER_OUTPUT_BYTES", 16)
    with pytest.raises(ParserFailure) as exc:
        run_isolated(TXT, b"alpha\nbeta\n")
    assert exc.value.reason == limits.PARSER_OUTPUT_LIMIT


# --- F-6: the output cap is enforced while stdout is read, not after it is buffered ------------

_ENDLESS_WRITER = [
    sys.executable,
    "-c",
    "import sys\nchunk = 'x' * 65536\nwhile True:\n    sys.stdout.write(chunk)\n",
]


def test_f6_an_endless_child_output_is_stopped_at_the_cap_not_at_the_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before the fix, stdout was buffered until the timeout, so the parent held unbounded output
    and the run ended as parser_timeout. The cap must stop the child while it writes."""
    monkeypatch.setattr(limits, "PARSER_OUTPUT_BYTES", 64 * 1024)
    monkeypatch.setattr(limits, "PARSER_TIMEOUT_SECONDS", 20)
    started = time.monotonic()
    with pytest.raises(ParserFailure) as exc:
        isolation._run_child(_ENDLESS_WRITER, b"")
    assert exc.value.reason == limits.PARSER_OUTPUT_LIMIT
    assert time.monotonic() - started < 10


def test_f6_the_child_is_reaped_when_its_output_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limits, "PARSER_OUTPUT_BYTES", 64 * 1024)
    monkeypatch.setattr(limits, "PARSER_TIMEOUT_SECONDS", 20)
    created: list[subprocess.Popen[bytes]] = []
    real_popen = subprocess.Popen

    class RecordingPopen(real_popen):  # type: ignore[valid-type,misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(isolation.subprocess, "Popen", RecordingPopen)
    with pytest.raises(ParserFailure):
        isolation._run_child(_ENDLESS_WRITER, b"")
    assert len(created) == 1
    assert created[0].poll() is not None


def test_f6_output_within_the_cap_is_returned_whole_with_the_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control: a child whose output is under the cap is not refused."""
    monkeypatch.setattr(limits, "PARSER_OUTPUT_BYTES", 64 * 1024)
    returncode, stdout = isolation._run_child(
        [sys.executable, "-c", "import sys; sys.stdout.write('alpha')"], b""
    )
    assert returncode == 0
    assert stdout == b"alpha"


# --- H-33: TXT offsets are exact and split on newline only -------------------------------------


def test_txt_offsets_recover_each_segment_exactly_and_split_only_on_newlines() -> None:
    data = "Alpha\r\n  Beta\u2028still beta\u0085 end  \nGamma\n".encode()
    result = parse_text(data)
    decoded = data.decode("utf-8")
    assert [draft.text for draft in result.segments] == [
        "Alpha",
        "Beta\u2028still beta\u0085 end",
        "Gamma",
    ]
    for draft in result.segments:
        locator = draft.locator
        assert decoded[locator["start_offset"] : locator["end_offset"]] == draft.text
    assert result.segments[1].locator["line_start"] == 2


# --- H-33: EML provenance carries the Message-ID; HTML-only bodies are reported ----------------


def test_eml_segments_carry_the_message_id_as_provenance_not_content() -> None:
    result = parse_eml(build_eml(html_only=False))
    assert result.status == "succeeded"
    for draft in result.segments:
        assert draft.locator["message_id"] == "<synthetic-0001@example.test>"
        assert "synthetic-0001" not in draft.text


def test_an_html_only_eml_body_is_reported_as_an_unextractable_region() -> None:
    result = parse_eml(build_eml(html_only=True))
    assert result.status == "partial"
    assert result.flagged_regions == ["eml_part:body_html_only"]
    assert [draft.locator["eml_part"] for draft in result.segments] == ["subject"]


# --- H-33: DOCX table cells are segments with their own locator ---------------------------------


def test_docx_table_cells_are_segments_with_table_row_and_cell_locators() -> None:
    result = parse_docx(build_docx(["Body text"], [["Cell A", "Cell B"], ["Cell C", ""]]))
    cells = [d for d in result.segments if "table_index" in d.locator]
    assert [(d.text, d.locator["row"], d.locator["cell"]) for d in cells] == [
        ("Cell A", 1, 1),
        ("Cell B", 1, 2),
        ("Cell C", 2, 1),
    ]
    assert all(d.locator["table_index"] == 1 for d in cells)
    assert result.status == "succeeded"


# --- H-33: an image-only PDF page is partial, not blank ----------------------------------------


def test_an_image_only_pdf_page_is_partial_and_a_blank_page_is_not_flagged() -> None:
    partial = parse_pdf(build_pdf(["First", None, "Third"]))
    assert partial.status == "partial"
    assert partial.flagged_regions == ["pdf_page:2"]
    blank = parse_pdf(build_pdf(["First", "", "Third"]))
    assert blank.status == "succeeded"
    assert blank.flagged_regions == []


# --- H-31: the DOCX element count and the PDF page stream size are bounded ---------------------


def test_a_docx_with_more_elements_than_the_limit_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limits, "MAX_DOCX_ELEMENTS", 2)
    with pytest.raises(ParserFailure) as exc:
        parse_docx(build_docx(["one", "two", "three"]))
    assert exc.value.reason == limits.DOCX_ELEMENT_LIMIT


def test_a_pdf_page_stream_over_the_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_PDF_PAGE_STREAM_BYTES", 8)
    with pytest.raises(ParserFailure) as exc:
        parse_pdf(build_pdf(["a stream longer than eight bytes"]))
    assert exc.value.reason == limits.PDF_STREAM_LIMIT
