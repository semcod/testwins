#!/bin/sh
set -eu
umask 077
mkdir -p "$HOME" /tmp/project
# Disposable writable copy; the included project is never modified on the host.
cp -R /input/. /tmp/project/
# The worker has a fresh display, no access to the host desktop socket.
exec xvfb-run -a -s '-screen 0 1440x1000x24 -nolisten tcp' \
  python -m testwins.task_worker "$@" --project /tmp/project
