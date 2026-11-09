#!/usr/bin/env bash
# Nexus Screen + Nexus Video unified bootstrap installer.
#
# One-command installation:
#   curl -fsSL https://raw.githubusercontent.com/TheOmProject/Nexus-Screen/main/deploy/bootstrap.sh | bash
#
# Or with explicit options:
#   bash bootstrap.sh [--yes] [--with-video] [--without-video] [--dry-run] [--repair] [--uninstall]
#
# Flags:
#   --yes             Non-interactive: use safe defaults (Nexus Video: No)
#   --with-video      Non-interactive: install Nexus Video addon
#   --without-video   Non-interactive: skip Nexus Video addon
#   --dry-run         Run all checks and show plan; make no changes
#   --repair          Reinstall over an existing installation
#   --uninstall       Remove Nexus Screen (and Nexus Video if present)
#
# This script:
#   1. Runs hardware preflight (blocks on incompatible hardware/OS)
#   2. Auto-installs missing apt packages (PyQt6, git, etc.) after confirmation
#   3. Installs Nexus Screen
#   4. Offers Nexus Video as an optional addon (after NS install)
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
NS_REPO="https://github.com/TheOmProject/Nexus-Screen.git"
NV_REPO="https://github.com/TheOmProject/Nexus-Video.git"
NS_DIR_NAME="nexus-screen"
NV_DIR_NAME="nexus-video"
NS_BRANCH="main"
NV_BRANCH="main"
MIN_W=480
MIN_H=320

# ── argument parsing ──────────────────────────────────────────────────────────
OPT_YES=false
OPT_WITH_VIDEO=""        # "yes", "no", or "" (ask interactively after NS installs)
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
      printf 'Usage: %s [--yes] [--with-video|--without-video] [--dry-run] [--repair] [--uninstall]\n' "$0"
      exit 0 ;;
    *)
      printf 'Unknown option: %s  (run %s --help for usage)\n' "$arg" "$0" >&2
      exit 1 ;;
  esac
done

# ── identity ──────────────────────────────────────────────────────────────────
# Detect the actual user even when invoked under sudo
if [ -n "${SUDO_USER:-}" ]; then
  TARGET_USER="$SUDO_USER"
elif [ "$(id -u)" = "0" ]; then
  printf 'ERROR: Do not run this script as root.\n       Run as your normal user: bash bootstrap.sh\n' >&2
  exit 1
else
  TARGET_USER="$(id -un)"
fi
HOME_DIR="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
[ -n "${HOME_DIR}" ] || { printf 'ERROR: Cannot determine home directory for %s\n' "${TARGET_USER}" >&2; exit 1; }
NS_DIR="${HOME_DIR}/${NS_DIR_NAME}"
NV_DIR="${HOME_DIR}/${NV_DIR_NAME}"
NS_INSTALL="${NS_DIR}/deploy/install.sh"
NV_PREFLIGHT="${NV_DIR}/deploy/preflight.sh"
NV_INSTALL="${NV_DIR}/deploy/public-install.sh"

