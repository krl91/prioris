#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  ./scripts/install_unix.sh
fi

. .venv/bin/activate
python -m prioris.bot.main
