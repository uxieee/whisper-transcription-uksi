#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: virtual environment not found at $PYTHON_BIN"
  echo "Create it first, then install dependencies."
  exit 1
fi

exec "$PYTHON_BIN" "$SCRIPT_DIR/transcribe.py" "$@"
