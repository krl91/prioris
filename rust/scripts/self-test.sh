#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec ./prioris --self-test
