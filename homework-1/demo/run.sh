#!/usr/bin/env bash
# Start the Banking Transactions API on http://localhost:3000
#
#   ./demo/run.sh          start the server with demo data (demo/sample-data.json)
#   SEED_DATA=0 ./demo/run.sh   start with an empty store
#   ./demo/run.sh test     run the test suite instead
#
# Creates .venv and installs requirements.txt on first run.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    PYTHON="$(command -v python3 || command -v python)"
    echo "Creating virtual environment with $PYTHON ..."
    "$PYTHON" -m venv .venv
fi

# .venv/bin on Linux/macOS, .venv/Scripts on Windows (Git Bash)
if [ -x .venv/bin/python ]; then VENV_PY=.venv/bin/python; else VENV_PY=.venv/Scripts/python; fi

echo "Installing dependencies ..."
"$VENV_PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt

if [ "${1:-}" = "test" ]; then
    exec "$VENV_PY" -m pytest
fi

export SEED_DATA="${SEED_DATA:-1}"
export PORT="${PORT:-3000}"
echo "Starting API on http://localhost:$PORT (seed data: $SEED_DATA). Press Ctrl+C to stop."
exec "$VENV_PY" -m src.app
