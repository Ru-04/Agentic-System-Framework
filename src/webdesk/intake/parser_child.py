"""Parser child process entry point (Phase 4, H-32).

Usage: ``python -s -m webdesk.intake.parser_child <mime>`` with the file on stdin. The result is one
JSON object on stdout. Only the parsers are imported here: nothing from the database, storage or
authority layers. The parent (``isolation.run_isolated``) enforces the timeout and the output cap.

Fault injection (``WEBDESK_PARSER_FAULT=crash|hang``) exists only for the subprocess tests and is
ignored unless ``WEBDESK_ENV=test``.
"""

from __future__ import annotations

import json
import os
import sys
import time

from webdesk.intake.parsers import PARSERS, ParseResult, ParserFailure


def _inject_fault() -> None:
    if os.environ.get("WEBDESK_ENV") != "test":
        return
    fault = os.environ.get("WEBDESK_PARSER_FAULT")
    if fault == "crash":
        os._exit(3)
    if fault == "hang":
        time.sleep(3600)


def _encode(result: ParseResult) -> dict[str, object]:
    return {
        "status": result.status,
        "segments": [
            {"locator_type": draft.locator_type, "locator": draft.locator, "text": draft.text}
            for draft in result.segments
        ],
        "flagged_regions": result.flagged_regions,
        "unprocessed_attachments": result.unprocessed_attachments,
    }


def main(argv: list[str]) -> int:
    mime = argv[1]
    data = sys.stdin.buffer.read()
    _inject_fault()
    parser = PARSERS.get(mime)
    if parser is None:
        payload: dict[str, object] = {"failure": "unsupported_mime"}
    else:
        try:
            payload = _encode(parser(data))
        except ParserFailure as exc:
            payload = {"failure": exc.reason}
        except Exception:
            payload = {"failure": "parser_exception"}
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
