"""Isolated parser execution (Phase 4, H-32).

Each parse runs in a child process (``webdesk.intake.parser_child``) that imports the parsers and
nothing from the database layer. The child receives the file on stdin and returns a JSON result on
stdout. The parent enforces a wall-clock timeout, an output cap and (on POSIX) an address-space cap,
and maps every failure to a stable class. A crashed, hung or oversized child fails only the version
being parsed; the worker process survives and the child is always reaped.

The child environment is built from an allowlist. No database URL, storage key or operator secret
reaches the child, so a parser holds no database privilege (H-32).
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import webdesk
from webdesk.intake import limits
from webdesk.intake.parsers import PARSERS, ParseResult, ParserFailure, SegmentDraft

# Fault injection for the subprocess tests. Honoured only when WEBDESK_ENV=test (see parser_child).
FAULT_ENV = "WEBDESK_PARSER_FAULT"
_ALLOWED_ENV = ("SYSTEMROOT", "TEMP", "TMP", "PATH", "WEBDESK_ENV")

Runner = Callable[[str, bytes], ParseResult]


def _src_root() -> str:
    """The directory that holds the ``webdesk`` package, so the child imports this same code."""
    return str(Path(webdesk.__file__).resolve().parents[1])


def child_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """The only environment a parser child receives. It is an allowlist, never a copy."""
    env_source = os.environ if source is None else source
    env = {key: env_source[key] for key in _ALLOWED_ENV if key in env_source}
    env["PYTHONPATH"] = _src_root()
    if env_source.get("WEBDESK_ENV") == "test" and FAULT_ENV in env_source:
        env[FAULT_ENV] = env_source[FAULT_ENV]
    return env


def _limit_memory() -> None:  # pragma: no cover - runs in the child on POSIX only
    if sys.platform == "win32":
        return
    import resource

    cap = limits.PARSER_MEMORY_BYTES
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))


_READ_CHUNK = 64 * 1024


def _spawn_options() -> dict[str, Any]:
    if sys.platform == "win32":
        # No console window for the child. The process timeout is the bound on Windows (H-DEC-4).
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {"preexec_fn": _limit_memory}


def _run_child(command: list[str], data: bytes) -> tuple[int, bytes]:
    """Run one child with ``data`` on stdin. Return its exit code and its stdout.

    Stdout is read while the child runs and never holds more than ``PARSER_OUTPUT_BYTES + 1``
    bytes (F-6). Past that the child is killed and ``ParserFailure(PARSER_OUTPUT_LIMIT)`` is raised,
    so the parent does not buffer an oversized output before it refuses it. The whole run is bounded
    by ``PARSER_TIMEOUT_SECONDS``: a child over it is killed and reaped, and
    ``subprocess.TimeoutExpired`` is raised.
    """
    cap = limits.PARSER_OUTPUT_BYTES
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=child_environment(),
        cwd=_src_root(),
        **_spawn_options(),
    )
    assert process.stdin is not None and process.stdout is not None
    stdin, stdout = process.stdin, process.stdout
    output = bytearray()
    overflow = threading.Event()

    def feed() -> None:
        try:
            stdin.write(data)
        except OSError:
            pass  # the child exited before it read all of its input; its exit status decides
        finally:
            with contextlib.suppress(OSError):
                stdin.close()

    def drain() -> None:
        while True:
            chunk = stdout.read1(min(_READ_CHUNK, cap + 1 - len(output)))
            if not chunk:
                return
            output.extend(chunk)
            if len(output) > cap:
                overflow.set()
                process.kill()
                return

    feeder = threading.Thread(target=feed, daemon=True)
    reader = threading.Thread(target=drain, daemon=True)
    deadline = time.monotonic() + limits.PARSER_TIMEOUT_SECONDS
    try:
        feeder.start()
        reader.start()
        reader.join(limits.PARSER_TIMEOUT_SECONDS)
        if reader.is_alive():
            raise subprocess.TimeoutExpired(command, limits.PARSER_TIMEOUT_SECONDS)
        if overflow.is_set():
            raise ParserFailure(limits.PARSER_OUTPUT_LIMIT)
        returncode = process.wait(timeout=max(0.0, deadline - time.monotonic()))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        feeder.join(timeout=5)
        reader.join(timeout=5)
        stdout.close()
    return returncode, bytes(output)


def run_isolated(mime: str, data: bytes) -> ParseResult:
    """Parse ``data`` in a child process. Any fault raises ``ParserFailure`` with a stable class."""
    # ``-s`` skips the user site. ``-I`` is not used because it would ignore PYTHONPATH, and the
    # child must import this same source tree. The environment is an allowlist either way.
    command = [sys.executable, "-s", "-m", "webdesk.intake.parser_child", mime]
    try:
        returncode, stdout = _run_child(command, data)
    except subprocess.TimeoutExpired as exc:
        # subprocess.run kills the child and waits for it before raising.
        raise ParserFailure(limits.PARSER_TIMEOUT) from exc
    except OSError as exc:
        raise ParserFailure(limits.PARSER_CRASH) from exc

    if returncode != 0:
        raise ParserFailure(limits.PARSER_CRASH)
    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParserFailure(limits.PARSER_CRASH) from exc
    if "failure" in payload:
        raise ParserFailure(str(payload["failure"]))
    return ParseResult(
        status=str(payload["status"]),
        segments=[
            SegmentDraft(str(item["locator_type"]), dict(item["locator"]), str(item["text"]))
            for item in payload["segments"]
        ],
        flagged_regions=[str(region) for region in payload["flagged_regions"]],
        unprocessed_attachments=list(payload["unprocessed_attachments"]),
    )


ADMISSION_MODE = "admission"


def open_pdf_in_child(data: bytes) -> bool:
    """Open a PDF for upload admission in the isolated child, and return whether it is encrypted.

    The API process never opens a PDF itself. The child runs under the parse's timeout and output
    cap, so a malformed structure that makes the reader loop or expand is refused as
    ``parser_timeout`` or a classified failure, and the request is released. The timeout is a
    containment, not a memory bound.
    """
    command = [sys.executable, "-s", "-m", "webdesk.intake.parser_child", ADMISSION_MODE]
    try:
        returncode, stdout = _run_child(command, data)
    except subprocess.TimeoutExpired as exc:
        raise ParserFailure(limits.PARSER_TIMEOUT) from exc
    except OSError as exc:
        raise ParserFailure(limits.PARSER_CRASH) from exc
    if returncode != 0:
        raise ParserFailure(limits.PARSER_CRASH)
    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ParserFailure(limits.PARSER_CRASH) from exc
    if "failure" in payload:
        raise ParserFailure(str(payload["failure"]))
    return bool(payload["encrypted"])


def run_in_process(mime: str, data: bytes) -> ParseResult:
    """The same parsers, run in the caller's process. Used by tests that inject a parser."""
    parser = PARSERS.get(mime)
    if parser is None:
        raise ParserFailure("unsupported_mime")
    return parser(data)
