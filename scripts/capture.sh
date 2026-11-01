#!/usr/bin/env bash
# Capture screenshots of the running PyQt6 app on a private Xvfb display.
# Resolution is controlled by NEXUS_SCREEN_W / NEXUS_SCREEN_H (default 800×480).
# Touches no real display, service or printer state.
#   scripts/capture.sh OUT_DIR
#   NEXUS_SCREEN_W=480 NEXUS_SCREEN_H=320 scripts/capture.sh OUT_DIR
#   scripts/capture-multi.sh OUT_DIR   # run all four reference resolutions
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?usage: capture.sh OUT_DIR}"
PY="${NEXUS_PY:-$HOME/nexus-screen-env/bin/python}"
W="${NEXUS_SCREEN_W:-800}"
H="${NEXUS_SCREEN_H:-480}"
mkdir -p "$OUT"

# Use Xvfb (xcb) when available, fall back to Qt offscreen platform.
XVFB_BIN="${NEXUS_XVFB:-$(command -v Xvfb 2>/dev/null || echo "")}"
if [ -n "$XVFB_BIN" ] && [ -x "$XVFB_BIN" ]; then
    DISP="${NEXUS_DISPLAY:-93}"
    "$XVFB_BIN" ":$DISP" -screen 0 "${W}x${H}x24" -nolisten tcp -noreset >"$OUT/xvfb.log" 2>&1 &
    XPID=$!
    trap 'kill $XPID 2>/dev/null || true' EXIT
    for _ in $(seq 1 50); do [ -e "/tmp/.X11-unix/X$DISP" ] && break; sleep 0.1; done
    QT_BACKEND="DISPLAY=:$DISP QT_QPA_PLATFORM=xcb"
    run() {
        local name="$1"; shift
        DISPLAY=":$DISP" QT_QPA_PLATFORM=xcb \
            NEXUS_SCREEN_W="$W" NEXUS_SCREEN_H="$H" \
            "$PY" "$HERE/main.py" --capture "$OUT/$name.png" "$@" \
            2>>"$OUT/app-stderr.log"
    }
else
    echo "Xvfb not found — using Qt offscreen platform" >&2
    run() {
        local name="$1"; shift
        QT_QPA_PLATFORM=offscreen \
            NEXUS_SCREEN_W="$W" NEXUS_SCREEN_H="$H" \
            "$PY" "$HERE/main.py" --capture "$OUT/$name.png" "$@" \
            2>>"$OUT/app-stderr.log"
    }
fi
run 01-home-standby          --state standby  --addons both
run 02-print-printing       --state printing --addons both
run 02b-print-stop-confirm  --state printing --addons both --review stop-dialog
run 03-print-paused         --state paused   --addons both
run 02c-print-thumbnail     --state printing --addons both --sim-file "Lid_PLA_4h34m.gcode"
run 03c-paused-thumbnail    --state paused   --addons both --sim-file "[TPU] NH36Sock_PLA_1h2m.gcode"
run 03b-home-during-print   --state printing --addons both --review home
run 04-home-stealthchanger   --state standby  --addons stealthchanger
run 05-home-boxturtle        --state standby  --addons boxturtle
run 06-home-no-addons        --state standby  --addons none
run 10-keypad-nozzle         --state standby  --review keypad-nozzle
run 11-keypad-bed-invalid    --state standby  --review keypad-bed
run 20-boxturtle-dashboard   --state standby  --review bt-dashboard
run 21-boxturtle-dash-8lanes --state standby  --review bt-dashboard --lanes 8
run 22-boxturtle-controls    --state standby  --review bt-controls
run 23-colour-picker         --state standby  --review colour-picker
run 30-stealthchanger-dash   --state standby  --review sc-dashboard
run 31-stealthchanger-ctrl   --state standby  --review sc-controls
run 32-material-picker       --state standby  --review material-picker
run 33-sc-controls-printing  --state printing --review sc-controls
run 40-temperature           --state standby  --review temperature
run 41-temperature-pid       --state standby  --review pid-confirm
run 42-fans                  --state standby  --review fans
run 43-lighting              --state standby  --review lighting
run 44-move                  --state standby  --review move
run 50-control               --state standby  --review control
run 51-z-offset              --state standby  --review z-offset
run 52-z-offset-preset       --state standby  --review z-offset-preset
run 53-bed-screws            --state standby  --review bed-screws
run 54-bed-mesh              --state standby  --review bed-mesh
run 55-bed-mesh-profile      --state standby  --review bed-mesh-profile
run 60-filament-page         --state standby  --review filament-page
run 61-filament              --state standby  --review filament
run 62-filament-heating      --state standby  --review filament-heating
run 63-filament-material     --state standby  --review filament-material
run 64-profiles              --state standby  --review profiles
run 65-profiles-edit         --state standby  --review profiles-edit
run 66-profiles-keypad       --state standby  --review profiles-keypad
run 67-extruder              --state printing --review extruder
run 68-extruder-hot          --state standby  --review extruder
run 69-extruder-pa           --state standby  --review extruder-pa
if [ "${NEXUS_LIVE:-0}" = 1 ]; then
    run 70-filament-live         --live --delay 3500 --review filament
    run 71-profiles-live         --live --delay 3500 --review profiles
    run 72-extruder-live         --live --delay 3500 --review extruder
    run 56-control-live          --live --delay 3500 --review control
    run 57-bed-screws-live       --live --delay 3500 --review bed-screws
    run 58-bed-mesh-live         --live --delay 5000 --review bed-mesh-default
    run 59-z-offset-live         --live --delay 3500 --review z-offset
    run 07-home-live-readonly    --live --delay 3500
    run 45-temperature-live      --live --delay 3500 --review temperature
    run 46-fans-live             --live --delay 3500 --review fans
    run 47-lighting-live         --live --delay 3500 --review lighting
    run 48-move-live             --live --delay 3500 --review move
fi
true
