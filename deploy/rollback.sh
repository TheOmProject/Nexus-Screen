#!/usr/bin/env bash
# Remove Nexus Screen as the permanent interface and restore the previous one.
# Works over SSH even when the screen is black.
#
#   sudo ~/nexus-screen/deploy/rollback.sh                        dry run: shows what would happen
#   sudo ~/nexus-screen/deploy/rollback.sh --confirm              stop + disable nexus-screen; restore
#                                                                 KlipperScreen to its pre-install state
#   sudo ~/nexus-screen/deploy/rollback.sh --confirm --start-klipperscreen
#                                                                 also enable + start KlipperScreen
#   add --remove-unit to delete /etc/systemd/system/nexus-screen.service
#
# Never touches Klipper, Moonraker, or printer configuration.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT=nexus-screen.service
UNIT_DST=/etc/systemd/system/$UNIT
OLD=KlipperScreen.service

# Detect install user from the most recent backup, then fall back to $SUDO_USER / current user
if [ -n "${SUDO_USER:-}" ]; then
    OWNER="$SUDO_USER"
else
    OWNER="$(id -un)"
fi
HOME_DIR="$(eval echo "~$OWNER")"
BACKUPS="$HOME_DIR/nexus-screen-backups"

confirm=0 start_old=0 remove=0
for a in "$@"; do
    case "$a" in
        --confirm) confirm=1 ;;
        --start-klipperscreen) start_old=1 ;;
        --remove-unit) remove=1 ;;
        *) echo "unknown option: $a" >&2; exit 2 ;;
    esac
done
[ "$confirm" = 0 ] || [ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }

# Load saved state from the most recent deploy backup
B="$(ls -d "$BACKUPS"/deploy-* 2>/dev/null | sort | tail -1 || true)"
KLIPPERSCREEN_ENABLED=disabled KLIPPERSCREEN_ACTIVE=inactive
[ -n "$B" ] && [ -f "$B/state.env" ] && . "$B/state.env"
echo "Backup used: ${B:-none (defaults: KlipperScreen disabled)}"
echo "Now:    $UNIT  enabled=$(systemctl is-enabled $UNIT 2>/dev/null || echo none)  active=$(systemctl is-active $UNIT 2>/dev/null || true)"
echo "        $OLD  enabled=$(systemctl is-enabled $OLD 2>/dev/null || true)  active=$(systemctl is-active $OLD 2>/dev/null || true)"
if [ "$start_old" = 1 ]; then
    target="enabled + started"
else
    target="enabled=$KLIPPERSCREEN_ENABLED active=$KLIPPERSCREEN_ACTIVE (as before install)"
fi
echo "Plan:   stop + disable $UNIT$([ "$remove" = 1 ] && echo ", delete $UNIT_DST" || true); $OLD -> $target; restore text console (chvt 1)"
[ "$confirm" = 1 ] || { echo "Dry run only.  Add --confirm to apply."; exit 0; }

systemctl disable --now $UNIT 2>/dev/null || true
[ "$remove" = 1 ] && rm -f "$UNIT_DST" || true
systemctl daemon-reload
chvt 1 || true
if [ "$start_old" = 1 ] || [ "$KLIPPERSCREEN_ENABLED" = enabled ]; then
    systemctl enable $OLD 2>/dev/null || true
fi
if [ "$start_old" = 1 ] || [ "$KLIPPERSCREEN_ACTIVE" = active ]; then
    systemctl start $OLD 2>/dev/null || true
fi
echo "Done:   $UNIT  enabled=$(systemctl is-enabled $UNIT 2>/dev/null || echo removed)  active=$(systemctl is-active $UNIT 2>/dev/null || true)"
echo "        $OLD  enabled=$(systemctl is-enabled $OLD 2>/dev/null || true)  active=$(systemctl is-active $OLD 2>/dev/null || true)"
echo "        klipper=$(systemctl is-active klipper)  moonraker=$(systemctl is-active moonraker)"
