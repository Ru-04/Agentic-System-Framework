#!/usr/bin/env bash
# Sprint 8 QA gate (S8-13). Runs the mandatory static and test checks in order and fails on the first error.
# Usage:
#   scripts/s8_qa_gate.sh                 unit mode: database checks reported as NOT RUN
#   WEBDESK_TEST_DATABASE_URL=... scripts/s8_qa_gate.sh   database mode: the full gate
# Requires the project venv (.venv) to be synced with: uv sync --extra dev --frozen
set -euo pipefail

PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"

echo "== ruff check"
"$PY" -m ruff check .
echo "== ruff format --check (Sprint 8 tests)"
"$PY" -m ruff format --check tests/sprint8 tests/perf
echo "== mypy --strict (configured scope: src/webdesk)"
"$PY" -m mypy --strict src/webdesk

if [ -n "${WEBDESK_TEST_DATABASE_URL:-}" ]; then
  echo "== Sprint 8 tests, database mode"
  S8_QA_MODE=db "$PY" -m pytest tests/sprint8 -q
  echo "== database security regression"
  "$PY" -m pytest tests/integration/test_outbox_worker.py tests/committed/test_ai_read_v1.py \
    tests/committed/test_durable_execution.py tests/integration/test_projects.py \
    tests/integration/test_phase2_guards.py tests/integration/test_runs_db.py -q
else
  echo "== Sprint 8 tests, unit mode (database verification NOT RUN)"
  env -u WEBDESK_TEST_DATABASE_URL S8_QA_MODE=unit "$PY" -m pytest tests/sprint8 -q
fi

echo "== unit regression"
env -u WEBDESK_TEST_DATABASE_URL "$PY" -m pytest tests/unit -q
echo "== S8 QA gate finished (exit 0)"
