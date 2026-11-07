# Nexus Screen — Hardware Compatibility

This document describes known hardware configurations and their compatibility status.

**Status definitions:**

| Status | Meaning |
|---|---|
| **PHYSICALLY TESTED** | Installed and confirmed working on real hardware |
| **SIMULATED / CODE-VALIDATED** | Installer logic verified; not run on real hardware |
| **NOT TESTED** | Unknown; may work or may not; community reports welcome |
| **NOT SUPPORTED** | Installer blocks; will not work |

---

## Single-Board Computers

| SBC | OS | Architecture | Status | Notes |
|---|---|---|---|---|
| Raspberry Pi 4 (2 GB) | Debian 12 Bookworm | aarch64 | **PHYSICALLY TESTED** | Reference configuration; v0.2.0-beta.1 through v0.2.0-beta.5 |
| Raspberry Pi 4 (4 GB) | Raspberry Pi OS Bookworm | aarch64 | **PHYSICALLY TESTED** | Voron 2.4; v0.2.0-beta.4 |
| BigTreeTech CB1 | CB1 OS (Bookworm-based) | aarch64 | **PHYSICALLY TESTED** | 480×320 RGB565; v0.2.0-beta.2 |
| Raspberry Pi 3 (B/B+) | Debian 12 Bookworm | aarch64 | NOT TESTED | 64-bit OS required; preflight accepts; RAM (1 GB) is at the minimum |
| Raspberry Pi 5 | Debian 12 Bookworm | aarch64 | NOT TESTED | Community reports welcome |
| Raspberry Pi Zero 2 W | Raspberry Pi OS Bookworm | aarch64 | NOT TESTED | RAM (512 MB) below 900 MB minimum — installer will block |
| Raspberry Pi 4 / any | Debian 11 Bullseye | any | **NOT SUPPORTED** | Installer blocks; `python3-pyqt6` not in Bullseye apt; see [docs/INSTALLATION.md](INSTALLATION.md) |
| Raspberry Pi 4 / any | 32-bit OS (armv7l) | armv7l | **NOT SUPPORTED** | Installer blocks; 64-bit aarch64 required |
| Orange Pi, Rock Pi, other ARM SBCs | any | aarch64 | NOT TESTED | May work if running Debian 12 aarch64 with `/dev/fb0` |

---

## Displays

| Display | Resolution | Pixel Format | Status | Notes |
|---|---|---|---|---|
| 7-inch DSI touchscreen (official RPi) | 800×480 | RGB565 (16bpp) | **PHYSICALLY TESTED** | Reference display |
| BigTreeTech TFT35 (CB1) | 480×320 | RGB565 (16bpp) | **PHYSICALLY TESTED** | Minimum resolution path |
| Voron 2.4 DSI panel | 800×480 | BGRA8888 (32bpp) | **PHYSICALLY TESTED** | BCM2708 framebuffer driver |
| Any display ≥ 480×320 | 480×320–800×480 | RGB565 or 32bpp BGRA/RGBA | SIMULATED / CODE-VALIDATED | Adaptive scaling verified in screen-bounds tests |
| Any display ≥ 800×480 | 800×480–1920×1080 | RGB565 or 32bpp BGRA/RGBA | SIMULATED / CODE-VALIDATED | Scaling path correct; not physically tested above 800×480 |
| HDMI displays | any | depends on driver | NOT TESTED | `/dev/fb0` must exist; depends on display/driver configuration |
| SPI displays | any | depends on driver | NOT TESTED | `/dev/fb0` required; most SPI drivers do not expose one |
| Any display < 480×320 | below 480×320 | any | **NOT SUPPORTED** | Installer blocks with INSTALLATION BLOCKED |

**Framebuffer requirement:** the display must expose a Linux framebuffer device at `/dev/fb0`
in one of these pixel formats:
- **RGB565** (16bpp) — `bits_per_pixel = 16`
- **BGRA8888, RGBA8888, ARGB8888, or ABGR8888** (32bpp) — `bits_per_pixel = 32` with 8-bit R, G, B channels

Verify with:
```bash
cat /sys/class/graphics/fb0/bits_per_pixel   # 16 or 32
cat /sys/class/graphics/fb0/virtual_size      # W,H
```

---

## Firmware

| Firmware | Status | Notes |
|---|---|---|
| Klipper (any recent version) + Moonraker | **PHYSICALLY TESTED** | Tested on v0.12.x + Moonraker v0.9.x |
| MainsailOS (Bookworm image) | **PHYSICALLY TESTED** | Recommended; Klipper + Moonraker preconfigured |
| FluiddOS (Bookworm image) | **PHYSICALLY TESTED** | Also recommended |
| KIAUH custom installation | SIMULATED / CODE-VALIDATED | Installer detects Klipper/Moonraker service names; not physically tested |

---

## Reporting Compatibility

If you test Nexus Screen on hardware not listed here — or find a configuration
listed as NOT TESTED that works or fails — please report it:

[Open a Hardware Compatibility Report](https://github.com/omarmunoz5371/Nexus-Screen/issues/new?template=hardware_report.yml)

Include:
- SBC model and RAM
- Operating system and version (`cat /etc/os-release`)
- Display model, resolution, and connector type
- Framebuffer pixel format (`cat /sys/class/graphics/fb0/bits_per_pixel`)
- Nexus Screen version
- Result (working, failing, or partial)
