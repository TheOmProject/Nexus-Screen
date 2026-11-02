#!/usr/bin/env bash
# Install Nexus Screen as the permanent touchscreen interface.
#
#   sudo ~/nexus-screen/deploy/install.sh            dry run: checks + plan, no changes
#   sudo ~/nexus-screen/deploy/install.sh --confirm  install, start, health-check (auto-rollback on failure)
#
# Never touches Klipper, Moonraker, printer configuration, or the KlipperScreen installation
# (KlipperScreen.service is only stopped and disabled; deploy/rollback.sh restores it).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
UNIT=nexus-screen.service
UNIT_DST=/etc/systemd/system/$UNIT
UNIT_TMPL="$REPO/deploy/nexus-screen.service.in"
OLD=KlipperScreen.service
confirm=0

for a in "$@"; do
    case "$a" in
        --confirm) confirm=1 ;;
        *) echo "unknown option: $a" >&2; echo "usage: sudo $0 [--confirm]" >&2; exit 2 ;;
    esac
done

[ "$confirm" = 0 ] || [ "$(id -u)" = 0 ] || \
    { echo "ABORT: --confirm must run as root:  sudo $0 --confirm" >&2; exit 1; }

# Detect the install user: the user who invoked sudo, or the current user
if [ -n "${SUDO_USER:-}" ]; then
    OWNER="$SUDO_USER"
else
    OWNER="$(id -un)"
fi
HOME_DIR="$(eval echo "~$OWNER")"
PY="$HOME_DIR/nexus-screen-env/bin/python"
BACKUPS="$HOME_DIR/nexus-screen-backups"

say()  { printf '  %-40s %s\n' "$1" "$2"; }
fail() { echo "ABORT: $*" >&2; exit 1; }
as_owner() { if [ "$(id -un)" = "$OWNER" ]; then "$@"; else sudo -u "$OWNER" "$@"; fi; }

echo "Preflight (installing for user: $OWNER)"

# Operating system: Debian 12 (Bookworm) or later required.
# Debian 11 (Bullseye) and older lack python3-pyqt6 in the apt repository. pip-based
# installation of PyQt6 on Bullseye is technically possible (PyQt6 6.7.1, manylinux_2_28)
# but the linuxfb hardware rendering path has not been validated on Bullseye hardware,
# and PyQt6 would be permanently pinned at 6.7.x with no upgrade path. Bullseye LTS also
# ended April 2024. Upgrade to Bookworm before installing Nexus Screen.
os_id="$(grep '^ID=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"')"
os_ver="$(grep '^VERSION_ID=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"')"
os_codename="$(grep '^VERSION_CODENAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"')"
if [ -z "$os_id" ] || [ -z "$os_ver" ]; then
    fail "Cannot determine OS version (/etc/os-release missing or malformed). Nexus Screen requires Debian 12 (Bookworm) or later."
fi
case "$os_id" in
    debian|raspbian)
        if [ "$os_ver" -lt 12 ] 2>/dev/null; then
            fail "Debian ${os_ver} (${os_codename}) is not supported. Nexus Screen requires Debian 12 (Bookworm) or later. See docs/INSTALLATION.md for details."
        fi
        ;;
    *)
        fail "Unsupported OS: ${os_id} ${os_ver}. Nexus Screen requires Debian 12 (Bookworm) or Raspberry Pi OS based on Bookworm."
        ;;
esac
say "operating system" "${os_id} ${os_ver} (${os_codename})"

# Python interpreter in the virtual environment: 3.11 or later required.
# Check $PY — the interpreter Nexus Screen actually runs — not the system python3.
# If the venv does not exist yet, skip this check; the PyQt6 import check below will
# catch the missing venv and print the correct "see docs/INSTALLATION.md" message.
if [ -x "$PY" ]; then
    py_ver="$(as_owner "$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo 0.0)"
    py_maj="$(echo "$py_ver" | cut -d. -f1)"
    py_min="$(echo "$py_ver" | cut -d. -f2)"
    if [ "$py_maj" -lt 3 ] 2>/dev/null || { [ "$py_maj" -eq 3 ] && [ "$py_min" -lt 11 ] 2>/dev/null; }; then
        fail "Python ${py_ver} in $PY is not supported. Nexus Screen requires Python 3.11 or later. Recreate the venv with a Python 3.11 interpreter: python3.11 -m venv ~/nexus-screen-env --system-site-packages"
    fi
    say "python (venv)" "$(as_owner "$PY" --version 2>&1)  ($PY)"
