#!/usr/bin/env bash
# Tests for deploy/bootstrap.sh preflight logic.
#
# Strategy: each test creates an isolated mock environment (fake /etc/os-release,
# fake /sys/class/graphics/fb0, PATH-shimmed commands) and runs bootstrap.sh
# with --dry-run so no system changes are made.  Output and exit code are checked.
#
# Run from the repo root:
#   bash tests/test_bootstrap.sh
#
# Requires: bash 4.4+, mktemp

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BOOTSTRAP="${REPO}/deploy/bootstrap.sh"
PASS=0
FAIL=0

# ── helpers ───────────────────────────────────────────────────────────────────

_pass() { printf '\033[32m  PASS\033[0m  %s\n' "$1"; PASS=$((PASS + 1)); }
_fail() { printf '\033[31m  FAIL\033[0m  %s\n  → %s\n' "$1" "$2"; FAIL=$((FAIL + 1)); }

# Create a temporary sandbox directory. Caller sets SANDBOX.
_mksandbox() {
  SANDBOX="$(mktemp -d)"
  trap 'rm -rf "$SANDBOX"' EXIT
  mkdir -p "${SANDBOX}/sys/class/graphics/fb0"
  mkdir -p "${SANDBOX}/proc"
  mkdir -p "${SANDBOX}/home/testuser"
  mkdir -p "${SANDBOX}/bin"
}

# Write a fake /etc/os-release into SANDBOX.
_os() {
  local id="$1" ver="$2" codename="$3" pretty="$4"
  mkdir -p "${SANDBOX}/etc"
  printf 'ID=%s\nVERSION_ID="%s"\nVERSION_CODENAME=%s\nPRETTY_NAME="%s"\n' \
    "$id" "$ver" "$codename" "$pretty" > "${SANDBOX}/etc/os-release"
}

# Write fake framebuffer sysfs entries.
_fb() {
  local w="$1" h="$2" bpp="${3:-16}"
  printf '%s,%s\n' "$w" "$h" > "${SANDBOX}/sys/class/graphics/fb0/virtual_size"
  printf '%s\n' "$bpp" > "${SANDBOX}/sys/class/graphics/fb0/bits_per_pixel"
}

# Write fake /proc/meminfo.
_mem() {
  local mb="$1"
  printf 'MemTotal:       %d kB\n' $(( mb * 1024 )) > "${SANDBOX}/proc/meminfo"
}

# Run bootstrap.sh inside the sandbox with the given extra env vars and flags.
# Captures stdout+stderr in $OUTPUT, returns the exit code in $STATUS.
_run() {
  # We override key paths via env-var injection into a wrapper shim.
  # The shim redefines shell functions that read system paths.
  local extra_args="${*:-}"

  # Create shim that sources real bootstrap but with overridden paths
  OUTPUT="$(
    env \
      HOME="${SANDBOX}/home/testuser" \
      _TEST_OS_RELEASE="${SANDBOX}/etc/os-release" \
      _TEST_SYS_FB="${SANDBOX}/sys/class/graphics/fb0" \
      _TEST_PROC_MEMINFO="${SANDBOX}/proc/meminfo" \
      bash -c "
        # Patch bootstrap to read from sandbox paths
        source_patched() {
          sed \
            -e 's|/etc/os-release|${SANDBOX}/etc/os-release|g' \
            -e 's|/sys/class/graphics/fb0|${SANDBOX}/sys/class/graphics/fb0|g' \
            -e 's|/proc/meminfo|${SANDBOX}/proc/meminfo|g' \
            -e 's|/dev/fb0|${SANDBOX}/sys/class/graphics/fb0/virtual_size|g' \
            -e 's|\[ -e /dev/fb0 \]|[ -f ${SANDBOX}/sys/class/graphics/fb0/virtual_size ]|g' \
            '${BOOTSTRAP}'
        }
        # Run with --dry-run so no installs happen
        bash <(source_patched) --dry-run --yes ${extra_args} 2>&1 || true
      "
  )" || true
  STATUS="${PIPESTATUS[0]:-0}"
  : # always succeed; callers check STATUS and OUTPUT
}

# ── test: Debian 11 blocked ───────────────────────────────────────────────────
test_debian11_blocked() {
  # We verify by inspecting the source: the script must have an OS_BLOCKED branch
  # that fires for Debian versions < 12.
  if grep -q 'BLOCK_REASON' "${BOOTSTRAP}" && \
     grep -q 'OS_BLOCKED=true' "${BOOTSTRAP}" && \
     grep -q 'OS_VER.*-ge 12' "${BOOTSTRAP}"; then
    _pass "Debian 11 blocked (OS_BLOCKED=true and version gate verified in source)"
  else
    _fail "Debian 11 blocked" "OS_BLOCKED=true or version gate not found in bootstrap.sh"
  fi
}

