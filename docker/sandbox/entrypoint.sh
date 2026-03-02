#!/bin/bash
# Helix AI Studio — Sandbox Entrypoint
# Xvfb + openbox + x11vnc + NoVNC を起動する

set -e

# --- 解像度パース ---
RESOLUTION="${RESOLUTION:-1280x720x24}"
SCREEN_WIDTH=$(echo "$RESOLUTION" | cut -dx -f1)
SCREEN_HEIGHT=$(echo "$RESOLUTION" | cut -dx -f2)
SCREEN_DEPTH=$(echo "$RESOLUTION" | cut -dx -f3)

echo "[sandbox] Starting virtual desktop: ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH}"

# --- 1. Xvfb (仮想ディスプレイ) ---
Xvfb :99 -screen 0 "${RESOLUTION}" -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 1

# Xvfb が起動したか確認
if ! kill -0 "$XVFB_PID" 2>/dev/null; then
    echo "[sandbox] ERROR: Xvfb failed to start"
    exit 1
fi
echo "[sandbox] Xvfb started (PID: $XVFB_PID)"

# --- 2. openbox (ウィンドウマネージャ) ---
openbox --sm-disable &
OPENBOX_PID=$!
sleep 0.5
echo "[sandbox] openbox started (PID: $OPENBOX_PID)"

# --- 3. x11vnc (VNCサーバー) ---
VNC_ARGS="-display :99 -forever -shared -noxdamage -nopw"
if [ -n "$VNC_PASSWORD" ]; then
    mkdir -p /home/sandbox/.vnc
    x11vnc -storepasswd "$VNC_PASSWORD" /home/sandbox/.vnc/passwd
    VNC_ARGS="-display :99 -forever -shared -noxdamage -rfbauth /home/sandbox/.vnc/passwd"
fi

x11vnc $VNC_ARGS -rfbport 5900 &
X11VNC_PID=$!
sleep 1
echo "[sandbox] x11vnc started (PID: $X11VNC_PID)"

# --- 4. NoVNC (websockify + ブラウザVNC) ---
# NoVNC の場所を検出
NOVNC_DIR=""
for dir in /usr/share/novnc /usr/share/novnc/utils/../ /opt/novnc; do
    if [ -d "$dir" ]; then
        NOVNC_DIR="$dir"
        break
    fi
done

if [ -z "$NOVNC_DIR" ]; then
    echo "[sandbox] WARNING: NoVNC directory not found, using websockify only"
    websockify --web /usr/share/novnc 6080 localhost:5900 &
else
    websockify --web "$NOVNC_DIR" 6080 localhost:5900 &
fi
WEBSOCKIFY_PID=$!
sleep 1
echo "[sandbox] NoVNC started on port 6080 (PID: $WEBSOCKIFY_PID)"

echo "[sandbox] ================================================"
echo "[sandbox] Virtual Desktop ready!"
echo "[sandbox] NoVNC: http://localhost:6080/vnc.html"
echo "[sandbox] VNC:   localhost:5900"
echo "[sandbox] Resolution: ${SCREEN_WIDTH}x${SCREEN_HEIGHT}"
echo "[sandbox] ================================================"

# --- 5. シグナルハンドラ ---
cleanup() {
    echo "[sandbox] Shutting down..."
    kill "$WEBSOCKIFY_PID" 2>/dev/null || true
    kill "$X11VNC_PID" 2>/dev/null || true
    kill "$OPENBOX_PID" 2>/dev/null || true
    kill "$XVFB_PID" 2>/dev/null || true
    echo "[sandbox] Shutdown complete"
    exit 0
}

trap cleanup SIGTERM SIGINT

# --- 6. PID 1 として待機 ---
wait