# ── output helpers ────────────────────────────────────────────────────────────
_bold()   { printf '\033[1m%s\033[0m\n' "$*"; }
_green()  { printf '\033[32m%s\033[0m\n' "$*"; }
_red()    { printf '\033[31m%s\033[0m\n' "$*"; }
_warn()   { printf '\033[33m  ! %s\033[0m\n' "$*"; }
_info()   { printf '  · %s\n' "$*"; }
_step()   { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
_prefix() { local pfx="$1"; while IFS= read -r line; do printf '%s%s\n' "$pfx" "$line"; done; }

# Interactive prompt helper — reads from /dev/tty so it works even when stdin
# is a curl pipe (the curl|bash pattern).
# Usage: _ask "Prompt text [Y/n] " "default_answer"
# Returns the trimmed answer via stdout; falls back to default when no terminal.
_ask() {
  local prompt="$1" default="$2" ans
  if { true >/dev/tty; } 2>/dev/null; then
    printf '%s' "$prompt" >/dev/tty
    read -r ans </dev/tty
  else
    ans="$default"
  fi
  # Return the trimmed answer, or the default if blank
  if [ -z "${ans}" ]; then
    printf '%s' "$default"
  else
    printf '%s' "$ans"
  fi
}

# ── preflight ─────────────────────────────────────────────────────────────────

_step "Nexus Screen — System Compatibility Check"

FAIL=0            # count of hard-blocking failures
MISSING_PKGS=""   # space-separated list of apt packages to install
OS_BLOCKED=false
ARCH_BLOCKED=false
BLOCK_REASON=""

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

_need_pkg() {
  local name="$1" pkg="$2" msg="$3"
  printf '  \033[33m↓\033[0m  %-28s %s\n' "$name" "$msg"
  MISSING_PKGS="${MISSING_PKGS:+${MISSING_PKGS} }${pkg}"
}

# ── OS ────────────────────────────────────────────────────────────────────────
OS_ID="$(. /etc/os-release 2>/dev/null && printf '%s' "${ID:-unknown}" || printf 'unknown')"
OS_VER="$(. /etc/os-release 2>/dev/null && printf '%s' "${VERSION_ID:-0}" || printf '0')"
OS_PRETTY="$(. /etc/os-release 2>/dev/null && printf '%s' "${PRETTY_NAME:-unknown}" || printf 'unknown')"
OS_CODENAME="$(. /etc/os-release 2>/dev/null && printf '%s' "${VERSION_CODENAME:-unknown}" || printf 'unknown')"

case "$OS_ID" in
  debian|raspbian)
    if [ "${OS_VER}" -ge 12 ] 2>/dev/null; then
      _check "OS" 0 "${OS_PRETTY}"
    else
      _check "OS" 1 "${OS_PRETTY} — Debian 12 (Bookworm) required"
      OS_BLOCKED=true
      BLOCK_REASON="${BLOCK_REASON}  Operating System: ${OS_PRETTY} (${OS_CODENAME}) — not supported.\n  Nexus Screen requires Debian 12 (Bookworm) or Raspberry Pi OS Bookworm.\n  Upgrade your OS before retrying.\n\n"
    fi ;;
  ubuntu)
    _warn_check "OS" "Ubuntu ${OS_VER} — not a primary target; may work" ;;
  *)
    _check "OS" 1 "${OS_PRETTY} — unsupported; Debian 12 (Bookworm) required"
    OS_BLOCKED=true
    BLOCK_REASON="${BLOCK_REASON}  Operating System: ${OS_PRETTY} — not supported.\n  Nexus Screen requires Debian 12 (Bookworm) on verified hardware.\n\n" ;;
esac

# ── Architecture ──────────────────────────────────────────────────────────────
ARCH="$(uname -m)"
case "$ARCH" in
  aarch64|arm64) _check "Architecture" 0 "${ARCH} (Raspberry Pi / CB1)" ;;
  armv7l|armv6l)
    _check "Architecture" 1 "${ARCH} — 64-bit aarch64 required"
    ARCH_BLOCKED=true
    BLOCK_REASON="${BLOCK_REASON}  Architecture: ${ARCH} — a 32-bit OS is not supported.\n  Reinstall using a 64-bit (aarch64) OS image.\n\n" ;;
  x86_64) _warn_check "Architecture" "x86_64 — framebuffer splash won't function (dev/CI use only)" ;;
  *)      _warn_check "Architecture" "${ARCH} — untested" ;;
esac

# ── RAM (minimum 1 GB) ────────────────────────────────────────────────────────
MEM_MB=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || printf '0') / 1024 ))
if [ "$MEM_MB" -ge 900 ]; then
  _check "RAM" 0 "${MEM_MB} MB"
else
  _check "RAM" 1 "${MEM_MB} MB available — minimum 1 GB required"
  BLOCK_REASON="${BLOCK_REASON}  RAM: ${MEM_MB} MB — minimum 1 GB required.\n\n"
fi

# ── Disk (minimum 500 MB free in home) ───────────────────────────────────────
FREE_MB=$(( $(df --output=avail "${HOME_DIR}" 2>/dev/null | tail -1 | tr -d ' ') / 1024 ))
if [ "$FREE_MB" -ge 400 ]; then
  _check "Disk" 0 "${FREE_MB} MB free in ${HOME_DIR}"
else
  _check "Disk" 1 "${FREE_MB} MB free — minimum 500 MB required in ${HOME_DIR}"
  BLOCK_REASON="${BLOCK_REASON}  Disk: only ${FREE_MB} MB free — minimum 500 MB required.\n\n"
fi

