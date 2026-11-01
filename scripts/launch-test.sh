#!/usr/bin/env bash
# Manual physical-touchscreen test launcher for Nexus Screen. Installs nothing, changes no
# service, never sends printer commands (refuses --allow-commands).
#
#   scripts/launch-test.sh --check            preflight only: prints what would run
#   scripts/launch-test.sh [sim|live] [--minutes N] [--evdev] [--display-writes]
#   scripts/launch-test.sh --stop             stop the test app started by this script
#
#   sim   (default) simulated printer data
#   live  real Moonraker status, read-only (all printer commands disabled)
#   --minutes N       dead-man timer: the app is stopped after N minutes (default 30)
#   --evdev           use Qt's evdev touch driver instead of libinput
#   --display-writes  allow the Screen settings to change the real backlight
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="${NEXUS_PY:-$HOME/nexus-screen-env/bin/python}"
FB=/dev/fb0
TOUCH=/dev/input/event3
RUN="$HERE/run"
PIDFILE="$RUN/test-app.pid"
mkdir -p "$RUN" "$HERE/logs"

mode=sim minutes=30 check=0 evdev=0 dwrites=0
for a in "$@"; do
    case "$a" in
        sim|live) mode=$a ;;
        --check) check=1 ;;
        --evdev) evdev=1 ;;
        --display-writes) dwrites=1 ;;
        --minutes) ;;
        --stop)
            if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
                kill "$(cat "$PIDFILE")" && echo "stopped test app (pid $(cat "$PIDFILE"))"
            else
                echo "no test app running"
            fi
            rm -f "$PIDFILE"; exit 0 ;;
        --allow-commands) echo "refused: printer commands stay disabled during physical testing" >&2; exit 2 ;;
        [0-9]*) minutes=$a ;;
        *) echo "unknown option: $a" >&2; exit 2 ;;
    esac
done

fail=0
say() { printf '  %-34s %s\n' "$1" "$2"; }
echo "Preflight"
[ -c "$FB" ] && say "framebuffer $FB" "ok ($(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null) @ $(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null) bpp)" || { say "framebuffer $FB" "MISSING"; fail=1; }
[ -r "$FB" ] && [ -w "$FB" ] && say "framebuffer access" "ok" || { say "framebuffer access" "NO (need group video)"; fail=1; }
[ -r "$TOUCH" ] && say "touchscreen $TOUCH" "ok" || { say "touchscreen $TOUCH" "NO ACCESS (need group input)"; fail=1; }
holders="$(fuser "$FB" 2>/dev/null | tr -s ' ' || true)"
if [ -n "${holders// /}" ]; then
    say "screen free" "NO — in use by pid(s):$holders"
    for p in $holders; do echo "      $(ps -o pid=,etime=,args= -p "$p" 2>/dev/null)"; done
    echo "      Stop those first (they are not started by this script), e.g. Ctrl+C in their terminal."
    fail=1
else
    say "screen free" "ok"
fi
for svc in KlipperScreen; do
    st="$(systemctl is-active "$svc" 2>/dev/null || true)"
    [ "$st" = active ] && { say "$svc.service" "ACTIVE — would fight for the screen; not touched"; fail=1; } || say "$svc.service" "$st (left as is)"
done
pgrep -x Xorg >/dev/null && { say "Xorg" "RUNNING — would fight for the screen"; fail=1; } || say "Xorg" "not running"
"$PY" -c "import PyQt6.QtCore as c; print(c.PYQT_VERSION_STR)" >/dev/null 2>&1 && say "PyQt6" "$("$PY" -c 'import PyQt6.QtCore as c; print(c.PYQT_VERSION_STR)')" || { say "PyQt6" "MISSING"; fail=1; }
[ -f /usr/lib/aarch64-linux-gnu/qt6/plugins/platforms/libqlinuxfb.so ] && say "Qt linuxfb plugin" "ok" || { say "Qt linuxfb plugin" "MISSING"; fail=1; }
if [ "$mode" = live ]; then
    curl -s -m 3 http://localhost:7125/server/info >/dev/null && say "Moonraker" "reachable (read-only use)" || say "Moonraker" "not reachable (app shows Disconnected)"
fi

export QT_QPA_PLATFORM="linuxfb:fb=$FB"
export QT_QPA_FB_HIDECURSOR=1
if [ "$evdev" = 1 ]; then
    export QT_QPA_FB_NO_LIBINPUT=1 QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS="$TOUCH"
fi
args=(--hardware-display)
[ "$dwrites" = 1 ] && args+=(--display-writes)
[ "$mode" = live ] && args+=(--live)
log="$HERE/logs/test-$(date +%Y%m%d-%H%M%S)-$mode.log"
echo
echo "Would run: QT_QPA_PLATFORM=$QT_QPA_PLATFORM${QT_QPA_FB_NO_LIBINPUT:+ (evdev touch)} $PY main.py ${args[*]}"
echo "Dead-man: stops after $minutes min · log: $log · stats: ${log%.log}-stats.csv"
[ "$check" = 1 ] && { [ "$fail" = 0 ] && echo "Preflight OK" || echo "Preflight FAILED"; exit "$fail"; }
[ "$fail" = 0 ] || { echo "Preflight failed: not starting." >&2; exit 1; }

# hide the console cursor on tty1 so it cannot blink through the app; restored on exit
TERM=linux setterm --cursor off >/dev/tty1 2>/dev/null || true
cleanup() {
    TERM=linux setterm --cursor on >/dev/tty1 2>/dev/null || true
    rm -f "$PIDFILE"
    [ -n "${sampler:-}" ] && kill "$sampler" 2>/dev/null || true
}
trap cleanup EXIT

cd "$HERE"
timeout --signal=TERM "${minutes}m" "$PY" main.py "${args[@]}" >"$log" 2>&1 &
app=$!
sleep 1
pid="$(pgrep -P "$app" -f "main.py" || echo "$app")"
echo "$pid" > "$PIDFILE"
( echo "time,cpu_percent_of_one_core,rss_mib"
  hz=$(getconf CLK_TCK); prev=$(awk '{print $14+$15}' "/proc/$pid/stat" 2>/dev/null || echo 0); t0=$(date +%s)
  while kill -0 "$pid" 2>/dev/null; do
      sleep 5
      cur=$(awk '{print $14+$15}' "/proc/$pid/stat" 2>/dev/null) || break
      rss=$(awk '/VmRSS/{print $2}' "/proc/$pid/status" 2>/dev/null) || break
      echo "$(( $(date +%s) - t0 )),$(awk -v d=$((cur - prev)) -v hz="$hz" 'BEGIN{printf "%.1f", 100*d/hz/5}'),$(awk -v r="$rss" 'BEGIN{printf "%.1f", r/1024}')"
      prev=$cur
  done ) > "${log%.log}-stats.csv" &
sampler=$!
echo "Running (pid $pid). Stop: Ctrl+C here, or scripts/launch-test.sh --stop from another terminal."
wait "$app" || true
echo "Stopped. Log: $log"
