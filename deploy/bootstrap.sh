#!/usr/bin/env bash
# Nexus Screen + Nexus Video unified bootstrap installer.
#
# One-command installation:
#   curl -fsSL https://raw.githubusercontent.com/omarmunoz5371/Nexus-Screen/main/deploy/bootstrap.sh | bash
#
# Or with explicit options:
#   bash bootstrap.sh [--yes] [--with-video] [--without-video] [--dry-run]
#
# Flags:
#   --yes             Non-interactive: use defaults (Nexus Video: No)
#   --with-video      Non-interactive: install Nexus Video addon
#   --without-video   Non-interactive: skip Nexus Video addon
#   --dry-run         Run all checks and show plan; make no changes
#   --repair          Reinstall over an existing installation
#   --uninstall       Remove Nexus Screen (and Nexus Video if present)
#
# This script:
#   1. Runs hardware preflight checks (blocks on failure — no changes made)
#   2. Displays an interactive wizard asking about optional addons
#   3. Installs Nexus Screen (required)
#   4. Installs Nexus Video (optional, if selected)
#   5. Registers Moonraker Update Manager entries
#   6. Verifies installed services
#
# Safety:
#   - Never modifies Klipper, Moonraker, or printer.cfg
#   - Creates backups before changing any service configuration
#   - Automatically rolls back Nexus Screen on health-check failure
#   - An addon (Nexus Video) failure leaves Nexus Screen working
#   - Does nothing when preflight fails

set -euo pipefail

# ── constants ─────────────────────────────────────────────────────────────────
NS_REPO="https://github.com/omarmunoz5371/Nexus-Screen.git"
NV_REPO="https://github.com/omarmunoz5371/Nexus-Video.git"
NS_DIR_NAME="nexus-screen"
NV_DIR_NAME="nexus-video"
NS_BRANCH="main"
NV_BRANCH="main"
MIN_W=480
MIN_H=320

# ── argument parsing ──────────────────────────────────────────────────────────
OPT_YES=false
OPT_WITH_VIDEO=""        # "yes", "no", or "" (ask interactively)
OPT_DRY_RUN=false
OPT_REPAIR=false
OPT_UNINSTALL=false

for arg in "$@"; do
  case "$arg" in
    --yes)            OPT_YES=true ;;
    --with-video)     OPT_WITH_VIDEO="yes" ;;
    --without-video)  OPT_WITH_VIDEO="no" ;;
    --dry-run)        OPT_DRY_RUN=true ;;
    --repair)         OPT_REPAIR=true ;;
    --uninstall)      OPT_UNINSTALL=true ;;
    --help|-h)
      echo "Usage: $0 [--yes] [--with-video|--without-video] [--dry-run] [--repair] [--uninstall]"
      exit 0 ;;
    *)
      echo "Unknown option: $arg  (run $0 --help for usage)" >&2
      exit 1 ;;
  esac
done

# ── identity ──────────────────────────────────────────────────────────────────
# Detect the actual user even when piped through sudo
if [ -n "${SUDO_USER:-}" ]; then
  TARGET_USER="$SUDO_USER"
elif [ "$(id -u)" = "0" ]; then
  echo "ERROR: Do not run this script directly as root." >&2
  echo "       Run as your normal user: bash bootstrap.sh" >&2
  exit 1
else
  TARGET_USER="$(id -un)"
fi
HOME_DIR="$(eval echo "~${TARGET_USER}")"
NS_DIR="${HOME_DIR}/${NS_DIR_NAME}"
NV_DIR="${HOME_DIR}/${NV_DIR_NAME}"
NS_INSTALL="${NS_DIR}/deploy/install.sh"
NV_PREFLIGHT="${NV_DIR}/deploy/preflight.sh"
NV_INSTALL="${NV_DIR}/deploy/install.sh"

# ── output helpers ────────────────────────────────────────────────────────────
_bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
_green() { printf '\033[32m%s\033[0m\n' "$*"; }
_red()   { printf '\033[31m%s\033[0m\n' "$*"; }
_warn()  { printf '\033[33m  ! %s\033[0m\n' "$*"; }
_info()  { printf '  · %s\n' "$*"; }
_step()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
_prefix() { local pfx="$1"; while IFS= read -r line; do printf '%s%s\n' "$pfx" "$line"; done; }

# ── preflight ─────────────────────────────────────────────────────────────────

_step "Nexus Screen — System Preflight Check"

FAIL=0

_check() {
  local name="$1" ok="$2" msg="$3"
  if [ "$ok" = "0" ]; then
    printf '  \033[32m✓\033[0m  %-28s %s\n' "$name" "$msg"
  else
    printf '  \033[31m✗\033[0m  %-28s %s\n' "$name" "$msg"
    FAIL=$((FAIL + 1))
  fi
}