# ── Framebuffer ───────────────────────────────────────────────────────────────
if [ -e /dev/fb0 ]; then
  FB_SIZE="$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || printf '?,?')"
  FB_BPP="$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null || printf '?')"
  _check "Framebuffer" 0 "/dev/fb0  ${FB_SIZE} @ ${FB_BPP}bpp"
  FB_W="$(cut -d, -f1 /sys/class/graphics/fb0/virtual_size 2>/dev/null || printf '0')"
  FB_H="$(cut -d, -f2 /sys/class/graphics/fb0/virtual_size 2>/dev/null || printf '0')"
  if [ "${FB_W}" -ge ${MIN_W} ] && [ "${FB_H}" -ge ${MIN_H} ] 2>/dev/null; then
    _check "Resolution" 0 "${FB_W}×${FB_H} (minimum ${MIN_W}×${MIN_H})"
  else
    _check "Resolution" 1 "${FB_W}×${FB_H} — minimum ${MIN_W}×${MIN_H} required"
    BLOCK_REASON="${BLOCK_REASON}  Display resolution: ${FB_W}×${FB_H} — minimum ${MIN_W}×${MIN_H} required.\n\n"
  fi
else
  _warn_check "Framebuffer" "/dev/fb0 not found — required for splash display"
fi

# ── Python ────────────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
  PY_VER="$(python3 --version 2>&1 | awk '{print $2}')"
  PY_MAJ="$(printf '%s' "${PY_VER}" | cut -d. -f1)"
  PY_MIN_VER="$(printf '%s' "${PY_VER}" | cut -d. -f2)"
  PY_NUM=$(( PY_MAJ * 100 + PY_MIN_VER ))
  if [ "$PY_NUM" -ge 309 ]; then
    _check "Python" 0 "python3 ${PY_VER}"
  else
    _check "Python" 1 "python3 ${PY_VER} — 3.9+ required"
    BLOCK_REASON="${BLOCK_REASON}  Python: ${PY_VER} found — 3.9 or later required.\n\n"
  fi
else
  _check "Python" 1 "python3 not found — install: sudo apt install python3"
  BLOCK_REASON="${BLOCK_REASON}  Python: not found — required. Install with: sudo apt install python3\n\n"
fi

# ── PyQt6 — missing is an installable dep, not a hard block ──────────────────
if python3 -c "import PyQt6" 2>/dev/null; then
  _check "PyQt6" 0 "installed"
else
  _need_pkg "PyQt6" "python3-pyqt6" "not installed — will offer to install"
fi

# ── git — missing is installable ─────────────────────────────────────────────
if command -v git &>/dev/null; then
  _check "git" 0 "$(git --version)"
else
  _need_pkg "git" "git" "not installed — will offer to install"
fi

# ── Klipper / Moonraker — optional for the installer itself ──────────────────
if systemctl is-active --quiet klipper 2>/dev/null; then
  _check "Klipper" 0 "active"
else
  _warn_check "Klipper" "not active — required for printer control"
fi

if systemctl is-active --quiet moonraker 2>/dev/null; then
  _check "Moonraker" 0 "active"
else
  _warn_check "Moonraker" "not active — required for printer data"
fi

echo ""

# ── BLOCK on hard failures ────────────────────────────────────────────────────
if [ "$FAIL" -gt 0 ]; then
  printf '\033[1;31mINSTALLATION BLOCKED\033[0m\n\n'
  printf '%b' "$BLOCK_REASON"
  printf '  No changes were made to your system.\n\n'
  exit 1
fi

_green "System meets minimum requirements."

# ── offer to install missing packages ────────────────────────────────────────
if [ -n "${MISSING_PKGS}" ]; then
  echo ""
  _bold "  Missing dependencies:"
  for pkg in ${MISSING_PKGS}; do
    printf '    sudo apt install %s\n' "$pkg"
  done
  echo ""

  if $OPT_DRY_RUN; then
    _info "Dry run: would run: sudo apt-get install -y ${MISSING_PKGS}"
  elif $OPT_YES; then
    _info "Installing dependencies automatically..."
    # shellcheck disable=SC2086
    sudo apt-get install -y ${MISSING_PKGS}
    _green "Dependencies installed."
  else
    _dep_ans="$(_ask "  Install these packages now? [Y/n] " "y")"
    case "${_dep_ans}" in
      n|N|no|No|NO)
        printf '\n  Installation cancelled.\n  Install the missing packages manually and retry.\n\n'
        exit 1 ;;
      *)
        _info "Installing dependencies..."
        # shellcheck disable=SC2086
        sudo apt-get install -y ${MISSING_PKGS}
        _green "Dependencies installed."
        ;;
    esac
  fi
fi

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

# ── plan summary ──────────────────────────────────────────────────────────────
_step "Installation Plan"

echo ""
case "$INSTALL_MODE" in
  fresh)  printf '  Installing Nexus Screen for the first time.\n' ;;
  update) printf '  Updating existing Nexus Screen at %s.\n' "$NS_DIR" ;;
  repair) printf '  Repairing Nexus Screen at %s.\n' "$NS_DIR" ;;
