"""Command-line entry point: run the synthetic demonstration and print structured JSON.

Usage (from the ai_engine/ directory):
    PYTHONPATH=src uv run python -m ai_engine.demo
    PYTHONPATH=src uv run python -m ai_engine.demo --out ../demo_report.json

Output is deterministic: the same fixture always produces byte-identical JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ai_engine.demo.workflow import run_demo


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
    args = parser.parse_args(argv)

    report = run_demo()
    text = render(report.model_dump(mode="json"))
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.write_text(text, encoding="utf-8")
        sys.stdout.write(f"wrote {args.out} ({report.status})\n")
    return 0
