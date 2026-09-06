#!/bin/bash
# Host-side bridges for running the Qt app inside Docker on macOS.
# Docker Desktop cannot reach USB serial or CoreAudio, so the host lends both:
#   serial : socat forwards the pen board's USB CDC port to TCP 7777
#   audio  : PulseAudio (brew) accepts network audio from the container
#   display: XQuartz shows the Qt window (start it yourself, enable
#            "Allow connections from network clients" in its settings)
set -euo pipefail

echo "== Pen Mixer host bridges =="

# --- serial -> tcp ----------------------------------------------------------
PORT_DEV=$(ls /dev/cu.usbmodem* 2>/dev/null | head -1 || true)
if [ -z "$PORT_DEV" ]; then
  echo "serial : no pen board found (/dev/cu.usbmodem*). Plug it in, or use Simulate mode in the app."
else
  command -v socat >/dev/null || { echo "serial : installing socat"; brew install socat; }
  echo "serial : $PORT_DEV -> tcp:7777"
  socat -u "FILE:$PORT_DEV,b115200,raw" TCP-LISTEN:7777,reuseaddr,fork &
  SOCAT_PID=$!
  trap 'kill $SOCAT_PID 2>/dev/null || true' EXIT
fi

# --- pulseaudio -------------------------------------------------------------
if ! command -v pulseaudio >/dev/null; then
  echo "audio  : installing pulseaudio"; brew install pulseaudio
fi
pkill -x pulseaudio 2>/dev/null || true
pulseaudio --exit-idle-time=-1 \
  --load="module-native-protocol-tcp auth-anonymous=1" \
  --load="module-coreaudio-detect" \
  --daemonize
echo "audio  : pulseaudio listening on tcp:4713 (module-native-protocol-tcp)"
echo "         In the app, pick the BlackHole source as input and your speakers as output."

# --- display ----------------------------------------------------------------
if pgrep -x Xquartz >/dev/null || pgrep -x XQuartz >/dev/null; then
  xhost + 127.0.0.1 2>/dev/null || true
  echo "display: XQuartz running, localhost allowed"
else
  echo "display: XQuartz NOT running. Install with 'brew install --cask xquartz',"
  echo "         start it, enable Settings -> Security -> 'Allow connections from"
  echo "         network clients', log out/in once, then rerun this script."
fi

echo
echo "Bridges up. Now run:  docker compose up --build app"
wait