else
    say "python (venv)" "venv not found at $PY — will fail at PyQt6 check below"
fi

# Repo integrity: clean working tree, on main branch
[ -z "$(as_owner git -C "$REPO" status --porcelain)" ] || fail "uncommitted changes in $REPO"
branch="$(as_owner git -C "$REPO" rev-parse --abbrev-ref HEAD)"
head="$(as_owner git -C "$REPO" rev-parse --short HEAD)"
say "repository" "branch=$branch HEAD=$head"

# Klipper and Moonraker
for s in klipper moonraker; do
    [ "$(systemctl is-active $s)" = active ] && say "$s.service" "active" \
        || fail "$s.service is not active — Nexus Screen requires both to be running"
done

# Klipper ready via Moonraker
klippy="$(curl -s -m 5 http://localhost:7125/printer/info \
    | python3 -c 'import sys,json; print(json.load(sys.stdin)["result"]["state"])' 2>/dev/null || true)"
[ "$klippy" = ready ] && say "Klipper (via Moonraker)" "ready" \
    || fail "Klipper state is '$klippy', not ready"

# Python environment with PyQt6
as_owner "$PY" -c "import PyQt6.QtWidgets" 2>/dev/null \
    && say "Python environment" "$PY" \
    || fail "PyQt6 not importable with $PY — see docs/INSTALLATION.md for setup instructions"

# NumPy (required for the health check screen-luminance test)
if ! as_owner "$PY" -c "import numpy" 2>/dev/null; then
    say "numpy" "not found — installing"
    if [ "$(id -u)" = 0 ]; then
        apt-get install -y python3-numpy >/dev/null 2>&1 \
            || as_owner "$PY" -m pip install --quiet numpy \
            || fail "Failed to install numpy — run: sudo apt-get install python3-numpy"
    else
        fail "numpy not importable with $PY and not running as root to install it; run: sudo apt-get install python3-numpy"
    fi
    as_owner "$PY" -c "import numpy" 2>/dev/null \
        && say "numpy" "installed" \
        || fail "numpy still not importable after install attempt"
else
    say "numpy" "ok"
fi

# Framebuffer — presence, bit depth, format, and resolution
[ -c /dev/fb0 ] || fail "/dev/fb0 missing"
fb_bpp="$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null || echo unknown)"
case "$fb_bpp" in
    16)
        FB_FMT="RGB565"
        ;;
    32)
        FB_FMT="$(python3 - <<'PYEOF' 2>/dev/null
import struct, fcntl, sys
try:
    with open("/dev/fb0", "rb") as f:
        raw = fcntl.ioctl(f, 0x4600, bytes(160))
    fields = struct.unpack_from("20I", raw)
    ro, rl = fields[8],  fields[9]
    go, gl = fields[11], fields[12]
    bo, bl = fields[14], fields[15]
    if rl == gl == bl == 8 and ro + 8 <= 32 and go + 8 <= 32 and bo + 8 <= 32:
        used = 0
        ok = True
        for off in (ro, go, bo):
            mask = 0xFF << off
            if used & mask:
                ok = False
            used |= mask
        if ok:
            if ro == 16 and go == 8 and bo == 0:
                print("BGRA8888", end="")
            elif ro == 0 and go == 8 and bo == 16:
                print("RGBA8888", end="")
            else:
                print(f"32bpp-R8/{ro}-G8/{go}-B8/{bo}", end="")
        else:
            print(f"UNSUPPORTED:channels-overlap", end="")
    else:
        print(f"UNSUPPORTED:R{rl}/{ro}-G{gl}/{go}-B{bl}/{bo}", end="")