_warn_check() {
  local name="$1" msg="$2"
  printf '  \033[33m!\033[0m  %-28s %s\n' "$name" "$msg"
}

# OS
OS_ID="$(. /etc/os-release 2>/dev/null && echo "${ID:-unknown}" || echo unknown)"
OS_VER="$(. /etc/os-release 2>/dev/null && echo "${VERSION_ID:-0}" || echo 0)"
OS_PRETTY="$(. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-unknown}" || echo unknown)"
case "$OS_ID" in
  debian|raspbian)
    if [ "${OS_VER}" -ge 12 ] 2>/dev/null; then
      _check "OS" 0 "${OS_PRETTY}"
    else
      _check "OS" 1 "${OS_PRETTY} — Debian 12 (Bookworm) required"
    fi ;;
  ubuntu)
    _warn_check "OS" "Ubuntu (${OS_PRETTY}) — not a primary target; may work" ;;
  *)
    _check "OS" 1 "${OS_PRETTY} — Debian Bookworm required" ;;
esac

# Architecture
ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64) _check "Architecture" 0 "${ARCH} (Raspberry Pi / CB1)" ;;
  armv7l|armv6l) _check "Architecture" 1 "${ARCH} — 64-bit OS required" ;;
  x86_64)        _warn_check "Architecture" "x86_64 — framebuffer splash won't function (dev only)" ;;
  *)             _warn_check "Architecture" "${ARCH} — untested" ;;
esac

# RAM (minimum 1 GB)
MEM_MB=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0) / 1024 ))
[ "$MEM_MB" -ge 900 ] && \
  _check "RAM" 0 "${MEM_MB} MB" || \
  _check "RAM" 1 "${MEM_MB} MB available — 1 GB required"

# Disk (minimum 500 MB free in home)
FREE_MB=$(( $(df --output=avail "${HOME_DIR}" 2>/dev/null | tail -1 | tr -d ' ') / 1024 ))
[ "$FREE_MB" -ge 400 ] && \
  _check "Disk" 0 "${FREE_MB} MB free in ${HOME_DIR}" || \
  _check "Disk" 1 "${FREE_MB} MB free — 500 MB required"

# Framebuffer
if [ -e /dev/fb0 ]; then
  FB_SIZE="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo '?,?')"
  FB_BPP="$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null || echo '?')"
  _check "Framebuffer" 0 "/dev/fb0 — ${FB_SIZE} at ${FB_BPP}bpp"
  # Resolution
  FB_W="$(cut -d, -f1 /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo 0)"
  FB_H="$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo 0)"
  if [ "${FB_W}" -ge ${MIN_W} ] && [ "${FB_H}" -ge ${MIN_H} ] 2>/dev/null; then
    _check "Display resolution" 0 "${FB_W}×${FB_H} — meets ${MIN_W}×${MIN_H} minimum"
  else
    _check "Display resolution" 1 "${FB_W}×${FB_H} — minimum ${MIN_W}×${MIN_H} required"
  fi
else
  _warn_check "Framebuffer" "/dev/fb0 not found — required for splash (minimum ${MIN_W}×${MIN_H})"
fi

# Python
PY_VER="$(python3 --version 2>&1 | awk '{print $2}')"
PY_MIN=$(($(echo "${PY_VER}" | cut -d. -f1) * 100 + $(echo "${PY_VER}" | cut -d. -f2)))
[ "$PY_MIN" -ge 309 ] && \
  _check "Python" 0 "python3 ${PY_VER}" || \
  _check "Python" 1 "python3 ${PY_VER} — 3.9+ required"

# PyQt6
python3 -c "import PyQt6" 2>/dev/null && \
  _check "PyQt6" 0 "installed" || \
  _check "PyQt6" 1 "not found — install: sudo apt install python3-pyqt6"

# git
command -v git &>/dev/null && \
  _check "git" 0 "$(git --version)" || \
  _check "git" 1 "not found — install: sudo apt install git"

# Klipper (optional for Nexus Screen)
if systemctl is-active --quiet klipper 2>/dev/null; then
  _check "Klipper" 0 "active"
else
  _warn_check "Klipper" "not active — required for printer control"
fi

# Moonraker (optional for Nexus Screen)
if systemctl is-active --quiet moonraker 2>/dev/null; then
  _check "Moonraker" 0 "active"
else
  _warn_check "Moonraker" "not active — required for printer data"
fi

echo ""
if [ "$FAIL" -gt 0 ]; then
  _red "INSTALLATION BLOCKED — Minimum system requirements not met."
  echo "  Resolve all ✗ failures listed above before retrying."
  exit 1
fi
_green "System meets all requirements."

# ── detect existing installation ──────────────────────────────────────────────

