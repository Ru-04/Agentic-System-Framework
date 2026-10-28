"""Connection attribution for test databases (QA D4).

Each test engine labels its connections with ``application_name``. The label names the run and the
factory, and nothing else: no password, address or data value.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.support.app_name import PREFIX, label

pytestmark = pytest.mark.integration


def test_a_committed_connection_names_its_run_and_factory(committed_engine: Engine) -> None:
    with committed_engine.connect() as conn:
        name = conn.execute(text("SELECT current_setting('application_name')")).scalar_one()
    assert name == label("committed")
    assert name.startswith(PREFIX + "/")
    assert len(name.encode()) <= 63


def test_labels_are_stable_clipped_and_free_of_secrets() -> None:
    value = label("a-factory")
    assert value == label("a-factory")
    assert "@" not in value and "://" not in value and "password" not in value.lower()
    assert len(value.encode()) <= 63
