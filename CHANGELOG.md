# Changelog

All notable changes to Nexus Screen are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [v0.2.0-beta.6] — 2026-11-07

### Nexus Sounds UI Integration

#### Added
- `nexus/screens/sounds.py`: SoundsScreen, EventSoundsScreen, EventSoundScreen,
  SoundPacksScreen, PackSoundsScreen — full Settings → Sounds panel
- `nexus/app.py`: SoundsScreen registered in the screen registry
- Settings → Sounds tile now navigates to the Sounds panel

#### Sounds UI features
- Main screen: master enable/mute toggle cards, volume row, Event Sounds and Sound Packs navigation
- Event Sounds: seven-event scrollable list with icons, filenames, chevrons; no ON/OFF switches
- Event Sound selector: file browser, Enable toggle, Preview/Apply/Cancel
- Sound Packs: two-column browser with pack metadata, Browse Sounds, Set as Active
- Graceful degradation: shows installation notice when Nexus Sounds is not installed

#### Documentation
- README updated: Nexus Sounds section with installation instructions
- docs/RELEASE-NOTES-v0.2.0-beta.6.md added

---

## [v0.2.0-beta.4] — 2026-11-01

### Voron 2.4 Physical Validation + Python Preflight Fix

#### Physical validation — Voron 2.4 (32-bit BGRA8888 framebuffer)

v0.2.0-beta.3 was installed and physically tested on a Voron 2.4 with an 800×480
display. The BCM2708 framebuffer reported BGRA8888 (32-bit, `bits_per_pixel = 32`,
`RGBA: 8/16, 8/8, 8/0, 8/24`). Installation completed without errors; the interface
and touchscreen worked correctly; StealthChanger was auto-detected. This confirms
that the 32-bit framebuffer support introduced in beta.3 works correctly on the
target hardware.

The "unverified hardware rendering" risk noted after beta.3 is resolved.

| Hardware | Framebuffer | Result |
|---|---|---|
| Voron 2.4 (Raspberry Pi 4) | 800×480 BGRA8888 (32-bit) | ✓ Installed, interface running, StealthChanger detected |
| BigTreeTech CB1 | 480×320 RGB565 (16-bit) | ✓ Previously validated (v0.2.0-beta.2) |

#### Python preflight check — now validates the venv interpreter

