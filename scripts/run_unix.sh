#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ "$(uname -s)" = "Darwin" ] && command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine . 2>/dev/null || true
fi

if [ ! -d .venv ]; then
  ./scripts/install_unix.sh
fi

. .venv/bin/activate
python -m prioris.bot.main
