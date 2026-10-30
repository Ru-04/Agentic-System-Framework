"""Atomic rate-limit check and record (H-72; EVAL-F11e), real PostgreSQL transactions.

Two connections race for one key with a limit of one. The second attempt must wait for the first to
finish, and then it must be refused. Requires WEBDESK_TEST_DATABASE_URL.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from webdesk.ratelimit.limiter import Limit, RateLimitExceeded, enforce

pytestmark = pytest.mark.integration

ONE_PER_WINDOW = Limit("test:h72", 1, timedelta(minutes=15))


@pytest.fixture
def engine(committed_engine: Engine) -> Iterator[Engine]:
    yield committed_engine


def _wait_for_waiter(engine: Engine, timeout: float = 15.0) -> None:
    """Return once a backend is blocked on an advisory lock. Polls the catalogue, no fixed sleep."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with engine.connect() as probe:
            waiting = probe.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE wait_event_type = 'Lock' AND backend_type = 'client backend'"
                )
            ).scalar_one()
        if int(waiting) >= 1:
            return
        time.sleep(0.02)
    raise AssertionError("the second attempt never waited on the rate-limit key")


def test_a_second_attempt_waits_for_the_first_and_is_then_refused(engine: Engine) -> None:
    first = engine.connect()
    second = engine.connect()
    first_tx = first.begin()
    second_tx = second.begin()
    outcome: dict[str, object] = {}

    def attempt() -> None:
        try:
            enforce(second, ONE_PER_WINDOW, "203.0.113.7")
            outcome["result"] = "allowed"
        except RateLimitExceeded:
            outcome["result"] = "refused"

    try:
        enforce(first, ONE_PER_WINDOW, "203.0.113.7")
        thread = threading.Thread(target=attempt, daemon=True)
        thread.start()
        _wait_for_waiter(engine)
        assert (
            "result" not in outcome
        ), "the second attempt must not finish while the first holds the key"
        first_tx.commit()
        thread.join(timeout=30)
        assert not thread.is_alive()
        assert outcome["result"] == "refused"
    finally:
        second_tx.rollback()
        second.close()
        if first_tx.is_active:
            first_tx.rollback()
        first.close()


def test_different_keys_do_not_block_each_other(engine: Engine) -> None:
    first = engine.connect()
    second = engine.connect()
    first_tx = first.begin()
    second_tx = second.begin()
    try:
        enforce(first, ONE_PER_WINDOW, "198.51.100.1")
        enforce(second, ONE_PER_WINDOW, "198.51.100.2")
    finally:
        second_tx.rollback()
        second.close()
        first_tx.rollback()
        first.close()
