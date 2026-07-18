#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$(uname -s)" = "Darwin" ] && [ -x "PRIORIS.app/Contents/MacOS/prioris" ]; then
  exec ./PRIORIS.app/Contents/MacOS/prioris --config config.toml "$@"
fi
exec ./prioris --config config.toml "$@"