NS_EXISTS=false
NV_EXISTS=false
[ -d "${NS_DIR}" ] && NS_EXISTS=true
[ -d "${NV_DIR}" ] && NV_EXISTS=true

INSTALL_MODE="fresh"
if $NS_EXISTS && $OPT_REPAIR; then
  INSTALL_MODE="repair"
elif $NS_EXISTS; then
  INSTALL_MODE="update"
fi

# ── uninstall path ────────────────────────────────────────────────────────────

if $OPT_UNINSTALL; then
  _step "Uninstall"
  if $NS_EXISTS; then
    _info "Running Nexus Screen uninstall..."
    if [ -x "${NS_DIR}/deploy/rollback.sh" ]; then
      sudo bash "${NS_DIR}/deploy/rollback.sh" --confirm
    fi
  fi
  if $NV_EXISTS; then
    _info "Running Nexus Video uninstall..."
    if [ -x "${NV_DIR}/deploy/uninstall.sh" ]; then
      bash "${NV_DIR}/deploy/uninstall.sh"
    fi
  fi
  _green "Uninstall complete."
  exit 0
fi

# ── interactive wizard ────────────────────────────────────────────────────────

_step "NEXUS SCREEN INSTALLER"

echo ""
case "$INSTALL_MODE" in
  fresh)  _bold "  Installing Nexus Screen for the first time." ;;
  update) _bold "  Nexus Screen is already installed at ${NS_DIR}." ;;
  repair) _bold "  Repairing Nexus Screen installation at ${NS_DIR}." ;;
esac
echo ""

# Determine if we should ask about Nexus Video
INSTALL_NV=false
if [ -n "$OPT_WITH_VIDEO" ]; then
  [ "$OPT_WITH_VIDEO" = "yes" ] && INSTALL_NV=true
elif $OPT_YES; then
  INSTALL_NV=false   # default: No
else
  # Interactive
  _bold "  Install Nexus Screen? YES — required."
  echo ""
  _bold "  Install optional addons?"
  echo ""
  echo "  ┌─────────────────────────────────────────────────────┐"
  echo "  │  Nexus Video — Startup Animations                  │"
  echo "  │                                                     │"
  echo "  │    Animated boot splash with video packs.          │"
  echo "  │    Requires a supported framebuffer display.       │"
  echo "  │    Adds ~20 MB (3 built-in packs).                 │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo ""
  if [ -t 0 ]; then
    printf "  Install Nexus Video? [y/N] "
    read -r _nv_answer
    case "${_nv_answer}" in
      y|Y|yes|Yes|YES) INSTALL_NV=true ;;
      *) INSTALL_NV=false ;;
    esac
  else
    _info "Non-interactive mode: Nexus Video will not be installed (pass --with-video to change)."
    INSTALL_NV=false
  fi
  echo ""
  _bold "  Nexus Sounds — Audio Notifications"
  echo "  Coming Soon — Not Available in this release."
  echo ""
fi

# ── summary ───────────────────────────────────────────────────────────────────

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Installation Summary                              │"
echo "  │                                                     │"
printf "  │  %-51s│\n" "Mode:              ${INSTALL_MODE}"
printf "  │  %-51s│\n" "Nexus Screen:      ${NS_DIR}"
if $INSTALL_NV; then
printf "  │  %-51s│\n" "Nexus Video:       ${NV_DIR} [will install]"
else
printf "  │  %-51s│\n" "Nexus Video:       skip"
fi
if $OPT_DRY_RUN; then
printf "  │  %-51s│\n" "Mode:              DRY RUN — no changes will be made"
fi
echo "  └─────────────────────────────────────────────────────┘"
echo ""

if ! $OPT_YES && [ -t 0 ] && ! $OPT_DRY_RUN; then
  printf "  Proceed? [Y/n] "
  read -r _proceed
  case "${_proceed}" in
    n|N|no|No|NO)
      echo "  Installation cancelled."
      exit 0 ;;
  esac
fi

$OPT_DRY_RUN && { _info "Dry run complete. No changes made."; exit 0; }

# ── clone / update Nexus Screen ───────────────────────────────────────────────

_step "Nexus Screen"

if $NS_EXISTS && [ "$INSTALL_MODE" = "update" ]; then
  _info "Pulling latest Nexus Screen..."
  sudo -u "${TARGET_USER}" git -C "${NS_DIR}" pull --ff-only 2>&1 | _prefix "  git: "
else
  if $NS_EXISTS; then
    _info "Removing existing Nexus Screen directory for repair..."
    rm -rf "${NS_DIR}"
  fi
  _info "Cloning Nexus Screen from GitHub..."
  sudo -u "${TARGET_USER}" git clone --depth 1 --branch "${NS_BRANCH}" \
    "${NS_REPO}" "${NS_DIR}" 2>&1 | _prefix "  git: "
