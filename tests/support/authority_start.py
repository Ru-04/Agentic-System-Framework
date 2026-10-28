"""Start-up helpers for the authority test process (QA F-authority startup).

The harness used to probe a free port, release it and hand the number to the child, which bound it
later. Another socket could take the port in between, and the child's failure text went to an
inherited stderr that no report captured. The child now binds an ephemeral port and reports the
real port on its start-up line. A failed start reports the exit code and a redacted stderr tail.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_LISTEN = re.compile(r"authority listening on \('127\.0\.0\.1', (\d+)\)")
_URL_USERINFO = re.compile(r"://[^@/\s]+@")


def listen_port(line: str) -> int | None:
    """The port named on the start-up line, or None when the line is not a start-up line."""
    match = _LISTEN.search(line)
    return int(match.group(1)) if match else None


def redact(text: str, secrets: Iterable[str]) -> str:
    """Remove each secret value and any URL user information from text before it is reported."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "<redacted>")
    return _URL_USERINFO.sub("://<redacted>@", text)
