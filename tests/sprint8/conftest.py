"""Sprint 8 QA gate: keeps a database-free run from reporting database verification as complete.

Modes, chosen with ``S8_QA_MODE`` (default ``unit``):

- ``unit``: database-free development run. Database checks are skipped with a ``BLOCKED:``
  reason, and the summary says database verification was NOT RUN. Exit status is unchanged.
- ``db``: database-required QA run. Refuses to start without ``WEBDESK_TEST_DATABASE_URL``.
  Fails the session if any check that is not a declared ``BLOCKED`` placeholder was skipped,
  failed or errored.

A ``BLOCKED`` skip is an explicit placeholder for a dependency that does not exist yet (OPEN-11,
S6-INT). It is counted separately and never counted as passed.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

MODE = os.environ.get("S8_QA_MODE", "unit")
_MODES = ("unit", "db")


def _is_blocked(report: pytest.TestReport) -> bool:
    """True only for a skip whose reason starts with ``BLOCKED:``."""
    longrepr = report.longrepr
    message = (
        str(longrepr[2]) if isinstance(longrepr, tuple) and len(longrepr) == 3 else str(longrepr)
    )
    reason = message.split(": ", 1)[-1]
    return reason.startswith("BLOCKED:")


def pytest_configure(config: pytest.Config) -> None:
    if MODE not in _MODES:
        raise pytest.UsageError(f"S8_QA_MODE must be one of {_MODES}, not {MODE!r}")
    if MODE == "db" and not os.environ.get("WEBDESK_TEST_DATABASE_URL"):
        raise pytest.UsageError(
            "BLOCKED: S8_QA_MODE=db requires WEBDESK_TEST_DATABASE_URL. "
            "No database was configured, so database verification was not run."
        )


def _counts(terminalreporter: Any) -> dict[str, int]:
    stats = terminalreporter.stats
    skipped = stats.get("skipped", [])
    blocked = [r for r in skipped if _is_blocked(r)]
    return {
        "passed": len(stats.get("passed", [])),
        "failed": len(stats.get("failed", [])) + len(stats.get("error", [])),
        "skipped": len(skipped) - len(blocked),
        "blocked": len(blocked),
    }


def pytest_terminal_summary(terminalreporter: Any) -> None:
    counts = _counts(terminalreporter)
    if MODE == "db":
        clean = counts["failed"] == 0 and counts["skipped"] == 0 and counts["passed"] > 0
        if not clean:
            verdict = "FAIL"
        elif counts["blocked"]:
            verdict = f"PASS WITH {counts['blocked']} BLOCKED (not verified)"
        else:
            verdict = "PASS"
    else:
        verdict = "UNIT ONLY" + (": database verification NOT RUN" if counts["blocked"] else "")
    terminalreporter.write_sep(
        "=",
        f"S8 QA gate mode={MODE} executed-passed={counts['passed']} "
        f"failed={counts['failed']} skipped={counts['skipped']} blocked={counts['blocked']} "
        f"verdict={verdict}",
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if MODE != "db":
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is None:
        return
    counts = _counts(reporter)
    if counts["failed"] or counts["skipped"] or counts["passed"] == 0:
        session.exitstatus = 1
