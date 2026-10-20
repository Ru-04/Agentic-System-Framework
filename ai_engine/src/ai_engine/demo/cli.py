"""Command-line entry point: run the synthetic demonstration and print structured JSON.

Investigation happens only for proposals an operator confirms with --confirm. Use --reject to record
an explicit rejection. Nothing is selected by default.

Usage (from the ai_engine/ directory):
    PYTHONPATH=src uv run python -m ai_engine.demo --confirm CAND-005 --operator demo-operator
Add --out FILE to write the JSON to a file instead of stdout.

Output is deterministic: the same inputs always produce byte-identical JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_engine.demo.workflow import DEFAULT_RATIONALE, run_demo
from ai_engine.selection.operator import SelectionError


def render(report_json: dict[str, object]) -> str:
    return json.dumps(report_json, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ai_engine.demo",
        description="Run the synthetic AI requirement investigation demonstration.",
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write JSON to this file instead of stdout"
    )
    parser.add_argument(
        "--confirm",
        action="append",
        default=[],
        metavar="PROPOSAL_KEY",
        help="operator confirms this proposal for investigation (repeatable)",
    )
    parser.add_argument(
        "--reject",
        action="append",
        default=[],
        metavar="PROPOSAL_KEY",
        help="operator explicitly rejects this proposal for investigation (repeatable)",
    )
    parser.add_argument("--operator", default=None, help="operator label recorded with decisions")
    parser.add_argument(
        "--rationale", default=DEFAULT_RATIONALE, help="rationale recorded per decision"
    )
    args = parser.parse_args(argv)

    try:
        report = run_demo(
            confirm=args.confirm,
            reject=args.reject,
            operator_label=args.operator,
            rationale=args.rationale,
        )
    except SelectionError as exc:
        sys.stderr.write(f"operator selection refused: {exc}\n")
        return 2

    text = render(report.model_dump(mode="json"))
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {args.out} ({report.status})\n")
    return 0
