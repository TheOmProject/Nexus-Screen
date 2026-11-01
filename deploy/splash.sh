#!/usr/bin/env bash
# Boot splash control. Every action is a dry run unless --confirm is given.
#
#   sudo ~/nexus-screen/deploy/splash.sh install --confirm   install the unit (not yet enabled)
#   sudo ~/nexus-screen/deploy/splash.sh test --confirm      test the full splash sequence now
#                                                            (printer must be idle; no reboot needed)
#   sudo ~/nexus-screen/deploy/splash.sh enable --confirm    play the splash at every boot
#   sudo ~/nexus-screen/deploy/splash.sh disable --confirm   stop, disable and remove the unit
#        ~/nexus-screen/deploy/splash.sh status              read-only status
#
# Kill switch (no root needed): touch ~/nexus-splash/DISABLED  — the unit then will not start.
# Never touches Klipper, Moonraker, printer commands, cmdline.txt or config.txt.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_DST=/etc/systemd/system/nexus-splash.service
UNIT_TMPL="$REPO/deploy/nexus-splash.service.in"

if [ -n "${SUDO_USER:-}" ]; then
    OWNER="$SUDO_USER"
else
    OWNER="$(id -un)"
fi
HOME_DIR="$(eval echo "~$OWNER")"
PY="$HOME_DIR/nexus-screen-env/bin/python"
NEXUS_SPLASH_DIR="$HOME_DIR/nexus-splash"
MEDIA="$NEXUS_SPLASH_DIR/build"
BACKUPS="$HOME_DIR/nexus-screen-backups"

action="${1:-}"; confirm=0; [ "${2:-}" = "--confirm" ] && confirm=1
case "$action" in install|test|enable|disable|status) ;; \
    *) echo "usage: $0 install|test|enable|disable|status [--confirm]" >&2; exit 2 ;; esac

status() {
    echo "unit installed : $([ -f $UNIT_DST ] && echo yes || echo no)"
    echo "enabled at boot: $(systemctl is-enabled nexus-splash 2>/dev/null || echo no)"
    echo "running        : $(systemctl is-active nexus-splash 2>/dev/null || true)"
    echo "kill switch    : $([ -e "$NEXUS_SPLASH_DIR/DISABLED" ] && echo ON || echo off)"
}
if [ "$action" = status ]; then status; journalctl -u nexus-splash -b --no-pager -n 15 2>/dev/null || true; exit 0; fi
[ "$confirm" = 0 ] || [ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

printer_idle() {
    curl -s -m 5 'http://localhost:7125/printer/objects/query?print_stats=state&idle_timeout=state' | python3 -c '
import sys, json
s = json.load(sys.stdin)["result"]["status"]
ok = s["print_stats"]["state"] not in ("printing", "paused") and s["idle_timeout"]["state"] != "Printing"
print(s["print_stats"]["state"], s["idle_timeout"]["state"]); sys.exit(0 if ok else 1)'
}

echo "Preflight"
grep -q "splash/player.py" "$REPO/deploy/precheck.sh" \
    && [ -f "$REPO/nexus/splash.py" ] && [ -f "$REPO/splash/player.py" ] \
    || { echo "splash support not found in $REPO — ensure Nexus Screen is installed" >&2; exit 1; }
[ -z "$(sudo -u "$OWNER" git -C "$REPO" status --porcelain 2>/dev/null)" ] \
    || { echo "uncommitted changes in $REPO" >&2; exit 1; }
[ -d "$MEDIA" ] && (cd "$MEDIA" && sha256sum -c --quiet SHA256SUMS) \
    || { echo "splash media missing or changed: run splash/build_media.sh first" >&2; exit 1; }
echo "  splash media verified"
status

case "$action" in
install)
    echo "Plan: generate $UNIT_DST from template, daemon-reload. Not enabled, not started."
    [ "$confirm" = 1 ] || { echo "Dry run only.  Add --confirm to apply."; exit 0; }
    sed -e "s|@USER@|$OWNER|g" \
        -e "s|@HOME@|$HOME_DIR|g" \
        -e "s|@REPO@|$REPO|g" \
        "$UNIT_TMPL" > "$UNIT_DST"
    chmod 644 "$UNIT_DST"
    systemctl daemon-reload
    systemd-analyze verify "$UNIT_DST" && echo "installed (not enabled)" ;;