fi

# ── install Nexus Screen ──────────────────────────────────────────────────────

_info "Running Nexus Screen installer..."
sudo bash "${NS_INSTALL}" --confirm
_green "Nexus Screen installed."

# ── optional: Nexus Video ─────────────────────────────────────────────────────

if $INSTALL_NV; then
  _step "Nexus Video (optional addon)"

  if $NV_EXISTS && [ -d "${NV_DIR}/.git" ]; then
    _info "Pulling latest Nexus Video..."
    sudo -u "${TARGET_USER}" git -C "${NV_DIR}" pull --ff-only 2>&1 | _prefix "  git: "
  else
    _info "Cloning Nexus Video from GitHub..."
    sudo -u "${TARGET_USER}" git clone --depth 1 --branch "${NV_BRANCH}" \
      "${NV_REPO}" "${NV_DIR}" 2>&1 | _prefix "  git: "
  fi

  # Run Nexus Video preflight (independent check for addon requirements)
  _info "Running Nexus Video preflight..."
  if sudo -u "${TARGET_USER}" bash "${NV_PREFLIGHT}"; then
    _info "Running Nexus Video installer..."
    if sudo -u "${TARGET_USER}" bash "${NV_INSTALL}"; then
      _green "Nexus Video installed."
    else
      _warn "Nexus Video installation failed — Nexus Screen is still working."
      _warn "Run  bash ${NV_INSTALL}  to retry."
    fi
  else
    _warn "Nexus Video preflight failed — addon not installed."
    _warn "Nexus Screen is fully operational without it."
    _warn "Run  bash ${NV_PREFLIGHT}  to see the failed requirements."
  fi
fi

# ── Moonraker Update Manager ──────────────────────────────────────────────────

_step "Moonraker Update Manager"

MOONRAKER_CONF="${HOME_DIR}/printer_data/config/moonraker.conf"
if [ ! -f "${MOONRAKER_CONF}" ]; then
  MOONRAKER_CONF="${HOME_DIR}/klipper_config/moonraker.conf"
fi

if [ -f "${MOONRAKER_CONF}" ]; then
  NS_UM_BLOCK="[update_manager nexus-screen]"
  if ! grep -q "${NS_UM_BLOCK}" "${MOONRAKER_CONF}"; then
    _info "Adding Nexus Screen to Moonraker Update Manager..."
    cat >> "${MOONRAKER_CONF}" << UMEOF

# Nexus Screen — added by bootstrap.sh
[update_manager nexus-screen]
type: git_repo
path: ${NS_DIR}
origin: ${NS_REPO}
primary_branch: main
is_system_service: False
UMEOF
    _green "Nexus Screen added to Moonraker Update Manager."
  else
    _info "Nexus Screen already in Moonraker Update Manager."
  fi

  if $INSTALL_NV && [ -d "${NV_DIR}" ]; then
    NV_UM_BLOCK="[update_manager nexus-video]"
    if ! grep -q "${NV_UM_BLOCK}" "${MOONRAKER_CONF}"; then
      _info "Adding Nexus Video to Moonraker Update Manager..."
      cat >> "${MOONRAKER_CONF}" << UMEOF

# Nexus Video — added by bootstrap.sh
[update_manager nexus-video]
type: git_repo
path: ${NV_DIR}
origin: ${NV_REPO}
primary_branch: main
is_system_service: False
managed_services: nexus-video
UMEOF
      _green "Nexus Video added to Moonraker Update Manager."
    else
      _info "Nexus Video already in Moonraker Update Manager."
    fi
  fi
else
  _warn "moonraker.conf not found — skipping Moonraker Update Manager registration."
  _warn "Add the update_manager blocks manually from:"
  if $INSTALL_NV; then
    _warn "  ${NV_DIR}/deploy/moonraker-update-manager.conf"
  fi
  _warn "  ${NS_DIR}/docs/moonraker-update-manager.md"
fi

# ── verification ──────────────────────────────────────────────────────────────

_step "Verification"

NS_STATE="$(systemctl is-active nexus-screen 2>/dev/null || echo inactive)"
printf '  %-36s %s\n' "nexus-screen.service" "${NS_STATE}"

if $INSTALL_NV && [ -d "${NV_DIR}" ]; then
  NV_STATE="$(systemctl is-active nexus-video 2>/dev/null || echo inactive)"
  printf '  %-36s %s\n' "nexus-video.service" "${NV_STATE}"
fi

echo ""
_bold "Installation complete."
echo ""
_info "Nexus Screen starts automatically on next reboot."
_info "To start now:  sudo systemctl start nexus-screen"
if $INSTALL_NV && [ -d "${NV_DIR}" ]; then
  _info "Nexus Video:   sudo systemctl start nexus-video"
fi
echo ""

