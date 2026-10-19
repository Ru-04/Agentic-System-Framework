"""Run errors, kept apart so the run service and the staleness module do not import each other."""

from __future__ import annotations


class RunError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(f"{status} {reason}")
        self.status = status
        self.reason = reason