test)
    [ -f "$UNIT_DST" ] || { echo "unit not installed: run '$0 install --confirm' first" >&2; exit 1; }
    st="$(printer_idle)" || { echo "printer not idle ($st) — not stopping Nexus Screen" >&2; exit 1; }
    echo "  printer idle: $st"
    echo "Plan: stop nexus-screen, start the splash, start nexus-screen once the intro finishes,"
    echo "      health check, verify splash log; on any failure Nexus Screen is restored."
    [ "$confirm" = 1 ] || { echo "Dry run only.  Add --confirm to apply."; exit 0; }
    B="$BACKUPS/splash-test-$(date +%Y%m%d-%H%M%S)"
    install -d -o "$OWNER" -g "$OWNER" "$B"
    since="$(date '+%Y-%m-%d %H:%M:%S')"
    snap() { sudo -u "$OWNER" "$PY" -c \
        "import sys; sys.path.insert(0, '$REPO/deploy'); import healthcheck as h; h.screen('$B/$1.png')" || true; }
    restore() {
        trap - EXIT INT TERM
        echo "FAIL — restoring: stop splash, start nexus-screen ($B)" >&2
        systemctl stop nexus-splash 2>/dev/null || true
        systemctl is-enabled -q nexus-splash 2>/dev/null && systemctl disable nexus-splash || true
        systemctl -q is-active nexus-screen || systemctl start nexus-screen
        journalctl -u nexus-splash -u nexus-screen --since "$since" --no-pager \
            -o short-precise > "$B/journal.txt" || true
        chown -R "$OWNER:$OWNER" "$B"; exit 1
    }
    trap restore EXIT INT TERM
    systemctl stop nexus-screen
    systemctl start nexus-splash
    sleep 5; snap during-intro
    pp="$(systemctl show -p MainPID --value nexus-splash)"
    for q in "$pp" $(cat /proc/"$pp"/task/"$pp"/children 2>/dev/null); do
        echo "$(tr '\0' ' ' < /proc/$q/cmdline | cut -c1-60): \
$(grep -E '^Cap(Eff|Amb|Bnd)' /proc/$q/status | tr '\n\t' '  ')"
    done > "$B/capabilities.txt" 2>/dev/null || true
    for _ in $(seq 20); do
        journalctl -u nexus-splash --since "$since" --no-pager | grep -q "intro.mp4:" && break; sleep 1; done
    sleep 3; snap during-loop
    systemctl start nexus-screen
    for _ in $(seq 60); do systemctl -q is-active nexus-splash || break; sleep 1; done
    sleep 2
    flag=""; grep -q -- "--allow-commands" <(systemctl cat nexus-screen) && flag="--commands" || true
    healthy=1
    sudo -u "$OWNER" "$PY" "$REPO/deploy/healthcheck.py" --wait 30 --max-restarts 99 $flag \
        --png "$B/after.png" > "$B/health.json" || healthy=0
    journalctl -u nexus-splash -u nexus-screen --since "$since" --no-pager \
        -o short-precise > "$B/journal.txt" || true
    chown -R "$OWNER:$OWNER" "$B"
    grep "nexus-splash:" "$B/journal.txt" | sed 's/^/  /' || true
    fail=""
    [ "$healthy" = 1 ]                                    || fail="$fail health-check"
    grep -q "intro.mp4: 240 frames" "$B/journal.txt"      || fail="$fail intro-incomplete"
    grep -Eq "loop.mp4: [1-9][0-9]* frames" "$B/journal.txt" || fail="$fail no-loop"
    grep -q "stopped: Nexus Screen ready" "$B/journal.txt" || fail="$fail no-handover"
    grep -q "console graphics mode not set" "$B/journal.txt" && fail="$fail console-mode-refused" || true
    systemctl -q is-active nexus-splash                   && fail="$fail splash-still-running" || true
    systemctl is-enabled -q nexus-splash 2>/dev/null      && fail="$fail splash-enabled" || true
    [ -z "$fail" ] || { echo "checks failed:$fail" >&2; restore; }
    trap - EXIT INT TERM
    echo "PASS — full intro, wait loop, handover; Nexus Screen healthy; splash not enabled at boot ($B)" ;;
enable)
    [ -f "$UNIT_DST" ] || { echo "unit not installed: run '$0 install --confirm' first" >&2; exit 1; }
    [ ! -e "$NEXUS_SPLASH_DIR/DISABLED" ] \
        || { echo "kill switch $NEXUS_SPLASH_DIR/DISABLED is set: remove it first" >&2; exit 1; }
    echo "Plan: systemctl enable nexus-splash (plays from the next boot). Nothing restarts now."
    [ "$confirm" = 1 ] || { echo "Dry run only.  Add --confirm to apply."; exit 0; }
    systemctl enable nexus-splash; status ;;
disable)
    echo "Plan: stop + disable nexus-splash, remove $UNIT_DST, daemon-reload. Nexus Screen keeps running."
    [ "$confirm" = 1 ] || { echo "Dry run only.  Add --confirm to apply."; exit 0; }
    systemctl disable --now nexus-splash 2>/dev/null || true
    rm -f "$UNIT_DST"; systemctl daemon-reload; status ;;
esac
