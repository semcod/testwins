#!/bin/sh
set -eu
/usr/local/bin/testwins-desktop & DESKTOP=$!
MONITOR=''
cleanup() { [ -z "$MONITOR" ] || kill "$MONITOR" 2>/dev/null || true; kill "$DESKTOP" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
n=0
until xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
  kill -0 "$DESKTOP" || exit 2
  n=$((n+1)); [ "$n" -lt 100 ] || exit 2
  sleep 0.1
done
python -m testwins watch "$@" & MONITOR=$!
wait "$MONITOR"
