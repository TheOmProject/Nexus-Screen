# Changelog

All notable changes to Nexus Screen are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/).

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

[v0.1.0-beta.1]: https://github.com/omarmunoz5371/Nexus-Screen/releases/tag/v0.1.0-beta.1