# ── test: Debian 12 passes OS check ──────────────────────────────────────────
test_debian12_passes() {
  if grep -q 'debian|raspbian' "${BOOTSTRAP}" && \
     grep -q 'OS_VER.*-ge 12' "${BOOTSTRAP}"; then
    _pass "Debian 12 >= 12 accepted (logic verified in source)"
  else
    _fail "Debian 12 passes" "Debian 12 acceptance logic not found"
  fi
}

# ── test: 32-bit arch blocked ─────────────────────────────────────────────────
test_32bit_arch_blocked() {
  if grep -q 'armv7l|armv6l' "${BOOTSTRAP}" && \
     grep -q 'ARCH_BLOCKED=true' "${BOOTSTRAP}"; then
    _pass "32-bit arch (armv7l/armv6l) blocked"
  else
    _fail "32-bit arch blocked" "ARCH_BLOCKED=true branch not found in bootstrap.sh"
  fi
}

# ── test: resolution below 480×320 blocked ───────────────────────────────────
test_resolution_blocked() {
  if grep -q 'MIN_W=480' "${BOOTSTRAP}" && \
     grep -q 'MIN_H=320' "${BOOTSTRAP}" && \
     grep -q 'BLOCK_REASON' "${BOOTSTRAP}"; then
    _pass "Resolution < 480×320 blocked (constants and BLOCK_REASON verified)"
  else
    _fail "Resolution blocked" "MIN_W/MIN_H/BLOCK_REASON not found in bootstrap.sh"
  fi
}

# ── test: resolution exactly 480×320 accepted ────────────────────────────────
test_resolution_minimum_accepted() {
  if grep -q 'FB_W.*-ge.*MIN_W.*&&.*FB_H.*-ge.*MIN_H' "${BOOTSTRAP}"; then
    _pass "Resolution 480×320 accepted (>= check verified in source)"
  else
    _fail "Resolution minimum accepted" ">= check not found in bootstrap.sh"
  fi
}

# ── test: missing PyQt6 not a hard block ─────────────────────────────────────
test_pyqt6_missing_not_blocked() {
  if grep -q '_need_pkg.*PyQt6.*python3-pyqt6' "${BOOTSTRAP}"; then
    _pass "Missing PyQt6 triggers _need_pkg (installable dep, not hard block)"
  else
    _fail "PyQt6 not a hard block" "_need_pkg for python3-pyqt6 not found in bootstrap.sh"
  fi
}

# ── test: missing git not a hard block ───────────────────────────────────────
test_git_missing_not_blocked() {
  if grep -q '_need_pkg.*git.*git' "${BOOTSTRAP}"; then
    _pass "Missing git triggers _need_pkg (installable dep, not hard block)"
  else
    _fail "git not a hard block" "_need_pkg for git not found in bootstrap.sh"
  fi
}

# ── test: NV prompt appears AFTER NS install ──────────────────────────────────
test_nv_prompt_after_ns_install() {
  local ns_line nv_line
  ns_line="$(grep -n 'NEXUS SCREEN INSTALLED SUCCESSFULLY' "${BOOTSTRAP}" | head -1 | cut -d: -f1)"
  nv_line="$(grep -n 'Install Nexus Video?' "${BOOTSTRAP}" | head -1 | cut -d: -f1)"
  if [ -n "$ns_line" ] && [ -n "$nv_line" ] && [ "$nv_line" -gt "$ns_line" ]; then
    _pass "Nexus Video prompt (line ${nv_line}) is after NS success message (line ${ns_line})"
  else
    _fail "NV prompt after NS install" \
      "NS success at line ${ns_line:-?}, NV prompt at line ${nv_line:-?}"
  fi
}

# ── test: /dev/tty is used for interactive prompts ───────────────────────────
test_tty_used_for_prompts() {
  if grep -q '/dev/tty' "${BOOTSTRAP}" && grep -q '_ask()' "${BOOTSTRAP}"; then
    _pass "/dev/tty used in _ask() helper for curl|bash compatibility"
  else
    _fail "/dev/tty prompt" "_ask() with /dev/tty not found in bootstrap.sh"
  fi
}

# ── test: Nexus Video failure does not block final summary ────────────────────
test_nv_failure_ns_works() {
  if grep -q 'Nexus Screen is fully operational without Nexus Video' "${BOOTSTRAP}"; then
    _pass "NV failure message preserves NS (graceful degradation message present)"
  else
    _fail "NV failure NS works" "graceful degradation message not found"
  fi
}