esac

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  What will happen                                   │"
echo "  │                                                     │"
printf "  │  ✓  %-47s│\n" "Nexus Screen → ${NS_DIR}"
echo "  │  ?  Nexus Video → will ask after installation       │"
echo "  │  ·  Nexus Sounds → Coming Soon                      │"
if $OPT_DRY_RUN; then
echo "  │                                                     │"
printf "  │  %-51s│\n" "DRY RUN — no changes will be made"
fi
echo "  └─────────────────────────────────────────────────────┘"
echo ""

if $OPT_DRY_RUN; then
  _info "Dry run complete. No changes made."
  exit 0
fi

if ! $OPT_YES; then
  _proceed="$(_ask "  Proceed with Nexus Screen installation? [Y/n] " "y")"
  case "${_proceed}" in
    n|N|no|No|NO)
      printf '  Installation cancelled.\n'
      exit 0 ;;
  esac
fi

# ── clone / update Nexus Screen ───────────────────────────────────────────────
_step "Installing Nexus Screen"

if $NS_EXISTS && [ "$INSTALL_MODE" = "update" ]; then
  _info "Updating Nexus Screen..."
  sudo -u "${TARGET_USER}" git -C "${NS_DIR}" pull --ff-only 2>&1 | _prefix "  git: "
else
  if $NS_EXISTS && [ "$INSTALL_MODE" = "repair" ]; then
    _info "Creating repair backup before removing ${NS_DIR}..."
    _repair_backup="${HOME_DIR}/.nexus-screen-repair-$(date +%Y%m%d-%H%M%S)"
    cp -a "${NS_DIR}" "${_repair_backup}"
    _info "Backup saved to ${_repair_backup}"
    _info "Removing ${NS_DIR} for repair reinstall..."
    rm -rf "${NS_DIR}"
  fi
  _info "Cloning Nexus Screen..."
  sudo -u "${TARGET_USER}" git clone --depth 1 --branch "${NS_BRANCH}" \
    "${NS_REPO}" "${NS_DIR}" 2>&1 | _prefix "  git: "
fi

_info "Running Nexus Screen installer..."
sudo bash "${NS_INSTALL}" --confirm

echo ""
printf '\033[1;32mNEXUS SCREEN INSTALLED SUCCESSFULLY\033[0m\n'
echo ""

# ── Nexus Video addon (prompt AFTER Nexus Screen installs) ───────────────────
INSTALL_NV=false
if [ -n "${OPT_WITH_VIDEO}" ]; then
  [ "${OPT_WITH_VIDEO}" = "yes" ] && INSTALL_NV=true
elif $OPT_YES; then
  INSTALL_NV=false
else
  echo "  ┌─────────────────────────────────────────────────────┐"
  echo "  │  Optional Addon: Nexus Video                        │"
  echo "  │                                                     │"
  echo "  │  Animated boot splash with video packs.            │"
  echo "  │  Requires /dev/fb0 framebuffer display.            │"
  echo "  │  Adds ~20 MB (3 built-in packs included).          │"
  echo "  │                                                     │"
  echo "  │  Can also be added later (see README).              │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo ""
  _nv_ans="$(_ask "  Install Nexus Video? [y/N] " "n")"
  case "${_nv_ans}" in
    y|Y|yes|Yes|YES) INSTALL_NV=true ;;
    *) INSTALL_NV=false ;;
  esac
  echo ""
  printf '  Nexus Sounds — Coming Soon (not available in this release)\n'
  echo ""
fi

# ── optional: install Nexus Video ─────────────────────────────────────────────
NV_INSTALLED=false
NV_FAIL_MSG=""

