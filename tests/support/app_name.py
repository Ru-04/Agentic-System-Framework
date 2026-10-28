"""Stable PostgreSQL ``application_name`` labels for test connections (QA D4).

A label names the test run (``WEBDESK_TEST_RUN_ID``) and the connection factory that opened the
connection, so ``pg_stat_activity`` and a teardown report can tell which run and factory own a
backend. A label carries no credential, address or data value: the run identifier is validated
by ``run_namespace`` and the factory names are fixed in code.
"""

from __future__ import annotations

import os

PREFIX = "webdesk-test"
# PostgreSQL truncates application_name at NAMEDATALEN - 1 bytes.
_MAX_BYTES = 63


def _clip(value: str) -> str:
    return value.encode()[:_MAX_BYTES].decode(errors="ignore")


def set_run_label(run_id: str) -> None:
    """Make every connection opened by this process, and its children, carry this run's label."""
    os.environ["PGAPPNAME"] = _clip(f"{PREFIX}/{run_id}")


def clear_run_label() -> None:
    os.environ.pop("PGAPPNAME", None)


def label(factory: str) -> str:
    """The application_name for a connection opened by the named test factory."""
    base = os.environ.get("PGAPPNAME") or PREFIX
    return _clip(f"{base}/{factory}")
