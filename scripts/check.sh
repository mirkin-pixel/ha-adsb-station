#!/usr/bin/env sh
# Runs what CI runs of the code itself: ruff, mypy, then the tests with coverage.
# The other two workflow jobs, hassfest and HACS validation, read the manifest
# and the repository layout rather than the code, and need a container.
set -e

cd "$(dirname "$0")/.."

echo "== ruff =="
ruff check .

echo "== mypy =="
mypy

echo "== pytest =="
pytest --cov --cov-report=term-missing
