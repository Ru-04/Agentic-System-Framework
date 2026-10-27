"""The ceremony clock is the database clock (Phase 3, H-21).

Ceremony deadlines are computed from ``clock_timestamp()`` read in the database,
so they share one source with lease times. The injected Python clock is not used
for deadlines. Tests inject a duration (the activation window), not a time.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


def database_now(conn: Connection) -> datetime:
    """The database's current wall-clock time, as an aware datetime."""
    value = conn.execute(text("SELECT clock_timestamp()")).scalar_one()
    if not isinstance(value, datetime):
        raise TypeError("clock_timestamp() did not return a datetime")
    return value
