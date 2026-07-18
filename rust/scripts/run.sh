#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "$(uname -s)" = "Darwin" ] && command -v xattr >/dev/null 2>&1; then
  # GitHub archives are not notarized; clear their download quarantine before launch.
  xattr -dr com.apple.quarantine . 2>/dev/null || true
fi
exec ./prioris --config config.toml "$@"
