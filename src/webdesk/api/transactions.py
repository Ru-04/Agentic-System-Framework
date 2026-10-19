"""Transaction runner: keep denial audits, discard everything else (C-2; EVAL-F12).

Services record a denial, then raise a domain refusal. If the caller rolled back on that refusal,
the denial audit would be lost. This runner commits when a known refusal is raised, and rolls back
on any other error. It relies on the services raising refusals before they write business rows.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.engine import Connection, Engine

from webdesk.api.errors import DOMAIN_ERRORS

T = TypeVar("T")


def run_in_transaction(engine: Engine, operation: Callable[[Connection], T]) -> T:
    connection = engine.connect()
    transaction = connection.begin()
    try:
        result = operation(connection)
    except DOMAIN_ERRORS:
        transaction.commit()
        raise
    except BaseException:
        transaction.rollback()
        raise
    else:
        transaction.commit()
        return result
    finally:
        connection.close()