The OS compatibility check added in beta.3 read `python3` (the system interpreter)
rather than `$PY` (the `~/nexus-screen-env/bin/python` interpreter that Nexus Screen
actually runs). On a standard Bookworm host the two are the same, so the check
passed silently. But a venv created from a non-default interpreter (e.g. an older
Python installed alongside Bookworm's 3.11) could satisfy the system check while the
actual Nexus Screen interpreter failed the version requirement.

**Fix (`deploy/install.sh`):** the Python version check now tests `$PY` directly.
If the venv does not exist yet (the user hasn't run Step 3 of INSTALLATION.md), the
Python version check is skipped — the PyQt6 import check that follows handles the
missing venv with a clear "see docs/INSTALLATION.md" message. The failure message
now names the venv path and includes the correct command to recreate it.

**Regression tests (`tests/test_os_compat.py`):** one additional test case added
(missing-venv skip behaviour); existing Python version cases updated to reflect the
venv-interpreter context.

---

## [v0.2.0-beta.3] — 2026-11-01

### 32-bit Framebuffer Support — Voron 2.4 / BCM2708 Compatible

The installer and health check previously rejected any framebuffer with a bit depth
other than 16 (RGB565). The BCM2708 framebuffer used by Raspberry Pi on Voron 2.4
machines exposes a 32-bit BGRA8888 layout (`RGBA: 8/16, 8/8, 8/0, 8/24`), causing
the preflight check to abort with an unsupported-format error before installation
could proceed.

**Root cause:** `deploy/install.sh` tested `bits_per_pixel = 16` as a hard gate;
`deploy/healthcheck.py` decoded pixels assuming 16-bit RGB565 unconditionally.
Neither consulted the actual channel layout reported by the kernel.

**Fix — `_parse_fb_format()` and `_read_pixels()` (`deploy/healthcheck.py`):**
The health check now reads the framebuffer channel layout using the
`FBIOGET_VSCREENINFO` ioctl (`0x4600`) and validates the result against supported
formats. `_parse_fb_format(bpp, r_off, r_len, g_off, g_len, b_off, b_len)` is a
pure function (no I/O) that accepts RGB565, BGRA8888, RGBA8888, and any compatible
32-bit layout with 8-bit, non-overlapping R/G/B channels, and rejects everything
else with a clear diagnostic message. `_read_pixels()` applies the detected channel
offsets at runtime, with correct stride handling for both formats. For 16-bit, the
ioctl result is used when available; if `/dev/fb0` is inaccessible (test
environments), the known-good RGB565 layout is assumed.

**Fix — `deploy/install.sh` framebuffer check:**
The installer replaces the `[ "$fb_bpp" = 16 ]` gate with a `case` statement that
accepts 16-bit directly as RGB565, validates 32-bit by calling a small inline Python
snippet to run `FBIOGET_VSCREENINFO`, and rejects any unsupported 32-bit layout or
unknown bit depth with a descriptive error. The detected format name (`RGB565`,
`BGRA8888`, `RGBA8888`, etc.) is logged in the preflight summary and saved in the
backup `state.env` as `FB_FMT`.

**Qt linuxfb:** Qt's linuxfb plugin calls `FBIOGET_VSCREENINFO` internally and
selects the correct `QImage` pixel format at startup. The service unit template and
application code are unchanged.

**Regression tests (`tests/test_fb_support.py`):**
25 tests covering `_parse_fb_format` and `_read_pixels` with synthetic framebuffer
files, padded strides, both pixel formats, and rejection of all invalid layouts.

| Check | 16-bit RGB565 | 32-bit BGRA8888 |
|---|---|---|
| `_parse_fb_format` accepts | ✓ | ✓ |
| `_parse_fb_format` rejects non-8-bit channel | — | ✓ |
| `_parse_fb_format` rejects channel overflow | — | ✓ |
| `_parse_fb_format` rejects channel overlap | — | ✓ |
| `_parse_fb_format` rejects 24-bit / 8-bit bpp | ✓ | ✓ |
| `_read_pixels` pure primary colours | ✓ | ✓ |
| `_read_pixels` padded stride | ✓ | ✓ |
| `_read_pixels` luminance not-black (white frame) | ✓ | ✓ |

Button boundary regression tests (from v0.2.0-beta.2) re-validated: 4/4 PASS.

**Installer and rollback scripts:** rollback.sh and commands.sh unchanged.

### OS Compatibility Enforcement — Debian 11 (Bullseye) Blocked with Clear Diagnostic

A public installation attempt failed on Debian 11 (Bullseye) because
`python3-pyqt6` does not exist in the Bullseye apt repository, and there is no
safe fallback. The installer previously gave no OS check and produced a confusing
`PyQt6 not importable` error with no explanation of the root cause.

**Findings (Bullseye investigation):**
A pip-based workaround exists in theory: PyQt6 6.7.1 is the last release with a
`manylinux_2_28_aarch64` wheel, which is installable on Bullseye (glibc 2.31).
PyQt6 6.8.0 and later require glibc 2.39 and are not installable. The pip-bundled
Qt 6.7 does include the linuxfb hardware platform plugin. However, the framebuffer
hardware rendering path via pip-bundled Qt on Bullseye hardware has not been validated,
the PyQt6 version would be permanently frozen at 6.7.x, and Bullseye LTS ended in
April 2024. Official Bullseye support is not feasible.

**Fix — OS and Python version preflight checks (`deploy/install.sh`):**
Two new checks run before any other preflight step. The OS check reads
`/etc/os-release` and accepts `debian` or `raspbian` with `VERSION_ID >= 12`; any
older version produces a specific error naming the detected OS, directing the user
to upgrade to Bookworm. The Python check requires `python3 >= 3.11`; earlier
versions produce a specific error with an install command. Both checks run on
every dry-run and confirmed install.

**Documentation (`docs/INSTALLATION.md`, `README.md`):**
Prerequisites updated to list Debian 12 (Bookworm) explicitly. A new
"Why Debian 12 or later?" section in INSTALLATION.md explains the technical
reasons for the Bullseye restriction and provides recommended upgrade paths.

**Regression tests (`tests/test_os_compat.py`):**
18 tests: 9 OS check cases (Bookworm accepted, Bullseye/Buster/Ubuntu/empty
rejected), 6 Python version cases (3.11+ accepted, 3.10/3.9/2.7 rejected),
`bash -n` syntax check on install.sh, and live host check.

| Test | Result |
|---|---|
| OS check: debian/raspbian 12+ accepted | ✓ PASS |
| OS check: debian/raspbian 11 (Bullseye) rejected | ✓ PASS |
| OS check: debian 10 (Buster) rejected | ✓ PASS |
| OS check: Ubuntu / unknown ID rejected | ✓ PASS |
| OS check: malformed/empty os-release rejected | ✓ PASS |
| Python 3.11 / 3.12 / 3.13 accepted | ✓ PASS |
| Python 3.10 / 3.9 / 2.7 rejected | ✓ PASS |
| install.sh bash syntax valid | ✓ PASS |

---

## [v0.2.0-beta.2] — 2026-11-01

### Button Boundary Fix — All Interactive Controls Stay On-Screen at 480×320

Physical CB1 testing after v0.2.0-beta.1 revealed that buttons in the Settings,
Control, Filament, and Print hub pages extended 7 px beyond the right edge of the
screen at 480×320, making the rightmost column of tiles unreachable by touch.

**Root cause:** the four hub pages (non-SubScreen pages that share the screen with
the sidebar) used `sx()` to scale their tile-grid widths. `sx()` maps against the
full screen width, but the sidebar has a minimum size floor (`max(60, …)`) that makes
it wider than `sx(80)` on small displays. At 480×320 the sidebar is 60 px rather than
the proportional 48 px, leaving only 420 px for content — but `sx(704)` produced
422 px, so the 4th tile column and the Recent Files list rows overflowed by 7 px.

**Fix — `cx()` scale helper (`nexus/config.py`):**
A new `cx(v)` function maps design-space values to the actual content-area width
`SCREEN_W − SIDEBAR_W`, correcting for the sidebar floor at any display size. The
four hub pages now use `cx()` for all x-coordinates and widths within their layouts.
`sx()` is unchanged and continues to be used everywhere else.

**Additional fixes (missed by Phase C):**
The coordinate audit also caught unscaled literal values in `paintEvent` methods of
`SettingsPage` and `PrintPage`, and confirmed the Phase C fixes to `ScreenSettings`,
`PrinterSettings`, and `NetworkScreen` are correctly applied.

**Regression tests (`tests/test_button_bounds.py`):**
A new automated test navigates to 13 screens and verifies that every visible
`QAbstractButton` has its window-coordinate rect fully inside the window at all four
reference resolutions. Replaces manual visual inspection for button boundary checks.

| Resolution | Result |
|---|---|
| 480×320 — CB1 minimum | ✓ PASS — 0 violations |
| 800×480 — reference / design | ✓ PASS — 0 violations |
| 1024×600 — tablet | ✓ PASS — 0 violations |
| 1920×1080 — HD monitor | ✓ PASS — 0 violations |

**Installer and rollback scripts:** unchanged from v0.2.0-beta.1.

---

## [v0.2.0-beta.1] — 2026-11-01

### Adaptive Display / Stretch to Fit

Nexus Screen now auto-detects the display resolution at startup and scales the
entire interface to fit. The 800×480 design is the reference: the layout is
pixel-identical on an 800×480 panel. On smaller or larger displays the interface
stretches proportionally while preserving circular shapes (jog wheel, status dots)
and minimum font sizes.

- **Automatic resolution detection** — reads `/sys/class/graphics/fb0/virtual_size`
  at startup; falls back to 800×480 if the sysfs entry is unavailable
- **Override via environment variables** — `NEXUS_SCREEN_W` and `NEXUS_SCREEN_H`
  override the detected resolution (the installer injects these for non-standard panels)
- **Coordinate helpers** — `sx(v)` (width), `sy(v)` (height), `smin(v)`
  (aspect-preserving, used for circles and fonts) applied across all 27 screens and
  all widget files
- **Installer support** — `deploy/install.sh` detects the framebuffer resolution; for
  non-800×480 panels it injects `NEXUS_SCREEN_W` / `NEXUS_SCREEN_H` into the systemd
  unit so the service always starts at the correct size
- **Healthcheck improvement** — `deploy/healthcheck.py` now reads the actual
  framebuffer stride (`/sys/class/graphics/fb0/stride`) for correct pixel reads on
  panels with row padding; rejects non-16-bpp framebuffers early
- **NumPy dependency** — `numpy` is now required for the health-check framebuffer read
- **Validated resolutions** — 800×480 (identity), 480×320, 1024×600, 1920×1080;
  zero crashes at all four resolutions

> **Note:** 800×480 is the recommended reference resolution. Smaller displays
> (480×320 and below) may show truncated labels and reduced readability on some
> screens. All primary interactive controls — Emergency Stop, Pause/Resume/Stop,
> jog wheel, temperature keypad, Z Offset, Bed Mesh — remain accessible at 480×320.

---

## [v0.1.0-beta.1] — 2026-11-01

First public beta release. The complete interface was developed and tested on a
Raspberry Pi 4 with a 7-inch 800×480 DSI touchscreen running Klipper and Moonraker.

### Core Interface

- **Home screen** — live temperature tiles, printer status, active add-on summary,
  Return to Print shortcut
- **Print Status** — full-screen layout during printing and paused states; print progress,
  elapsed/remaining time, file thumbnail; Pause/Resume/Stop (two-step confirmation); Baby Step Z offset
- **Print Files** — file browser with G-code thumbnails, Print Start action
- **Temperature** — landscape-adapted heater panel, numeric keypad, presets for nozzle and bed
- **Fans, Lighting, Move** — fan speed control, LED brightness, XYZ+E jog wheel with adjustable steps
- **Z Offset, Bed Screws, Bed Mesh** — calibration screens with live visualization
- **Filament** — heat-then-load workflow; Filament Profiles stored in Moonraker database
- **Extruder** — manual extrude/retract with configurable distance and speed
- **Control hub** — motion, temperature, calibration and filament sections in one place
- **Settings** — system information, network status, firmware version display, system actions
- **Macros, Webcam, Timelapse, Input Shaper** — screens present (some with placeholder content in beta)

### Add-on Support

- **BoxTurtle (AFC)** — multi-material unit dashboard and per-lane controls; auto-detected from
  Moonraker when the AFC Klipper plugin is present
- **StealthChanger** — toolchanger dashboard with per-tool color/material picker and controls;
  auto-detected when the toolchanger plugin is present

### Deployment and Safety

- Systemd service (`nexus-screen.service`) on tty7; owns the framebuffer exclusively
- Dry-run installer with automatic rollback if the health check fails after install
- Safe command gating — printer commands are sent only when the app runs with `--allow-commands`
  (disabled by default; enabled separately with `deploy/commands.sh`)
- KlipperScreen stopped and disabled during install; preserved and restorable via `deploy/rollback.sh`
- Health check tool (`deploy/healthcheck.py`) verifies service state, Moonraker connection,
  framebuffer ownership, and screen content
- Bug report tool (`scripts/bug-report.sh`) collects logs with automatic credential scrubbing
- Emergency stop allowed through the safe-mode restrictions in all states

### Boot Splash (Optional)

- Cinematic animated intro sequence plays on tty7 at boot, hands off to Nexus Screen when ready
- Dead-man switch: `touch ~/nexus-splash/DISABLED` stops the splash without root access
- Splash media is not distributed in the repository — see `splash/build_media.sh`

### Kinematics-Aware Home Image

- Home screen hero image switches between CoreXY, Cartesian, and Delta printer illustrations
  based on the kinematics reported by Moonraker

### Touchscreen Usability

- Touch targets sized for reliable bare-finger operation on 800×480
- Console cursor hidden in hardware-display mode
- Signal handling via `set_wakeup_fd` to minimize idle CPU usage

---

[v0.2.0-beta.4]: https://github.com/TheOmProject/Nexus-Screen/releases/tag/v0.2.0-beta.4
[v0.2.0-beta.3]: https://github.com/TheOmProject/Nexus-Screen/releases/tag/v0.2.0-beta.3
[v0.2.0-beta.2]: https://github.com/TheOmProject/Nexus-Screen/releases/tag/v0.2.0-beta.2
[v0.2.0-beta.1]: https://github.com/TheOmProject/Nexus-Screen/releases/tag/v0.2.0-beta.1
[v0.1.0-beta.1]: https://github.com/TheOmProject/Nexus-Screen/releases/tag/v0.1.0-beta.1