except Exception as e:
    print(f"UNKNOWN:{e}", end="")
PYEOF
        )"
        case "$FB_FMT" in
            UNSUPPORTED:*)
                fail "Unsupported 32-bit framebuffer (${FB_FMT#UNSUPPORTED:}). Nexus Screen requires 8-bit R, G, B channels." ;;
            UNKNOWN:*)
                fail "Cannot determine 32-bit framebuffer format: ${FB_FMT#UNKNOWN:}" ;;
        esac
        ;;
    *)
        fail "Unsupported framebuffer: ${fb_bpp} bits per pixel. Nexus Screen requires 16-bit RGB565 or a compatible 32-bit framebuffer."
        ;;
esac
fb_vsize="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo "")"
if [ -n "$fb_vsize" ]; then
    FB_W="${fb_vsize%%,*}"
    FB_H="${fb_vsize##*,}"
else
    FB_W=800; FB_H=480
fi
say "framebuffer" "/dev/fb0  ${FB_W}×${FB_H}  ${fb_bpp}-bpp  ${FB_FMT}"
[ "$FB_W" = 800 ] && [ "$FB_H" = 480 ] \
    || echo "  Notice: non-standard display (${FB_W}×${FB_H}) — adaptive scaling enabled"

# Service template exists
[ -f "$UNIT_TMPL" ] || fail "service template missing: $UNIT_TMPL"

# Unit not already installed
[ ! -e "$UNIT_DST" ] \
    || fail "$UNIT_DST already exists — to reinstall: sudo $REPO/deploy/rollback.sh --confirm --remove-unit, then re-run"

# KlipperScreen state (informational; absence is not an error)
old_enabled="$(systemctl is-enabled $OLD 2>/dev/null || echo not-installed)"
old_active="$(systemctl is-active $OLD 2>/dev/null || echo inactive)"
say "$OLD (current)" "enabled=$old_enabled active=$old_active"

# Manual test session
test_pid="$(cat "$REPO/run/test-app.pid" 2>/dev/null || true)"
[ -n "$test_pid" ] && kill -0 "$test_pid" 2>/dev/null \
    && say "manual test session" "pid $test_pid (will be stopped)" \
    || say "manual test session" "none"

echo
echo "Plan"
echo "  1. back up $OLD state and service files to $BACKUPS/deploy-<timestamp>/"
echo "  2. stop any manual test session; refuse if anything else holds /dev/fb0"
echo "  3. systemctl stop + disable $OLD  (installation left in place)"
echo "  4. generate $UNIT_DST from template, daemon-reload, enable --now $UNIT"
echo "     (live Moonraker data; printer commands disabled until deploy/commands.sh enable)"
echo "  5. health check up to 40 s — on failure: automatic rollback to the state above"

[ "$confirm" = 1 ] || { echo; echo "Dry run only.  To install:  sudo $0 --confirm"; exit 0; }

# ── 1. Backup ──────────────────────────────────────────────────────────────────
ts="$(date +%Y%m%d-%H%M%S)"
B="$BACKUPS/deploy-$ts"
install -d -o "$OWNER" -g "$OWNER" "$BACKUPS" "$B"
[ -f /etc/systemd/system/$OLD ] && cp -p /etc/systemd/system/$OLD "$B/" || true
systemctl cat $OLD > "$B/KlipperScreen.service.systemctl-cat" 2>&1 || true
cat > "$B/state.env" <<EOF
# service states before installing Nexus Screen ($ts)
KLIPPERSCREEN_ENABLED=$old_enabled
KLIPPERSCREEN_ACTIVE=$old_active
NEXUS_OWNER=$OWNER
NEXUS_REPO=$REPO
NEXUS_REPO_HEAD=$head
FB_W=$FB_W
FB_H=$FB_H
FB_FMT=$FB_FMT
EOF
ls -l /etc/systemd/system/multi-user.target.wants/ > "$B/multi-user.target.wants.txt"
cat > "$B/RESTORE.md" <<EOF
# Restore the previous interface (works over SSH even if the screen is black)

    sudo $REPO/deploy/rollback.sh --confirm
    sudo $REPO/deploy/rollback.sh --confirm --start-klipperscreen   # also start KlipperScreen

