#!/bin/sh
set -eu
umask 077
mkdir -p "$HOME" /tmp/testwins-vnc
if [ ! -r /run/secrets/vnc_password ]; then echo 'Missing VNC password secret' >&2; exit 2; fi
x11vnc -storepasswd "$(cat /run/secrets/vnc_password)" /tmp/testwins-vnc/passwd >/dev/null
Xvfb "$DISPLAY" -screen 0 1920x1400x24 -nolisten tcp >/tmp/xvfb.log 2>&1 & P1=$!
P2=''; P3=''; P4=''; P5=''
cleanup() { kill "$P1" ${P2:+$P2} ${P3:+$P3} ${P4:+$P4} ${P5:+$P5} 2>/dev/null || true; }
trap cleanup EXIT INT TERM
n=0
until xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
  n=$((n+1)); [ "$n" -lt 100 ] || { echo 'Xvfb startup failed' >&2; exit 2; }; sleep 0.1
done
fluxbox >/tmp/fluxbox.log 2>&1 & P2=$!
x11vnc -display "$DISPLAY" -localhost -rfbport 5900 -rfbauth /tmp/testwins-vnc/passwd \
  -forever -shared -noxdamage >/tmp/x11vnc.log 2>&1 & P3=$!
websockify --web=/usr/share/novnc/ 0.0.0.0:6080 127.0.0.1:5900 >/tmp/websockify.log 2>&1 & P4=$!
python /opt/testwins/report_server.py --directory /artifacts --host 0.0.0.0 --port 8088 >/tmp/report-server.log 2>&1 & P5=$!
# The audit is an explicit `docker compose exec`, not an unbounded background scanner.
while kill -0 "$P1" "$P2" "$P3" "$P4" "$P5" 2>/dev/null; do sleep 2; done
echo 'A desktop service stopped' >&2
exit 2