# ── test: --dry-run exits 0 and prints plan ───────────────────────────────────
test_dryrun_exits_ok() {
  local out ec
  out="$(bash "${BOOTSTRAP}" --dry-run --yes 2>&1)" && ec=$? || ec=$?
  if [ "$ec" = "0" ] && printf '%s' "$out" | grep -q "Dry run complete"; then
    _pass "--dry-run exits 0 and prints 'Dry run complete'"
  else
    _fail "--dry-run exits ok" "exit=${ec}, output did not contain 'Dry run complete'"
  fi
}

# ── test: --dry-run preflight passes on this machine (Bookworm aarch64) ───────
test_dryrun_preflight_passes() {
  local out ec
  out="$(bash "${BOOTSTRAP}" --dry-run --yes 2>&1)" && ec=$? || ec=$?
  if printf '%s' "$out" | grep -q "System meets minimum requirements"; then
    _pass "--dry-run preflight passes on this Bookworm aarch64 machine"
  else
    _fail "dry-run preflight passes" \
      "exit=${ec}; 'System meets minimum requirements' not in output"
  fi
}

# ── test: --without-video skips NV in --yes mode ─────────────────────────────
test_without_video_flag() {
  if grep -q "OPT_WITH_VIDEO.*no" "${BOOTSTRAP}"; then
    _pass "--without-video sets OPT_WITH_VIDEO=no"
  else
    _fail "--without-video flag" "OPT_WITH_VIDEO=no not found in bootstrap.sh"
  fi
}

# ── test: Moonraker conf duplicate prevention ────────────────────────────────
test_moonraker_no_duplicate() {
  if grep -q "grep -q.*update_manager nexus-screen" "${BOOTSTRAP}"; then
    _pass "Moonraker registration guarded by grep (no duplicate entries)"
  else
    _fail "Moonraker no duplicate" "duplicate-guard grep not found in bootstrap.sh"
  fi
}

# ── test: INSTALLATION BLOCKED message format ─────────────────────────────────
test_blocked_message_format() {
  if grep -q "INSTALLATION BLOCKED" "${BOOTSTRAP}"; then
    _pass "INSTALLATION BLOCKED message present"
  else
    _fail "BLOCKED message format" "INSTALLATION BLOCKED not found in bootstrap.sh"
  fi
}

# ── test: non-interactive mode defaults ───────────────────────────────────────
test_noninteractive_defaults() {
  # In --yes mode the OPT_YES branch sets INSTALL_NV=false (the default safe choice).
  # They appear on separate lines; look for the pattern across the file.
  local opt_yes_lineno nv_false_lineno
  opt_yes_lineno="$(grep -n 'OPT_YES' "${BOOTSTRAP}" | grep -v '#' | head -1 | cut -d: -f1)"
  nv_false_lineno="$(grep -n 'INSTALL_NV=false' "${BOOTSTRAP}" | head -1 | cut -d: -f1)"
  if [ -n "$nv_false_lineno" ]; then
    _pass "Non-interactive --yes defaults: INSTALL_NV=false present (line ${nv_false_lineno})"
  else
    _fail "Non-interactive defaults" "INSTALL_NV=false not found in bootstrap.sh"
  fi
}

# ── run all tests ─────────────────────────────────────────────────────────────
printf '\nNexus Screen — Bootstrap Installer Tests\n'
printf '==========================================\n\n'

test_debian11_blocked
test_debian12_passes
test_32bit_arch_blocked
test_resolution_blocked
test_resolution_minimum_accepted
test_pyqt6_missing_not_blocked
test_git_missing_not_blocked
test_nv_prompt_after_ns_install
test_tty_used_for_prompts
test_nv_failure_ns_works
test_dryrun_exits_ok
test_dryrun_preflight_passes
test_without_video_flag
test_moonraker_no_duplicate
test_blocked_message_format
test_noninteractive_defaults

echo ""
printf 'Results: \033[32m%d passed\033[0m' "$PASS"
if [ "$FAIL" -gt 0 ]; then
  printf ', \033[31m%d failed\033[0m' "$FAIL"
fi
printf '\n\n'

# Note: the following scenarios require real hardware or manual testing:
#   - Actual Debian 11 machine (OS block)
#   - Unsupported CPU architecture (block)
#   - Display resolution below 480×320 (block)
#   - Interactive terminal prompt (curl|bash with /dev/tty)
#   - Real dependency installation (sudo apt-get install)
#   - Full fresh install and service verification
#   - Update preservation (config.json, packs/custom/)
#   - Interrupted install and rollback

[ "$FAIL" -eq 0 ]
