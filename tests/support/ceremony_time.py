"""Signed-authorization expiry used by test fixtures (D-3).

Test fixtures construct the installation and recovery inputs directly, without a signed file. Their
expiry is
therefore set far in the future, and the database clock decides it, as in production. A fixture
never relies on
an application clock to grant or refuse authorization.
"""

from __future__ import annotations

from datetime import UTC, datetime

FAR_FUTURE = datetime(2999, 1, 1, tzinfo=UTC)
