# Changelog

All notable changes to Nexus Screen are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

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

[v0.2.0-beta.2]: https://github.com/omarmunoz5371/Nexus-Screen/releases/tag/v0.2.0-beta.2
[v0.2.0-beta.1]: https://github.com/omarmunoz5371/Nexus-Screen/releases/tag/v0.2.0-beta.1
[v0.1.0-beta.1]: https://github.com/omarmunoz5371/Nexus-Screen/releases/tag/v0.1.0-beta.1
