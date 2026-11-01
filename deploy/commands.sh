#!/usr/bin/env bash
# Turn Nexus Screen printer commands on or off (systemd drop-in).
#
#   sudo ~/nexus-screen/deploy/commands.sh enable              dry run
#   sudo ~/nexus-screen/deploy/commands.sh enable --confirm    install drop-in, restart, health check
#   sudo ~/nexus-screen/deploy/commands.sh disable --confirm   back to read-only
#
# Restarts only nexus-screen.service. Sends nothing to the printer.
# If the health check fails after enabling, read-only mode is restored automatically.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DIR=/etc/systemd/system/nexus-screen.service.d
DROPIN=$DIR/allow-commands.conf

if [ -n "${SUDO_USER:-}" ]; then
    OWNER="$SUDO_USER"
else
    OWNER="$(id -un)"
fi
HOME_DIR="$(eval echo "~$OWNER")"
PY="$HOME_DIR/nexus-screen-env/bin/python"
BACKUPS="$HOME_DIR/nexus-screen-backups"

action="${1:-}"; confirm=0; [ "${2:-}" = "--confirm" ] && confirm=1
case "$action" in enable|disable) ;; *) echo "usage: sudo $0 enable|disable [--confirm]" >&2; exit 2 ;; esac
[ "$confirm" = 0 ] || [ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

echo "Preflight"
[ "$(systemctl is-active nexus-screen)" = active ] \
    || { echo "nexus-screen.service is not running" >&2; exit 1; }
for s in klipper moonraker; do
    [ "$(systemctl is-active $s)" = active ] || { echo "$s not active" >&2; exit 1; }
done
state="$(curl -s -m 5 'http://localhost:7125/printer/objects/query?print_stats=state' \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["status"]["print_stats"]["state"])' \
    2>/dev/null || echo unknown)"
echo "  services active; printer state: $state; drop-in now: $([ -f $DROPIN ] && echo present || echo absent)"
[ -z "$(sudo -u "$OWNER" git -C "$REPO" status --porcelain 2>/dev/null)" ] \
    || { echo "uncommitted changes in $REPO" >&2; exit 1; }
echo "Plan: $action printer commands -> $([ "$action" = enable ] && echo "install $DROPIN" || echo "remove $DROPIN"), daemon-reload, restart nexus-screen, health check"
[ "$confirm" = 1 ] || { echo "Dry run only.  Add --confirm to apply."; exit 0; }

B="$BACKUPS/commands-$action-$(date +%Y%m%d-%H%M%S)"
install -d -o "$OWNER" -g "$OWNER" "$B"
systemctl cat nexus-screen > "$B/nexus-screen.before.systemctl-cat"
chown "$OWNER:$OWNER" "$B"/*

apply() {
    if [ "$1" = enable ]; then
        install -d "$DIR"
        printf '[Service]\nExecStart=\nExecStart=%s %s/main.py --hardware-display --live --allow-commands\n' \
            "$PY" "$REPO" > "$DROPIN"
        chmod 644 "$DROPIN"
    else
        rm -f "$DROPIN"; rmdir "$DIR" 2>/dev/null || true
    fi
    systemctl daemon-reload
    systemctl restart nexus-screen
}
check() {
    local flag=""; [ "$1" = enable ] && flag="--commands"
    sudo -u "$OWNER" "$PY" "$REPO/deploy/healthcheck.py" --wait 40 --max-restarts 5 $flag \
        --png "$B/after.png" > "$B/health.json"
}

apply "$action"
if check "$action"; then
    chown "$OWNER:$OWNER" "$B"/*
    echo "OK: printer commands $([ "$action" = enable ] && echo ENABLED || echo disabled).  Health: $B/health.json"
else
    cat "$B/health.json" >&2
    if [ "$action" = enable ]; then
        echo "Health check failed — restoring read-only mode" >&2
        apply disable; check disable || true
    fi
    chown "$OWNER:$OWNER" "$B"/* 2>/dev/null || true
    exit 1
fi