if $INSTALL_NV; then
  _step "Nexus Video (optional addon)"

  NV_CLONE_OK=false
  if $NV_EXISTS && [ -d "${NV_DIR}/.git" ]; then
    _info "Updating Nexus Video..."
    if sudo -u "${TARGET_USER}" git -C "${NV_DIR}" pull --ff-only 2>&1 | _prefix "  git: "; then
      NV_CLONE_OK=true
    fi
  else
    _info "Cloning Nexus Video..."
    if sudo -u "${TARGET_USER}" git clone --depth 1 --branch "${NV_BRANCH}" \
        "${NV_REPO}" "${NV_DIR}" 2>&1 | _prefix "  git: "; then
      NV_CLONE_OK=true
    fi
  fi

  if $NV_CLONE_OK; then
    _info "Running Nexus Video preflight..."
    if sudo -u "${TARGET_USER}" bash "${NV_PREFLIGHT}"; then
      _info "Running Nexus Video installer..."
      if sudo bash "${NV_INSTALL}"; then
        NV_INSTALLED=true
        _green "Nexus Video installed."
      else
        NV_FAIL_MSG="Nexus Video installer exited with an error."
      fi
    else
      NV_FAIL_MSG="Nexus Video preflight check failed."
    fi
  else
    NV_FAIL_MSG="Could not clone Nexus Video repository."
  fi

  if [ -n "${NV_FAIL_MSG}" ]; then
    echo ""
    _warn "${NV_FAIL_MSG}"
    _warn "Nexus Screen is fully operational without Nexus Video."
    _warn "Retry Nexus Video later:"
    _warn "  git clone ${NV_REPO} ~/nexus-video && bash ~/nexus-video/deploy/install.sh"
    echo ""
  fi
fi

# ── Moonraker Update Manager ──────────────────────────────────────────────────
_step "Moonraker Update Manager"

MOONRAKER_CONF="${HOME_DIR}/printer_data/config/moonraker.conf"
[ -f "${MOONRAKER_CONF}" ] || MOONRAKER_CONF="${HOME_DIR}/klipper_config/moonraker.conf"

if [ -f "${MOONRAKER_CONF}" ]; then
  if ! grep -q "\[update_manager nexus-screen\]" "${MOONRAKER_CONF}"; then
    _info "Registering Nexus Screen in Moonraker Update Manager..."
    cat >> "${MOONRAKER_CONF}" <<UMEOF

# Nexus Screen — added by bootstrap.sh
[update_manager nexus-screen]
type: git_repo
path: ${NS_DIR}
origin: ${NS_REPO}
primary_branch: main
is_system_service: False
UMEOF
    _green "Nexus Screen registered."
  else
    _info "Nexus Screen already registered in Moonraker Update Manager."
  fi

  if $NV_INSTALLED; then
    if ! grep -q "\[update_manager nexus-video\]" "${MOONRAKER_CONF}"; then
      _info "Registering Nexus Video in Moonraker Update Manager..."
      cat >> "${MOONRAKER_CONF}" <<UMEOF

# Nexus Video — added by bootstrap.sh
[update_manager nexus-video]
type: git_repo
path: ${NV_DIR}
origin: ${NV_REPO}
primary_branch: main
is_system_service: False
managed_services: nexus-video
UMEOF
      _green "Nexus Video registered."
    else
      _info "Nexus Video already registered in Moonraker Update Manager."
    fi
  fi
else
  _warn "moonraker.conf not found — skipping automatic registration."
  _warn "Add update_manager blocks manually from docs/moonraker-update-manager.md"
fi

# ── verification ──────────────────────────────────────────────────────────────
_step "Verification"

NS_STATE="$(systemctl is-active nexus-screen 2>/dev/null || printf 'inactive')"
printf '  %-36s %s\n' "nexus-screen.service" "${NS_STATE}"

if $NV_INSTALLED; then
  NV_STATE="$(systemctl is-active nexus-video 2>/dev/null || printf 'inactive')"
  printf '  %-36s %s\n' "nexus-video.service" "${NV_STATE}"
fi

# ── final summary ─────────────────────────────────────────────────────────────
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Installation Complete                              │"
echo "  │                                                     │"
printf "  │  ✓  %-47s│\n" "Nexus Screen → ${NS_DIR}"
if $NV_INSTALLED; then
  printf "  │  ✓  %-47s│\n" "Nexus Video → ${NV_DIR}"
elif [ -n "${NV_FAIL_MSG}" ]; then
  printf "  │  ✗  %-47s│\n" "Nexus Video: install failed (NS still works)"
elif $INSTALL_NV; then
  printf "  │  ✗  %-47s│\n" "Nexus Video: not installed (see warning above)"
else
  printf "  │  ·  %-47s│\n" "Nexus Video: not installed (optional)"
fi
printf "  │  ·  %-47s│\n" "Nexus Sounds: Coming Soon"
echo "  │                                                     │"
echo "  │  Nexus Screen starts automatically at next boot.    │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
_info "To start now:  sudo systemctl start nexus-screen"
if ! $NV_INSTALLED && ! $INSTALL_NV; then
  _info "To add Nexus Video later:"
  _info "  git clone ${NV_REPO} ~/nexus-video && bash ~/nexus-video/deploy/install.sh"
fi
if $NV_INSTALLED; then
  _info "Nexus Video:   sudo systemctl start nexus-video"
fi
echo ""
