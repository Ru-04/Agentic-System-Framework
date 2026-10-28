"""The single registry of AI-S10 executors: the Stage 1 set plus the Stage 3 set.

Duplicate names are refused, so one scenario identifier can never silently resolve to two
implementations.
"""

from __future__ import annotations

from collections.abc import Callable

from evaluation import scenarios, scenarios_s10
from evaluation.catalog import Check


def build_executors() -> dict[str, Callable[[], Check]]:
    executors = scenarios.build_executors()
    overlap = sorted(set(executors) & set(scenarios_s10.EXECUTORS))
    if overlap:
        raise ValueError(f"executor names defined twice: {overlap}")
    executors.update(scenarios_s10.EXECUTORS)
    return executors