Without the script:

    sudo systemctl disable --now nexus-screen
    sudo chvt 1
    sudo systemctl enable --now KlipperScreen   # only if you want KlipperScreen back

Before this install: KlipperScreen enabled=$old_enabled active=$old_active (installed by $OWNER on $ts).
EOF
(cd "$B" && sha256sum * > SHA256SUMS)
chown -R "$OWNER:$OWNER" "$B"
echo "Backup: $B"

rollback() {
    echo "ROLLBACK: $*" >&2
    systemctl disable --now $UNIT 2>/dev/null || true
    rm -f "$UNIT_DST"; systemctl daemon-reload
    [ "$old_enabled" = enabled ] && systemctl enable $OLD 2>/dev/null || true
    [ "$old_active"  = active  ] && systemctl start  $OLD 2>/dev/null || true
    chvt 1 || true
    echo "Restored: $OLD enabled=$(systemctl is-enabled $OLD 2>/dev/null || true) active=$(systemctl is-active $OLD 2>/dev/null || true)" >&2
    journalctl -u $UNIT -n 25 --no-pager > "$B/failed-start.journal" 2>&1 || true
    chown "$OWNER:$OWNER" "$B/failed-start.journal" || true
    echo "Journal of the failed start: $B/failed-start.journal" >&2
    exit 1
}

# ── 2. Free the screen ─────────────────────────────────────────────────────────
if [ -n "$test_pid" ] && kill -0 "$test_pid" 2>/dev/null; then
    as_owner "$REPO/scripts/launch-test.sh" --stop 2>/dev/null || true
    sleep 2
fi
holders="$(fuser /dev/fb0 2>/dev/null | tr -s ' ' || true)"
[ -z "${holders// /}" ] \
    || fail "screen still in use by pid(s):$holders — nothing changed except the backup"

# ── 3. KlipperScreen off (not uninstalled) ─────────────────────────────────────
systemctl stop    $OLD 2>/dev/null || true
systemctl disable $OLD 2>/dev/null || true
systemctl reset-failed $OLD 2>/dev/null || true

# ── 4. Install service unit from template ──────────────────────────────────────
UNIT_GEN="$B/generated-$UNIT"
sed -e "s|@USER@|$OWNER|g" \
    -e "s|@HOME@|$HOME_DIR|g" \
    -e "s|@REPO@|$REPO|g" \
    "$UNIT_TMPL" > "$UNIT_GEN"
# Inject display dimensions for non-standard resolutions so the service
# starts with the correct scale factors on every future boot.
if [ "$FB_W" != 800 ] || [ "$FB_H" != 480 ]; then
    sed -i "s|^Environment=PYTHONUNBUFFERED=1|Environment=PYTHONUNBUFFERED=1\nEnvironment=NEXUS_SCREEN_W=${FB_W}\nEnvironment=NEXUS_SCREEN_H=${FB_H}|" "$UNIT_GEN"
fi
install -m 644 -o root -g root "$UNIT_GEN" "$UNIT_DST"
systemctl daemon-reload
systemctl enable --now $UNIT || rollback "systemctl enable --now failed"

# ── 5. Health check ────────────────────────────────────────────────────────────
if as_owner "$PY" "$REPO/deploy/healthcheck.py" --wait 40 --png "$B/first-start.png" \
        > "$B/first-start-health.json"; then
    chown "$OWNER:$OWNER" "$B"/first-start* || true
    echo "Nexus Screen is running."
    echo "Health report : $B/first-start-health.json"
    echo "Recovery      : sudo $REPO/deploy/rollback.sh --confirm   (see $B/RESTORE.md)"
else
    cat "$B/first-start-health.json" >&2
    rollback "health check failed"
fi
