#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --find-links wheelhouse -e .

if [ ! -f config.toml ]; then
  cp config.example.toml config.toml
fi

printf '%s\n' "PRIORIS installed."
printf '%s\n' "Edit config.toml, then run ./scripts/run_unix.sh"
